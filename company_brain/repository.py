from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import normalize_status, utc_now, validate_skill


class SkillRepository:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self.skills_dir = self.data_dir / "skills"
        self.executions_path = self.data_dir / "executions.jsonl"
        self.feedback_path = self.data_dir / "feedback.jsonl"
        self.candidates_path = self.data_dir / "candidate_skills.jsonl"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> list[dict[str, Any]]:
        skills = []
        for path in sorted(self.skills_dir.glob("*.skill.json")):
            skills.append(self._read_json(path))
        return skills

    def get_skill(self, skill_id: str) -> dict[str, Any]:
        path = self._skill_path(skill_id)
        if path.exists():
            return self._read_json(path)

        for skill in self.list_skills():
            if skill.get("skill_id") == skill_id:
                return skill
        raise KeyError(f"Unknown skill: {skill_id}")

    def save_skill(self, skill: dict[str, Any]) -> None:
        validate_skill(skill)
        path = self._skill_path(skill["skill_id"])
        self._write_json(path, skill)

    def append_execution(self, execution: dict[str, Any]) -> None:
        self._append_jsonl(self.executions_path, execution)

    def list_executions(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.executions_path)

    def append_feedback(self, feedback: dict[str, Any]) -> None:
        self._append_jsonl(self.feedback_path, feedback)

    def list_feedback(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.feedback_path)

    def list_candidates(self, status: str | None = None) -> list[dict[str, Any]]:
        candidates = self._read_jsonl(self.candidates_path)
        if status is None:
            return candidates
        normalized = normalize_status(status)
        return [candidate for candidate in candidates if normalize_status(candidate.get("status")) == normalized]

    def add_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        candidates = self.list_candidates()
        candidate.setdefault("status", "pending")
        candidate.setdefault("created_at", utc_now())

        replaced = False
        for index, existing in enumerate(candidates):
            if existing.get("candidate_id") == candidate.get("candidate_id"):
                candidates[index] = {**existing, **candidate}
                replaced = True
                break

        if not replaced:
            candidates.append(candidate)

        self._write_jsonl(self.candidates_path, candidates)
        return candidate

    def update_candidate_status(self, candidate_id: str, status: str, note: str | None = None) -> dict[str, Any]:
        candidates = self.list_candidates()
        for candidate in candidates:
            if candidate.get("candidate_id") == candidate_id:
                candidate["status"] = normalize_status(status)
                candidate["reviewed_at"] = utc_now()
                if note:
                    candidate["review_note"] = note
                self._write_jsonl(self.candidates_path, candidates)
                return candidate
        raise KeyError(f"Unknown candidate: {candidate_id}")

    def approve_candidate(self, candidate_id: str) -> dict[str, Any]:
        candidates = self.list_candidates()
        for candidate in candidates:
            if candidate.get("candidate_id") == candidate_id:
                proposed_skill = candidate.get("proposed_skill")
                if not isinstance(proposed_skill, dict):
                    raise ValueError("Candidate does not include a proposed_skill")
                proposed_skill["last_updated"] = proposed_skill.get("last_updated") or utc_now()[:10]
                self.save_skill(proposed_skill)
                candidate["status"] = "approved"
                candidate["reviewed_at"] = utc_now()
                candidate["promoted_skill_id"] = proposed_skill["skill_id"]
                self._write_jsonl(self.candidates_path, candidates)
                return proposed_skill
        raise KeyError(f"Unknown candidate: {candidate_id}")

    def _skill_path(self, skill_id: str) -> Path:
        safe_id = "".join(char for char in skill_id if char.isalnum() or char in ("_", "-")).strip()
        if not safe_id:
            raise ValueError("skill_id must include at least one safe filename character")
        return self.skills_dir / f"{safe_id}.skill.json"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(path)

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        content = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
