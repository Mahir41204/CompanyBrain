from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from company_brain.models import utc_now


@dataclass
class Event:
    timestamp: str
    actor: str
    action: str
    object: str
    outcome: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "object": self.object,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Event":
        return cls(
            timestamp=str(payload.get("timestamp", utc_now())),
            actor=str(payload.get("actor", "unknown")),
            action=str(payload["action"]),
            object=str(payload.get("object", payload.get("object_id", "unknown"))),
            outcome=str(payload.get("outcome", "")),
        )


class EventStore:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.path = Path(data_dir) / "events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: Event) -> Event:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), separators=(",", ":")) + "\n")
        return event

    def append_many(self, events: list[Event]) -> list[Event]:
        for event in events:
            self.append(event)
        return events

    def list_events(self) -> list[Event]:
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(Event.from_dict(json.loads(line)))
        return events
