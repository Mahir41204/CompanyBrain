from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from company_brain.models import clamp


@dataclass
class Evidence:
    id: str
    source_type: str
    source_ref: str
    text: str
    timestamp: str
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "text": self.text,
            "timestamp": self.timestamp,
            "confidence": round(clamp(float(self.confidence)), 4),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Evidence":
        return cls(
            id=str(payload["id"]),
            source_type=str(payload["source_type"]),
            source_ref=str(payload["source_ref"]),
            text=str(payload["text"]),
            timestamp=str(payload["timestamp"]),
            confidence=float(payload.get("confidence", 0.5)),
        )
