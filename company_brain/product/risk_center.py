from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph
from company_brain.graph.temporal import MemorySnapshot

from .dashboard import DashboardService


class RiskCenterService:
    def __init__(self, graph: BrainGraph, snapshots: list[MemorySnapshot], coverage: dict[str, Any]) -> None:
        self.dashboard = DashboardService(graph, snapshots, coverage)

    def build(self) -> dict[str, Any]:
        data = self.dashboard.build()
        health = data["organizational_health"]
        return {
            "knowledge_risk_score": data["kpis"]["knowledge_risk_score"],
            "gaps": data["gaps"],
            "top_risks": health["top_risks"],
            "top_bottlenecks": health["top_bottlenecks"],
            "top_unknown_owners": health["top_unknown_owners"],
            "top_policy_conflicts": health["top_policy_conflicts"],
            "recommended_actions": data["recommended_actions"],
        }
