from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from company_brain.models import utc_now


@dataclass
class AgentTask:
    id: str
    goal: str
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "created"
    created_at: str = field(default_factory=utc_now)
    plan: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "context": self.context,
            "status": self.status,
            "created_at": self.created_at,
            "plan": self.plan,
            "results": self.results,
        }
