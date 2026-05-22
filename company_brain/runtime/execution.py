from __future__ import annotations

import hashlib
from typing import Any

from company_brain.core.graph import BrainGraph
from company_brain.decision_engine import DecisionEngine
from company_brain.execution.planner import ExecutionPlanner
from company_brain.learning import LearningService
from company_brain.repository import SkillRepository

from .agents import AgentTask


class AgentRuntime:
    def __init__(
        self,
        graph: BrainGraph,
        repository: SkillRepository,
        decision_engine: DecisionEngine,
        learning_service: LearningService,
    ) -> None:
        self.graph = graph
        self.repository = repository
        self.decision_engine = decision_engine
        self.learning_service = learning_service

    def run(self, goal: str, context: dict[str, Any] | None = None, execute: bool = True) -> AgentTask:
        context = context or {}
        task = AgentTask(id=self._task_id(goal, context), goal=goal, context=context)
        plan_result = ExecutionPlanner(self.graph).build_plan(goal)
        task.plan = plan_result["steps"]
        task.status = "planned"

        if not execute:
            return task

        task.results = [self._execute_step(step, context) for step in task.plan]
        task.status = "completed" if all(row["status"] != "failed" for row in task.results) else "needs_review"
        return task

    def learn(self, task: AgentTask, outcome: str, notes: str | None = None) -> dict[str, Any]:
        feedback = []
        for result in task.results:
            if result.get("type") != "skill_execution":
                continue
            feedback.append(
                self.learning_service.submit_outcome(
                    {
                        "skill_id": result["skill_id"],
                        "execution_id": result.get("execution_id"),
                        "outcome": outcome,
                        "notes": notes,
                    }
                )["feedback"]
            )
        return {"task_id": task.id, "feedback": feedback}

    def _execute_step(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        action = step.get("action")
        target = step.get("target")

        if action == "execute_skill" and target:
            skill_id = str(target)
            try:
                skill = self.repository.get_skill(skill_id)
                decision = self.decision_engine.execute(skill, context)
                execution = self.learning_service.record_execution(skill_id, context, decision)
                return {
                    "type": "skill_execution",
                    "status": "completed",
                    "skill_id": skill_id,
                    "decision": decision,
                    "execution_id": execution["execution_id"],
                }
            except KeyError:
                return {
                    "type": "skill_execution",
                    "status": "failed",
                    "skill_id": skill_id,
                    "error": f"Unknown skill: {skill_id}",
                }

        return {
            "type": "operational_step",
            "status": "planned",
            "action": action,
            "target": target,
            "rationale": step.get("rationale", ""),
        }

    @staticmethod
    def _task_id(goal: str, context: dict[str, Any]) -> str:
        digest = hashlib.sha1(f"{goal}:{context}".encode("utf-8")).hexdigest()[:14]
        return f"task_{digest}"
