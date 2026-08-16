"""SQL-backed KnowledgeGraphRepository -- the production adapter over the curated
business-knowledge catalogue (root_causes / problems / blind_spots / interventions).

Loads the whole catalogue once, at construction, and answers get_node/outgoing from
an in-memory adjacency built by `graph_builder.build_graph` -- these tables are a
small, slow-changing reference catalogue (hundreds of rows, not per-founder data),
so one query per table per request is cheap and avoids N+1 lookups during traversal
(which calls get_node/outgoing many times per expand()).

Deliberately does NOT catch its own load errors -- it raises. `container.knowledge_graph(db)`
is the one place that decides what "the catalogue failed to load" degrades to (keep
serving the last good cached graph rather than replacing it with an empty one; see
that method's docstring). Swallowing here too would mean a transient DB hiccup
silently overwrites a perfectly good cached graph with an empty one for the whole
TTL window, which is worse than not caching at all.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.ally.kg.graph_builder import build_graph
from app.api.v1.ally.kg.repository import InMemoryKnowledgeGraphRepository, KnowledgeGraphRepository
from app.api.v1.ally.kg.schemas import GraphEdge, GraphNode

_ROOT_CAUSES_SQL = """
    select root_cause_id, root_cause_name, root_cause_category, layer,
           confidence_weight, primary_stage_group, problem_id
      from root_causes
"""
_PROBLEMS_SQL = "select problem_id, problem_name, category, layer, subcategory from problems"
_BLIND_SPOTS_SQL = """
    select blind_spot_id, blind_spot_name, blind_spot_type,
           linked_problem_ids, linked_root_cause_ids
      from blind_spots
"""
_INTERVENTIONS_SQL = """
    select intervention_id, intervention_code, problem_id, root_cause_ids,
           capability_domain, section
      from interventions
"""


class SqlKnowledgeGraphRepository(KnowledgeGraphRepository):
    def __init__(self, db: Session):
        nodes, edges = self._load(db)
        self._delegate = InMemoryKnowledgeGraphRepository(nodes, edges)

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._delegate.get_node(node_id)

    def outgoing(self, node_id: str) -> tuple[GraphEdge, ...]:
        return self._delegate.outgoing(node_id)

    @staticmethod
    def _load(db: Session) -> tuple[list[GraphNode], list[GraphEdge]]:
        root_causes = [dict(r) for r in db.execute(text(_ROOT_CAUSES_SQL)).mappings().all()]
        problems = [dict(r) for r in db.execute(text(_PROBLEMS_SQL)).mappings().all()]
        blind_spots = [dict(r) for r in db.execute(text(_BLIND_SPOTS_SQL)).mappings().all()]
        interventions = [dict(r) for r in db.execute(text(_INTERVENTIONS_SQL)).mappings().all()]
        return build_graph(root_causes=root_causes, problems=problems,
                           blind_spots=blind_spots, interventions=interventions)
