from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph
from company_brain.reasoning import OrganizationalSimulator


class SimulationService:
    def __init__(self, graph: BrainGraph) -> None:
        self.graph = graph
        self.simulator = OrganizationalSimulator(graph)

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        scenario = self._scenario(payload)
        baseline = self._run_one(scenario)
        comparison_payload = payload.get("compare_to")
        comparison = self._run_one(self._scenario(comparison_payload)) if isinstance(comparison_payload, dict) else None
        return {
            "scenario": scenario,
            "result": baseline,
            "comparison": comparison,
            "library": self.library(),
        }

    def _run_one(self, scenario: dict[str, Any]) -> dict[str, Any]:
        raw = self.simulator.simulate_removal(scenario["target"])
        mitigations = scenario.get("mitigations", [])
        before = self._resilience(raw)
        after = min(100, before + self._mitigation_lift(mitigations))
        affected_process_count = len(raw.get("affected_processes", []))
        monthly_cost = self._monthly_cost(raw, scenario)
        return {
            "raw": raw,
            "resilience": {
                "before": before,
                "after": after,
                "delta": after - before,
            },
            "timeline": self._timeline(raw, scenario),
            "confidence": self._confidence(raw),
            "impact_cost_breakdown": monthly_cost,
            "recommendations": self._recommendations(raw, scenario),
        }

    def library(self) -> list[dict[str, str]]:
        return [
            {"type": "person_departure", "label": "Person leaves", "default_target": "Sarah"},
            {"type": "tool_outage", "label": "Tool outage", "default_target": "Zendesk"},
            {"type": "policy_change", "label": "Policy change", "default_target": "refund policy"},
            {"type": "team_merge", "label": "Team merge", "default_target": "Finance Team"},
            {"type": "budget_reduction", "label": "Budget reduction", "default_target": "Support Team"},
            {"type": "hiring_freeze", "label": "Hiring freeze", "default_target": "Engineering"},
        ]

    @staticmethod
    def _scenario(payload: dict[str, Any] | None) -> dict[str, Any]:
        payload = payload or {}
        return {
            "type": str(payload.get("type", "person_departure")),
            "target": str(payload.get("target", "Sarah")),
            "description": str(payload.get("description", "")),
            "mitigations": list(payload.get("mitigations", [])),
        }

    @staticmethod
    def _resilience(raw: dict[str, Any]) -> int:
        blast = raw.get("blast_radius", {})
        penalty = blast.get("transitive_affected", 0) * 7 + blast.get("direct_neighbors", 0) * 4
        if raw.get("risk") == "critical":
            penalty += 20
        elif raw.get("risk") == "high":
            penalty += 12
        return max(0, min(100, 88 - penalty))

    @staticmethod
    def _mitigation_lift(mitigations: list[str]) -> int:
        lift = 0
        for mitigation in mitigations:
            lower = mitigation.lower()
            if "backup" in lower or "owner" in lower:
                lift += 12
            elif "document" in lower:
                lift += 8
            elif "replace" in lower or "alternate" in lower:
                lift += 10
            else:
                lift += 5
        return min(lift, 35)

    @staticmethod
    def _monthly_cost(raw: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
        processes = len(raw.get("affected_processes", []))
        teams = len(raw.get("affected_teams", []))
        customers = len(raw.get("affected_customers", []))
        ticket_volume = max(20, processes * 35 + teams * 18)
        csat_drop = min(18, 3 + processes * 2 + customers * 3)
        churn_risk = round(ticket_volume * csat_drop * 7.5)
        productivity_loss = round((processes + teams + 1) * 1200)
        return {
            "monthly_estimate": churn_risk + productivity_loss,
            "ticket_volume_basis": ticket_volume,
            "csat_drop_points": csat_drop,
            "historical_churn_component": churn_risk,
            "productivity_loss_component": productivity_loss,
            "explanation": f"Estimated from affected processes, teams, customer exposure, and scenario type {scenario['type']}.",
        }

    @staticmethod
    def _confidence(raw: dict[str, Any]) -> dict[str, Any]:
        paths = raw.get("propagation", {}).get("paths", [])
        confidences = []
        evidence_count = 0
        for path in paths:
            for step in path.get("steps", []):
                confidences.append(float(step.get("confidence", 0.5)))
                evidence_count += len(step.get("evidence", []))
        avg = round(sum(confidences) / len(confidences), 4) if confidences else 0.45
        return {
            "overall": avg,
            "label": "high" if avg >= 0.8 else "medium" if avg >= 0.6 else "low",
            "evidence_used": evidence_count,
            "dependency_strength": round(avg * 100),
            "historical_examples": len(paths),
            "why": "Based on mapped dependency strengths, supporting evidence count, and number of comparable graph paths.",
        }

    @staticmethod
    def _timeline(raw: dict[str, Any], scenario: dict[str, Any]) -> list[dict[str, Any]]:
        risk = raw.get("risk", "medium")
        target = scenario["target"]
        return [
            {"time": "0 hours", "event": f"{scenario['type']} triggered for {target}", "severity": "critical" if risk in {"high", "critical"} else "high"},
            {"time": "48 hours", "event": "Queues and owner handoffs begin to show stress", "severity": "high"},
            {"time": "1 week", "event": "Dependent processes slow down without mitigation", "severity": "medium"},
            {"time": "2 weeks", "event": "Customer/team impact becomes measurable", "severity": "medium"},
            {"time": "1 month", "event": "Revenue and productivity risk stabilizes or compounds", "severity": risk},
        ]

    @staticmethod
    def _recommendations(raw: dict[str, Any], scenario: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        recommendations = {"critical": [], "high": [], "medium": [], "low": []}
        target = scenario["target"]
        if raw.get("replacement_needed"):
            recommendations["critical"].append(
                {"action": "Assign backup owner", "target": target, "reason": "Primary dependency has no guaranteed fallback."}
            )
        for rec in raw.get("recommendations", []):
            recommendations["high"].append({"action": rec, "target": target, "reason": "Reduces direct blast radius."})
        recommendations["medium"].append(
            {"action": "Document dependent workflow", "target": target, "reason": "Improves future simulation confidence."}
        )
        recommendations["low"].append(
            {"action": "Review after 30 days", "target": target, "reason": "Validate whether mitigation reduced incidents."}
        )
        return recommendations
