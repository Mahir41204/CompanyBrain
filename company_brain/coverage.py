from __future__ import annotations

from collections import Counter
from typing import Any

from .repository import SkillRepository
from .reasoning import ConflictDetector
from .storage import (
    DiscoveryRepository,
    EdgeRepository,
    EntityRepository,
    EvidenceRepository,
    SnapshotRepository,
)


class CoverageService:
    def __init__(self, repository: SkillRepository) -> None:
        self.repository = repository
        self.entities = EntityRepository(repository.data_dir)
        self.edges = EdgeRepository(repository.data_dir)
        self.evidence = EvidenceRepository(repository.data_dir)
        self.discoveries = DiscoveryRepository(repository.data_dir)
        self.snapshots = SnapshotRepository(repository.data_dir)

    def compute(self) -> dict[str, Any]:
        skills = self.repository.list_skills()
        candidates = self.repository.list_candidates(status="pending")
        total = len(skills)
        high_confidence = [skill for skill in skills if float(skill.get("confidence_score", 0)) >= 0.75]
        domains = Counter(skill.get("domain", "operations") for skill in skills)
        candidate_domains = Counter(
            candidate.get("proposed_skill", {}).get("domain", "operations") for candidate in candidates
        )
        average_confidence = (
            round(sum(float(skill.get("confidence_score", 0.5)) for skill in skills) / total, 4)
            if total
            else 0.0
        )
        denominator = max(total + len(candidates), 1)

        return {
            "total_skills": total,
            "high_confidence_skills": len(high_confidence),
            "average_confidence": average_confidence,
            "pending_candidate_skills": len(candidates),
            "memory_entities": len(self.entities.list_entities()),
            "memory_edges": len(self.edges.list_edges()),
            "evidence_items": len(self.evidence.list_evidence()),
            "discoveries": len(self.discoveries.list_discoveries()),
            "memory_snapshots": len(self.snapshots.list_snapshots()),
            "open_conflicts": len(ConflictDetector().detect(self.snapshots.list_snapshots())),
            "skills_by_domain": dict(domains),
            "pending_candidates_by_domain": dict(candidate_domains),
            "operations_covered_estimate": round(len(high_confidence) / denominator, 4),
            "top_review_gaps": [
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "domain": candidate.get("proposed_skill", {}).get("domain", "operations"),
                    "description": candidate.get("proposed_skill", {}).get("description", ""),
                    "confidence": candidate.get("extraction_confidence"),
                }
                for candidate in candidates[:10]
            ],
        }
