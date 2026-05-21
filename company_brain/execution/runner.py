from __future__ import annotations

from typing import Any

from .planner import PlanStep


class PlanRunner:
    def dry_run(self, steps: list[PlanStep]) -> list[dict[str, Any]]:
        return [{"status": "planned", **step.to_dict()} for step in steps]
