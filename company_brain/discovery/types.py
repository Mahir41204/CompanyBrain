from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Discovery:
    id: str
    process: str
    steps: list[str] = field(default_factory=list)
    owner: str | None = None
    exceptions: list[str] = field(default_factory=list)
    tool: str | None = None
    policies: dict[str, Any] = field(default_factory=dict)
    source_refs: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "process": self.process,
            "steps": self.steps,
            "owner": self.owner,
            "exceptions": self.exceptions,
            "tool": self.tool,
            "policies": self.policies,
            "source_refs": self.source_refs,
            "evidence_ids": self.evidence_ids,
            "confidence": round(self.confidence, 4),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Discovery":
        return cls(
            id=str(payload["id"]),
            process=str(payload["process"]),
            steps=list(payload.get("steps", [])),
            owner=payload.get("owner"),
            exceptions=list(payload.get("exceptions", [])),
            tool=payload.get("tool"),
            policies=dict(payload.get("policies", {})),
            source_refs=list(payload.get("source_refs", [])),
            evidence_ids=list(payload.get("evidence_ids", [])),
            confidence=float(payload.get("confidence", 0.5)),
            created_at=str(payload.get("created_at", "")),
        )
