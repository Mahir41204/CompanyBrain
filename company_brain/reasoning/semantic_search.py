from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from company_brain.core.graph import BrainGraph


class SemanticSearchService:
    def __init__(self, graph: BrainGraph) -> None:
        self.graph = graph

    def search(self, query: str, limit: int = 10) -> dict[str, Any]:
        query_tokens = self._tokens(query)
        if not query_tokens:
            return {"query": query, "results": []}
        query_vector = Counter(query_tokens)
        rows = []
        for entity in self.graph.entities.values():
            evidence_text = " ".join(
                self.graph.evidence[evidence_id].text
                for evidence_id in entity.sources
                if evidence_id in self.graph.evidence
            )
            text = " ".join(
                [
                    entity.name,
                    entity.type.value,
                    entity.id.replace("_", " "),
                    " ".join(str(value) for value in entity.attributes.values()),
                    evidence_text,
                ]
            )
            score = self._cosine(query_vector, Counter(self._tokens(text)))
            if score <= 0:
                continue
            rows.append(
                {
                    "entity": entity.to_dict(),
                    "score": round(score, 4),
                    "matched_evidence": [
                        self.graph.evidence[evidence_id].to_dict()
                        for evidence_id in entity.sources[:3]
                        if evidence_id in self.graph.evidence
                    ],
                }
            )
        rows.sort(key=lambda row: (row["score"], row["entity"]["confidence"]), reverse=True)
        return {"query": query, "results": rows[:limit]}

    @staticmethod
    def _tokens(text: str) -> list[str]:
        stop = {"the", "a", "an", "and", "or", "to", "of", "in", "for", "with", "by", "is"}
        return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in stop]

    @staticmethod
    def _cosine(left: Counter[str], right: Counter[str]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(left[token] * right.get(token, 0) for token in left)
        if dot == 0:
            return 0.0
        left_mag = math.sqrt(sum(value * value for value in left.values()))
        right_mag = math.sqrt(sum(value * value for value in right.values()))
        return dot / (left_mag * right_mag)
