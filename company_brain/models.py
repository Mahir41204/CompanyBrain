from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


REQUIRED_SKILL_FIELDS = {"skill_id", "version", "description", "decision_tree"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def validate_skill(skill: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_SKILL_FIELDS - set(skill))
    if missing:
        raise ValueError(f"Skill is missing required fields: {', '.join(missing)}")

    if not isinstance(skill.get("decision_tree"), list) or not skill["decision_tree"]:
        raise ValueError("Skill decision_tree must be a non-empty list")

    if "confidence_score" in skill:
        score = skill["confidence_score"]
        if not isinstance(score, int | float) or not 0 <= float(score) <= 1:
            raise ValueError("Skill confidence_score must be between 0 and 1")


def skill_summary(skill: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_id": skill["skill_id"],
        "version": skill.get("version", "0.0.0"),
        "domain": skill.get("domain", "operations"),
        "description": skill.get("description", ""),
        "confidence_score": skill.get("confidence_score", 0.5),
        "last_updated": skill.get("last_updated"),
        "inputs": skill.get("inputs", []),
        "related_skills": skill.get("related_skills", []),
    }


def normalize_status(value: str | None) -> str:
    return (value or "pending").strip().lower().replace(" ", "_")
