from __future__ import annotations

from typing import Any
from uuid import uuid4

from .models import clamp, utc_now
from .repository import SkillRepository


class LearningService:
    def __init__(self, repository: SkillRepository) -> None:
        self.repository = repository

    def record_execution(
        self,
        skill_id: str,
        context: dict[str, Any],
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        execution = {
            "execution_id": f"exec_{uuid4().hex[:16]}",
            "skill_id": skill_id,
            "created_at": utc_now(),
            "context": context,
            "decision": decision,
        }
        self.repository.append_execution(execution)
        return execution

    def submit_outcome(self, payload: dict[str, Any]) -> dict[str, Any]:
        skill_id = payload.get("skill_id")
        if not skill_id:
            raise ValueError("skill_id is required")

        outcome = str(payload.get("outcome", "neutral")).strip().lower()
        skill = self.repository.get_skill(skill_id)
        old_confidence = float(skill.get("confidence_score", 0.5))
        delta = payload.get("confidence_delta")
        if delta is None:
            delta = self._default_delta(outcome)

        new_confidence = round(clamp(old_confidence + float(delta), 0.05, 0.99), 4)
        performance = skill.setdefault("performance", {})
        performance["successes"] = int(performance.get("successes", 0))
        performance["failures"] = int(performance.get("failures", 0))
        performance["neutral"] = int(performance.get("neutral", 0))

        if outcome in ("success", "succeeded", "closed_won", "resolved", "good"):
            performance["successes"] += 1
        elif outcome in ("failure", "failed", "closed_lost", "bad", "override"):
            performance["failures"] += 1
        else:
            performance["neutral"] += 1

        skill["confidence_score"] = new_confidence
        skill["last_feedback_at"] = utc_now()
        self.repository.save_skill(skill)

        feedback = {
            "feedback_id": f"fb_{uuid4().hex[:16]}",
            "created_at": utc_now(),
            "skill_id": skill_id,
            "execution_id": payload.get("execution_id"),
            "outcome": outcome,
            "notes": payload.get("notes"),
            "old_confidence": old_confidence,
            "new_confidence": new_confidence,
        }
        self.repository.append_feedback(feedback)
        return {"skill": skill, "feedback": feedback}

    @staticmethod
    def _default_delta(outcome: str) -> float:
        if outcome in ("success", "succeeded", "closed_won", "resolved", "good"):
            return 0.05
        if outcome in ("failure", "failed", "closed_lost", "bad", "override"):
            return -0.10
        return 0.0
