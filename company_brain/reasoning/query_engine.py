from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph
from company_brain.graph.temporal import MemorySnapshot

from .dependency_analyzer import DependencyAnalyzer


class BrainQueryEngine:
    def __init__(self, graph: BrainGraph, snapshots: list[MemorySnapshot] | None = None) -> None:
        self.graph = graph
        self.snapshots = snapshots or []
        self.dependencies = DependencyAnalyzer(graph)

    def search(self, query: str, limit: int = 8) -> dict[str, Any]:
        return {"query": query, "results": [entity.to_dict() for entity in self.graph.search(query, limit=limit)]}

    def find_owner(self, query: str) -> dict[str, Any]:
        root = self._match(query)
        if not root:
            return {"query": query, "matched_entity": None, "owners": []}

        owners = []
        for row in self.graph.neighbors(root.id):
            relation = row["relation"]
            entity = row["entity"]
            if relation == "owns" and row["direction"] == "in":
                owners.append(self._owner_row(entity, row, "direct_owner"))
            if relation == "requires_approval" and entity["type"] == "team":
                owners.append(self._owner_row(entity, row, "approval_owner"))
            if relation == "governed_by" and row["direction"] == "out":
                for policy_row in self.graph.neighbors(entity["id"], direction="in"):
                    if policy_row["relation"] == "owns":
                        owners.append(self._owner_row(policy_row["entity"], policy_row, "policy_owner"))

        return {
            "query": query,
            "matched_entity": root.to_dict(),
            "owners": self._dedupe_rows(owners),
        }

    def find_dependencies(self, query: str, max_depth: int = 3) -> dict[str, Any]:
        return self.dependencies.dependencies_for(query, max_depth=max_depth)

    def find_affected(self, query: str, max_depth: int = 4) -> dict[str, Any]:
        return self.dependencies.affected_by_removal(query, max_depth=max_depth)

    def trace_decision(self, query: str) -> dict[str, Any]:
        root = self._match(query)
        if not root:
            return {"query": query, "matched_entity": None, "trace": []}

        explanation = self.graph.explain(query)
        owners = self.find_owner(query)["owners"]
        dependencies = self.find_dependencies(query, max_depth=2)["dependencies"]
        trace = []
        for relation, rows in explanation.get("relations", {}).items():
            for row in rows:
                trace.append(
                    {
                        "relation": relation,
                        "entity": row["entity"],
                        "confidence": row["confidence"],
                        "reason": f"{root.name} is connected by {relation}.",
                    }
                )

        return {
            "query": query,
            "matched_entity": root.to_dict(),
            "owners": owners,
            "dependencies": dependencies,
            "trace": trace,
            "evidence": explanation.get("evidence", []),
        }

    def timeline(self, query_or_entity_id: str) -> dict[str, Any]:
        entity_id = query_or_entity_id
        if entity_id not in self.graph.entities:
            root = self._match(query_or_entity_id)
            if not root:
                return {"query": query_or_entity_id, "matched_entity": None, "timeline": []}
            entity_id = root.id

        timeline = [snapshot for snapshot in self.snapshots if snapshot.entity_id == entity_id]
        timeline.sort(key=lambda snapshot: snapshot.valid_from)
        return {
            "query": query_or_entity_id,
            "matched_entity": self.graph.entities.get(entity_id).to_dict() if entity_id in self.graph.entities else None,
            "timeline": [snapshot.to_dict() for snapshot in timeline],
        }

    def _match(self, query: str):
        matches = self.graph.search(query, limit=1)
        return matches[0] if matches else None

    @staticmethod
    def _owner_row(entity: dict[str, Any], row: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            "entity": entity,
            "relation": row["relation"],
            "confidence": row["edge"]["confidence"],
            "reason": reason,
            "evidence": row.get("evidence", []),
        }

    @staticmethod
    def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped = {}
        for row in rows:
            entity_id = row["entity"]["id"]
            if entity_id not in deduped or row["confidence"] > deduped[entity_id]["confidence"]:
                deduped[entity_id] = row
        return sorted(deduped.values(), key=lambda item: item["confidence"], reverse=True)
