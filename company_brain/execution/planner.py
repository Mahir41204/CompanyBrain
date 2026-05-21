from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from company_brain.core.graph import BrainGraph


@dataclass
class PlanStep:
    action: str
    target: str | None = None
    inputs: dict[str, Any] | None = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target": self.target,
            "inputs": self.inputs or {},
            "rationale": self.rationale,
        }


class ExecutionPlanner:
    def __init__(self, graph: BrainGraph) -> None:
        self.graph = graph

    def build_plan(self, query: str) -> dict[str, Any]:
        explanation = self.graph.explain(query)
        root = explanation.get("matched_entity")
        if not root:
            return {"query": query, "steps": [PlanStep("needs_human_review").to_dict()], "explanation": explanation}

        steps: list[PlanStep] = [
            PlanStep("load_context", root["id"], rationale="Start from the matched process, policy, or skill.")
        ]

        relations = explanation.get("relations", {})
        for row in relations.get("uses", []):
            entity = row["entity"]
            steps.append(PlanStep("open_tool", entity["name"], rationale=f"{root['name']} uses {entity['name']}."))

        for row in relations.get("requires_approval", []):
            entity = row["entity"]
            steps.append(
                PlanStep("notify_approver", entity["name"], rationale=f"{entity['name']} is required for approval.")
            )

        for row in relations.get("has_exception", []):
            entity = row["entity"]
            steps.append(
                PlanStep("check_exception", entity["name"], rationale=f"{entity['name']} is a known exception path.")
            )

        for row in relations.get("implements_by", []):
            entity = row["entity"]
            steps.append(PlanStep("execute_skill", entity["name"], rationale=f"{entity['name']} implements this memory."))

        steps.append(PlanStep("attach_evidence", rationale="Attach supporting evidence before acting."))
        steps.append(PlanStep("wait_for_outcome", rationale="Hold state open until the operational result is known."))
        steps.append(PlanStep("record_feedback", rationale="Feed the outcome back into confidence scoring."))

        return {"query": query, "steps": [step.to_dict() for step in steps], "explanation": explanation}
