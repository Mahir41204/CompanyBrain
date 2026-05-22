from __future__ import annotations

import re
from typing import Any


class PolicyDiscovery:
    def discover(self, text: str, process: str) -> dict[str, Any]:
        lower = text.lower()
        policy: dict[str, Any] = {"name": f"{process} policy"}

        threshold = self._threshold(lower)
        if threshold is not None:
            policy["approval_threshold_usd"] = threshold

        percent = self._percent(lower)
        if percent is not None:
            policy["approval_threshold_percent"] = percent

        days = self._days(lower)
        if days is not None:
            policy["sla_days"] = days if "sla" in lower else None
            policy["grace_period_days"] = days if "refund" in lower and "sla" not in lower else None
            policy = {key: value for key, value in policy.items() if value is not None}

        if "require" in lower or "requires" in lower:
            policy["requirement"] = self._requirement(lower)
        if "skip review" in lower or "bypass" in lower:
            policy["bypass_allowed"] = True

        return policy

    @staticmethod
    def _threshold(text: str) -> int | None:
        match = re.search(r"(?:above|over|greater than|>)\s*\$?\s*(\d+(?:,\d{3})*)", text)
        if match:
            return int(match.group(1).replace(",", ""))
        match = re.search(r"\$\s*(\d+(?:,\d{3})*)", text)
        if match:
            return int(match.group(1).replace(",", ""))
        return None

    @staticmethod
    def _percent(text: str) -> int | None:
        match = re.search(r"(\d+)\s*%", text)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _days(text: str) -> int | None:
        match = re.search(r"(\d+)\s*days?", text)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _requirement(text: str) -> str:
        match = re.search(r"requires?\s+([a-z\s]{3,50})(?:\.|,|$)", text)
        if not match:
            return "approval"
        return " ".join(match.group(1).split())
