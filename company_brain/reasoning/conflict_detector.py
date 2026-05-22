from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

from company_brain.graph.temporal import MemorySnapshot

from .conflict import Conflict


class ConflictDetector:
    def detect(self, snapshots: list[MemorySnapshot]) -> list[Conflict]:
        by_entity: dict[str, list[MemorySnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            by_entity[snapshot.entity_id].append(snapshot)

        conflicts: list[Conflict] = []
        for entity_id, entity_snapshots in by_entity.items():
            attribute_values: dict[str, dict[str, list[MemorySnapshot]]] = defaultdict(lambda: defaultdict(list))
            for snapshot in entity_snapshots:
                for attribute, value in snapshot.attributes.items():
                    if value is None or value == "":
                        continue
                    attribute_values[attribute][self._value_key(value)].append(snapshot)

            for attribute, values in attribute_values.items():
                if len(values) < 2:
                    continue
                value_keys = sorted(values)
                first = values[value_keys[0]][0]
                second = values[value_keys[1]][0]
                conflict_id = self._conflict_id(entity_id, attribute, value_keys[:2])
                active_values = {
                    key for key, rows in values.items()
                    if any(snapshot.valid_until == "" for snapshot in rows)
                }
                conflicts.append(
                    Conflict(
                        id=conflict_id,
                        entity_id=entity_id,
                        attribute=attribute,
                        version_a=first.attributes.get(attribute),
                        version_b=second.attributes.get(attribute),
                        sources=sorted(set(first.sources + second.sources)),
                        snapshots=sorted({snapshot.id for rows in values.values() for snapshot in rows}),
                        severity="high" if len(active_values) > 1 else "medium",
                        reason=f"{entity_id} has conflicting values for {attribute}.",
                    )
                )
        return conflicts

    @staticmethod
    def _value_key(value: Any) -> str:
        return repr(value)

    @staticmethod
    def _conflict_id(entity_id: str, attribute: str, values: list[str]) -> str:
        digest = hashlib.sha1(f"{entity_id}:{attribute}:{values}".encode("utf-8")).hexdigest()[:12]
        return f"conflict_{digest}"
