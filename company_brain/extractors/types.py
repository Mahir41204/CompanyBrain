from __future__ import annotations

from dataclasses import dataclass, field

from company_brain.core.edges import Edge
from company_brain.core.entities import Entity


@dataclass
class ExtractionResult:
    entities: list[Entity] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def extend(self, other: "ExtractionResult") -> None:
        self.entities.extend(other.entities)
        self.edges.extend(other.edges)
