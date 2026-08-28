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


# --- sales-collateral content gate ------------------------------------------

def _sales_collateral_chunk(db):
    """A real (chunk_id, vector) tagged content_class=sales_collateral, or None."""
    row = db.execute(text(
        "select chunk_id, embedding::text from rag_chunks "
        "where metadata_tags->>'content_class' = 'sales_collateral' "
        "and embedding is not null limit 1"
    )).first()
    if row is None:
        return None
    cid, emb = row
    return cid, json.loads(emb)


def test_build_sql_gates_sales_collateral_by_default():
    """Hermetic: the RAG_CHUNKS SQL excludes recommendation-only / sales-collateral
    rows by default, and only a privileged retrieval drops the guard."""
    from app.services.retrieval.engine import SOURCE_SPECS

    eng = RetrievalEngine(None, embedder=None)
    spec = SOURCE_SPECS[RetrievalSource.RAG_CHUNKS]
    default_sql = eng._build_sql(spec)
    privileged_sql = eng._build_sql(spec, include_restricted=True)
    assert "sales_collateral" in default_sql and "recommendation_only" in default_sql
    assert "sales_collateral" not in privileged_sql
    # A source without a restricted_where is unaffected either way.
    rc_sql = eng._build_sql(SOURCE_SPECS[RetrievalSource.ROOT_CAUSES])
    assert "sales_collateral" not in rc_sql


def test_sales_collateral_excluded_from_default_search_live(db):
    """Even querying with the collateral chunk's OWN vector (similarity ~1.0), the
    default retrieval must not return it; a privileged retrieval must."""
    data = _sales_collateral_chunk(db)
    if data is None:
        pytest.skip("no sales_collateral chunk embedded in the DB")
    cid, vec = data
    eng = RetrievalEngine(db, embedder=None, expected_dimension=len(vec))
    default_ids = [e.source_id for e in eng.search_by_vector(
        vec, sources=(RetrievalSource.RAG_CHUNKS,), k=10)]
    privileged_ids = [e.source_id for e in eng.search_by_vector(
        vec, sources=(RetrievalSource.RAG_CHUNKS,), k=10, include_restricted=True)]
    assert cid not in default_ids          # gated out despite being its own vector
    assert cid in privileged_ids           # visible only to a deliberate recommendation


def test_rag_root_cause_filter_is_applied_before_vector_top_k():
    """RAG root-cause linkage must constrain candidates inside the inner SQL."""
    from app.services.retrieval.engine import SOURCE_SPECS

    eng = RetrievalEngine(None, embedder=None)
    spec = SOURCE_SPECS[RetrievalSource.RAG_CHUNKS]

    sql = eng._build_sql(spec, ("root_cause_code",))

    assert "jsonb_exists(metadata_tags->'maps_to_root_causes'" in sql
    assert ":flt_root_cause_code" in sql
    assert sql.index("jsonb_exists") < sql.index("ORDER BY")
