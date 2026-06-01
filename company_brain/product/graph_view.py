from __future__ import annotations

import math
from typing import Any

from company_brain.core.graph import BrainGraph
from company_brain.graph.temporal import MemorySnapshot
from company_brain.reasoning import ConflictDetector
from company_brain.reasoning.relation_strength import relation_strength


class GraphViewService:
    def __init__(self, graph: BrainGraph, snapshots: list[MemorySnapshot]) -> None:
        self.graph = graph
        self.snapshots = snapshots
        self.conflict_entity_ids = {conflict.entity_id for conflict in ConflictDetector().detect(snapshots)}

    def build(self) -> dict[str, Any]:
        entities = list(self.graph.entities.values())
        positions = self._positions(len(entities))
        nodes = []
        for index, entity in enumerate(entities):
            degree = len([edge for edge in self.graph.edges.values() if entity.id in {edge.source_id, edge.target_id}])
            criticality = self._criticality(degree, entity.confidence, entity.id in self.conflict_entity_ids)
            nodes.append(
                {
                    **entity.to_dict(),
                    "x": positions[index]["x"],
                    "y": positions[index]["y"],
                    "degree": degree,
                    "criticality": criticality,
                    "criticality_label": self._criticality_label(criticality),
                    "has_conflict": entity.id in self.conflict_entity_ids,
                    "evidence": self._evidence(entity.sources),
                }
            )

        edges = [
            {
                **edge.to_dict(),
                "strength": relation_strength(edge),
                "source": self.graph.entities.get(edge.source_id).to_dict() if edge.source_id in self.graph.entities else None,
                "target": self.graph.entities.get(edge.target_id).to_dict() if edge.target_id in self.graph.entities else None,
                "evidence": self._evidence(edge.evidence),
            }
            for edge in self.graph.edges.values()
        ]
        return {
            "nodes": nodes,
            "edges": edges,
            "filters": ["person", "team", "process", "policy", "tool", "customer", "decision", "skill", "conflict", "high-risk"],
            "timeline": self._timeline(),
        }

    @staticmethod
    def _positions(count: int) -> list[dict[str, float]]:
        if count == 0:
            return []
        center_x = 480
        center_y = 280
        rings = [120, 210, 290]
        rows = []
        for index in range(count):
            ring = rings[min(index // 8, len(rings) - 1)]
            angle = (index % 8) / 8 * math.tau + (index // 8) * 0.25
            rows.append({"x": round(center_x + math.cos(angle) * ring, 2), "y": round(center_y + math.sin(angle) * ring, 2)})
        return rows

    @staticmethod
    def _criticality(degree: int, confidence: float, has_conflict: bool) -> int:
        return min(100, round(20 + degree * 10 + confidence * 25 + (20 if has_conflict else 0)))

    @staticmethod
    def _criticality_label(score: int) -> str:
        if score >= 75:
            return "high"
        if score >= 50:
            return "medium"
        return "low"

    def _evidence(self, evidence_ids: list[str]) -> list[dict[str, Any]]:
        return [
            self.graph.evidence[evidence_id].to_dict()
            for evidence_id in evidence_ids
            if evidence_id in self.graph.evidence
        ]

    def _timeline(self) -> list[dict[str, Any]]:
        dates = sorted({snapshot.valid_from for snapshot in self.snapshots if snapshot.valid_from})
        labels = ["90 days ago", "30 days ago", "Today"]
        if not dates:
            return [{"label": label, "snapshot_count": 0} for label in labels]
        return [
            {"label": "90 days ago", "snapshot_count": max(1, len(dates) - 2), "date": dates[0]},
            {"label": "30 days ago", "snapshot_count": max(1, len(dates) - 1), "date": dates[max(0, len(dates) - 2)]},
            {"label": "Today", "snapshot_count": len(dates), "date": dates[-1]},
        ]
