from __future__ import annotations

from typing import Any

from company_brain.core.graph import BrainGraph


class CoverageViewService:
    def __init__(self, graph: BrainGraph, coverage: dict[str, Any]) -> None:
        self.graph = graph
        self.coverage = coverage

    def build(self) -> dict[str, Any]:
        processes = [entity for entity in self.graph.entities.values() if entity.type.value == "process"]
        policies = [entity for entity in self.graph.entities.values() if entity.type.value == "policy"]
        owner_targets = set()
        for edge in self.graph.edges.values():
            if edge.relation in {"owns", "approves"}:
                owner_targets.add(edge.target_id)
            elif edge.relation == "requires_approval":
                owner_targets.add(edge.source_id)
        dependencies = {
            edge.source_id for edge in self.graph.edges.values()
            if edge.relation in {"uses", "depends_on", "governed_by", "requires_approval"}
        }
        process_rows = []
        for process in processes:
            process_rows.append(
                {
                    **process.to_dict(),
                    "owner_known": process.id in owner_targets,
                    "dependencies_mapped": process.id in dependencies,
                    "evidence_count": len(process.sources),
                }
            )
        return {
            "summary": {
                **self.coverage,
                "processes_documented": len(processes),
                "policies_mapped": len(policies),
                "owners_known": len([entity for entity in processes + policies if entity.id in owner_targets]),
                "dependencies_mapped": len([entity for entity in processes if entity.id in dependencies]),
            },
            "processes": process_rows,
            "policies": [policy.to_dict() for policy in policies],
        }
