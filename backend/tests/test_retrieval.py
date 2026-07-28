"""RetrievalEngine against the real seeded embeddings (read-only, live DB).

Rewritten for the current API: the old `similarity_search` helper was refactored
into `RetrievalEngine`. Also covers the stage/category/problem pre-filter.
"""

import json

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.retrieval.engine import RetrievalEngine, RetrievalError
from app.services.retrieval.evidence import RetrievalSource


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _embedded_root_cause(db):
    """A real (root_cause_id, vector, category) with an embedding, or None."""
    row = db.execute(text(
        "select root_cause_id, embedding::text, root_cause_category "
        "from root_causes where embedding is not null limit 1"
    )).first()
    if row is None:
        return None
    rid, emb, category = row
    return rid, json.loads(emb), category


def test_search_returns_self_as_top_match(db):
    data = _embedded_root_cause(db)
    if data is None:
        pytest.skip("no embedded root_causes in the DB")
    rid, vec, _ = data
    eng = RetrievalEngine(db, embedder=None, expected_dimension=len(vec))
    results = eng.search_by_vector(vec, sources=(RetrievalSource.ROOT_CAUSES,), k=3)
    assert len(results) == 3
    assert results[0].source_id == rid                     # itself, first
    assert float(results[0].similarity) > 0.99
    assert results[0].similarity >= results[1].similarity >= results[2].similarity


def test_wrong_dimension_rejected(db):
    eng = RetrievalEngine(db, embedder=None, expected_dimension=384)
    with pytest.raises(RetrievalError):
        eng.search_by_vector([0.0] * 10, sources=(RetrievalSource.ROOT_CAUSES,), k=5)


def test_prefilter_scopes_results_to_category(db):
    """The pre-filter restricts candidates before the vector top-k: every hit is
    within the requested category."""
    data = _embedded_root_cause(db)
    if data is None:
        pytest.skip("no embedded root_causes in the DB")
    _, vec, category = data
    eng = RetrievalEngine(db, embedder=None, expected_dimension=len(vec))
    results = eng.search_by_vector(
        vec, sources=(RetrievalSource.ROOT_CAUSES,), k=10, filters={"category": category}
    )
    assert results  # at least the seed row itself
    assert all(r.metadata.get("root_cause_category") == category for r in results)
