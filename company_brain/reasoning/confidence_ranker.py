from __future__ import annotations

from company_brain.core.entities import Entity


class ConfidenceRanker:
    def rank_entities(self, entities: list[Entity]) -> list[dict[str, object]]:
        ranked = []
        for entity in entities:
            evidence_boost = min(len(entity.sources) * 0.03, 0.18)
            score = min(round(entity.confidence + evidence_boost, 4), 0.99)
            ranked.append({"entity": entity.to_dict(), "score": score})
        return sorted(ranked, key=lambda row: row["score"], reverse=True)
