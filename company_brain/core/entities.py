from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from company_brain.models import clamp


class EntityType(Enum):
    PERSON = "person"
    TEAM = "team"
    PROCESS = "process"
    POLICY = "policy"
    TOOL = "tool"
    CUSTOMER = "customer"
    INCIDENT = "incident"
    DECISION = "decision"
    SKILL = "skill"


@dataclass
class Entity:
    id: str
    type: EntityType
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    sources: list[str] = field(default_factory=list)

    def merge(self, other: "Entity") -> "Entity":
        self.attributes = {**self.attributes, **other.attributes}
        self.confidence = round(max(self.confidence, other.confidence), 4)
        self.sources = sorted(set(self.sources + other.sources))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "name": self.name,
            "attributes": self.attributes,
            "confidence": round(clamp(float(self.confidence)), 4),
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Entity":
        return cls(
            id=str(payload["id"]),
            type=EntityType(str(payload["type"])),
            name=str(payload["name"]),
            attributes=dict(payload.get("attributes", {})),
            confidence=float(payload.get("confidence", 0.5)),
            sources=list(payload.get("sources", [])),
        )


def entity_id(entity_type: EntityType | str, name: str) -> str:
    type_value = entity_type.value if isinstance(entity_type, EntityType) else str(entity_type)
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not slug:
        slug = "unknown"
    return f"{type_value}_{slug}"
