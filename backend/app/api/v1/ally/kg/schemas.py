"""Typed DTOs for the Knowledge Graph Query Layer (Phase 5, Milestone 4).

Strongly-typed nodes, edges and relationship types over business knowledge. The
graph is deterministic structured data -- it never generates text, scores or
answers. Node ids are canonical `"{type}:{ref_id}"` strings so a node is unique
and traversal can dedupe and cycle-detect reliably.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class NodeType(str, Enum):
    ROOT_CAUSE = "root_cause"
    PROBLEM = "problem"
    BLIND_SPOT = "blind_spot"
    INTERVENTION = "intervention"
    RECOMMENDATION = "recommendation"
    CASE_STUDY = "case_study"        # future
    FRAMEWORK = "framework"          # future


# Deterministic type ordering for stable output (traversal-order along the chain).
NODE_TYPE_ORDER: dict[str, int] = {t.value: i for i, t in enumerate(NodeType)}


class RelationshipType(str, Enum):
    ROOT_CAUSE_TO_PROBLEM = "root_cause_to_problem"
    ROOT_CAUSE_TO_BLIND_SPOT = "root_cause_to_blind_spot"
    ROOT_CAUSE_TO_INTERVENTION = "root_cause_to_intervention"
    PROBLEM_TO_BLIND_SPOT = "problem_to_blind_spot"
    INTERVENTION_TO_RECOMMENDATION = "intervention_to_recommendation"


@dataclass(frozen=True)
class GraphNode:
    node_id: str                     # canonical, e.g. "root_cause:10"
    node_type: NodeType
    ref_id: int | str                # id in the source table
    label: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    source: str                      # source node_id
    target: str                      # target node_id
    relationship: RelationshipType


@dataclass(frozen=True)
class TraversalRequest:
    root_cause_ids: tuple[int, ...]
    max_depth: int


@dataclass(frozen=True)
class TraversalResult:
    """Raw output of the traversal engine -- nodes/edges plus traversal stats.
    The service wraps this into a GraphView with aggregate metadata."""

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    depth_reached: int
    truncated: bool                  # True if max_depth stopped further expansion


@dataclass(frozen=True)
class GraphMetadata:
    root_cause_ids: tuple[int, ...]
    traversal_depth: int
    truncated: bool
    node_count: int
    edge_count: int
    node_type_counts: Mapping[str, int]
    relationship_counts: Mapping[str, int]


@dataclass(frozen=True)
class GraphView:
    """The public output of expand(): the traversed subgraph + metadata. Empty
    (no nodes/edges) when nothing resolved -- never invented."""

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    metadata: GraphMetadata

    @property
    def is_empty(self) -> bool:
        return len(self.nodes) == 0


def root_cause_node_id(root_cause_id: int) -> str:
    """Canonical node id for a root cause -- the traversal entry point."""
    return f"{NodeType.ROOT_CAUSE.value}:{root_cause_id}"
