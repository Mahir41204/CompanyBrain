from __future__ import annotations

from pathlib import Path
from typing import Any

from company_brain.models import utc_now

from .json_file import read_json_array, write_json_array


class SourceSyncRepository:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.path = Path(data_dir) / "source_syncs.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_sources(self) -> list[dict[str, Any]]:
        return read_json_array(self.path)

    def get(self, source_id: str) -> dict[str, Any] | None:
        for source in self.list_sources():
            if source.get("id") == source_id:
                return source
        return None

    def upsert(self, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        sources = {row["id"]: row for row in self.list_sources() if "id" in row}
        existing = sources.get(source_id, {})
        sources[source_id] = {
            **existing,
            "id": source_id,
            "updated_at": utc_now(),
            **payload,
        }
        write_json_array(self.path, [sources[key] for key in sorted(sources)])
        return sources[source_id]

    def mark_syncing(self, source_id: str, source_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.upsert(
            source_id,
            {
                "source_type": source_type,
                "status": "syncing",
                "connected": True,
                "last_error": None,
                "sync_started_at": utc_now(),
                "metadata": metadata or {},
            },
        )

    def mark_finished(
        self,
        source_id: str,
        source_type: str,
        *,
        documents_processed: int,
        knowledge_extracted: int,
        cursor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.upsert(
            source_id,
            {
                "source_type": source_type,
                "status": "connected",
                "connected": True,
                "last_sync_at": utc_now(),
                "cursor": cursor,
                "documents_processed": documents_processed,
                "knowledge_extracted": knowledge_extracted,
                "last_error": None,
                "metadata": metadata or {},
            },
        )

    def mark_failed(self, source_id: str, source_type: str, error: str) -> dict[str, Any]:
        return self.upsert(
            source_id,
            {
                "source_type": source_type,
                "status": "error",
                "connected": False,
                "last_error": error,
                "last_sync_at": utc_now(),
            },
        )
