from __future__ import annotations

from collections import deque
from typing import Any

from company_brain.core.graph import BrainGraph


class GraphTraverser:
    def __init__(self, graph: BrainGraph) -> None:
        self.graph = graph

    def traverse(
        self,
        start_id: str,
        max_depth: int = 3,
        direction: str = "both",
        relations: set[str] | None = None,
    ) -> dict[str, Any]:
        if start_id not in self.graph.entities:
            return {"start_id": start_id, "paths": [], "visited": []}

        queue: deque[tuple[str, int, list[dict[str, Any]]]] = deque([(start_id, 0, [])])
        seen = {start_id}
        paths: list[dict[str, Any]] = []

        while queue:
            current_id, depth, path = queue.popleft()
            if depth >= max_depth:
                continue

            for row in self.graph.neighbors(current_id, direction=direction):
                relation = row["relation"]
                if relations and relation not in relations:
                    continue

                entity = row["entity"]
                if entity["id"] in seen:
                    continue
                step = {
                    "from": current_id,
                    "to": entity["id"],
                    "relation": relation,
                    "direction": row["direction"],
                    "entity": entity,
                    "confidence": row["edge"]["confidence"],
                    "evidence": row.get("evidence", []),
                }
                next_path = path + [step]
                paths.append({"depth": depth + 1, "steps": next_path})

                seen.add(entity["id"])
                queue.append((entity["id"], depth + 1, next_path))

        return {
            "start_id": start_id,
            "paths": paths,
            "visited": [self.graph.entities[entity_id].to_dict() for entity_id in sorted(seen)],
        }
