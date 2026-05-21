from __future__ import annotations

from collections import deque
from typing import Any

from .edges import Edge
from .entities import Entity
from .evidence import Evidence


class BrainGraph:
    def __init__(
        self,
        entities: list[Entity] | None = None,
        edges: list[Edge] | None = None,
        evidence: list[Evidence] | None = None,
    ) -> None:
        self.entities: dict[str, Entity] = {}
        self.edges: dict[str, Edge] = {}
        self.evidence: dict[str, Evidence] = {}

        for item in evidence or []:
            self.evidence[item.id] = item
        for item in entities or []:
            self.add_entity(item)
        for item in edges or []:
            self.add_edge(item)

    def add_entity(self, entity: Entity) -> Entity:
        existing = self.entities.get(entity.id)
        if existing:
            return existing.merge(entity)
        self.entities[entity.id] = entity
        return entity

    def add_edge(self, edge: Edge) -> Edge:
        existing = self.edges.get(edge.id)
        if existing:
            return existing.merge(edge)
        self.edges[edge.id] = edge
        return edge

    def add_evidence(self, evidence: Evidence) -> Evidence:
        self.evidence[evidence.id] = evidence
        return evidence

    def neighbors(self, entity_id: str, direction: str = "both") -> list[dict[str, Any]]:
        rows = []
        for edge in self.edges.values():
            outbound = edge.source_id == entity_id and direction in ("both", "out")
            inbound = edge.target_id == entity_id and direction in ("both", "in")
            if not outbound and not inbound:
                continue

            neighbor_id = edge.target_id if outbound else edge.source_id
            entity = self.entities.get(neighbor_id)
            if not entity:
                continue

            rows.append(
                {
                    "direction": "out" if outbound else "in",
                    "relation": edge.relation,
                    "edge": edge.to_dict(),
                    "entity": entity.to_dict(),
                    "evidence": self._evidence_for(edge.evidence),
                }
            )
        return rows

    def path(self, source_id: str, target_id: str, max_depth: int = 4) -> dict[str, Any] | None:
        if source_id not in self.entities or target_id not in self.entities:
            return None

        queue: deque[tuple[str, list[str], list[str]]] = deque([(source_id, [source_id], [])])
        seen = {source_id}
        while queue:
            current, entity_path, edge_path = queue.popleft()
            if len(edge_path) >= max_depth:
                continue
            for edge in self.edges.values():
                if edge.source_id == current:
                    nxt = edge.target_id
                elif edge.target_id == current:
                    nxt = edge.source_id
                else:
                    continue
                if nxt in seen:
                    continue
                next_entity_path = entity_path + [nxt]
                next_edge_path = edge_path + [edge.id]
                if nxt == target_id:
                    return {
                        "entities": [self.entities[item].to_dict() for item in next_entity_path],
                        "edges": [self.edges[item].to_dict() for item in next_edge_path],
                    }
                seen.add(nxt)
                queue.append((nxt, next_entity_path, next_edge_path))
        return None

    def search(self, query: str, limit: int = 8) -> list[Entity]:
        tokens = [token for token in query.lower().replace("_", " ").split() if token]
        if not tokens:
            return []

        scored: list[tuple[int, Entity]] = []
        for entity in self.entities.values():
            haystack = " ".join(
                [
                    entity.id.lower().replace("_", " "),
                    entity.name.lower(),
                    entity.type.value.lower(),
                    " ".join(str(value).lower() for value in entity.attributes.values()),
                ]
            )
            score = sum(1 for token in tokens if token in haystack)
            if score:
                scored.append((score, entity))

        scored.sort(key=lambda item: (item[0], item[1].confidence), reverse=True)
        return [entity for _, entity in scored[:limit]]

    def explain(self, query: str) -> dict[str, Any]:
        matches = self.search(query, limit=6)
        if not matches:
            return {
                "query": query,
                "matched_entity": None,
                "confidence": 0.0,
                "relations": {},
                "evidence": [],
            }

        root = matches[0]
        neighbor_rows = self.neighbors(root.id)
        relations: dict[str, list[dict[str, Any]]] = {}
        evidence_ids = set(root.sources)

        for row in neighbor_rows:
            relation = row["relation"]
            if row["direction"] == "in":
                relation = f"{relation}_by"
            relations.setdefault(relation, []).append(
                {
                    "entity": row["entity"],
                    "confidence": row["edge"]["confidence"],
                    "direction": row["direction"],
                }
            )
            evidence_ids.update(row["edge"].get("evidence", []))

        edge_confidences = [row["edge"]["confidence"] for row in neighbor_rows]
        confidence_values = [root.confidence] + edge_confidences
        confidence = round(sum(confidence_values) / len(confidence_values), 4)

        return {
            "query": query,
            "matched_entity": root.to_dict(),
            "confidence": confidence,
            "relations": relations,
            "evidence": self._evidence_for(sorted(evidence_ids)),
            "also_matched": [entity.to_dict() for entity in matches[1:]],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [entity.to_dict() for entity in self.entities.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()],
            "evidence": [evidence.to_dict() for evidence in self.evidence.values()],
        }

    def _evidence_for(self, evidence_ids: list[str]) -> list[dict[str, Any]]:
        return [
            self.evidence[evidence_id].to_dict()
            for evidence_id in evidence_ids
            if evidence_id in self.evidence
        ]
