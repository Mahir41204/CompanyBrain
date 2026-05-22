from __future__ import annotations

from pathlib import Path

from company_brain.discovery.types import Discovery

from .json_file import read_json_array, write_json_array


class DiscoveryRepository:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.path = Path(data_dir) / "discoveries.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_discoveries(self) -> list[Discovery]:
        return [Discovery.from_dict(row) for row in read_json_array(self.path)]

    def upsert(self, discovery: Discovery) -> Discovery:
        rows = {item.id: item for item in self.list_discoveries()}
        rows[discovery.id] = discovery
        write_json_array(self.path, [item.to_dict() for item in sorted(rows.values(), key=lambda row: row.id)])
        return discovery
