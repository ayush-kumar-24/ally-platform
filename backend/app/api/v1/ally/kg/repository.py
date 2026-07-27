"""Knowledge Graph Repository -- loads nodes and edges. Nothing else.

Loading only: no traversal, no business logic, no persistence writes. This is the
provider-independent seam. Today an in-memory or relational-table adapter; tomorrow
a Neo4j adapter -- the traversal engine and service never change, because they only
depend on this interface.
"""

from __future__ import annotations

import abc
from collections import defaultdict
from collections.abc import Iterable

from app.api.v1.ally.kg.schemas import GraphEdge, GraphNode


class KnowledgeGraphRepository(abc.ABC):
    @abc.abstractmethod
    def get_node(self, node_id: str) -> GraphNode | None:
        """The node for an id, or None when it does not exist (fail-closed)."""
        raise NotImplementedError

    @abc.abstractmethod
    def outgoing(self, node_id: str) -> tuple[GraphEdge, ...]:
        """Edges leaving `node_id`. Empty when the node has none or is unknown."""
        raise NotImplementedError


class InMemoryKnowledgeGraphRepository(KnowledgeGraphRepository):
    """In-memory adjacency. The source of truth for tests, and a valid production
    adapter for a small static graph."""

    def __init__(self, nodes: Iterable[GraphNode], edges: Iterable[GraphEdge]):
        self._nodes: dict[str, GraphNode] = {n.node_id: n for n in nodes}
        self._outgoing: dict[str, list[GraphEdge]] = defaultdict(list)
        for e in edges:
            self._outgoing[e.source].append(e)

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def outgoing(self, node_id: str) -> tuple[GraphEdge, ...]:
        return tuple(self._outgoing.get(node_id, ()))
