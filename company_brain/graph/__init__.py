"""History-aware graph layer.

The early MVP used ``company_brain.core`` for graph primitives. This package keeps
those models available while adding temporal memory.
"""

from company_brain.core.edges import Edge
from company_brain.core.entities import Entity, EntityType
from company_brain.core.evidence import Evidence
from company_brain.core.graph import BrainGraph

from .temporal import MemorySnapshot

__all__ = ["BrainGraph", "Edge", "Entity", "EntityType", "Evidence", "MemorySnapshot"]
