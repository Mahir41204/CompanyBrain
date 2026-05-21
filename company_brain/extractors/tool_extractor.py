from __future__ import annotations

from company_brain.core.entities import Entity, EntityType, entity_id

from .types import ExtractionResult


KNOWN_TOOLS = {
    "zendesk": "Zendesk",
    "salesforce": "Salesforce",
    "hubspot": "HubSpot",
    "jira": "Jira",
    "linear": "Linear",
    "asana": "Asana",
    "slack": "Slack",
    "teams": "Teams",
    "gmail": "Gmail",
    "outlook": "Outlook",
    "notion": "Notion",
    "confluence": "Confluence",
    "supplieros": "SupplierOS",
    "netsuite": "NetSuite",
    "quickbooks": "QuickBooks",
    "workday": "Workday",
    "bamboohr": "BambooHR",
    "rippling": "Rippling",
}


class ToolExtractor:
    def extract(self, text: str, evidence_id: str) -> ExtractionResult:
        lower = text.lower()
        tools = [
            Entity(
                id=entity_id(EntityType.TOOL, display),
                type=EntityType.TOOL,
                name=display,
                confidence=0.86,
                sources=[evidence_id],
            )
            for key, display in KNOWN_TOOLS.items()
            if key in lower
        ]
        return ExtractionResult(entities=tools)
