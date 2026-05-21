from __future__ import annotations

import re
from typing import Any

from .models import clamp


MISSING = object()


class DecisionEngine:
    def execute(self, skill: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        fallback_rule: tuple[int, dict[str, Any]] | None = None
        matched_rule: tuple[int, dict[str, Any]] | None = None

        for index, rule in enumerate(skill.get("decision_tree", [])):
            if "else" in rule and "if" not in rule:
                fallback_rule = (index, rule)
                continue

            if self.evaluate(rule.get("if"), context):
                matched_rule = (index, rule)
                break

        if matched_rule is None:
            matched_rule = fallback_rule

        if matched_rule is None:
            return self._no_match(skill)

        index, rule = matched_rule
        branch = "then" if "then" in rule else "else"
        decision = self._normalize_decision(rule.get(branch, {"action": "needs_human_review"}))
        missing_inputs = self._missing_required_inputs(skill, context)
        confidence = float(rule.get("confidence", skill.get("confidence_score", 0.5)))

        if missing_inputs:
            confidence = min(confidence, 0.4)
            decision.setdefault("requires_approval", True)

        return {
            "skill_id": skill.get("skill_id"),
            "skill_version": skill.get("version"),
            "matched_rule_index": index,
            "matched_branch": branch,
            "action": decision.get("action", "needs_human_review"),
            "decision": decision,
            "confidence": round(clamp(confidence, 0.0, 1.0), 4),
            "reasoning": rule.get("reasoning", skill.get("description", "")),
            "requires_approval": bool(decision.get("requires_approval", False)),
            "missing_inputs": missing_inputs,
            "lineage": skill.get("learned_from", [])[:5],
            "related_skills": skill.get("related_skills", []),
        }

    def evaluate(self, condition: Any, context: dict[str, Any]) -> bool:
        if condition is None:
            return False

        if isinstance(condition, list):
            return all(self.evaluate(item, context) for item in condition)

        if not isinstance(condition, dict):
            return bool(condition)

        if "all" in condition:
            return all(self.evaluate(item, context) for item in condition["all"])
        if "any" in condition:
            return any(self.evaluate(item, context) for item in condition["any"])
        if "not" in condition:
            return not self.evaluate(condition["not"], context)

        field = condition.get("field")
        operator = condition.get("operator", "==")
        expected = condition.get("value")
        actual = self._get_value(context, field)
        return self._compare(actual, operator, expected)

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        op = operator.strip().lower()

        if op in ("exists", "present"):
            return actual is not MISSING and actual is not None
        if op in ("missing", "absent"):
            return actual is MISSING or actual is None
        if actual is MISSING:
            return False

        if op in ("==", "=", "eq"):
            return actual == expected
        if op in ("!=", "<>", "neq"):
            return actual != expected

        if op in (">", ">=", "<", "<="):
            left = self._as_number(actual)
            right = self._as_number(expected)
            if left is None or right is None:
                return False
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
            if op == "<":
                return left < right
            return left <= right

        if op in ("in", "one_of"):
            if isinstance(expected, list | tuple | set):
                return actual in expected
            return actual == expected

        if op in ("not_in", "not_one_of"):
            if isinstance(expected, list | tuple | set):
                return actual not in expected
            return actual != expected

        if op == "contains":
            if isinstance(actual, list | tuple | set):
                return expected in actual
            return str(expected).lower() in str(actual).lower()

        if op == "between":
            if not isinstance(expected, list | tuple) or len(expected) != 2:
                return False
            left = self._as_number(actual)
            low = self._as_number(expected[0])
            high = self._as_number(expected[1])
            if left is None or low is None or high is None:
                return False
            return low <= left <= high

        if op == "regex":
            return re.search(str(expected), str(actual)) is not None

        raise ValueError(f"Unsupported operator: {operator}")

    @staticmethod
    def _get_value(context: dict[str, Any], field: str | None) -> Any:
        if not field:
            return MISSING

        current: Any = context
        for part in str(field).split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return MISSING
        return current

    @staticmethod
    def _as_number(value: Any) -> float | None:
        if isinstance(value, int | float):
            return float(value)
        try:
            return float(str(value).replace("$", "").replace(",", "").replace("%", ""))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_decision(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        return {"action": str(value)}

    @staticmethod
    def _missing_required_inputs(skill: dict[str, Any], context: dict[str, Any]) -> list[str]:
        missing = []
        for item in skill.get("inputs", []):
            if isinstance(item, str):
                name = item
                required = True
            else:
                name = item.get("name")
                required = item.get("required", True)

            if required and name and DecisionEngine._get_value(context, name) is MISSING:
                missing.append(name)
        return missing

    @staticmethod
    def _no_match(skill: dict[str, Any]) -> dict[str, Any]:
        return {
            "skill_id": skill.get("skill_id"),
            "skill_version": skill.get("version"),
            "matched_rule_index": None,
            "matched_branch": None,
            "action": "needs_human_review",
            "decision": {"action": "needs_human_review", "requires_approval": True},
            "confidence": 0.0,
            "reasoning": "No decision rule matched and no fallback rule is defined.",
            "requires_approval": True,
            "missing_inputs": [],
            "lineage": skill.get("learned_from", [])[:5],
            "related_skills": skill.get("related_skills", []),
        }
