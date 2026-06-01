from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from company_brain.models import clamp


ENTITY_TYPES = {
    "person",
    "team",
    "process",
    "policy",
    "decision",
    "tool",
    "customer",
    "incident",
    "skill",
}

RELATION_TYPES = {
    "owns",
    "uses",
    "depends_on",
    "approves",
    "escalates_to",
    "governs",
    "blocks",
    "supports",
    "has_exception",
    "implements",
}


@dataclass
class LLMDiscoveryResult:
    provider: str
    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    processes: list[dict[str, Any]] = field(default_factory=list)
    policies: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "entities": self.entities,
            "relationships": self.relationships,
            "processes": self.processes,
            "policies": self.policies,
            "warnings": self.warnings,
        }


class DiscoveryProvider(Protocol):
    name: str

    def discover(self, record: dict[str, Any], evidence_id: str) -> dict[str, Any]:
        ...


class OpenAICompatibleDiscoveryProvider:
    name = "openai_compatible"

    def __init__(self) -> None:
        self.endpoint = os.getenv("COMPANYBRAIN_LLM_ENDPOINT", "https://api.openai.com/v1/chat/completions")
        self.api_key = os.getenv("COMPANYBRAIN_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("COMPANYBRAIN_LLM_MODEL", "gpt-4.1-mini")

    def available(self) -> bool:
        return bool(self.api_key)

    def discover(self, record: dict[str, Any], evidence_id: str) -> dict[str, Any]:
        if not self.available():
            raise RuntimeError("No LLM API key configured")

        text = str(record.get("content", ""))
        source = str(record.get("source", "manual"))
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract organizational memory as strict JSON. "
                        "Do not invent unsupported facts. Every entity and relationship must include evidence_id, source, and confidence. "
                        "Allowed entity types: person, team, process, policy, decision, tool, customer, incident, skill. "
                        "Allowed relationship types: owns, uses, depends_on, approves, escalates_to, governs, blocks, supports, has_exception, implements."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source": source,
                            "evidence_id": evidence_id,
                            "text": text,
                            "schema": {
                                "entities": [
                                    {
                                        "name": "string",
                                        "type": "allowed entity type",
                                        "confidence": "0..1",
                                        "evidence": [evidence_id],
                                        "source": source,
                                        "attributes": {},
                                    }
                                ],
                                "relationships": [
                                    {
                                        "source": "entity name",
                                        "target": "entity name",
                                        "relation": "allowed relationship type",
                                        "confidence": "0..1",
                                        "evidence": [evidence_id],
                                        "source_ref": source,
                                    }
                                ],
                                "processes": [
                                    {
                                        "name": "string",
                                        "owner": "string|null",
                                        "steps": ["string"],
                                        "dependencies": ["string"],
                                        "tools": ["string"],
                                        "policies": ["string"],
                                        "exceptions": ["string"],
                                        "confidence": "0..1",
                                        "evidence": [evidence_id],
                                    }
                                ],
                                "policies": [
                                    {
                                        "name": "string",
                                        "rules": {},
                                        "owner": "string|null",
                                        "exceptions": ["string"],
                                        "confidence": "0..1",
                                        "evidence": [evidence_id],
                                    }
                                ],
                            },
                        }
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        return json.loads(content)


class SchemaFallbackDiscoveryProvider:
    """Offline fallback that emits the same schema as the LLM provider."""

    name = "schema_fallback"

    def discover(self, record: dict[str, Any], evidence_id: str) -> dict[str, Any]:
        text = str(record.get("content", ""))
        lower = text.lower()
        source = str(record.get("source", "manual"))
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        processes: list[dict[str, Any]] = []
        policies: list[dict[str, Any]] = []

        def add_entity(name: str, entity_type: str, confidence: float = 0.72, attributes: dict[str, Any] | None = None) -> None:
            if not name:
                return
            key = (name.lower(), entity_type)
            if any((row["name"].lower(), row["type"]) == key for row in entities):
                return
            entities.append(
                {
                    "name": name,
                    "type": entity_type,
                    "confidence": confidence,
                    "evidence": [evidence_id],
                    "source": source,
                    "attributes": attributes or {},
                }
            )

        def add_rel(source_name: str, target_name: str, relation: str, confidence: float = 0.72) -> None:
            if not source_name or not target_name:
                return
            relationships.append(
                {
                    "source": source_name,
                    "target": target_name,
                    "relation": relation,
                    "confidence": confidence,
                    "evidence": [evidence_id],
                    "source_ref": source,
                }
            )

        tool_names = {
            "notion": "Notion",
            "confluence": "Confluence",
            "zendesk": "Zendesk",
            "jira": "Jira",
            "linear": "Linear",
            "salesforce": "Salesforce",
            "slack": "Slack",
            "github": "GitHub",
            "google docs": "Google Docs",
        }
        teams = {
            "finance": "Finance Team",
            "support": "Support Team",
            "customer success": "Customer Success Team",
            "sales": "Sales Team",
            "engineering": "Engineering Team",
            "ops": "Ops Team",
            "operations": "Ops Team",
            "legal": "Legal Team",
        }
        process_name = self._process_name(lower)
        if process_name:
            add_entity(process_name, "process", 0.76)
            processes.append(
                {
                    "name": process_name,
                    "owner": None,
                    "steps": self._steps(lower),
                    "dependencies": [],
                    "tools": [],
                    "policies": [],
                    "exceptions": self._exceptions(lower),
                    "confidence": 0.76,
                    "evidence": [evidence_id],
                }
            )

        for key, display in tool_names.items():
            if key in lower:
                add_entity(display, "tool", 0.82)
                if process_name:
                    add_rel(process_name, display, "uses", 0.82)
                    processes[-1]["tools"].append(display)

        for key, display in teams.items():
            if re.search(rf"\b{re.escape(key)}\b", lower):
                add_entity(display, "team", 0.80)
                if process_name and any(token in lower for token in ("approve", "approval", "requires")):
                    add_rel(display, process_name, "approves", 0.80)
                    processes[-1]["owner"] = display

        for name in self._people(text):
            add_entity(name, "person", 0.74)
            if process_name and "escalate" in lower:
                add_rel(process_name, name, "escalates_to", 0.78)

        policy_name = self._policy_name(lower, process_name)
        if policy_name:
            rules = self._rules(lower)
            add_entity(policy_name, "policy", 0.78, rules)
            policies.append(
                {
                    "name": policy_name,
                    "rules": rules,
                    "owner": processes[-1]["owner"] if processes else None,
                    "exceptions": self._exceptions(lower),
                    "confidence": 0.78,
                    "evidence": [evidence_id],
                }
            )
            if process_name:
                add_rel(policy_name, process_name, "governs", 0.78)
                processes[-1]["policies"].append(policy_name)

        for exception in self._exceptions(lower):
            entity_type = "customer" if "customer" in exception.lower() else "incident"
            add_entity(exception, entity_type, 0.70, {"exception": True})
            if policy_name:
                add_rel(policy_name, exception, "has_exception", 0.72)

        for match in re.finditer(r"([a-z][a-z\s]{2,40})\s+depends on\s+([a-z][a-z\s]{2,40})", lower):
            left = self._title(match.group(1))
            right = self._title(match.group(2))
            add_entity(left, "process", 0.68)
            add_entity(right, "tool", 0.66)
            add_rel(left, right, "depends_on", 0.70)

        return {
            "entities": entities,
            "relationships": relationships,
            "processes": processes,
            "policies": policies,
        }

    @staticmethod
    def _process_name(text: str) -> str | None:
        explicit = re.search(r"([a-z][a-z\s]{2,40})\s+process", text)
        if explicit:
            phrase = " ".join(explicit.group(0).split())
            return phrase
        for token in ("refund", "onboarding", "handoff", "incident", "approval", "access", "renewal", "support"):
            if token in text:
                return f"{token} process"
        return None

    @staticmethod
    def _policy_name(text: str, process_name: str | None) -> str | None:
        explicit = re.search(r"([a-z][a-z\s]{2,40})\s+policy", text)
        if explicit:
            return " ".join(explicit.group(0).split())
        if "policy" in text and process_name:
            return process_name.replace(" process", " policy")
        if any(token in text for token in ("requires", "must", "skip review", "bypass")) and process_name:
            return process_name.replace(" process", " policy")
        return None

    @staticmethod
    def _steps(text: str) -> list[str]:
        steps = []
        for token in ("open", "triage", "review", "approve", "escalate", "document", "notify", "close"):
            if token in text:
                steps.append(token)
        return steps or ["review", "decide", "record"]

    @staticmethod
    def _exceptions(text: str) -> list[str]:
        exceptions = []
        if "vip" in text:
            exceptions.append("VIP customer")
        if "enterprise" in text:
            exceptions.append("enterprise customer")
        if "sla" in text:
            exceptions.append("SLA breach")
        if "churn" in text:
            exceptions.append("churn-risk customer")
        return exceptions

    @staticmethod
    def _rules(text: str) -> dict[str, Any]:
        rules: dict[str, Any] = {}
        money = re.search(r"(?:above|over|>)\s*\$?\s*(\d+(?:,\d{3})*)", text)
        if money:
            rules["approval_threshold_usd"] = int(money.group(1).replace(",", ""))
        days = re.search(r"(\d+)\s*days?", text)
        if days:
            rules["days"] = int(days.group(1))
        if "skip review" in text or "bypass" in text:
            rules["bypass_review"] = True
        return rules

    @staticmethod
    def _people(text: str) -> list[str]:
        names = []
        for match in re.finditer(r"\b(?:to|ask|notify|owner)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text):
            names.append(match.group(1).strip())
        return sorted(set(names))

    @staticmethod
    def _title(value: str) -> str:
        return " ".join(value.split()).strip().title()


class LLMDiscoveryEngine:
    def __init__(self, provider: DiscoveryProvider | None = None) -> None:
        self.fallback = SchemaFallbackDiscoveryProvider()
        self.provider = provider or OpenAICompatibleDiscoveryProvider()

    def discover(self, record: dict[str, Any], evidence_id: str) -> LLMDiscoveryResult:
        warnings: list[str] = []
        provider_name = getattr(self.provider, "name", "unknown")
        try:
            if hasattr(self.provider, "available") and not self.provider.available():  # type: ignore[attr-defined]
                raise RuntimeError("LLM provider unavailable")
            raw = self.provider.discover(record, evidence_id)
        except Exception as exc:
            warnings.append(f"LLM provider unavailable; used schema fallback: {exc}")
            provider_name = self.fallback.name
            raw = self.fallback.discover(record, evidence_id)
        return self._normalize(raw, provider_name, warnings, record, evidence_id)

    def _normalize(
        self,
        raw: dict[str, Any],
        provider: str,
        warnings: list[str],
        record: dict[str, Any],
        evidence_id: str,
    ) -> LLMDiscoveryResult:
        source = str(record.get("source", "manual"))
        entities = [self._entity(row, source, evidence_id) for row in raw.get("entities", []) if isinstance(row, dict)]
        relationships = [
            self._relationship(row, source, evidence_id)
            for row in raw.get("relationships", [])
            if isinstance(row, dict)
        ]
        processes = [self._process(row, evidence_id) for row in raw.get("processes", []) if isinstance(row, dict)]
        policies = [self._policy(row, evidence_id) for row in raw.get("policies", []) if isinstance(row, dict)]
        return LLMDiscoveryResult(
            provider=provider,
            entities=entities,
            relationships=relationships,
            processes=processes,
            policies=policies,
            warnings=warnings,
        )

    @staticmethod
    def _entity(row: dict[str, Any], source: str, evidence_id: str) -> dict[str, Any]:
        entity_type = str(row.get("type", "process")).lower()
        if entity_type not in ENTITY_TYPES:
            entity_type = "process"
        return {
            "name": str(row.get("name", "")).strip(),
            "type": entity_type,
            "confidence": round(clamp(float(row.get("confidence", 0.5))), 4),
            "evidence": list(row.get("evidence") or [evidence_id]),
            "source": str(row.get("source", source)),
            "attributes": dict(row.get("attributes", {})),
        }

    @staticmethod
    def _relationship(row: dict[str, Any], source: str, evidence_id: str) -> dict[str, Any]:
        relation = str(row.get("relation", "depends_on")).lower()
        if relation not in RELATION_TYPES:
            relation = "depends_on"
        return {
            "source": str(row.get("source", "")).strip(),
            "target": str(row.get("target", "")).strip(),
            "relation": relation,
            "confidence": round(clamp(float(row.get("confidence", 0.5))), 4),
            "evidence": list(row.get("evidence") or [evidence_id]),
            "source_ref": str(row.get("source_ref", source)),
        }

    @staticmethod
    def _process(row: dict[str, Any], evidence_id: str) -> dict[str, Any]:
        return {
            "name": str(row.get("name", "")).strip(),
            "owner": row.get("owner"),
            "steps": list(row.get("steps", [])),
            "dependencies": list(row.get("dependencies", [])),
            "tools": list(row.get("tools", [])),
            "policies": list(row.get("policies", [])),
            "exceptions": list(row.get("exceptions", [])),
            "confidence": round(clamp(float(row.get("confidence", 0.5))), 4),
            "evidence": list(row.get("evidence") or [evidence_id]),
        }

    @staticmethod
    def _policy(row: dict[str, Any], evidence_id: str) -> dict[str, Any]:
        return {
            "name": str(row.get("name", "")).strip(),
            "rules": dict(row.get("rules", {})),
            "owner": row.get("owner"),
            "exceptions": list(row.get("exceptions", [])),
            "confidence": round(clamp(float(row.get("confidence", 0.5))), 4),
            "evidence": list(row.get("evidence") or [evidence_id]),
        }
