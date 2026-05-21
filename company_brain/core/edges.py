from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from company_brain.models import clamp


@dataclass
class Edge:
    source_id: str
    target_id: str
    relation: str
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return edge_id(self.source_id, self.target_id, self.relation)

    def merge(self, other: "Edge") -> "Edge":
        self.confidence = round(max(self.confidence, other.confidence), 4)
        self.evidence = sorted(set(self.evidence + other.evidence))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "confidence": round(clamp(float(self.confidence)), 4),
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Edge":
        return cls(
            source_id=str(payload["source_id"]),
            target_id=str(payload["target_id"]),
            relation=str(payload["relation"]),
            confidence=float(payload.get("confidence", 0.5)),
            evidence=list(payload.get("evidence", [])),
        )


def edge_id(source_id: str, target_id: str, relation: str) -> str:
    return f"{source_id}::{relation}::{target_id}"
