from __future__ import annotations

import re

from company_brain.core.entities import Entity, EntityType, entity_id

from .types import ExtractionResult


class ProcessExtractor:
    def extract(self, text: str, evidence_id: str) -> ExtractionResult:
        lower = text.lower()
        names = set()

        if "refund" in lower:
            names.add("refund process")
        if any(token in lower for token in ("discount", "pricing", "deal")):
            names.add("pricing exception process")
        if any(token in lower for token in ("supplier", "procurement", "sourcing")):
            names.add("supplier approval process")
        if "incident" in lower:
            names.add("incident response process")

        for match in re.finditer(r"([a-z][a-z\s]{2,40})\s+process", lower):
            phrase = " ".join(match.group(0).split())
            if 2 <= len(phrase.split()) <= 5:
                names.add(phrase)

        return ExtractionResult(
            entities=[
                Entity(
                    id=entity_id(EntityType.PROCESS, name),
                    type=EntityType.PROCESS,
                    name=name,
                    confidence=0.74,
                    sources=[evidence_id],
                )
                for name in sorted(names)
            ]
        )
