"""Knowledge Graph Service -- traversal orchestration, no persistence.

Turns root-cause ids into a structured GraphView by running the traversal engine
over the repository, then aggregating metadata. It integrates with M1 by pulling
root-cause ids from an AllyContext, but reads NOTHING else from it and modifies
nothing.

Strict boundaries (enforced by imports): imports only the kg package and the M1
context schema. It does NOT call an LLM, retrieval, the Prompt Manager, Memory or
the Router, and it never scores or modifies a diagnosis.

Fail-closed: on any failure, or when nothing resolves, it returns an EMPTY
GraphView -- never an invented node or relationship.
"""

from __future__ import annotations

from collections import Counter

from app.api.v1.ally.context.schemas import AllyContext
from app.api.v1.ally.kg.repository import KnowledgeGraphRepository
from app.api.v1.ally.kg.schemas import (
    GraphMetadata,
    GraphView,
    TraversalRequest,
    TraversalResult,
)
from app.api.v1.ally.kg.traversal import neighbors, shortest_path, traverse
from app.core.logger import logger

_DEFAULT_MAX_DEPTH = 5


class KnowledgeGraphService:
    def __init__(
        self,
        repository: KnowledgeGraphRepository,
        *,
        default_max_depth: int = _DEFAULT_MAX_DEPTH,
    ):
        self.repository = repository
        self.default_max_depth = default_max_depth

    def expand(self, root_cause_ids, *, max_depth: int | None = None) -> GraphView:
        ids = tuple(dict.fromkeys(int(i) for i in root_cause_ids))  # ordered-unique
        depth = self.default_max_depth if max_depth is None else max(0, max_depth)
        request = TraversalRequest(root_cause_ids=ids, max_depth=depth)
        try:
            result = traverse(request, self.repository)
        except Exception as exc:  # fail closed -- never fabricate a graph
            logger.warning(
                "knowledge-graph traversal failed; returning empty view",
                extra={"stage": "kg_expand", "error": str(exc)},
            )
            return self._empty(ids)
        return self._view(result, ids)

    def expand_for_context(self, context: AllyContext, *, max_depth: int | None = None) -> GraphView:
        """M1 integration: expand from the context's top-finding root causes (all
        detected causes if none are flagged top). Read-only."""
        top = [rc.root_cause_id for rc in context.root_causes if rc.is_top_finding]
        ids = top or [rc.root_cause_id for rc in context.root_causes]
        return self.expand(ids, max_depth=max_depth)

    def neighbors(self, node_id: str):
        """Immediate outgoing edges of a node (deterministic)."""
        return neighbors(node_id, self.repository)

    def shortest_path(self, source_id: str, target_id: str, *, max_depth: int = 6):
        return shortest_path(source_id, target_id, self.repository, max_depth=max_depth)

    # --- View assembly ----------------------------------------------------

    def _view(self, result: TraversalResult, root_cause_ids: tuple[int, ...]) -> GraphView:
        node_type_counts = Counter(n.node_type.value for n in result.nodes)
        relationship_counts = Counter(e.relationship.value for e in result.edges)
        metadata = GraphMetadata(
            root_cause_ids=root_cause_ids,
            traversal_depth=result.depth_reached,
            truncated=result.truncated,
            node_count=len(result.nodes),
            edge_count=len(result.edges),
            node_type_counts=dict(node_type_counts),
            relationship_counts=dict(relationship_counts),
        )
        return GraphView(nodes=result.nodes, edges=result.edges, metadata=metadata)

    def _empty(self, root_cause_ids: tuple[int, ...]) -> GraphView:
        return GraphView(
            nodes=(),
            edges=(),
            metadata=GraphMetadata(
                root_cause_ids=root_cause_ids, traversal_depth=0, truncated=False,
                node_count=0, edge_count=0, node_type_counts={}, relationship_counts={},
            ),
        )


def build_knowledge_graph_service(
    repository: KnowledgeGraphRepository, *, default_max_depth: int = _DEFAULT_MAX_DEPTH
) -> KnowledgeGraphService:
    return KnowledgeGraphService(repository, default_max_depth=default_max_depth)
