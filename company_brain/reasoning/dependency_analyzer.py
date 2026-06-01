from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph

from .graph_traverser import GraphTraverser


DEPENDENCY_RELATIONS = {
    "uses",
    "depends_on",
    "governed_by",
    "requires_approval",
    "has_decision",
    "implements",
    "approves",
    "escalates_to",
    "blocks",
    "blocked_by",
}


class DependencyAnalyzer:
    def __init__(self, graph: BrainGraph) -> None:
        self.graph = graph
        self.traverser = GraphTraverser(graph)

    def dependencies_for(self, query: str, max_depth: int = 3) -> dict[str, Any]:
        root = self._match(query)
        if not root:
            return {"query": query, "matched_entity": None, "dependencies": [], "paths": []}

        traversal = self.traverser.traverse(
            root.id,
            max_depth=max_depth,
            direction="out",
            relations=DEPENDENCY_RELATIONS,
        )
        return {
            "query": query,
            "matched_entity": root.to_dict(),
            "dependencies": self._summarize_paths(traversal["paths"]),
            "paths": traversal["paths"],
        }

    def affected_by_removal(self, query: str, max_depth: int = 4) -> dict[str, Any]:
        root = self._match(query)
        if not root:
            return {"query": query, "matched_entity": None, "affected": [], "paths": []}

        traversal = self.traverser.traverse(
            root.id,
            max_depth=max_depth,
            direction="both",
            relations=DEPENDENCY_RELATIONS | {"owns", "has_exception"},
        )
        affected_paths = []
        for path in traversal["paths"]:
            if not path["steps"]:
                continue
            first = path["steps"][0]
            # A removal primarily affects nodes that point at the removed entity,
            # plus downstream neighbors of those nodes.
            if first["direction"] == "in" or len(path["steps"]) > 1:
                affected_paths.append(path)

        return {
            "query": query,
            "matched_entity": root.to_dict(),
            "affected": self._summarize_paths(affected_paths),
            "paths": affected_paths,
        }

    def _match(self, query: str):
        matches = self.graph.search(query, limit=1)
        return matches[0] if matches else None

    @staticmethod
    def _summarize_paths(paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for path in paths:
            if not path["steps"]:
                continue
            last = path["steps"][-1]
            entity = last["entity"]
            current = seen.setdefault(
                entity["id"],
                {
                    "entity": entity,
                    "min_depth": path["depth"],
                    "relations": [],
                    "max_confidence": 0,
                },
            )
            current["min_depth"] = min(current["min_depth"], path["depth"])
            current["max_confidence"] = max(current["max_confidence"], last["confidence"])
            current["relations"].append(last["relation"])

        rows = []
        for row in seen.values():
            row["relations"] = sorted(set(row["relations"]))
            row["max_confidence"] = round(row["max_confidence"], 4)
            rows.append(row)
        return sorted(rows, key=lambda item: (item["min_depth"], item["entity"]["type"], item["entity"]["name"]))
