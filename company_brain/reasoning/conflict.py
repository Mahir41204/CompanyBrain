from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Conflict:
    id: str
    entity_id: str
    attribute: str
    version_a: Any
    version_b: Any
    sources: list[str] = field(default_factory=list)
    snapshots: list[str] = field(default_factory=list)
    severity: str = "medium"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "attribute": self.attribute,
            "version_a": self.version_a,
            "version_b": self.version_b,
            "sources": self.sources,
            "snapshots": self.snapshots,
            "severity": self.severity,
            "reason": self.reason,
        }
