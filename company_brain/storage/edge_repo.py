from __future__ import annotations

from pathlib import Path

from company_brain.core.edges import Edge

from .json_file import read_json_array, write_json_array


class EdgeRepository:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.path = Path(data_dir) / "edges.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_edges(self) -> list[Edge]:
        return [Edge.from_dict(row) for row in read_json_array(self.path)]

    def upsert(self, edge: Edge) -> Edge:
        edges = {item.id: item for item in self.list_edges()}
        if edge.id in edges:
            edges[edge.id].merge(edge)
        else:
            edges[edge.id] = edge
        write_json_array(self.path, [item.to_dict() for item in sorted(edges.values(), key=lambda row: row.id)])
        return edges[edge.id]

    def upsert_many(self, edges: list[Edge]) -> list[Edge]:
        return [self.upsert(edge) for edge in edges]
