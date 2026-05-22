from __future__ import annotations

from company_brain.graph.temporal import MemorySnapshot

from .conflict import Conflict


class ConflictResolver:
    def suggest(self, conflict: Conflict, snapshots: list[MemorySnapshot]) -> dict[str, object]:
        relevant = [
            snapshot for snapshot in snapshots
            if snapshot.id in conflict.snapshots and conflict.attribute in snapshot.attributes
        ]
        if not relevant:
            return {
                "conflict_id": conflict.id,
                "resolution": "needs_human_review",
                "reason": "No supporting snapshots were available.",
            }

        relevant.sort(key=lambda row: (row.confidence, row.valid_from), reverse=True)
        winner = relevant[0]
        return {
            "conflict_id": conflict.id,
            "resolution": "prefer_snapshot",
            "snapshot_id": winner.id,
            "entity_id": winner.entity_id,
            "attribute": conflict.attribute,
            "value": winner.attributes.get(conflict.attribute),
            "confidence": winner.confidence,
            "reason": "Highest confidence and most recent supporting memory wins until a human marks a canonical answer.",
        }
