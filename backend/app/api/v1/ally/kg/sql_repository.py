"""SQL-backed KnowledgeGraphRepository -- real data over the existing relational
tables. No new graph schema: root_causes.problem_id and interventions.
root_cause_ids/secondary_root_cause_ids are already real foreign-key-shaped
relationships, so this repository just reads them as graph edges.

Partial coverage, deliberately. Of the 5 modelled RelationshipTypes, this covers
2: root_cause->problem and root_cause->intervention. The other 3
(*_TO_BLIND_SPOT, INTERVENTION_TO_RECOMMENDATION) have no backing data anywhere
in the pipeline yet -- blind_spot_ids is explicitly left empty by the reasoning
report today (see reasoning/service.py's own comment on that), and there is no
"recommendation" table distinct from interventions. Wiring those in without real
data would mean inventing edges, which the traversal engine's whole contract
(fail-closed, never fabricate) exists to prevent. get_node/outgoing simply
return nothing for those node types until that data exists.

Fail-closed like every other adapter here: an unknown node id, a node with no
outgoing edges, or a query that finds nothing all return the "not found" /
empty result, never an error surfaced as a fabricated edge.
"""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.ally.kg.repository import KnowledgeGraphRepository
from app.api.v1.ally.kg.schemas import (
    GraphEdge,
    GraphNode,
    NodeType,
    RelationshipType,
    intervention_node_id,
    problem_node_id,
    root_cause_node_id,
)

# node_type -> (table, id column, label column). Only types with a real data
# source belong here; anything else (blind_spot, recommendation, case_study,
# framework) has no row to read and correctly falls through to "not found".
_NODE_TABLES: dict[str, tuple[str, str, str]] = {
    NodeType.ROOT_CAUSE.value: ("root_causes", "root_cause_id", "root_cause_name"),
    NodeType.PROBLEM.value: ("problems", "problem_id", "problem_name"),
    # interventions has no free-text "name" column -- intervention_code is the
    # only human-readable label it carries.
    NodeType.INTERVENTION.value: ("interventions", "intervention_id", "intervention_code"),
}


class SqlKnowledgeGraphRepository(KnowledgeGraphRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_node(self, node_id: str) -> GraphNode | None:
        node_type, _, ref_id = node_id.partition(":")
        spec = _NODE_TABLES.get(node_type)
        if spec is None or not ref_id.isdigit():
            return None
        table, id_col, label_col = spec
        row = self.db.execute(
            text(f"SELECT {id_col} AS ref_id, {label_col} AS label FROM {table} WHERE {id_col} = :id"),
            {"id": int(ref_id)},
        ).mappings().first()
        if row is None:
            return None
        return GraphNode(
            node_id=node_id, node_type=NodeType(node_type),
            ref_id=row["ref_id"], label=row["label"] or f"{node_type} {row['ref_id']}",
        )

    def outgoing(self, node_id: str) -> tuple[GraphEdge, ...]:
        node_type, _, ref_id = node_id.partition(":")
        if node_type != NodeType.ROOT_CAUSE.value or not ref_id.isdigit():
            # Only root_cause has outgoing edges in this partial implementation --
            # problem/intervention nodes are leaves here until the missing
            # relationship types (blind_spot, recommendation) have real data.
            return ()
        rc_id = int(ref_id)
        edges: list[GraphEdge] = []

        rc_row = self.db.execute(
            text("SELECT problem_id, root_cause_code FROM root_causes WHERE root_cause_id = :id"),
            {"id": rc_id},
        ).first()
        if rc_row is None:
            return ()
        problem_id, root_cause_code = rc_row
        if problem_id is not None:
            edges.append(GraphEdge(
                source=node_id, target=problem_node_id(problem_id),
                relationship=RelationshipType.ROOT_CAUSE_TO_PROBLEM,
            ))

        # jsonb array containment (@>): root_cause_ids / secondary_root_cause_ids
        # store the root cause's founder-facing CODE ("RC-001"), not its integer
        # root_cause_id -- confirmed against live data before shipping this;
        # the integer-id version of this query silently matched nothing at all.
        if root_cause_code:
            code_json = json.dumps([root_cause_code])
            intervention_rows = self.db.execute(
                text(
                    "SELECT intervention_id FROM interventions "
                    "WHERE root_cause_ids @> CAST(:code_json AS jsonb) "
                    "   OR secondary_root_cause_ids @> CAST(:code_json AS jsonb) "
                    "ORDER BY intervention_id"
                ),
                {"code_json": code_json},
            ).all()
            for (intervention_id,) in intervention_rows:
                edges.append(GraphEdge(
                    source=node_id, target=intervention_node_id(intervention_id),
                    relationship=RelationshipType.ROOT_CAUSE_TO_INTERVENTION,
                ))

        return tuple(edges)
