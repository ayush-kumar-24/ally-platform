"""Ally Knowledge Graph Query Layer (Phase 5, Milestone 4).

A deterministic business-knowledge traversal engine (NOT a graph database). Given
root-cause ids (or an AllyContext), it expands structured relationships
(root cause -> problems -> blind spots -> interventions -> recommendations) into a
typed GraphView. It never generates answers, calls an LLM, retrieves vectors,
builds prompts, or touches Memory/Router/diagnosis, and it fails closed to an empty
GraphView.
"""

from app.api.v1.ally.kg.repository import (
    InMemoryKnowledgeGraphRepository,
    KnowledgeGraphRepository,
)
from app.api.v1.ally.kg.graph_builder import build_graph
from app.api.v1.ally.kg.sql_repository import SqlKnowledgeGraphRepository
from app.api.v1.ally.kg.schemas import (
    GraphEdge,
    GraphMetadata,
    GraphNode,
    GraphView,
    NodeType,
    RelationshipType,
    TraversalRequest,
    TraversalResult,
    root_cause_node_id,
)
from app.api.v1.ally.kg.service import (
    KnowledgeGraphService,
    build_knowledge_graph_service,
)
from app.api.v1.ally.kg.traversal import neighbors, shortest_path, traverse

__all__ = [
    "KnowledgeGraphService",
    "build_knowledge_graph_service",
    "KnowledgeGraphRepository",
    "InMemoryKnowledgeGraphRepository",
    "SqlKnowledgeGraphRepository",
    "build_graph",
    "traverse",
    "neighbors",
    "shortest_path",
    "GraphNode",
    "GraphEdge",
    "GraphView",
    "GraphMetadata",
    "NodeType",
    "RelationshipType",
    "TraversalRequest",
    "TraversalResult",
    "root_cause_node_id",
]
