from __future__ import annotations

import hashlib
import re
from typing import Any

from .memory.ingestion import MemoryIngestionService
from .models import utc_now
from .repository import SkillRepository


class IngestionService:
    def __init__(self, repository: SkillRepository) -> None:
        self.repository = repository
        self.memory_ingestion = MemoryIngestionService(repository.data_dir)

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        records = payload.get("records", payload)
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            raise ValueError("records must be an object or a list of objects")

        candidates = []
        for record in records:
            candidate = self.extract_candidate(record)
            memory = self.memory_ingestion.ingest_record(
                record,
                skill_id=candidate["proposed_skill"]["skill_id"],
            )
            candidate["memory"] = {
                "evidence_id": memory["evidence"]["id"],
                "entities_created": len(memory["entities"]),
                "edges_created": len(memory["edges"]),
            }
            self.repository.add_candidate(candidate)
            candidates.append(candidate)
        return {"count": len(candidates), "candidates": candidates}

    def extract_candidate(self, record: dict[str, Any]) -> dict[str, Any]:
        content = str(record.get("content", "")).strip()
        if not content:
            raise ValueError("record content is required")

        source = str(record.get("source", "manual_note"))
        metadata = record.get("metadata", {})
        digest = hashlib.sha1(f"{source}:{content}".encode("utf-8")).hexdigest()[:12]
        domain = self._infer_domain(content)
        proposed_skill = self._build_skill(domain, digest, content, source, metadata)

        return {
            "candidate_id": f"cand_{digest}",
            "status": "pending",
            "created_at": utc_now(),
            "source": source,
            "source_metadata": metadata,
            "extraction_confidence": proposed_skill["confidence_score"],
            "proposed_skill": proposed_skill,
        }

    def _build_skill(
        self,
        domain: str,
        digest: str,
        content: str,
        source: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        lower = content.lower()
        skill_id = f"{domain}_candidate_{digest}"
        conditions: list[dict[str, Any]] = []
        action = {"action": "needs_human_review", "requires_approval": True}
        inputs: list[dict[str, Any]] = []

        if domain == "support":
            inputs = [
                {"name": "customer_tier", "required": False},
                {"name": "days_since_purchase", "required": False},
                {"name": "previous_refund_requests", "required": False},
                {"name": "churn_risk", "required": False},
            ]
            if "enterprise" in lower:
                conditions.append({"field": "customer_tier", "operator": "==", "value": "enterprise"})
            if "first" in lower and "refund" in lower:
                conditions.append({"field": "previous_refund_requests", "operator": "==", "value": 0})
            days = self._extract_number_before_word(lower, "day")
            if days is not None:
                operator = ">" if any(token in lower for token in ("after", "over", "outside")) else "<="
                conditions.append({"field": "days_since_purchase", "operator": operator, "value": days})
            if "churn" in lower:
                conditions.append({"field": "churn_risk", "operator": "==", "value": True})
            if "approve" in lower:
                action = {"action": "approve_refund", "requires_approval": False, "log_in": "zendesk"}
            elif "escalate" in lower:
                action = {"action": "escalate", "requires_approval": True, "escalate_to": "support_lead"}

        elif domain == "sales":
            inputs = [
                {"name": "deal_size", "required": False},
                {"name": "discount_percent", "required": False},
                {"name": "customer_tier", "required": False},
            ]
            amount = self._extract_money(lower)
            percent = self._extract_percent(lower)
            if amount is not None:
                conditions.append({"field": "deal_size", "operator": ">=", "value": amount})
            if percent is not None:
                conditions.append({"field": "discount_percent", "operator": ">", "value": percent})
            if "enterprise" in lower:
                conditions.append({"field": "customer_tier", "operator": "==", "value": "enterprise"})
            action = {
                "action": "requires_vp_approval" if "vp" in lower or "approval" in lower else "document_exception",
                "requires_approval": "approval" in lower or "vp" in lower,
                "escalate_to": metadata.get("owner", "vp_sales"),
            }

        elif domain == "procurement":
            inputs = [
                {"name": "iso_9001_certified", "required": False},
                {"name": "audit_passed_last_12mo", "required": False},
                {"name": "previous_delivery_delays", "required": False},
                {"name": "country_risk", "required": False},
            ]
            if "iso" in lower:
                conditions.append({"field": "iso_9001_certified", "operator": "==", "value": True})
            if "audit" in lower:
                conditions.append({"field": "audit_passed_last_12mo", "operator": "==", "value": True})
            delay_count = self._extract_number_before_word(lower, "delay")
            if delay_count is not None:
                conditions.append({"field": "previous_delivery_delays", "operator": ">", "value": delay_count})
            if "high risk" in lower or "high-risk" in lower:
                conditions.append({"field": "country_risk", "operator": "==", "value": "high"})
            if "approve" in lower and "delay" not in lower and "risk" not in lower:
                action = {"action": "auto_approve_supplier", "requires_approval": False}
            else:
                action = {"action": "enhanced_due_diligence", "requires_approval": True, "escalate_to": "compliance_team"}

        condition_block: dict[str, Any] = {"all": conditions} if conditions else {"field": "_never", "operator": "exists"}
        return {
            "skill_id": skill_id,
            "version": "0.1.0",
            "domain": domain,
            "last_updated": utc_now()[:10],
            "confidence_score": 0.55 if conditions else 0.35,
            "description": self._description_from_content(content),
            "inputs": inputs,
            "decision_tree": [
                {
                    "if": condition_block,
                    "then": action,
                    "reasoning": "Candidate rule extracted from operational source text.",
                },
                {
                    "else": {
                        "action": "needs_human_review",
                        "requires_approval": True,
                        "escalate_to": metadata.get("owner", "operations_reviewer"),
                    },
                    "reasoning": "Input did not match the extracted candidate rule.",
                },
            ],
            "learned_from": [
                {
                    "source": source,
                    "date": metadata.get("date", utc_now()[:10]),
                    "record_id": metadata.get("id"),
                }
            ],
            "related_skills": [],
        }

    @staticmethod
    def _infer_domain(content: str) -> str:
        lower = content.lower()
        if any(word in lower for word in ("refund", "ticket", "customer success", "zendesk")):
            return "support"
        if any(word in lower for word in ("discount", "pricing", "deal", "sales", "opportunity")):
            return "sales"
        if any(word in lower for word in ("supplier", "audit", "iso", "procurement", "sourcing")):
            return "procurement"
        return "operations"

    @staticmethod
    def _description_from_content(content: str) -> str:
        compact = " ".join(content.split())
        if len(compact) <= 240:
            return compact
        return compact[:237].rstrip() + "..."

    @staticmethod
    def _extract_number_before_word(content: str, word: str) -> int | None:
        match = re.search(r"(\d+)\s*" + re.escape(word), content)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _extract_percent(content: str) -> int | None:
        match = re.search(r"(\d+)\s*%", content)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _extract_money(content: str) -> int | None:
        match = re.search(r"\$?\s*(\d+(?:,\d{3})*|\d+)\s*k\b", content)
        if match:
            return int(match.group(1).replace(",", "")) * 1000
        match = re.search(r"\$\s*(\d+(?:,\d{3})*)", content)
        if match:
            return int(match.group(1).replace(",", ""))
        return None
