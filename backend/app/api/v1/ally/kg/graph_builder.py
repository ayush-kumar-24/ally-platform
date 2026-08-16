"""Pure row-to-graph mapping -- the curated business-knowledge catalogue
(root_causes / problems / blind_spots / interventions) turned into typed nodes and
edges. Kept separate from `sql_repository.py` so the mapping logic is testable
without a database: feed it plain dicts, get back (nodes, edges).

Relationship sources (see each table's columns in app/models/schema.py):
  root_cause -> problem        root_causes.problem_id            (FK, one per cause)
  root_cause -> blind_spot     blind_spots.linked_root_cause_ids  (JSONB array)
  root_cause -> intervention   interventions.root_cause_ids       (JSONB array)
  problem    -> blind_spot     blind_spots.linked_problem_ids     (JSONB array)

There is deliberately no intervention -> recommendation edge here: a "recommendation"
(app/api/v1/reasoning/engines/recommendation.py) is an intervention already scored
and prioritised FOR ONE FOUNDER at report time, not a second global catalogue --
there is no table of standalone recommendation records to load. NodeType.RECOMMENDATION
stays a valid node type for a future per-report graph view; this static catalogue
repository simply never emits one, which is what "fail closed, never invent" means
in practice here.

Malformed JSONB entries (a non-integer id, a reference to an id that turns out not
to exist) are skipped rather than raising -- the traversal engine already treats a
dangling edge as fail-closed (skips it), so the stricter behaviour lives there once,
not duplicated at every call site that builds edges.
"""

from __future__ import annotations

from app.api.v1.ally.kg.schemas import GraphEdge, GraphNode, NodeType, RelationshipType

_RC = NodeType.ROOT_CAUSE.value
_PROB = NodeType.PROBLEM.value
_BS = NodeType.BLIND_SPOT.value
_IV = NodeType.INTERVENTION.value


def _int_ids(raw) -> list[int]:
    """Coerce a JSONB array (of ints, numeric strings, or a stray bad entry) into
    a list of ints, dropping anything that does not parse. JSONB round-trips
    numbers faithfully, but this stays defensive against hand-edited catalogue
    rows (e.g. `"12"` or `12.0` instead of `12`)."""
    if not raw:
        return []
    out = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def build_graph(*, root_causes: list[dict], problems: list[dict],
                 blind_spots: list[dict], interventions: list[dict]
                 ) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    for p in problems:
        nodes.append(GraphNode(
            node_id=f"{_PROB}:{p['problem_id']}", node_type=NodeType.PROBLEM,
            ref_id=p["problem_id"], label=p["problem_name"],
            metadata={"category": p.get("category"), "layer": p.get("layer"),
                      "subcategory": p.get("subcategory")}))

    for rc in root_causes:
        rc_id = rc["root_cause_id"]
        nodes.append(GraphNode(
            node_id=f"{_RC}:{rc_id}", node_type=NodeType.ROOT_CAUSE, ref_id=rc_id,
            label=rc["root_cause_name"],
            metadata={"category": rc.get("root_cause_category"), "layer": rc.get("layer"),
                      "confidence_weight": rc.get("confidence_weight"),
                      "primary_stage_group": rc.get("primary_stage_group")}))
        if rc.get("problem_id") is not None:
            edges.append(GraphEdge(source=f"{_RC}:{rc_id}", target=f"{_PROB}:{rc['problem_id']}",
                                   relationship=RelationshipType.ROOT_CAUSE_TO_PROBLEM))

    for iv in interventions:
        iv_id = iv["intervention_id"]
        nodes.append(GraphNode(
            node_id=f"{_IV}:{iv_id}", node_type=NodeType.INTERVENTION, ref_id=iv_id,
            label=iv.get("intervention_code") or f"intervention {iv_id}",
            metadata={"capability_domain": iv.get("capability_domain"),
                      "section": iv.get("section"), "problem_id": iv.get("problem_id")}))
        for rc_id in _int_ids(iv.get("root_cause_ids")):
            edges.append(GraphEdge(source=f"{_RC}:{rc_id}", target=f"{_IV}:{iv_id}",
                                   relationship=RelationshipType.ROOT_CAUSE_TO_INTERVENTION))

    for bs in blind_spots:
        bs_id = bs["blind_spot_id"]
        nodes.append(GraphNode(
            node_id=f"{_BS}:{bs_id}", node_type=NodeType.BLIND_SPOT, ref_id=bs_id,
            label=bs["blind_spot_name"], metadata={"blind_spot_type": bs.get("blind_spot_type")}))
        for rc_id in _int_ids(bs.get("linked_root_cause_ids")):
            edges.append(GraphEdge(source=f"{_RC}:{rc_id}", target=f"{_BS}:{bs_id}",
                                   relationship=RelationshipType.ROOT_CAUSE_TO_BLIND_SPOT))
        for p_id in _int_ids(bs.get("linked_problem_ids")):
            edges.append(GraphEdge(source=f"{_PROB}:{p_id}", target=f"{_BS}:{bs_id}",
                                   relationship=RelationshipType.PROBLEM_TO_BLIND_SPOT))

    return nodes, edges
