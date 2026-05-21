from __future__ import annotations

from company_brain.core.entities import Entity, EntityType, entity_id

from .types import ExtractionResult


TEAM_KEYWORDS = {
    "finance": "Finance Team",
    "support": "Support Team",
    "customer success": "Customer Success Team",
    "sales": "Sales Team",
    "procurement": "Procurement Team",
    "compliance": "Compliance Team",
}


class PolicyExtractor:
    def extract(self, text: str, evidence_id: str) -> ExtractionResult:
        lower = text.lower()
        entities = []

        if "refund" in lower:
            entities.append(
                Entity(
                    id=entity_id(EntityType.POLICY, "refund policy"),
                    type=EntityType.POLICY,
                    name="refund policy",
                    attributes=self._refund_attributes(lower),
                    confidence=0.82,
                    sources=[evidence_id],
                )
            )
        if "discount" in lower or "pricing" in lower:
            entities.append(
                Entity(
                    id=entity_id(EntityType.POLICY, "pricing exception policy"),
                    type=EntityType.POLICY,
                    name="pricing exception policy",
                    confidence=0.78,
                    sources=[evidence_id],
                )
            )
        if "supplier" in lower or "procurement" in lower:
            entities.append(
                Entity(
                    id=entity_id(EntityType.POLICY, "supplier approval policy"),
                    type=EntityType.POLICY,
                    name="supplier approval policy",
                    confidence=0.80,
                    sources=[evidence_id],
                )
            )
        if "enterprise" in lower:
            entities.append(
                Entity(
                    id=entity_id(EntityType.CUSTOMER, "enterprise customer"),
                    type=EntityType.CUSTOMER,
                    name="enterprise customer",
                    attributes={"tier": "enterprise"},
                    confidence=0.84,
                    sources=[evidence_id],
                )
            )

        for keyword, display in TEAM_KEYWORDS.items():
            if keyword in lower:
                entities.append(
                    Entity(
                        id=entity_id(EntityType.TEAM, display),
                        type=EntityType.TEAM,
                        name=display,
                        confidence=0.82,
                        sources=[evidence_id],
                    )
                )

        return ExtractionResult(entities=entities)

    @staticmethod
    def _refund_attributes(text: str) -> dict[str, object]:
        attributes: dict[str, object] = {}
        if "enterprise" in text:
            attributes["known_exception"] = "enterprise customer"
        if "$500" in text or "500" in text:
            attributes["approval_threshold_usd"] = 500
        return attributes
