from __future__ import annotations

from typing import Any

from company_brain.connectors import NotionConnector
from company_brain.storage import SourceSyncRepository


class SourceDashboardService:
    def __init__(self, sources: SourceSyncRepository, notion: NotionConnector) -> None:
        self.sources = sources
        self.notion = notion

    def build(self) -> dict[str, Any]:
        stored = {row["id"]: row for row in self.sources.list_sources() if "id" in row}
        stored[self.notion.source_id] = {**self.notion.status(), **stored.get(self.notion.source_id, {})}
        return {
            "sources": [stored[key] for key in sorted(stored)],
            "summary": {
                "connected": len([row for row in stored.values() if row.get("connected")]),
                "documents_processed": sum(int(row.get("documents_processed", 0) or 0) for row in stored.values()),
                "knowledge_extracted": sum(int(row.get("knowledge_extracted", 0) or 0) for row in stored.values()),
            },
        }
