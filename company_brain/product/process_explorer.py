from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph
from company_brain.discovery import Discovery


class ProcessExplorerService:
    def __init__(self, graph: BrainGraph, discoveries: list[Discovery], llm_results: list[dict[str, Any]]) -> None:
        self.graph = graph
        self.discoveries = discoveries
        self.llm_results = llm_results

    def build(self) -> dict[str, Any]:
        processes = []
        for entity in self.graph.entities.values():
            if entity.type.value != "process":
                continue
            processes.append(self._process(entity.id))
        processes.sort(key=lambda row: (row["risk_score"], row["confidence"]), reverse=True)
        return {
            "processes": processes,
            "summary": {
                "count": len(processes),
                "with_owner": len([row for row in processes if row["owner"]]),
                "with_steps": len([row for row in processes if row["steps"]]),
                "with_evidence": len([row for row in processes if row["evidence"]]),
            },
        }

    def _process(self, process_id: str) -> dict[str, Any]:
        entity = self.graph.entities[process_id]
        neighbors = self.graph.neighbors(process_id)
        owner = None
        tools = []
        policies = []
        dependencies = []
        exceptions = []
        edge_evidence = []
        for row in neighbors:
            relation = row["relation"]
            related = row["entity"]
            edge_evidence.extend(item["id"] for item in row.get("evidence", []))
            if relation == "owns" and row["direction"] == "in":
                owner = related
            elif relation in {"requires_approval", "approves"} and related["type"] in {"team", "person"}:
                owner = owner or related
            elif relation == "uses" and related["type"] == "tool":
                tools.append(related)
            elif relation in {"depends_on", "supports", "blocks"}:
                dependencies.append(related)
            elif relation in {"governed_by", "governs"} and related["type"] == "policy":
                policies.append(related)
            elif relation == "has_exception":
                exceptions.append(related)

        steps = list(entity.attributes.get("steps", []))
        if not steps:
            steps = self._steps_from_discoveries(entity.name)
        evidence_ids = sorted(set(entity.sources + edge_evidence))
        evidence = [self.graph.evidence[evidence_id].to_dict() for evidence_id in evidence_ids if evidence_id in self.graph.evidence]
        risk_score = self._risk_score(entity.confidence, owner, dependencies, exceptions, evidence)
        return {
            **entity.to_dict(),
            "owner": owner,
            "steps": steps,
            "tools": self._dedupe(tools),
            "policies": self._dedupe(policies),
            "dependencies": self._dedupe(dependencies),
            "exceptions": self._dedupe(exceptions),
            "evidence": evidence,
            "risk_score": risk_score,
        }

    def _steps_from_discoveries(self, process_name: str) -> list[str]:
        normalized = process_name.lower().replace(" process", "")
        for discovery in self.discoveries:
            if discovery.process.lower() in normalized or normalized in discovery.process.lower():
                return discovery.steps
        for row in self.llm_results:
            for process in row.get("processes", []):
                if str(process.get("name", "")).lower() == process_name.lower():
                    return list(process.get("steps", []))
        return []

    @staticmethod
    def _risk_score(
        confidence: float,
        owner: dict[str, Any] | None,
        dependencies: list[dict[str, Any]],
        exceptions: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> int:
        score = 30
        if not owner:
            score += 24
        if not evidence:
            score += 18
        score += min(22, len(dependencies) * 7)
        score += min(16, len(exceptions) * 5)
        score += round((1 - confidence) * 20)
        return max(0, min(100, score))

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped = {}
        for row in rows:
            deduped[row["id"]] = row
        return list(deduped.values())
