from __future__ import annotations


class ExceptionDiscovery:
    KNOWN_EXCEPTIONS = {
        "vip": "VIP customer",
        "enterprise": "enterprise customer",
        "churn": "churn-risk customer",
        "first refund": "first refund request",
        "high-risk": "high-risk supplier",
        "high risk": "high-risk supplier",
        "sla": "SLA breach",
    }

    def discover(self, text: str) -> list[str]:
        lower = text.lower()
        exceptions = []
        for keyword, display in self.KNOWN_EXCEPTIONS.items():
            if keyword in lower and display not in exceptions:
                exceptions.append(display)
        if "skip review" in lower and "review bypass" not in exceptions:
            exceptions.append("review bypass")
        return exceptions
