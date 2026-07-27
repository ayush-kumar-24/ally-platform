"""Unit tests for the Ally Knowledge Graph Query Layer (Phase 5, Milestone 4).

Hermetic: builds an in-memory graph. No database, no LLM, no retrieval.
"""

from decimal import Decimal

from app.api.v1.ally.context.schemas import (
    AllyContext,
    DiagnosisContext,
    FounderProfileContext,
    RootCauseContext,
)
from app.api.v1.ally.kg import (
    GraphEdge,
    GraphNode,
    GraphView,
    InMemoryKnowledgeGraphRepository,
    NodeType,
    RelationshipType,
    build_knowledge_graph_service,
)

NT = NodeType
RT = RelationshipType


def N(t, ref, label=None):
    return GraphNode(f"{t.value}:{ref}", t, ref, label or f"{t.value}-{ref}")


def E(s, t, rel):
    return GraphEdge(s.node_id, t.node_id, rel)


# --- Main fixture: two overlapping subgraphs + one disconnected -------------
RC10, RC20, RC30 = N(NT.ROOT_CAUSE, 10), N(NT.ROOT_CAUSE, 20), N(NT.ROOT_CAUSE, 30)
P5, P6, P8 = N(NT.PROBLEM, 5), N(NT.PROBLEM, 6), N(NT.PROBLEM, 8)
B3, B4, B9 = N(NT.BLIND_SPOT, 3), N(NT.BLIND_SPOT, 4), N(NT.BLIND_SPOT, 9)
I7, R2 = N(NT.INTERVENTION, 7), N(NT.RECOMMENDATION, 2)

NODES = [RC10, RC20, RC30, P5, P6, P8, B3, B4, B9, I7, R2]
EDGES = [
    E(RC10, P5, RT.ROOT_CAUSE_TO_PROBLEM),
    E(P5, B3, RT.PROBLEM_TO_BLIND_SPOT),
    E(RC10, I7, RT.ROOT_CAUSE_TO_INTERVENTION),
    E(I7, R2, RT.INTERVENTION_TO_RECOMMENDATION),
    E(RC20, P6, RT.ROOT_CAUSE_TO_PROBLEM),
    E(P6, B4, RT.PROBLEM_TO_BLIND_SPOT),
    E(RC20, P5, RT.ROOT_CAUSE_TO_PROBLEM),          # shared node -> dedup
    E(RC30, P8, RT.ROOT_CAUSE_TO_PROBLEM),          # disconnected component
    E(P8, B9, RT.PROBLEM_TO_BLIND_SPOT),
]


def svc(nodes=NODES, edges=EDGES, **kw):
    return build_knowledge_graph_service(InMemoryKnowledgeGraphRepository(nodes, edges), **kw)


def ids(view):
    return {n.node_id for n in view.nodes}


# --- Traversal --------------------------------------------------------------


def test_single_root_cause_traversal():
    v = svc().expand([10])
    assert ids(v) == {"root_cause:10", "problem:5", "blind_spot:3", "intervention:7", "recommendation:2"}
    assert v.metadata.edge_count == 4
    assert v.metadata.traversal_depth == 2
    assert v.metadata.truncated is False


def test_multiple_root_causes():
    v = svc().expand([10, 20])
    assert ids(v) == {
        "root_cause:10", "root_cause:20", "problem:5", "problem:6",
        "blind_spot:3", "blind_spot:4", "intervention:7", "recommendation:2",
    }


def test_duplicate_node_removal():
    v = svc().expand([10, 20])
    # problem:5 is linked by both RC10 and RC20 -> appears once as a node...
    assert sum(1 for n in v.nodes if n.node_id == "problem:5") == 1
    # ...but both edges into it are kept.
    into_p5 = [e for e in v.edges if e.target == "problem:5"]
    assert {e.source for e in into_p5} == {"root_cause:10", "root_cause:20"}


def test_traversal_depth_limit_truncates():
    v = svc().expand([10], max_depth=1)
    assert ids(v) == {"root_cause:10", "problem:5", "intervention:7"}
    assert v.metadata.edge_count == 2
    assert v.metadata.traversal_depth == 1
    assert v.metadata.truncated is True


def test_relationship_typing_and_counts():
    v = svc().expand([10])
    assert all(isinstance(e.relationship, RelationshipType) for e in v.edges)
    assert v.metadata.relationship_counts == {
        "root_cause_to_problem": 1,
        "problem_to_blind_spot": 1,
        "root_cause_to_intervention": 1,
        "intervention_to_recommendation": 1,
    }
    assert v.metadata.node_type_counts["root_cause"] == 1


# --- Fail-closed ------------------------------------------------------------


def test_unknown_root_cause_returns_empty():
    v = svc().expand([999])
    assert v.is_empty
    assert v.metadata.root_cause_ids == (999,)
    assert v.metadata.node_count == 0 and v.metadata.edge_count == 0


def test_empty_graph_returns_empty():
    v = svc(nodes=[], edges=[]).expand([10])
    assert v.is_empty


def test_dangling_edge_is_not_followed():
    # An edge pointing to a non-existent node must never invent that node.
    nodes = [RC10]
    edges = [GraphEdge("root_cause:10", "problem:404", RT.ROOT_CAUSE_TO_PROBLEM)]
    v = svc(nodes, edges).expand([10])
    assert ids(v) == {"root_cause:10"}
    assert v.metadata.edge_count == 0


# --- Cycles + disconnected --------------------------------------------------


def test_cycle_detection_terminates():
    c1, c2, c3 = N(NT.ROOT_CAUSE, 1), N(NT.PROBLEM, 1), N(NT.BLIND_SPOT, 1)
    cyclic_edges = [
        E(c1, c2, RT.ROOT_CAUSE_TO_PROBLEM),
        E(c2, c3, RT.PROBLEM_TO_BLIND_SPOT),
        E(c3, c1, RT.ROOT_CAUSE_TO_PROBLEM),        # back-edge -> cycle
    ]
    v = svc([c1, c2, c3], cyclic_edges).expand([1])
    assert v.metadata.node_count == 3               # each node exactly once
    assert v.metadata.edge_count == 3


def test_disconnected_components_stay_separate():
    v = svc().expand([10, 30])
    a = {"root_cause:10", "problem:5", "blind_spot:3", "intervention:7", "recommendation:2"}
    b = {"root_cause:30", "problem:8", "blind_spot:9"}
    assert ids(v) == a | b
    # No edge crosses between the two components.
    for e in v.edges:
        assert not (e.source in a and e.target in b)
        assert not (e.source in b and e.target in a)


# --- Determinism ------------------------------------------------------------


def test_deterministic_ordering():
    s = svc()
    first = s.expand([10, 20])
    assert all(s.expand([10, 20]) == first for _ in range(5))
    # Nodes are ordered by type (root_cause first, recommendation last).
    types = [n.node_type for n in first.nodes]
    assert types == sorted(types, key=lambda t: list(NodeType).index(t))


def test_expand_is_order_independent_for_root_ids():
    # The traversed graph is identical regardless of root-id order; only the
    # metadata echo of the requested ids reflects the caller's order.
    a, b = svc().expand([10, 20]), svc().expand([20, 10])
    assert a.nodes == b.nodes and a.edges == b.edges


# --- Neighbors + shortest path (future-ready) --------------------------------


def test_neighbors_returns_immediate_edges():
    n = svc().neighbors("root_cause:10")
    assert {e.target for e in n} == {"problem:5", "intervention:7"}


def test_shortest_path():
    assert svc().shortest_path("root_cause:10", "recommendation:2") == (
        "root_cause:10", "intervention:7", "recommendation:2")
    assert svc().shortest_path("root_cause:10", "nope:1") == ()


# --- M1 integration ---------------------------------------------------------


def test_expand_for_context_uses_top_findings():
    founder = FounderProfileContext(1, "Asha", 5, "Growth / Scaling", "SaaS")
    diagnosis = DiagnosisContext(42, Decimal("72"), "validate", False, "stable", "s", (), ())
    rcs = (
        RootCauseContext(10, "RC-010", "Weak activation", "Sales & Revenue", 1, "unconfirmed", Decimal("0.8"), True),
        RootCauseContext(999, "RC-999", "Unknown", "X", 2, "unconfirmed", Decimal("0.1"), False),
    )
    ctx = AllyContext(founder=founder, has_diagnosis=True, diagnosis=diagnosis, root_causes=rcs)
    v = svc().expand_for_context(ctx)
    assert isinstance(v, GraphView)
    assert v.metadata.root_cause_ids == (10,)       # only the top finding
    assert "problem:5" in ids(v)
