from __future__ import annotations

import re


class OwnerDiscovery:
    TEAMS = {
        "finance": "Finance Team",
        "sales": "Sales Team",
        "support": "Support Team",
        "customer success": "Customer Success Team",
        "procurement": "Procurement Team",
        "compliance": "Compliance Team",
        "ops": "Ops Team",
        "operations": "Ops Team",
    }

    def discover(self, text: str) -> str | None:
        lower = text.lower()
        owner_match = re.search(r"(?:owned by|owner is|owners?[:=])\s+([a-z\s]{3,40})", lower)
        if owner_match:
            owner = " ".join(owner_match.group(1).split()[:3])
            return self._display(owner)

        for keyword, display in self.TEAMS.items():
            if re.search(rf"\b{re.escape(keyword)}\b", lower):
                return display
        return None

    def _display(self, owner: str) -> str:
        return self.TEAMS.get(owner.lower(), owner.title())
