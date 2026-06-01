from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph


class PeopleExplorerService:
    def __init__(self, graph: BrainGraph) -> None:
        self.graph = graph

    def build(self) -> dict[str, Any]:
        rows = []
        for entity in self.graph.entities.values():
            if entity.type.value not in {"person", "team"}:
                continue
            rows.append(self._person_or_team(entity.id))
        rows.sort(key=lambda row: row["tribal_knowledge_score"], reverse=True)
        return {
            "people_and_teams": rows,
            "summary": {
                "people": len([row for row in rows if row["type"] == "person"]),
                "teams": len([row for row in rows if row["type"] == "team"]),
                "top_concentration": rows[0] if rows else None,
            },
        }

    def _person_or_team(self, entity_id: str) -> dict[str, Any]:
        entity = self.graph.entities[entity_id]
        owns = []
        approvals = []
        escalations = []
        supported = []
        evidence_ids = set(entity.sources)
        for row in self.graph.neighbors(entity_id):
            related = row["entity"]
            relation = row["relation"]
            evidence_ids.update(item["id"] for item in row.get("evidence", []))
            if relation == "owns":
                owns.append(related)
            elif relation in {"requires_approval", "approves"}:
                approvals.append(related)
            elif relation == "escalates_to":
                escalations.append(related)
            else:
                supported.append(related)
        degree = len(owns) + len(approvals) + len(escalations) + len(supported)
        score = min(100, round(25 + degree * 11 + len(evidence_ids) * 5 + entity.confidence * 15))
        return {
            **entity.to_dict(),
            "owns": self._dedupe(owns),
            "approvals": self._dedupe(approvals),
            "escalations": self._dedupe(escalations),
            "supported": self._dedupe(supported),
            "evidence": [
                self.graph.evidence[evidence_id].to_dict()
                for evidence_id in sorted(evidence_ids)
                if evidence_id in self.graph.evidence
            ],
            "tribal_knowledge_score": score,
            "risk_label": "high" if score >= 75 else "medium" if score >= 50 else "low",
        }

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped = {}
        for row in rows:
            deduped[row["id"]] = row
        return list(deduped.values())
