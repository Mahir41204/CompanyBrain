from __future__ import annotations

import hashlib
from typing import Any

from company_brain.models import utc_now

from .exception_discovery import ExceptionDiscovery
from .owner_discovery import OwnerDiscovery
from .policy_discovery import PolicyDiscovery
from .process_discovery import ProcessDiscovery
from .tool_discovery import ToolDiscovery
from .types import Discovery


class DiscoveryEngine:
    def __init__(self) -> None:
        self.process = ProcessDiscovery()
        self.policy = PolicyDiscovery()
        self.owner = OwnerDiscovery()
        self.exceptions = ExceptionDiscovery()
        self.tool = ToolDiscovery()

    def discover(self, record: dict[str, Any], evidence_id: str | None = None) -> Discovery:
        text = str(record.get("content", "")).strip()
        if not text:
            raise ValueError("record content is required")

        source = str(record.get("source", "manual_note"))
        metadata = record.get("metadata", {})
        process_result = self.process.discover(text)
        process = str(process_result["process"])
        digest = hashlib.sha1(f"{source}:{text}".encode("utf-8")).hexdigest()[:14]
        evidence_ids = [evidence_id] if evidence_id else []

        return Discovery(
            id=f"discovery_{digest}",
            process=process,
            steps=list(process_result["steps"]),
            owner=self.owner.discover(text),
            exceptions=self.exceptions.discover(text),
            tool=self.tool.discover(text),
            policies=self.policy.discover(text, process),
            source_refs=[str(metadata.get("id", source))],
            evidence_ids=evidence_ids,
            confidence=self._confidence(text, process_result),
            created_at=utc_now(),
        )

    @staticmethod
    def _confidence(text: str, process_result: dict[str, object]) -> float:
        score = 0.52
        lower = text.lower()
        if process_result.get("process") != "operations":
            score += 0.12
        if process_result.get("steps"):
            score += 0.08
        if any(token in lower for token in ("requires", "approve", "approval", "escalate")):
            score += 0.10
        if any(token in lower for token in ("zendesk", "salesforce", "supplieros", "jira", "linear")):
            score += 0.08
        return min(round(score, 4), 0.92)
