from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .event_store import Event


def discover_flow(events: list[Event]) -> dict[str, Any]:
    sorted_events = sorted(events, key=lambda event: (event.object, event.timestamp))
    by_object: dict[str, list[Event]] = defaultdict(list)
    for event in sorted_events:
        by_object[event.object].append(event)

    transitions: Counter[tuple[str, str]] = Counter()
    for object_events in by_object.values():
        for index in range(len(object_events) - 1):
            transitions[(object_events[index].action, object_events[index + 1].action)] += 1

    return {
        "transitions": [
            {"from": source, "to": target, "count": count}
            for (source, target), count in transitions.most_common()
        ],
        "objects_observed": len(by_object),
        "events_observed": len(events),
    }


class ProcessMiner:
    def discover_flow(self, events: list[Event]) -> dict[str, Any]:
        return discover_flow(events)
