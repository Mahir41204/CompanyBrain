from __future__ import annotations

import re

from company_brain.core.entities import Entity, EntityType, entity_id

from .types import ExtractionResult


class DecisionExtractor:
    def extract(self, text: str, evidence_id: str) -> ExtractionResult:
        lower = text.lower()
        names = set()

        if any(token in lower for token in ("require", "approve", "escalate", "if ", "when ")):
            if "refund" in lower:
                names.add("refund approval decision")
            elif "supplier" in lower:
                names.add("supplier approval decision")
            elif "discount" in lower or "pricing" in lower:
                names.add("pricing approval decision")

        for match in re.finditer(r"(approve|reject|escalate|review)\s+([a-z\s]{3,40})", lower):
            action, obj = match.groups()
            words = obj.split()[:4]
            if words:
                names.add(f"{action} {' '.join(words)} decision")

        return ExtractionResult(
            entities=[
                Entity(
                    id=entity_id(EntityType.DECISION, name),
                    type=EntityType.DECISION,
                    name=name,
                    confidence=0.70,
                    sources=[evidence_id],
                )
                for name in sorted(names)
            ]
        )
