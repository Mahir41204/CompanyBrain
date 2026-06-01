from __future__ import annotations

import re

from company_brain.core.edges import Edge
from company_brain.core.entities import Entity, EntityType, entity_id


class RelationDiscovery:
    def discover(self, text: str, entities: list[Entity], evidence_id: str) -> list[Edge]:
        lower = text.lower()
        by_type: dict[EntityType, list[Entity]] = {}
        for entity in entities:
            by_type.setdefault(entity.type, []).append(entity)

        edges: list[Edge] = []
        processes = by_type.get(EntityType.PROCESS, [])
        policies = by_type.get(EntityType.POLICY, [])
        teams = by_type.get(EntityType.TEAM, [])
        people = by_type.get(EntityType.PERSON, [])
        tools = by_type.get(EntityType.TOOL, [])
        decisions = by_type.get(EntityType.DECISION, [])

        for process in processes:
            for tool in tools:
                if self._mentions_tool_use(lower, tool.name):
                    edges.append(Edge(process.id, tool.id, "uses", 0.88, [evidence_id]))
                if self._mentions_dependency(lower, tool.name):
                    edges.append(Edge(process.id, tool.id, "depends_on", 0.82, [evidence_id]))

            for team in teams:
                if self._mentions_approval(lower, team.name):
                    edges.append(Edge(team.id, process.id, "approves", 0.84, [evidence_id]))
                    edges.append(Edge(process.id, team.id, "requires_approval", 0.84, [evidence_id]))
                if self._mentions_ownership(lower, team.name):
                    for policy in policies:
                        edges.append(Edge(team.id, policy.id, "owns", 0.80, [evidence_id]))

            for person in people:
                if "escalate" in lower:
                    edges.append(Edge(process.id, person.id, "escalates_to", 0.86, [evidence_id]))
                if self._mentions_blocker(lower, person.name):
                    edges.append(Edge(person.id, process.id, "blocks", 0.72, [evidence_id]))
                    edges.append(Edge(process.id, person.id, "blocked_by", 0.72, [evidence_id]))

            for decision in decisions:
                edges.append(Edge(process.id, decision.id, "has_decision", 0.78, [evidence_id]))

        for policy in policies:
            for team in teams:
                if self._mentions_approval(lower, team.name):
                    edges.append(Edge(team.id, policy.id, "approves", 0.80, [evidence_id]))
                if self._mentions_ownership(lower, team.name):
                    edges.append(Edge(team.id, policy.id, "owns", 0.80, [evidence_id]))

        edges.extend(self._explicit_dependency_edges(lower, entities, evidence_id))
        return edges

    @staticmethod
    def _mentions_tool_use(text: str, name: str) -> bool:
        tool = re.escape(name.lower())
        return bool(re.search(rf"\b(use|uses|used|handled in|logged in|workflow in)\b.*\b{tool}\b", text))

    @staticmethod
    def _mentions_dependency(text: str, name: str) -> bool:
        token = re.escape(name.lower())
        return bool(re.search(rf"\b(depends on|requires|needs)\b.*\b{token}\b", text))

    @staticmethod
    def _mentions_approval(text: str, name: str) -> bool:
        normalized = name.lower().replace(" team", "")
        return normalized in text and any(token in text for token in ("approve", "approval", "requires"))

    @staticmethod
    def _mentions_ownership(text: str, name: str) -> bool:
        normalized = name.lower().replace(" team", "")
        return normalized in text and any(token in text for token in ("owns", "owned by", "owner"))

    @staticmethod
    def _mentions_blocker(text: str, name: str) -> bool:
        return name.lower() in text and any(token in text for token in ("blocked by", "blocks", "waiting on"))

    @staticmethod
    def _explicit_dependency_edges(text: str, entities: list[Entity], evidence_id: str) -> list[Edge]:
        edges: list[Edge] = []
        entity_by_name = {entity.name.lower(): entity for entity in entities}
        for match in re.finditer(r"([a-z][a-z\s]{2,40})\s+depends on\s+([a-z][a-z\s]{2,40})", text):
            left_name = " ".join(match.group(1).split()).strip()
            right_name = " ".join(match.group(2).split()).strip()
            left = entity_by_name.get(left_name)
            right = entity_by_name.get(right_name)
            if left and right:
                edges.append(Edge(left.id, right.id, "depends_on", 0.76, [evidence_id]))
        return edges


def relation_target_id(entity_type: EntityType, name: str) -> str:
    return entity_id(entity_type, name)
