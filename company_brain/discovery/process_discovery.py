from __future__ import annotations

import re


class ProcessDiscovery:
    KNOWN_PROCESSES = {
        "refund": ["open", "review", "approve", "payout", "close"],
        "pricing": ["review_deal", "check_discount", "approve", "document"],
        "supplier": ["intake", "audit_review", "risk_review", "approve", "onboard"],
        "incident": ["detect", "triage", "escalate", "resolve", "postmortem"],
        "support": ["open_ticket", "triage", "respond", "resolve", "close"],
    }

    ACTIONS = {
        "open": "open",
        "opened": "open",
        "review": "review",
        "approve": "approve",
        "approved": "approve",
        "close": "close",
        "closed": "close",
        "payout": "payout",
        "pay": "payout",
        "triage": "triage",
        "escalate": "escalate",
        "resolve": "resolve",
        "notify": "notify",
        "attach": "attach_docs",
        "document": "document",
    }

    def discover(self, text: str) -> dict[str, object]:
        lower = text.lower()
        process = self._process_name(lower)
        steps = self._steps(lower, process)
        return {"process": process, "steps": steps}

    def _process_name(self, text: str) -> str:
        for name in self.KNOWN_PROCESSES:
            if name in text:
                return name

        match = re.search(r"([a-z][a-z\s]{2,40})\s+process", text)
        if match:
            return " ".join(match.group(1).split()[-2:])
        return "operations"

    def _steps(self, text: str, process: str) -> list[str]:
        discovered = []
        for token, step in self.ACTIONS.items():
            if re.search(rf"\b{re.escape(token)}\b", text) and step not in discovered:
                discovered.append(step)

        if "workflow" in text and process in self.KNOWN_PROCESSES:
            for step in self.KNOWN_PROCESSES[process]:
                if step not in discovered:
                    discovered.append(step)

        if not discovered:
            return list(self.KNOWN_PROCESSES.get(process, ["review", "decide", "record"]))
        return discovered
