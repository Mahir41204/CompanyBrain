from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from company_brain.core.edges import Edge
from company_brain.core.entities import Entity, EntityType, entity_id
from company_brain.core.evidence import Evidence
from company_brain.discovery import Discovery, DiscoveryEngine, RelationDiscovery
from company_brain.extractors import (
    DecisionExtractor,
    ExtractionResult,
    PersonExtractor,
    PolicyExtractor,
    ProcessExtractor,
    ToolExtractor,
)
from company_brain.models import utc_now
from company_brain.storage import (
    DiscoveryRepository,
    EdgeRepository,
    EntityRepository,
    EvidenceRepository,
    SnapshotRepository,
)


class MemoryIngestionService:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.entities = EntityRepository(data_dir)
        self.edges = EdgeRepository(data_dir)
        self.evidence = EvidenceRepository(data_dir)
        self.discoveries = DiscoveryRepository(data_dir)
        self.snapshots = SnapshotRepository(data_dir)
        self.discovery_engine = DiscoveryEngine()
        self.relation_discovery = RelationDiscovery()
        self.extractors = [
            ProcessExtractor(),
            PolicyExtractor(),
            ToolExtractor(),
            PersonExtractor(),
            DecisionExtractor(),
        ]

    def ingest_record(self, record: dict[str, Any], skill_id: str | None = None) -> dict[str, Any]:
        text = str(record.get("content", "")).strip()
        if not text:
            raise ValueError("record content is required")

        evidence = self._evidence_from(record, text)
        self.evidence.upsert(evidence)

        extraction = ExtractionResult()
        for extractor in self.extractors:
            extraction.extend(extractor.extract(text, evidence.id))

        extraction.edges.extend(self._derive_edges(text, extraction.entities, evidence.id, skill_id))
        discovery = self.discovery_engine.discover(record, evidence.id)
        self.discoveries.upsert(discovery)
        discovery_entities, discovery_edges = self._memory_from_discovery(discovery, skill_id)
        extraction.entities.extend(discovery_entities)
        extraction.edges.extend(discovery_edges)
        extraction.edges.extend(self.relation_discovery.discover(text, extraction.entities, evidence.id))

        self.entities.upsert_many(extraction.entities)
        self.edges.upsert_many(extraction.edges)
        for entity in extraction.entities:
            self.snapshots.record_entity(entity, evidence.timestamp)

        return {
            "evidence": evidence.to_dict(),
            "discovery": discovery.to_dict(),
            "entities": [entity.to_dict() for entity in extraction.entities],
            "edges": [edge.to_dict() for edge in extraction.edges],
        }

    def _evidence_from(self, record: dict[str, Any], text: str) -> Evidence:
        source = str(record.get("source", "manual_note"))
        metadata = record.get("metadata", {})
        source_type = str(metadata.get("source_type", source.split("_")[0] or "manual"))
        source_ref = str(metadata.get("id", source))
        timestamp = str(metadata.get("timestamp", metadata.get("date", utc_now())))
        digest = hashlib.sha1(f"{source_type}:{source_ref}:{text}".encode("utf-8")).hexdigest()[:14]
        return Evidence(
            id=f"evidence_{digest}",
            source_type=source_type,
            source_ref=source_ref,
            text=text,
            timestamp=timestamp,
            confidence=float(metadata.get("confidence", 0.78)),
        )

    def _derive_edges(
        self,
        text: str,
        entities: list[Entity],
        evidence_id: str,
        skill_id: str | None,
    ) -> list[Edge]:
        lower = text.lower()
        by_type: dict[EntityType, list[Entity]] = {}
        for entity in entities:
            by_type.setdefault(entity.type, []).append(entity)

        edges: list[Edge] = []
        processes = by_type.get(EntityType.PROCESS, [])
        policies = by_type.get(EntityType.POLICY, [])
        tools = by_type.get(EntityType.TOOL, [])
        people = by_type.get(EntityType.PERSON, [])
        teams = by_type.get(EntityType.TEAM, [])
        customers = by_type.get(EntityType.CUSTOMER, [])
        decisions = by_type.get(EntityType.DECISION, [])

        for process in processes:
            for tool in tools:
                edges.append(Edge(process.id, tool.id, "uses", 0.82, [evidence_id]))
            for policy in policies:
                edges.append(Edge(process.id, policy.id, "governed_by", 0.76, [evidence_id]))
            for decision in decisions:
                edges.append(Edge(process.id, decision.id, "has_decision", 0.72, [evidence_id]))
            for person in people:
                if "escalate" in lower or "notify" in lower:
                    edges.append(Edge(process.id, person.id, "escalates_to", 0.78, [evidence_id]))
            for team in teams:
                if "approval" in lower or "approve" in lower or "requires" in lower:
                    edges.append(Edge(process.id, team.id, "requires_approval", 0.80, [evidence_id]))

        for policy in policies:
            for team in teams:
                if "own" in lower or "approval" in lower or "requires" in lower:
                    edges.append(Edge(team.id, policy.id, "owns", 0.66, [evidence_id]))
            for customer in customers:
                edges.append(Edge(policy.id, customer.id, "has_exception", 0.75, [evidence_id]))

        if skill_id:
            skill = Entity(
                id=entity_id(EntityType.SKILL, skill_id),
                type=EntityType.SKILL,
                name=skill_id,
                attributes={"skill_id": skill_id},
                confidence=0.68,
                sources=[evidence_id],
            )
            entities.append(skill)
            for target in policies or processes:
                edges.append(Edge(skill.id, target.id, "implements", 0.70, [evidence_id]))

        return edges

    def _memory_from_discovery(
        self,
        discovery: Discovery,
        skill_id: str | None,
    ) -> tuple[list[Entity], list[Edge]]:
        evidence_ids = discovery.evidence_ids
        source_confidence = discovery.confidence
        process_name = f"{discovery.process} process"
        process = Entity(
            id=entity_id(EntityType.PROCESS, process_name),
            type=EntityType.PROCESS,
            name=process_name,
            attributes={"steps": discovery.steps},
            confidence=source_confidence,
            sources=evidence_ids,
        )
        policy = Entity(
            id=entity_id(EntityType.POLICY, discovery.policies.get("name", f"{discovery.process} policy")),
            type=EntityType.POLICY,
            name=str(discovery.policies.get("name", f"{discovery.process} policy")),
            attributes={key: value for key, value in discovery.policies.items() if key != "name"},
            confidence=source_confidence,
            sources=evidence_ids,
        )

        entities = [process, policy]
        edges = [Edge(process.id, policy.id, "governed_by", source_confidence, evidence_ids)]

        if discovery.owner:
            owner = Entity(
                id=entity_id(EntityType.TEAM, discovery.owner),
                type=EntityType.TEAM,
                name=discovery.owner,
                confidence=source_confidence,
                sources=evidence_ids,
            )
            entities.append(owner)
            edges.append(Edge(owner.id, policy.id, "owns", source_confidence, evidence_ids))
            edges.append(Edge(process.id, owner.id, "requires_approval", source_confidence, evidence_ids))

        if discovery.tool:
            tool = Entity(
                id=entity_id(EntityType.TOOL, discovery.tool),
                type=EntityType.TOOL,
                name=discovery.tool,
                confidence=source_confidence,
                sources=evidence_ids,
            )
            entities.append(tool)
            edges.append(Edge(process.id, tool.id, "uses", source_confidence, evidence_ids))

        for exception in discovery.exceptions:
            exception_type = EntityType.CUSTOMER if "customer" in exception.lower() else EntityType.INCIDENT
            exception_entity = Entity(
                id=entity_id(exception_type, exception),
                type=exception_type,
                name=exception,
                attributes={"exception": True},
                confidence=source_confidence,
                sources=evidence_ids,
            )
            entities.append(exception_entity)
            edges.append(Edge(policy.id, exception_entity.id, "has_exception", source_confidence, evidence_ids))

        if skill_id:
            skill = Entity(
                id=entity_id(EntityType.SKILL, skill_id),
                type=EntityType.SKILL,
                name=skill_id,
                attributes={"skill_id": skill_id},
                confidence=source_confidence,
                sources=evidence_ids,
            )
            entities.append(skill)
            edges.append(Edge(skill.id, policy.id, "implements", source_confidence, evidence_ids))

        return entities, edges
