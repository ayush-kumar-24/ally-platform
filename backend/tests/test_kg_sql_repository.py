"""Tests for the SQL-backed Knowledge Graph adapter.

graph_builder.build_graph is pure (dict rows in, nodes/edges out) so it is tested
directly with no database. SqlKnowledgeGraphRepository's DB-touching parts are
covered with a stub Session -- consistent with this codebase's convention that a
SQL repository's query correctness is proven against a live DB (untested here),
while its *load* and *fail-open* contract is proven with a double (see
app/privacy/db_repository.py's own docstring for the same trade-off).
"""

from app.api.v1.ally.kg.graph_builder import build_graph
from app.api.v1.ally.kg.schemas import NodeType, RelationshipType
from app.api.v1.ally.kg.sql_repository import SqlKnowledgeGraphRepository

RC = NodeType.ROOT_CAUSE.value
PROB = NodeType.PROBLEM.value
BS = NodeType.BLIND_SPOT.value
IV = NodeType.INTERVENTION.value


# --- build_graph: pure mapping -------------------------------------------------


def test_root_cause_to_problem_edge_from_fk():
    nodes, edges = build_graph(
        root_causes=[{"root_cause_id": 10, "root_cause_name": "RC", "problem_id": 5}],
        problems=[{"problem_id": 5, "problem_name": "P"}],
        blind_spots=[], interventions=[])
    ids = {n.node_id for n in nodes}
    assert {f"{RC}:10", f"{PROB}:5"} <= ids
    assert (f"{RC}:10", RelationshipType.ROOT_CAUSE_TO_PROBLEM.value, f"{PROB}:5") == \
           (edges[0].source, edges[0].relationship.value, edges[0].target)


def test_intervention_root_cause_ids_produce_reverse_edges():
    nodes, edges = build_graph(
        root_causes=[{"root_cause_id": 10, "root_cause_name": "RC"}],
        problems=[],
        blind_spots=[],
        interventions=[{"intervention_id": 7, "intervention_code": "IV-1",
                        "root_cause_ids": [10]}])
    assert any(e.source == f"{RC}:10" and e.target == f"{IV}:7"
              and e.relationship == RelationshipType.ROOT_CAUSE_TO_INTERVENTION
              for e in edges)


def test_blind_spot_links_produce_both_relationship_types():
    nodes, edges = build_graph(
        root_causes=[{"root_cause_id": 10, "root_cause_name": "RC"}],
        problems=[{"problem_id": 5, "problem_name": "P"}],
        blind_spots=[{"blind_spot_id": 3, "blind_spot_name": "BS",
                      "linked_root_cause_ids": [10], "linked_problem_ids": [5]}],
        interventions=[])
    rels = {(e.source, e.target, e.relationship) for e in edges}
    assert (f"{RC}:10", f"{BS}:3", RelationshipType.ROOT_CAUSE_TO_BLIND_SPOT) in rels
    assert (f"{PROB}:5", f"{BS}:3", RelationshipType.PROBLEM_TO_BLIND_SPOT) in rels


def test_malformed_linked_ids_are_skipped_not_raised():
    nodes, edges = build_graph(
        root_causes=[],
        problems=[],
        blind_spots=[{"blind_spot_id": 3, "blind_spot_name": "BS",
                      "linked_root_cause_ids": ["not-an-id", None, 12],
                      "linked_problem_ids": []}],
        interventions=[])
    # Only the one parseable id (12) becomes an edge; the rest are dropped, not raised.
    assert len(edges) == 1 and edges[0].source == f"{RC}:12"


def test_dangling_reference_is_still_emitted_as_an_edge():
    """build_graph does not filter dangling targets -- that is the traversal
    engine's job (it already skips an edge whose target node doesn't resolve).
    Keeping that check in one place (traversal.py) means it can't drift."""
    nodes, edges = build_graph(
        root_causes=[{"root_cause_id": 10, "root_cause_name": "RC"}],
        problems=[],
        blind_spots=[{"blind_spot_id": 3, "blind_spot_name": "BS",
                      "linked_root_cause_ids": [999], "linked_problem_ids": []}],
        interventions=[])
    assert any(e.target == f"{BS}:3" and e.source == f"{RC}:999" for e in edges)


def test_empty_catalogue_yields_empty_graph():
    nodes, edges = build_graph(root_causes=[], problems=[], blind_spots=[], interventions=[])
    assert nodes == [] and edges == []


# --- SqlKnowledgeGraphRepository: raises on a broken load ----------------------
#
# Deliberately does NOT fail open itself -- see the module docstring for why the
# fail-open decision belongs to container.knowledge_graph(db), which also decides
# what a failed refresh degrades to (last-good cache, not a wiped-empty graph).


class _RaisingSession:
    def execute(self, *a, **k):
        raise RuntimeError('relation "root_causes" does not exist')


def test_repository_raises_on_db_error_rather_than_hiding_it():
    try:
        SqlKnowledgeGraphRepository(_RaisingSession())
        assert False, "expected the load error to propagate"
    except RuntimeError as exc:
        assert "root_causes" in str(exc)


class _StubResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _StubSession:
    """Returns canned rows keyed by a substring of the query, in call order."""

    def __init__(self, tables: dict[str, list[dict]]):
        self._tables = tables

    def execute(self, clause, *a, **k):
        sql = str(clause)
        for table, rows in self._tables.items():
            if f"from {table}" in sql:
                return _StubResult(rows)
        return _StubResult([])


def test_repository_loads_and_serves_a_real_traversal():
    db = _StubSession({
        "root_causes": [{"root_cause_id": 10, "root_cause_name": "RC", "root_cause_category": "c",
                         "layer": "internal", "confidence_weight": 0.5,
                         "primary_stage_group": "Stage 0", "problem_id": 5}],
        "problems": [{"problem_id": 5, "problem_name": "P", "category": "c",
                     "layer": "internal", "subcategory": None}],
        "blind_spots": [],
        "interventions": [],
    })
    repo = SqlKnowledgeGraphRepository(db)
    node = repo.get_node(f"{RC}:10")
    assert node is not None and node.label == "RC"
    outgoing = repo.outgoing(f"{RC}:10")
    assert len(outgoing) == 1 and outgoing[0].target == f"{PROB}:5"
