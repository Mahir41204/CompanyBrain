from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph

from .people_explorer import PeopleExplorerService
from .simulation import SimulationService


class PeopleRiskService:
    """Buyer-facing departure-risk packaging for the product dashboard."""

    def __init__(self, graph: BrainGraph) -> None:
        self.graph = graph
        self.people = PeopleExplorerService(graph)
        self.simulation = SimulationService(graph)

    def build(self, target: str | None = None) -> dict[str, Any]:
        people_data = self.people.build()
        people = [row for row in people_data["people_and_teams"] if row["type"] == "person"]
        teams = [row for row in people_data["people_and_teams"] if row["type"] == "team"]
        ranked = people or teams
        selected = self._match(ranked, target) or (ranked[0] if ranked else None)
        target_name = selected["name"] if selected else str(target or "Sarah Kim")
        simulation = self.simulation.run(
            {
                "type": "person_departure",
                "target": target_name,
                "mitigations": [],
                "compare_to": {
                    "type": "person_departure",
                    "target": target_name,
                    "mitigations": ["assign backup owner", "document process"],
                },
            }
        )

        return {
            "positioning": {
                "category": "People Risk Intelligence",
                "buyer_question": f"What breaks if {target_name} leaves?",
                "primary_buyer": "COO / Head of Operations",
                "why_now": "Key-person transitions create immediate operational risk, budget urgency, and a clear owner.",
            },
            "summary": self._summary(people, teams),
            "top_people": [self._compact_person(row) for row in ranked[:8]],
            "selected_person": self._selected_person(selected, simulation),
            "departure_simulation": self._simulation_summary(simulation),
            "control_plan": self._control_plan(selected, simulation),
            "proof_points": self._proof_points(selected),
        }

    def _summary(self, people: list[dict[str, Any]], teams: list[dict[str, Any]]) -> dict[str, Any]:
        high_risk = [row for row in people if row["tribal_knowledge_score"] >= 75]
        mapped_backups = sum(1 for row in people if self._backup_edges(row["id"]))
        return {
            "people_mapped": len(people),
            "teams_mapped": len(teams),
            "high_risk_people": len(high_risk),
            "backup_candidates_mapped": mapped_backups,
            "average_people_confidence": self._avg(row["confidence"] for row in people),
        }

    def _selected_person(self, selected: dict[str, Any] | None, simulation: dict[str, Any]) -> dict[str, Any] | None:
        if not selected:
            return None
        raw = simulation["result"]["raw"]
        profile = {
            "id": selected["id"],
            "name": selected["name"],
            "role": selected.get("attributes", {}).get("role", selected["type"]),
            "risk_label": selected["risk_label"],
            "tribal_knowledge_score": selected["tribal_knowledge_score"],
            "confidence": selected["confidence"],
            "owns": selected["owns"],
            "approvals": selected["approvals"],
            "escalations": selected["escalations"],
            "supported": selected["supported"],
            "evidence_count": len(selected["evidence"]),
            "backup_status": self._backup_status(selected["id"]),
        }
        profile["controlled_processes"] = self._dedupe(
            [
                *[row for row in profile["owns"] if row["type"] == "process"],
                *[row for row in profile["escalations"] if row["type"] == "process"],
                *raw.get("affected_processes", []),
            ]
        )
        profile["controlled_tools"] = self._dedupe(
            [
                *[row for row in profile["owns"] if row["type"] == "tool"],
                *raw.get("affected_tools", []),
            ]
        )
        return profile

    def _simulation_summary(self, simulation: dict[str, Any]) -> dict[str, Any]:
        result = simulation["result"]
        raw = result["raw"]
        comparison = simulation.get("comparison")
        return {
            "risk": raw.get("risk", "unknown"),
            "resilience": result["resilience"],
            "mitigated_resilience": comparison["resilience"] if comparison else None,
            "monthly_cost": result["impact_cost_breakdown"],
            "confidence": result["confidence"],
            "blast_radius": raw.get("blast_radius", {}),
            "affected": {
                "processes": raw.get("affected_processes", []),
                "teams": raw.get("affected_teams", []),
                "tools": raw.get("affected_tools", []),
                "policies": raw.get("affected_policies", []),
                "customers": raw.get("affected_customers", []),
            },
            "failure_paths": self._failure_paths(raw),
            "recommendations": result["recommendations"],
        }

    def _control_plan(
        self,
        selected: dict[str, Any] | None,
        simulation: dict[str, Any],
    ) -> list[dict[str, str]]:
        target = selected["name"] if selected else simulation["scenario"]["target"]
        affected = simulation["result"]["raw"].get("affected_processes", [])
        first_process = affected[0]["name"] if affected else "highest-risk workflow"
        return [
            {
                "priority": "critical",
                "action": "Assign backup owner",
                "target": target,
                "reason": "Remove the single-person approval and escalation dependency.",
            },
            {
                "priority": "high",
                "action": "Transfer runbook knowledge",
                "target": first_process,
                "reason": "Move tacit handoffs into source-backed process evidence.",
            },
            {
                "priority": "high",
                "action": "Verify approval authority",
                "target": "Finance / Support",
                "reason": "Confirm who can approve exceptions when the primary owner is absent.",
            },
            {
                "priority": "medium",
                "action": "Re-run simulation",
                "target": "30 days",
                "reason": "Measure whether resilience improved after mitigation.",
            },
        ]

    def _proof_points(self, selected: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not selected:
            return []
        return [
            {
                "source_type": item["source_type"],
                "source_ref": item["source_ref"],
                "text": item["text"],
                "confidence": item["confidence"],
            }
            for item in selected["evidence"][:4]
        ]

    def _compact_person(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "role": row.get("attributes", {}).get("role", row["type"]),
            "risk_label": row["risk_label"],
            "tribal_knowledge_score": row["tribal_knowledge_score"],
            "confidence": row["confidence"],
            "owns_count": len(row["owns"]),
            "approval_count": len(row["approvals"]),
            "escalation_count": len(row["escalations"]),
            "evidence_count": len(row["evidence"]),
            "backup_status": self._backup_status(row["id"]),
        }

    @staticmethod
    def _match(rows: list[dict[str, Any]], target: str | None) -> dict[str, Any] | None:
        if not target:
            return None
        query = target.strip().lower()
        for row in rows:
            if query in {row["id"].lower(), row["name"].lower()} or query in row["name"].lower():
                return row
        return None

    def _backup_status(self, entity_id: str) -> str:
        backups = self._backup_edges(entity_id)
        if not backups:
            return "No backup owner mapped"
        names = []
        for edge in backups:
            backup_id = edge.source_id if edge.target_id == entity_id else edge.target_id
            entity = self.graph.entities.get(backup_id)
            if entity:
                names.append(entity.name)
        if not names:
            return "Backup candidate mapped"
        return f"Backup candidate: {', '.join(sorted(set(names)))}"

    def _backup_edges(self, entity_id: str):
        return [
            edge
            for edge in self.graph.edges.values()
            if edge.relation in {"backs_up", "backup_for"}
            and entity_id in {edge.source_id, edge.target_id}
        ]

    @staticmethod
    def _failure_paths(raw: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for path in raw.get("propagation", {}).get("paths", [])[:6]:
            names = []
            relations = []
            for step in path.get("steps", []):
                names.append(step["entity"]["name"])
                relations.append(step["relation"])
            if names:
                rows.append(
                    {
                        "depth": path.get("depth", len(names)),
                        "nodes": names,
                        "relations": relations,
                    }
                )
        return rows

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped = {}
        for row in rows:
            deduped[row["id"]] = row
        return list(deduped.values())

    @staticmethod
    def _avg(values) -> float:
        rows = [float(value) for value in values]
        return round(sum(rows) / len(rows), 4) if rows else 0.0
