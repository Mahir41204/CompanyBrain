from __future__ import annotations

import hashlib
from pathlib import Path

from company_brain.core.entities import Entity
from company_brain.graph.temporal import MemorySnapshot

from .json_file import read_json_array, write_json_array


class SnapshotRepository:
    OPEN_END = ""

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.path = Path(data_dir) / "memory_snapshots.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_snapshots(self, entity_id: str | None = None) -> list[MemorySnapshot]:
        snapshots = [MemorySnapshot.from_dict(row) for row in read_json_array(self.path)]
        if entity_id is None:
            return snapshots
        return [snapshot for snapshot in snapshots if snapshot.entity_id == entity_id]

    def current(self, entity_id: str) -> MemorySnapshot | None:
        snapshots = [
            snapshot for snapshot in self.list_snapshots(entity_id)
            if snapshot.valid_until == self.OPEN_END
        ]
        if not snapshots:
            return None
        snapshots.sort(key=lambda snapshot: snapshot.valid_from, reverse=True)
        return snapshots[0]

    def at(self, entity_id: str, timestamp: str) -> MemorySnapshot | None:
        snapshots = self.list_snapshots(entity_id)
        for snapshot in sorted(snapshots, key=lambda row: row.valid_from, reverse=True):
            starts_before = snapshot.valid_from <= timestamp
            ends_after = not snapshot.valid_until or timestamp < snapshot.valid_until
            if starts_before and ends_after:
                return snapshot
        return None

    def record_entity(self, entity: Entity, valid_from: str) -> MemorySnapshot:
        snapshots = self.list_snapshots()
        current = self.current(entity.id)
        attributes = dict(entity.attributes)
        sources = sorted(set(entity.sources))

        if current and current.attributes == attributes:
            current.sources = sorted(set(current.sources + sources))
            current.confidence = max(current.confidence, entity.confidence)
            self._write(self._replace(snapshots, current))
            return current

        previous_id = current.id if current else None
        if current:
            current.valid_until = valid_from
            snapshots = self._replace(snapshots, current)

        digest = hashlib.sha1(f"{entity.id}:{valid_from}:{attributes}".encode("utf-8")).hexdigest()[:12]
        snapshot = MemorySnapshot(
            id=f"snapshot_{digest}",
            entity_id=entity.id,
            valid_from=valid_from,
            valid_until=self.OPEN_END,
            previous=previous_id,
            attributes=attributes,
            sources=sources,
            confidence=entity.confidence,
        )
        snapshots.append(snapshot)
        self._write(snapshots)
        return snapshot

    def _replace(self, snapshots: list[MemorySnapshot], replacement: MemorySnapshot) -> list[MemorySnapshot]:
        return [replacement if snapshot.id == replacement.id else snapshot for snapshot in snapshots]

    def _write(self, snapshots: list[MemorySnapshot]) -> None:
        write_json_array(self.path, [snapshot.to_dict() for snapshot in sorted(snapshots, key=lambda row: row.id)])
