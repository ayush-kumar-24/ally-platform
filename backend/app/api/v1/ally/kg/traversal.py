"""Traversal Engine -- deterministic, depth-limited breadth-first expansion.

Pure graph algorithms over the repository interface. Deterministic by
construction:
  * neighbours are visited in a sorted order,
  * every node is visited at most once (a `visited` set = cycle detection AND
    duplicate-node removal),
  * final nodes and edges are sorted, so the output never depends on discovery
    order or dict iteration.

Fail-closed: an edge whose target node does not exist is skipped -- the engine
never invents a node or a relationship.
"""

from __future__ import annotations

from collections import deque

from app.api.v1.ally.kg.repository import KnowledgeGraphRepository
from app.api.v1.ally.kg.schemas import (
    NODE_TYPE_ORDER,
    GraphEdge,
    GraphNode,
    TraversalRequest,
    TraversalResult,
    root_cause_node_id,
)


def _edge_key(edge: GraphEdge) -> tuple:
    return (edge.source, edge.relationship.value, edge.target)


def _node_key(node: GraphNode) -> tuple:
    return (NODE_TYPE_ORDER.get(node.node_type.value, 99), str(node.ref_id), node.node_id)


def traverse(request: TraversalRequest, repository: KnowledgeGraphRepository) -> TraversalResult:
    # Resolve the entry points; unknown root causes are simply skipped (fail-closed).
    roots = [
        node
        for rc in request.root_cause_ids
        if (node := repository.get_node(root_cause_node_id(rc))) is not None
    ]

    visited: dict[str, GraphNode] = {}
    edges: dict[tuple, GraphEdge] = {}
    depth_reached = 0
    truncated = False

    queue: deque[tuple[GraphNode, int]] = deque()
    for r in sorted(roots, key=_node_key):
        if r.node_id not in visited:
            visited[r.node_id] = r
            queue.append((r, 0))

    while queue:
        node, depth = queue.popleft()
        outgoing = repository.outgoing(node.node_id)
        if depth >= request.max_depth:
            if outgoing:
                truncated = True      # there was more to expand, but depth stopped us
            continue
        for edge in sorted(outgoing, key=_edge_key):
            target = repository.get_node(edge.target)
            if target is None:
                continue              # fail-closed: never follow a dangling edge
            edges.setdefault(_edge_key(edge), edge)
            if target.node_id not in visited:
                visited[target.node_id] = target
                depth_reached = max(depth_reached, depth + 1)
                queue.append((target, depth + 1))

    return TraversalResult(
        nodes=tuple(sorted(visited.values(), key=_node_key)),
        edges=tuple(sorted(edges.values(), key=_edge_key)),
        depth_reached=depth_reached,
        truncated=truncated,
    )


def neighbors(node_id: str, repository: KnowledgeGraphRepository) -> tuple[GraphEdge, ...]:
    """Immediate outgoing edges whose target exists, sorted deterministically."""
    resolved = [
        e for e in repository.outgoing(node_id) if repository.get_node(e.target) is not None
    ]
    return tuple(sorted(resolved, key=_edge_key))


def shortest_path(
    source_id: str,
    target_id: str,
    repository: KnowledgeGraphRepository,
    *,
    max_depth: int = 6,
) -> tuple[str, ...]:
    """Deterministic BFS shortest path (node ids) from source to target, or empty
    when either endpoint is unknown or no path within max_depth. Future-ready:
    reasoning agents can use it to explain how a cause connects to an intervention."""
    if repository.get_node(source_id) is None or repository.get_node(target_id) is None:
        return ()
    if source_id == target_id:
        return (source_id,)

    prev: dict[str, str] = {source_id: source_id}
    queue: deque[tuple[str, int]] = deque([(source_id, 0)])
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in sorted(repository.outgoing(current), key=_edge_key):
            if repository.get_node(edge.target) is None or edge.target in prev:
                continue
            prev[edge.target] = current
            if edge.target == target_id:
                return _rebuild_path(prev, source_id, target_id)
            queue.append((edge.target, depth + 1))
    return ()


def _rebuild_path(prev: dict[str, str], source_id: str, target_id: str) -> tuple[str, ...]:
    path = [target_id]
    while path[-1] != source_id:
        path.append(prev[path[-1]])
    return tuple(reversed(path))
