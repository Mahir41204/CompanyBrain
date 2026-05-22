from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph
from company_brain.graph.temporal import MemorySnapshot

from .conflict_detector import ConflictDetector
from .resolver import ConflictResolver


class MemoryExplainer:
    def __init__(self, graph: BrainGraph, snapshots: list[MemorySnapshot]) -> None:
        self.graph = graph
        self.snapshots = snapshots

    def explain(self, query: str, at: str | None = None) -> dict[str, Any]:
        explanation = self.graph.explain(query)
        entity = explanation.get("matched_entity")
        if not entity:
            return explanation

        entity_id = entity["id"]
        history = [snapshot for snapshot in self.snapshots if snapshot.entity_id == entity_id]
        if at:
            history = [
                snapshot for snapshot in history
                if snapshot.valid_from <= at and (not snapshot.valid_until or at < snapshot.valid_until)
            ]

        conflicts = [
            conflict for conflict in ConflictDetector().detect(self.snapshots)
            if conflict.entity_id == entity_id
        ]
        resolver = ConflictResolver()

        explanation["history"] = [snapshot.to_dict() for snapshot in history]
        explanation["conflicts"] = [conflict.to_dict() for conflict in conflicts]
        explanation["resolution_suggestions"] = [
            resolver.suggest(conflict, self.snapshots) for conflict in conflicts
        ]
        return explanation
