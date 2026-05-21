from __future__ import annotations

from pathlib import Path

from company_brain.core.entities import Entity

from .json_file import read_json_array, write_json_array


class EntityRepository:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.path = Path(data_dir) / "entities.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_entities(self) -> list[Entity]:
        return [Entity.from_dict(row) for row in read_json_array(self.path)]

    def get(self, entity_id: str) -> Entity | None:
        for entity in self.list_entities():
            if entity.id == entity_id:
                return entity
        return None

    def upsert(self, entity: Entity) -> Entity:
        entities = {item.id: item for item in self.list_entities()}
        if entity.id in entities:
            entities[entity.id].merge(entity)
        else:
            entities[entity.id] = entity
        write_json_array(self.path, [item.to_dict() for item in sorted(entities.values(), key=lambda row: row.id)])
        return entities[entity.id]

    def upsert_many(self, entities: list[Entity]) -> list[Entity]:
        return [self.upsert(entity) for entity in entities]
