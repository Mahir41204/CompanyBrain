from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from company_brain.memory.ingestion import MemoryIngestionService
from company_brain.models import utc_now
from company_brain.storage import SourceSyncRepository


class NotionConnector:
    source_id = "notion"
    source_type = "notion"

    def __init__(
        self,
        data_dir: str | Path = "data",
        api_key: str | None = None,
        ingestion: MemoryIngestionService | None = None,
        sources: SourceSyncRepository | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.api_key = api_key or os.getenv("NOTION_API_KEY")
        self.ingestion = ingestion or MemoryIngestionService(data_dir)
        self.sources = sources or SourceSyncRepository(data_dir)
        self.api_base = "https://api.notion.com/v1"
        self.notion_version = os.getenv("NOTION_VERSION", "2022-06-28")

    def status(self) -> dict[str, Any]:
        stored = self.sources.get(self.source_id) or {
            "id": self.source_id,
            "source_type": self.source_type,
            "status": "not_connected",
            "connected": False,
            "documents_processed": 0,
            "knowledge_extracted": 0,
            "last_sync_at": None,
            "last_error": None,
            "metadata": {},
        }
        return {
            **stored,
            "auth_configured": bool(self.api_key),
            "supports": ["initial_sync", "incremental_sync", "metadata_tracking", "source_attribution"],
        }

    def sync(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        records = self._payload_records(payload)
        since = str(payload.get("since") or payload.get("cursor") or (self.sources.get(self.source_id) or {}).get("cursor") or "")
        metadata = {"mode": "payload" if records else "api", "since": since or None}
        self.sources.mark_syncing(self.source_id, self.source_type, metadata)

        try:
            if not records:
                if not self.api_key:
                    raise ValueError("Notion API key or records are required")
                records = self._fetch_records(payload, since=since or None)

            processed = 0
            extracted = 0
            ingested = []
            for record in records:
                if not str(record.get("content", "")).strip():
                    continue
                result = self.ingestion.ingest_record(record)
                processed += 1
                extracted += len(result.get("entities", [])) + len(result.get("edges", []))
                ingested.append(
                    {
                        "evidence_id": result["evidence"]["id"],
                        "entities": len(result.get("entities", [])),
                        "relationships": len(result.get("edges", [])),
                    }
                )

            cursor = utc_now()
            source = self.sources.mark_finished(
                self.source_id,
                self.source_type,
                documents_processed=processed,
                knowledge_extracted=extracted,
                cursor=cursor,
                metadata={**metadata, "records_seen": len(records)},
            )
            return {
                "source": source,
                "documents_processed": processed,
                "knowledge_extracted": extracted,
                "ingested": ingested,
            }
        except Exception as exc:
            self.sources.mark_failed(self.source_id, self.source_type, str(exc))
            raise

    def _payload_records(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = payload.get("records") or payload.get("documents") or []
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            raise ValueError("records must be a list")

        records = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            content = str(row.get("content") or row.get("text") or "")
            title = str(row.get("title") or row.get("name") or f"Notion document {index + 1}")
            page_id = str(row.get("id") or row.get("page_id") or f"payload-{index + 1}")
            records.append(
                {
                    "source": f"notion:{page_id}",
                    "content": content,
                    "metadata": {
                        "id": page_id,
                        "title": title,
                        "source_type": "notion",
                        "timestamp": str(row.get("last_edited_time") or row.get("timestamp") or utc_now()),
                        "url": row.get("url"),
                        "connector": "notion",
                    },
                }
            )
        return records

    def _fetch_records(self, payload: dict[str, Any], since: str | None = None) -> list[dict[str, Any]]:
        page_ids = list(payload.get("page_ids") or [])
        database_ids = list(payload.get("database_ids") or [])
        limit = int(payload.get("limit") or 25)

        pages: list[dict[str, Any]] = []
        for page_id in page_ids:
            pages.append(self._fetch_page(str(page_id)))
        for database_id in database_ids:
            pages.extend(self._fetch_database_pages(str(database_id), limit=limit))
        if not page_ids and not database_ids:
            pages.extend(self._search_pages(limit=limit))

        records = []
        for page in pages:
            if since and str(page.get("last_edited_time", "")) <= since:
                continue
            page_id = page["id"]
            text = self._fetch_block_text(page_id)
            records.append(
                {
                    "source": f"notion:{page_id}",
                    "content": text,
                    "metadata": {
                        "id": page_id,
                        "title": self._page_title(page),
                        "source_type": "notion",
                        "timestamp": page.get("last_edited_time") or utc_now(),
                        "url": page.get("url"),
                        "connector": "notion",
                    },
                }
            )
        return records

    def _fetch_page(self, page_id: str) -> dict[str, Any]:
        return self._request(f"/pages/{urllib.parse.quote(page_id)}", method="GET")

    def _fetch_database_pages(self, database_id: str, limit: int) -> list[dict[str, Any]]:
        payload = {"page_size": min(limit, 100)}
        response = self._request(f"/databases/{urllib.parse.quote(database_id)}/query", payload=payload)
        return list(response.get("results", []))

    def _search_pages(self, limit: int) -> list[dict[str, Any]]:
        payload = {
            "page_size": min(limit, 100),
            "filter": {"property": "object", "value": "page"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
        }
        response = self._request("/search", payload=payload)
        return list(response.get("results", []))

    def _fetch_block_text(self, block_id: str) -> str:
        response = self._request(f"/blocks/{urllib.parse.quote(block_id)}/children?page_size=100", method="GET")
        chunks = []
        for block in response.get("results", []):
            block_type = block.get("type")
            payload = block.get(block_type, {}) if block_type else {}
            chunks.extend(self._rich_text(payload.get("rich_text", [])))
            if block.get("has_children"):
                child_text = self._fetch_block_text(block["id"])
                if child_text:
                    chunks.append(child_text)
        return "\n".join(chunk for chunk in chunks if chunk).strip()

    def _request(self, path: str, payload: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("Notion API key is required")
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Notion-Version": self.notion_version,
            },
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _page_title(page: dict[str, Any]) -> str:
        properties = page.get("properties", {})
        for prop in properties.values():
            if prop.get("type") == "title":
                title = " ".join(NotionConnector._rich_text(prop.get("title", []))).strip()
                if title:
                    return title
        return str(page.get("id", "Untitled Notion page"))

    @staticmethod
    def _rich_text(rows: list[dict[str, Any]]) -> list[str]:
        chunks = []
        for row in rows:
            text = row.get("plain_text")
            if text:
                chunks.append(str(text))
        return chunks
