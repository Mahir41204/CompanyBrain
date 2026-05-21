from __future__ import annotations

from pathlib import Path

from company_brain.core.evidence import Evidence

from .json_file import read_json_array, write_json_array


class EvidenceRepository:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.path = Path(data_dir) / "evidence.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_evidence(self) -> list[Evidence]:
        return [Evidence.from_dict(row) for row in read_json_array(self.path)]

    def get(self, evidence_id: str) -> Evidence | None:
        for evidence in self.list_evidence():
            if evidence.id == evidence_id:
                return evidence
        return None

    def upsert(self, evidence: Evidence) -> Evidence:
        rows = {item.id: item for item in self.list_evidence()}
        rows[evidence.id] = evidence
        write_json_array(self.path, [item.to_dict() for item in sorted(rows.values(), key=lambda row: row.id)])
        return evidence
