from __future__ import annotations

from company_brain.core.edges import Edge


def relation_strength(edge: Edge) -> int:
    evidence_bonus = min(18, max(0, len(edge.evidence) - 1) * 6)
    confidence_score = round(edge.confidence * 82)
    return max(1, min(100, confidence_score + evidence_bonus))
