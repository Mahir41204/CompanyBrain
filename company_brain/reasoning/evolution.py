from __future__ import annotations

from collections import defaultdict
from typing import Any

from company_brain.core.graph import BrainGraph
from company_brain.graph.temporal import MemorySnapshot


class OrganizationalEvolution:
    def __init__(self, graph: BrainGraph, snapshots: list[MemorySnapshot]) -> None:
        self.graph = graph
        self.snapshots = snapshots

    def timeline(self, entity_id: str | None = None) -> dict[str, Any]:
        by_entity: dict[str, list[MemorySnapshot]] = defaultdict(list)
        for snapshot in self.snapshots:
            if entity_id and snapshot.entity_id != entity_id:
                continue
            by_entity[snapshot.entity_id].append(snapshot)

        changes = []
        for current_entity_id, rows in by_entity.items():
            rows.sort(key=lambda snapshot: snapshot.valid_from)
            for index, snapshot in enumerate(rows):
                previous = rows[index - 1] if index > 0 else None
                changes.append(self._change_record(current_entity_id, previous, snapshot))

        return {
            "entity_id": entity_id,
            "changes": changes,
        }

    def _change_record(
        self,
        entity_id: str,
        previous: MemorySnapshot | None,
        current: MemorySnapshot,
    ) -> dict[str, Any]:
        entity = self.graph.entities.get(entity_id)
        diff = self._diff(previous.attributes if previous else {}, current.attributes)
        return {
            "entity": entity.to_dict() if entity else {"id": entity_id},
            "snapshot_id": current.id,
            "valid_from": current.valid_from,
            "valid_until": current.valid_until,
            "previous": previous.id if previous else None,
            "diff": diff,
            "why_changed": self._why_changed(previous, current, diff),
            "changed_by": self._changed_by(current),
            "impact": self._impact(entity_id, diff),
            "sources": current.sources,
            "confidence": current.confidence,
        }

    @staticmethod
    def _diff(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        added = {key: current[key] for key in current.keys() - previous.keys()}
        removed = {key: previous[key] for key in previous.keys() - current.keys()}
        changed = {
            key: {"from": previous[key], "to": current[key]}
            for key in previous.keys() & current.keys()
            if previous[key] != current[key]
        }
        return {"added": added, "removed": removed, "changed": changed}

    @staticmethod
    def _why_changed(
        previous: MemorySnapshot | None,
        current: MemorySnapshot,
        diff: dict[str, Any],
    ) -> str:
        if previous is None:
            return "Initial observed memory version."
        if diff["changed"] or diff["added"] or diff["removed"]:
            return "Observed source evidence changed the entity attributes."
        if set(previous.sources) != set(current.sources):
            return "Supporting evidence changed but attributes remained stable."
        return "Version carried forward without material attribute change."

    @staticmethod
    def _changed_by(snapshot: MemorySnapshot) -> str:
        if not snapshot.sources:
            return "unknown"
        return ", ".join(snapshot.sources)

    @staticmethod
    def _impact(entity_id: str, diff: dict[str, Any]) -> list[str]:
        impacts = []
        changed_keys = set(diff["changed"]) | set(diff["added"]) | set(diff["removed"])
        if any("threshold" in key for key in changed_keys):
            impacts.append("Approval routing and autonomous execution boundaries may change.")
        if any("bypass" in key or "exception" in key for key in changed_keys):
            impacts.append("Exception handling may change for affected customer or supplier segments.")
        if any("owner" in key for key in changed_keys):
            impacts.append("Accountability and escalation paths may change.")
        if not impacts:
            impacts.append(f"Review downstream dependencies of {entity_id}.")
        return impacts
