from __future__ import annotations

import re

from company_brain.core.entities import Entity, EntityType, entity_id

from .types import ExtractionResult


class PersonExtractor:
    def extract(self, text: str, evidence_id: str) -> ExtractionResult:
        names = set()
        patterns = [
            r"escalate\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"escalate\b.*?\bto\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"ask\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"notify\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"@([A-Za-z][A-Za-z0-9_.-]+)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                candidate = match.group(1).replace(".", " ").replace("_", " ").strip()
                candidate = re.split(r"\b(if|when|because|for|about|on|in)\b", candidate, flags=re.IGNORECASE)[0]
                candidate = candidate.strip().title()
                if candidate.lower() not in {"finance", "support", "sales", "zendesk"}:
                    names.add(candidate)

        return ExtractionResult(
            entities=[
                Entity(
                    id=entity_id(EntityType.PERSON, name),
                    type=EntityType.PERSON,
                    name=name,
                    confidence=0.76,
                    sources=[evidence_id],
                )
                for name in sorted(names)
            ]
        )
