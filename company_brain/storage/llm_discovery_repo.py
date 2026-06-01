from __future__ import annotations

from pathlib import Path
from typing import Any

from .json_file import read_json_array, write_json_array


class LLMDiscoveryRepository:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.path = Path(data_dir) / "llm_discoveries.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_results(self) -> list[dict[str, Any]]:
        return read_json_array(self.path)

    def upsert(self, discovery_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = {row["id"]: row for row in self.list_results() if "id" in row}
        rows[discovery_id] = {"id": discovery_id, **payload}
        write_json_array(self.path, [rows[key] for key in sorted(rows)])
        return rows[discovery_id]
