from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from company_brain.core.edges import Edge
from company_brain.core.entities import Entity, EntityType, entity_id
from company_brain.core.evidence import Evidence
from company_brain.discovery import Discovery, DiscoveryEngine, LLMDiscoveryEngine, LLMDiscoveryResult, RelationDiscovery
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
    LLMDiscoveryRepository,
    SnapshotRepository,
)


class MemoryIngestionService:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.entities = EntityRepository(data_dir)
        self.edges = EdgeRepository(data_dir)
        self.evidence = EvidenceRepository(data_dir)
        self.discoveries = DiscoveryRepository(data_dir)
        self.llm_results = LLMDiscoveryRepository(data_dir)
        self.snapshots = SnapshotRepository(data_dir)
        self.llm_discovery = LLMDiscoveryEngine()
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

        llm_result = self.llm_discovery.discover(record, evidence.id)
        self.llm_results.upsert(
            f"llm_{evidence.id}",
            {
                **llm_result.to_dict(),
                "evidence_id": evidence.id,
                "source": record.get("source", "manual_note"),
                "created_at": utc_now(),
            },
        )

        extraction = ExtractionResult()
        for extractor in self.extractors:
            extraction.extend(extractor.extract(text, evidence.id))

        llm_entities, llm_edges = self._memory_from_llm_discovery(llm_result, skill_id)
        extraction.entities.extend(llm_entities)
        extraction.edges.extend(llm_edges)
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
            "llm_discovery": llm_result.to_dict(),
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

    def _memory_from_llm_discovery(
        self,
        result: LLMDiscoveryResult,
        skill_id: str | None,
    ) -> tuple[list[Entity], list[Edge]]:
        entities: dict[str, Entity] = {}
        edges: list[Edge] = []
        name_index: dict[str, str] = {}

        def remember(entity: Entity) -> Entity:
            if entity.id in entities:
                entities[entity.id].merge(entity)
            else:
                entities[entity.id] = entity
            name_index[entity.name.strip().lower()] = entity.id
            return entities[entity.id]

        def make_entity(
            name: str,
            entity_type: EntityType,
            confidence: float,
            evidence_ids: list[str],
            attributes: dict[str, Any] | None = None,
        ) -> Entity:
            return remember(
                Entity(
                    id=entity_id(entity_type, name),
                    type=entity_type,
                    name=name,
                    attributes=attributes or {},
                    confidence=confidence,
                    sources=evidence_ids,
                )
            )

        for row in result.entities:
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            entity_type = EntityType(str(row.get("type", "process")))
            make_entity(
                name,
                entity_type,
                float(row.get("confidence", 0.5)),
                list(row.get("evidence", [])),
                dict(row.get("attributes", {})),
            )

        for row in result.processes:
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            confidence = float(row.get("confidence", 0.5))
            evidence_ids = list(row.get("evidence", []))
            process = make_entity(
                name,
                EntityType.PROCESS,
                confidence,
                evidence_ids,
                {
                    "steps": list(row.get("steps", [])),
                    "dependencies": list(row.get("dependencies", [])),
                    "tools": list(row.get("tools", [])),
                    "policies": list(row.get("policies", [])),
                    "exceptions": list(row.get("exceptions", [])),
                },
            )
            owner_name = str(row.get("owner") or "").strip()
            if owner_name:
                owner = make_entity(
                    owner_name,
                    self._owner_type(owner_name),
                    confidence,
                    evidence_ids,
                )
                edges.append(Edge(owner.id, process.id, "owns", confidence, evidence_ids))
                edges.append(Edge(process.id, owner.id, "requires_approval", confidence, evidence_ids))
            for tool_name in list(row.get("tools", [])):
                tool = make_entity(str(tool_name), EntityType.TOOL, confidence, evidence_ids)
                edges.append(Edge(process.id, tool.id, "uses", confidence, evidence_ids))
            for dependency in list(row.get("dependencies", [])):
                dependency_entity = make_entity(str(dependency), EntityType.TOOL, confidence, evidence_ids)
                edges.append(Edge(process.id, dependency_entity.id, "depends_on", confidence, evidence_ids))
            for policy_name in list(row.get("policies", [])):
                policy = make_entity(str(policy_name), EntityType.POLICY, confidence, evidence_ids)
                edges.append(Edge(process.id, policy.id, "governed_by", confidence, evidence_ids))
            for exception in list(row.get("exceptions", [])):
                exception_type = EntityType.CUSTOMER if "customer" in str(exception).lower() else EntityType.INCIDENT
                exception_entity = make_entity(
                    str(exception),
                    exception_type,
                    confidence,
                    evidence_ids,
                    {"exception": True},
                )
                edges.append(Edge(process.id, exception_entity.id, "has_exception", confidence, evidence_ids))

        for row in result.policies:
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            confidence = float(row.get("confidence", 0.5))
            evidence_ids = list(row.get("evidence", []))
            policy = make_entity(
                name,
                EntityType.POLICY,
                confidence,
                evidence_ids,
                {
                    "rules": dict(row.get("rules", {})),
                    "exceptions": list(row.get("exceptions", [])),
                },
            )
            owner_name = str(row.get("owner") or "").strip()
            if owner_name:
                owner = make_entity(owner_name, self._owner_type(owner_name), confidence, evidence_ids)
                edges.append(Edge(owner.id, policy.id, "owns", confidence, evidence_ids))
            for exception in list(row.get("exceptions", [])):
                exception_type = EntityType.CUSTOMER if "customer" in str(exception).lower() else EntityType.INCIDENT
                exception_entity = make_entity(
                    str(exception),
                    exception_type,
                    confidence,
                    evidence_ids,
                    {"exception": True},
                )
                edges.append(Edge(policy.id, exception_entity.id, "has_exception", confidence, evidence_ids))

        for row in result.relationships:
            source_name = str(row.get("source", "")).strip().lower()
            target_name = str(row.get("target", "")).strip().lower()
            source_id = name_index.get(source_name)
            target_id = name_index.get(target_name)
            if not source_id or not target_id:
                continue
            relation = str(row.get("relation", "depends_on"))
            confidence = float(row.get("confidence", 0.5))
            evidence_ids = list(row.get("evidence", []))
            edges.append(Edge(source_id, target_id, relation, confidence, evidence_ids))
            if relation == "governs":
                edges.append(Edge(target_id, source_id, "governed_by", confidence, evidence_ids))

        if skill_id:
            skill = make_entity(
                skill_id,
                EntityType.SKILL,
                0.68,
                sorted({source for entity in entities.values() for source in entity.sources}),
                {"skill_id": skill_id},
            )
            for entity in list(entities.values()):
                if entity.type in {EntityType.POLICY, EntityType.PROCESS}:
                    edges.append(Edge(skill.id, entity.id, "implements", skill.confidence, entity.sources))

        return list(entities.values()), edges

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

    @staticmethod
    def _owner_type(name: str) -> EntityType:
        lower = name.lower()
        if "team" in lower or lower in {"finance", "support", "sales", "engineering", "ops", "operations", "legal"}:
            return EntityType.TEAM
        return EntityType.PERSON
