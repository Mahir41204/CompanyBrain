from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph


class EvidenceExplorerService:
    def __init__(self, graph: BrainGraph, llm_results: list[dict[str, Any]]) -> None:
        self.graph = graph
        self.llm_results = llm_results

    def build(self, query: str | None = None) -> dict[str, Any]:
        evidence_rows = []
        for evidence in self.graph.evidence.values():
            if query and query.lower() not in " ".join([evidence.text, evidence.source_ref, evidence.source_type]).lower():
                continue
            evidence_rows.append(
                {
                    **evidence.to_dict(),
                    "entities": [
                        entity.to_dict()
                        for entity in self.graph.entities.values()
                        if evidence.id in entity.sources
                    ],
                    "relationships": [
                        edge.to_dict()
                        for edge in self.graph.edges.values()
                        if evidence.id in edge.evidence
                    ],
                    "insights": self._insights(evidence.id),
                }
            )
        evidence_rows.sort(key=lambda row: row["timestamp"], reverse=True)
        return {
            "evidence": evidence_rows,
            "summary": {
                "count": len(evidence_rows),
                "sources": self._source_counts(evidence_rows),
                "average_confidence": self._average_confidence(evidence_rows),
            },
        }

    def _insights(self, evidence_id: str) -> list[dict[str, Any]]:
        insights = []
        for row in self.llm_results:
            if row.get("evidence_id") != evidence_id:
                continue
            insights.extend({"insight_type": "entity", **item} for item in row.get("entities", []))
            insights.extend({"insight_type": "relationship", **item} for item in row.get("relationships", []))
            insights.extend({"insight_type": "process", **item} for item in row.get("processes", []))
            insights.extend({"insight_type": "policy", **item} for item in row.get("policies", []))
        return insights

    @staticmethod
    def _source_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["source_type"]] = counts.get(row["source_type"], 0) + 1
        return counts

    @staticmethod
    def _average_confidence(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        return round(sum(float(row.get("confidence", 0.5)) for row in rows) / len(rows), 4)
