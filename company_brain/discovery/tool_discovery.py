from __future__ import annotations

from company_brain.extractors.tool_extractor import KNOWN_TOOLS


class ToolDiscovery:
    def discover(self, text: str) -> str | None:
        lower = text.lower()
        for key, display in KNOWN_TOOLS.items():
            if key in lower:
                return display
        return None
