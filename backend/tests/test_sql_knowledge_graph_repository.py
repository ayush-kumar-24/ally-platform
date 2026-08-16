"""SqlKnowledgeGraphRepository -- live conformance, read-only.

Uses a real DB session but never writes: root_causes/problems/interventions
have several NOT NULL columns (including vector embeddings) that make inserting
throwaway fixture rows heavier than it's worth here, so this reads real existing
rows instead. Picks its own fixtures from the live data rather than hardcoding
ids, so it stays valid as the seed data evolves.
"""

import pytest

from app.api.v1.ally.kg.schemas import (
    GraphEdge,
    NodeType,
    RelationshipType,
    intervention_node_id,
    problem_node_id,
    root_cause_node_id,
)
from app.api.v1.ally.kg.sql_repository import SqlKnowledgeGraphRepository
from app.db.session import SessionLocal
from sqlalchemy import text


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def repo(db):
    return SqlKnowledgeGraphRepository(db)


def _a_root_cause_with_problem(db):
    return db.execute(text(
        "SELECT root_cause_id, root_cause_name, problem_id FROM root_causes "
        "WHERE problem_id IS NOT NULL ORDER BY root_cause_id LIMIT 1"
    )).mappings().first()


def _a_root_cause_with_intervention(db):
    row = db.execute(text(
        "SELECT intervention_id, root_cause_ids FROM interventions "
        "WHERE jsonb_array_length(root_cause_ids) > 0 ORDER BY intervention_id LIMIT 1"
    )).mappings().first()
    if row is None:
        return None, None
    code = row["root_cause_ids"][0]
    rc = db.execute(
        text("SELECT root_cause_id FROM root_causes WHERE root_cause_code = :code"), {"code": code}
    ).first()
    return (rc[0] if rc else None), row["intervention_id"]


# --- get_node -----------------------------------------------------------------

def test_get_node_root_cause(db, repo):
    row = _a_root_cause_with_problem(db)
    if row is None:
        pytest.skip("no root_causes with a problem_id in this DB")
    node = repo.get_node(root_cause_node_id(row["root_cause_id"]))
    assert node is not None
    assert node.node_type == NodeType.ROOT_CAUSE
    assert node.ref_id == row["root_cause_id"]
    assert node.label == row["root_cause_name"]


def test_get_node_problem(db, repo):
    row = _a_root_cause_with_problem(db)
    if row is None:
        pytest.skip("no root_causes with a problem_id in this DB")
    node = repo.get_node(problem_node_id(row["problem_id"]))
    assert node is not None
    assert node.node_type == NodeType.PROBLEM


def test_get_node_unknown_returns_none(repo):
    assert repo.get_node("root_cause:99999999") is None


def test_get_node_unmodelled_type_returns_none(repo):
    # blind_spot has no data source in this partial implementation -- must
    # fail closed to "not found", never fabricate a node.
    assert repo.get_node("blind_spot:1") is None


def test_get_node_malformed_id_returns_none(repo):
    assert repo.get_node("not-a-valid-id") is None
    assert repo.get_node("root_cause:not-a-number") is None


# --- outgoing -------------------------------------------------------------------

def test_outgoing_includes_problem_edge(db, repo):
    row = _a_root_cause_with_problem(db)
    if row is None:
        pytest.skip("no root_causes with a problem_id in this DB")
    edges = repo.outgoing(root_cause_node_id(row["root_cause_id"]))
    expected = GraphEdge(
        source=root_cause_node_id(row["root_cause_id"]),
        target=problem_node_id(row["problem_id"]),
        relationship=RelationshipType.ROOT_CAUSE_TO_PROBLEM,
    )
    assert expected in edges


def test_outgoing_resolves_intervention_via_code_not_integer_id(db, repo):
    # The regression this test exists for: interventions.root_cause_ids stores
    # the root cause's CODE ("RC-001"), not its integer root_cause_id. An
    # implementation that queries by integer id silently returns nothing.
    rc_id, intervention_id = _a_root_cause_with_intervention(db)
    if rc_id is None:
        pytest.skip("no root_cause code in interventions.root_cause_ids resolved to a real row")
    edges = repo.outgoing(root_cause_node_id(rc_id))
    targets = {e.target for e in edges if e.relationship == RelationshipType.ROOT_CAUSE_TO_INTERVENTION}
    assert intervention_node_id(intervention_id) in targets


def test_outgoing_problem_and_intervention_nodes_are_leaves(db, repo):
    row = _a_root_cause_with_problem(db)
    if row is None:
        pytest.skip("no root_causes with a problem_id in this DB")
    # Partial coverage is deliberate: problem/intervention nodes have no
    # outgoing edges yet (blind_spot/recommendation have no data source).
    assert repo.outgoing(problem_node_id(row["problem_id"])) == ()


def test_outgoing_unknown_root_cause_is_empty(repo):
    assert repo.outgoing(root_cause_node_id(99999999)) == ()
