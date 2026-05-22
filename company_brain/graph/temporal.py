from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemorySnapshot:
    id: str
    entity_id: str
    valid_from: str
    valid_until: str
    previous: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "previous": self.previous,
            "attributes": self.attributes,
            "sources": self.sources,
            "confidence": round(self.confidence, 4),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemorySnapshot":
        return cls(
            id=str(payload["id"]),
            entity_id=str(payload["entity_id"]),
            valid_from=str(payload["valid_from"]),
            valid_until=str(payload.get("valid_until", "")),
            previous=payload.get("previous"),
            attributes=dict(payload.get("attributes", {})),
            sources=list(payload.get("sources", [])),
            confidence=float(payload.get("confidence", 0.5)),
        )
