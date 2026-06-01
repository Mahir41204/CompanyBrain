from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph

from .dependency_analyzer import DependencyAnalyzer


class OrganizationalSimulator:
    def __init__(self, graph: BrainGraph) -> None:
        self.graph = graph
        self.dependencies = DependencyAnalyzer(graph)

    def simulate_removal(self, query: str) -> dict[str, Any]:
        matches = self.graph.search(query, limit=1)
        if not matches:
            return {
                "query": query,
                "removed_entity": None,
                "risk": "unknown",
                "affected_processes": [],
                "affected_teams": [],
                "affected_tools": [],
                "replacement_needed": False,
                "recommendations": ["Add the entity to the memory graph before simulating impact."],
            }

        removed = matches[0]
        neighbors = self.graph.neighbors(removed.id)
        propagation = self.dependencies.affected_by_removal(query, max_depth=4)
        affected = propagation.get("affected", [])
        affected_processes = self._entities_by_type(affected, "process")
        affected_teams = self._entities_by_type(affected, "team")
        affected_tools = self._entities_by_type(affected, "tool")
        affected_policies = self._entities_by_type(affected, "policy")
        affected_skills = self._entities_by_type(affected, "skill")
        affected_customers = self._entities_by_type(affected, "customer")
        recommendations = []

        for row in neighbors:
            entity = row["entity"]
            relation = row["relation"]
            entity_type = entity["type"]
            if entity_type == "process":
                affected_processes.append(entity)
            elif entity_type == "team":
                affected_teams.append(entity)
            elif entity_type == "tool":
                affected_tools.append(entity)

            if removed.type.value == "person" and relation in {"owns", "escalates_to"}:
                recommendations.append("Assign a backup owner and update escalation paths.")
            if removed.type.value == "tool" and relation == "uses":
                recommendations.append("Pick a replacement tool and update process runbooks.")
            if removed.type.value == "team" and relation in {"owns", "requires_approval"}:
                recommendations.append("Move approval authority to another accountable team.")

        affected_processes = self._dedupe_entities(affected_processes, exclude={removed.id})
        affected_teams = self._dedupe_entities(affected_teams, exclude={removed.id})
        affected_tools = self._dedupe_entities(affected_tools, exclude={removed.id})
        affected_policies = self._dedupe_entities(affected_policies, exclude={removed.id})
        affected_skills = self._dedupe_entities(affected_skills, exclude={removed.id})
        affected_customers = self._dedupe_entities(affected_customers, exclude={removed.id})

        if not recommendations:
            recommendations.append("Review direct graph neighbors and confirm no operational dependency is missing.")

        impact_count = len(affected) + len(neighbors)
        risk = "critical" if impact_count >= 8 else "high" if impact_count >= 4 else "medium" if impact_count >= 2 else "low"

        return {
            "query": query,
            "removed_entity": removed.to_dict(),
            "risk": risk,
            "affected_processes": affected_processes,
            "affected_teams": affected_teams,
            "affected_tools": affected_tools,
            "affected_policies": affected_policies,
            "affected_skills": affected_skills,
            "affected_customers": affected_customers,
            "propagation": propagation,
            "blast_radius": {
                "direct_neighbors": len(neighbors),
                "transitive_affected": len(affected),
                "max_depth": max([path["depth"] for path in propagation.get("paths", [])], default=0),
            },
            "replacement_needed": bool(neighbors),
            "recommendations": sorted(set(recommendations)),
        }

    @staticmethod
    def _entities_by_type(rows: list[dict[str, Any]], entity_type: str) -> list[dict[str, Any]]:
        entities = []
        seen = set()
        for row in rows:
            entity = row["entity"]
            if entity["type"] != entity_type or entity["id"] in seen:
                continue
            seen.add(entity["id"])
            entities.append(entity)
        return entities

    @staticmethod
    def _dedupe_entities(
        entities: list[dict[str, Any]],
        exclude: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        exclude = exclude or set()
        rows = []
        seen = set()
        for entity in entities:
            if entity["id"] in exclude or entity["id"] in seen:
                continue
            seen.add(entity["id"])
            rows.append(entity)
        return rows
