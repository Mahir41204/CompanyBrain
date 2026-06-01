from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from company_brain.core.entities import Entity
from company_brain.core.evidence import Evidence
from company_brain.graph.temporal import MemorySnapshot
from company_brain.models import clamp, utc_now


class MemoryHealth:
    def __init__(
        self,
        entities: list[Entity],
        evidence: list[Evidence],
        snapshots: list[MemorySnapshot],
    ) -> None:
        self.entities = entities
        self.evidence_by_id = {item.id: item for item in evidence}
        self.snapshots = snapshots

    def assess(
        self,
        as_of: str | None = None,
        stale_after_days: int = 180,
        expired_after_days: int = 365,
        decay_rate: float = 0.0015,
    ) -> dict[str, Any]:
        now = self._parse_time(as_of or utc_now())
        rows = [
            self._entity_health(entity, now, stale_after_days, expired_after_days, decay_rate)
            for entity in self.entities
        ]
        stale = [row for row in rows if row["status"] == "stale"]
        expired = [row for row in rows if row["status"] == "expired"]
        aging = [row for row in rows if row["status"] == "aging"]

        return {
            "as_of": now.isoformat().replace("+00:00", "Z"),
            "summary": {
                "total": len(rows),
                "fresh": len([row for row in rows if row["status"] == "fresh"]),
                "aging": len(aging),
                "stale": len(stale),
                "expired": len(expired),
            },
            "items": sorted(rows, key=lambda row: (row["status_rank"], -row["age_days"], row["entity"]["id"])),
        }

    def _entity_health(
        self,
        entity: Entity,
        now: datetime,
        stale_after_days: int,
        expired_after_days: int,
        decay_rate: float,
    ) -> dict[str, Any]:
        last_seen = self._last_seen(entity, now)
        age_days = max((now - last_seen).days, 0) if last_seen else expired_after_days + 1
        if age_days >= expired_after_days:
            status = "expired"
            status_rank = 0
        elif age_days >= stale_after_days:
            status = "stale"
            status_rank = 1
        elif age_days >= max(stale_after_days // 2, 1):
            status = "aging"
            status_rank = 2
        else:
            status = "fresh"
            status_rank = 3

        decay = min(age_days * decay_rate, 0.75)
        decayed_confidence = round(clamp(entity.confidence * (1 - decay)), 4)
        return {
            "entity": entity.to_dict(),
            "last_seen": last_seen.isoformat().replace("+00:00", "Z") if last_seen else None,
            "age_days": age_days,
            "decay_rate": decay_rate,
            "original_confidence": round(entity.confidence, 4),
            "decayed_confidence": decayed_confidence,
            "status": status,
            "status_rank": status_rank,
            "recommendation": self._recommendation(status),
        }

    def _last_seen(self, entity: Entity, now: datetime) -> datetime | None:
        dates = []
        for evidence_id in entity.sources:
            evidence = self.evidence_by_id.get(evidence_id)
            if evidence:
                dates.append(self._parse_time(evidence.timestamp))
        for snapshot in self.snapshots:
            if snapshot.entity_id == entity.id:
                dates.append(self._parse_time(snapshot.valid_from))
                if snapshot.valid_until:
                    dates.append(self._parse_time(snapshot.valid_until))
        if not dates:
            return None
        observed_dates = [date for date in dates if date <= now]
        if not observed_dates:
            return None
        return max(observed_dates)

    @staticmethod
    def _parse_time(value: str) -> datetime:
        normalized = value.replace("Z", "+00:00")
        if len(normalized) == 10:
            normalized = f"{normalized}T00:00:00+00:00"
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _recommendation(status: str) -> str:
        if status == "expired":
            return "Require human review before execution and refresh from source systems."
        if status == "stale":
            return "Schedule owner verification and lower autonomous execution confidence."
        if status == "aging":
            return "Watch for contradictory behavior and prioritize if frequently used."
        return "No freshness action needed."
