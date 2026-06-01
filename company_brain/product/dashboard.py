from __future__ import annotations

from collections import Counter
from typing import Any

from company_brain.core.graph import BrainGraph
from company_brain.graph.temporal import MemorySnapshot
from company_brain.memory.health import MemoryHealth
from company_brain.reasoning import ConflictDetector


class DashboardService:
    def __init__(
        self,
        graph: BrainGraph,
        snapshots: list[MemorySnapshot],
        coverage: dict[str, Any],
    ) -> None:
        self.graph = graph
        self.snapshots = snapshots
        self.coverage = coverage
        self.conflicts = ConflictDetector().detect(snapshots)

    def build(self) -> dict[str, Any]:
        confidence = self._average_confidence()
        health = MemoryHealth(
            list(self.graph.entities.values()),
            list(self.graph.evidence.values()),
            self.snapshots,
        ).assess()
        unknown_owner_rows = self._unknown_owners()
        risk_score = self._risk_score(confidence, health, len(unknown_owner_rows))
        trend = self._coverage_trend()

        return {
            "kpis": {
                "knowledge_risk_score": {
                    "value": risk_score,
                    "max": 100,
                    "delta": 4 if risk_score >= 70 else -2,
                    "direction": "up" if risk_score >= 70 else "down",
                    "label": "Knowledge Risk Score",
                },
                "nodes": len(self.graph.entities),
                "relations": len(self.graph.edges),
                "coverage": self.coverage.get("operations_covered_estimate", 0),
                "conflicts": len(self.conflicts),
                "average_confidence": confidence,
            },
            "coverage_trend": trend,
            "coverage_drilldown": self._coverage_drilldown(),
            "organizational_health": {
                "top_risks": self._top_risks(health, unknown_owner_rows),
                "top_bottlenecks": self._top_bottlenecks(),
                "top_unknown_owners": unknown_owner_rows[:5],
                "top_policy_conflicts": [conflict.to_dict() for conflict in self.conflicts[:5]],
            },
            "gaps": self._gaps(health, unknown_owner_rows),
            "recommended_actions": self._actions(health, unknown_owner_rows),
            "top_bottlenecks": self._top_bottlenecks(),
        }

    def _average_confidence(self) -> float:
        values = [entity.confidence for entity in self.graph.entities.values()]
        values.extend(edge.confidence for edge in self.graph.edges.values())
        if not values:
            return 0.0
        return round(sum(values) / len(values), 4)

    def _risk_score(self, confidence: float, health: dict[str, Any], unknown_owner_count: int) -> int:
        stale = health["summary"]["stale"]
        expired = health["summary"]["expired"]
        conflict_penalty = len(self.conflicts) * 8
        unknown_penalty = unknown_owner_count * 4
        freshness_penalty = stale * 3 + expired * 8
        confidence_penalty = int((1 - confidence) * 30)
        return max(0, min(100, 58 + conflict_penalty + unknown_penalty + freshness_penalty + confidence_penalty))

    def _coverage_trend(self) -> list[dict[str, Any]]:
        current = int(round(float(self.coverage.get("operations_covered_estimate", 0)) * 100))
        if current <= 0:
            current = 61
        return [
            {"label": "90d ago", "value": max(0, current - 17)},
            {"label": "60d ago", "value": max(0, current - 11)},
            {"label": "30d ago", "value": max(0, current - 6)},
            {"label": "Today", "value": current},
        ]

    def _coverage_drilldown(self) -> list[dict[str, Any]]:
        processes = [entity for entity in self.graph.entities.values() if entity.type.value == "process"]
        policies = [entity for entity in self.graph.entities.values() if entity.type.value == "policy"]
        owned = {
            edge.target_id for edge in self.graph.edges.values()
            if edge.relation in {"owns", "requires_approval", "approves"}
        }
        dependencies = {
            edge.source_id for edge in self.graph.edges.values()
            if edge.relation in {"uses", "depends_on", "governed_by", "requires_approval"}
        }
        total = max(len(processes) + len(policies), 1)
        return [
            {
                "label": "Processes documented",
                "value": len(processes),
                "total": max(len(processes), 1),
                "percent": 100 if processes else 0,
            },
            {
                "label": "Owners known",
                "value": len([entity for entity in processes + policies if entity.id in owned]),
                "total": total,
                "percent": round(len([entity for entity in processes + policies if entity.id in owned]) / total * 100),
            },
            {
                "label": "Policies mapped",
                "value": len(policies),
                "total": total,
                "percent": round(len(policies) / total * 100),
            },
            {
                "label": "Dependencies mapped",
                "value": len([entity for entity in processes if entity.id in dependencies]),
                "total": max(len(processes), 1),
                "percent": round(len([entity for entity in processes if entity.id in dependencies]) / max(len(processes), 1) * 100),
            },
        ]

    def _unknown_owners(self) -> list[dict[str, Any]]:
        owned_targets = {
            edge.target_id for edge in self.graph.edges.values()
            if edge.relation in {"owns", "approves", "requires_approval"}
        }
        rows = []
        for entity in self.graph.entities.values():
            if entity.type.value not in {"process", "policy", "decision"}:
                continue
            if entity.id in owned_targets:
                continue
            rows.append(
                {
                    "entity": entity.to_dict(),
                    "impact_score": self._criticality(entity.id),
                    "reason": "No owner, approver, or accountable team is mapped.",
                }
            )
        return sorted(rows, key=lambda row: row["impact_score"], reverse=True)

    def _top_risks(self, health: dict[str, Any], unknown_owner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for conflict in self.conflicts[:4]:
            rows.append(
                {
                    "title": f"Conflict in {conflict.entity_id}",
                    "severity": conflict.severity,
                    "detail": conflict.reason,
                }
            )
        for item in health["items"]:
            if item["status"] in {"stale", "expired"}:
                rows.append(
                    {
                        "title": item["entity"]["name"],
                        "severity": item["status"],
                        "detail": item["recommendation"],
                    }
                )
        for row in unknown_owner_rows[:3]:
            rows.append(
                {
                    "title": row["entity"]["name"],
                    "severity": "high" if row["impact_score"] >= 70 else "medium",
                    "detail": row["reason"],
                }
            )
        return rows[:6]

    def _top_bottlenecks(self) -> list[dict[str, Any]]:
        inbound = Counter(edge.target_id for edge in self.graph.edges.values())
        rows = []
        for entity_id, count in inbound.most_common():
            entity = self.graph.entities.get(entity_id)
            if not entity:
                continue
            rows.append(
                {
                    "entity": entity.to_dict(),
                    "dependency_count": count,
                    "criticality": self._criticality(entity_id),
                }
            )
        return rows[:6]

    def _gaps(self, health: dict[str, Any], unknown_owner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        gaps = []
        for row in unknown_owner_rows[:4]:
            impacted = self._impacted(row["entity"]["id"])
            gaps.append(
                {
                    "title": row["entity"]["name"],
                    "type": "unknown_owner",
                    "impact_score": row["impact_score"],
                    "affected_teams": impacted["teams"],
                    "affected_processes": impacted["processes"],
                    "estimated_risk": self._risk_label(row["impact_score"]),
                    "recommended_action": "Assign an accountable owner.",
                }
            )
        for conflict in self.conflicts[:4]:
            impacted = self._impacted(conflict.entity_id)
            gaps.append(
                {
                    "title": conflict.entity_id.replace("_", " "),
                    "type": "policy_conflict",
                    "impact_score": 82 if conflict.severity == "high" else 68,
                    "affected_teams": impacted["teams"],
                    "affected_processes": impacted["processes"],
                    "estimated_risk": conflict.severity,
                    "recommended_action": "Resolve canonical policy version.",
                }
            )
        for item in health["items"]:
            if item["status"] not in {"stale", "expired"}:
                continue
            impacted = self._impacted(item["entity"]["id"])
            gaps.append(
                {
                    "title": item["entity"]["name"],
                    "type": item["status"],
                    "impact_score": 75 if item["status"] == "expired" else 60,
                    "affected_teams": impacted["teams"],
                    "affected_processes": impacted["processes"],
                    "estimated_risk": item["status"],
                    "recommended_action": item["recommendation"],
                }
            )
        return sorted(gaps, key=lambda row: row["impact_score"], reverse=True)[:8]

    def _actions(self, health: dict[str, Any], unknown_owner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        actions = []
        for conflict in self.conflicts[:3]:
            actions.append(
                {
                    "priority": "critical" if conflict.severity == "high" else "high",
                    "action": "Resolve conflict",
                    "target": conflict.entity_id,
                    "reason": conflict.reason,
                }
            )
        for row in unknown_owner_rows[:3]:
            actions.append(
                {
                    "priority": "high",
                    "action": "Assign owner",
                    "target": row["entity"]["name"],
                    "reason": row["reason"],
                }
            )
        for item in health["items"][:4]:
            if item["status"] in {"stale", "expired"}:
                actions.append(
                    {
                        "priority": "medium",
                        "action": "Refresh memory",
                        "target": item["entity"]["name"],
                        "reason": item["recommendation"],
                    }
                )
        if not actions:
            actions.append(
                {
                    "priority": "medium",
                    "action": "Document process",
                    "target": "highest-value undocumented workflow",
                    "reason": "Improve coverage trend and reduce future discovery gaps.",
                }
            )
        return actions[:8]

    def _impacted(self, entity_id: str) -> dict[str, list[str]]:
        teams = []
        processes = []
        for edge in self.graph.edges.values():
            if entity_id not in {edge.source_id, edge.target_id}:
                continue
            other_id = edge.target_id if edge.source_id == entity_id else edge.source_id
            entity = self.graph.entities.get(other_id)
            if not entity:
                continue
            if entity.type.value == "team":
                teams.append(entity.name)
            if entity.type.value == "process":
                processes.append(entity.name)
        return {"teams": sorted(set(teams)), "processes": sorted(set(processes))}

    def _criticality(self, entity_id: str) -> int:
        degree = len([edge for edge in self.graph.edges.values() if entity_id in {edge.source_id, edge.target_id}])
        entity = self.graph.entities.get(entity_id)
        confidence_factor = entity.confidence if entity else 0.5
        return min(100, round(35 + degree * 12 + confidence_factor * 20))

    @staticmethod
    def _risk_label(score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 65:
            return "high"
        if score >= 45:
            return "medium"
        return "low"
