from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph


class OrganizationalSimulator:
    def __init__(self, graph: BrainGraph) -> None:
        self.graph = graph

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
        affected_processes = []
        affected_teams = []
        affected_tools = []
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

        if not recommendations:
            recommendations.append("Review direct graph neighbors and confirm no operational dependency is missing.")

        impact_count = len(affected_processes) + len(affected_teams) + len(affected_tools) + len(neighbors)
        risk = "high" if impact_count >= 4 else "medium" if impact_count >= 2 else "low"

        return {
            "query": query,
            "removed_entity": removed.to_dict(),
            "risk": risk,
            "affected_processes": affected_processes,
            "affected_teams": affected_teams,
            "affected_tools": affected_tools,
            "replacement_needed": bool(neighbors),
            "recommendations": sorted(set(recommendations)),
        }
