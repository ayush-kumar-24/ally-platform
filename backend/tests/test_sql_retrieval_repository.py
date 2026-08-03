"""SqlVectorRetrievalRepository -- live pgvector conformance.

Uses a real DB session and a deterministic FakeEmbedder (fixed vectors, no network
call) so results are exact and tests don't depend on/cost against the live OpenAI
API. Fixture rows are inserted directly with hand-picked embeddings so similarity
ordering is predictable; cleaned up in a finally block, in FK order.
"""

from decimal import Decimal

from sqlalchemy import text

from app.api.v1.ally.rag.schemas import RetrievalFilters, RetrievalRequest
from app.api.v1.ally.rag.sql_repository import SqlVectorRetrievalRepository
from app.db.session import SessionLocal

# rag_chunks.embedding is a fixed Vector(1536) column -- test vectors must match
# that width even though only the first few components carry any signal here.
_DIM = 1536


def _pad(pattern: list[float]) -> list[float]:
    return pattern + [0.0] * (_DIM - len(pattern))


class FakeEmbedder:
    """Returns a fixed vector regardless of input text -- deterministic, offline."""

    name = "fake"
    model = "fake-fixed"
    dimension = _DIM

    def __init__(self, vector):
        self._vector = vector

    def embed(self, text: str):
        return list(self._vector)


def _vec(values) -> str:
    return "[" + ",".join(str(v) for v in values) + "]"


def _insert_document(db, *, name, document_type="playbook", industry_tag=None,
                      stage_relevance=None, review_status="approved", is_active=True):
    row = db.execute(
        text(
            "INSERT INTO rag_documents (document_name, document_type, review_status, "
            "is_active, industry_tag, stage_relevance) "
            "VALUES (:name, :dtype, :status, :active, :industry, :stage) "
            "RETURNING document_id"
        ),
        {"name": name, "dtype": document_type, "status": review_status,
         "active": is_active, "industry": industry_tag, "stage": stage_relevance},
    ).first()
    db.commit()
    return row[0]


def _insert_chunk(db, *, document_id, chunk_index, text_content, embedding,
                   metadata_tags=None, is_active=True):
    import json
    row = db.execute(
        text(
            "INSERT INTO rag_chunks (document_id, chunk_index, chunk_text, embedding, "
            "metadata_tags, is_active) "
            "VALUES (:doc_id, :idx, :content, CAST(:emb AS vector), CAST(:tags AS jsonb), :active) "
            "RETURNING chunk_id"
        ),
        {"doc_id": document_id, "idx": chunk_index, "content": text_content,
         "emb": _vec(embedding), "tags": json.dumps(metadata_tags or {}), "active": is_active},
    ).first()
    db.commit()
    return row[0]


def _cleanup(*document_ids: int) -> None:
    db = SessionLocal()
    for doc_id in document_ids:
        db.execute(text("DELETE FROM rag_chunks WHERE document_id = :d"), {"d": doc_id})
        db.execute(text("DELETE FROM rag_documents WHERE document_id = :d"), {"d": doc_id})
    db.commit()
    db.close()


# --- basic search --------------------------------------------------------------


def test_returns_closest_chunk_first():
    # Against a real, populated corpus (a live table, not a hermetic fixture set),
    # only an exact-match fixture is a reliable top-1 -- anything less than that
    # can plausibly be outscored by genuine content, so this checks rank #1 and
    # similarity == 1.0 rather than a relative "close beats far" comparison.
    db = SessionLocal()
    doc_id = _insert_document(db, name="test: closest first")
    close_id = _insert_chunk(db, document_id=doc_id, chunk_index=0,
                              text_content="close match", embedding=_pad([1, 0]))
    try:
        repo = SqlVectorRetrievalRepository(db, FakeEmbedder(_pad([1, 0])), expected_dimension=_DIM)
        req = RetrievalRequest(query="q", filters=RetrievalFilters(top_k=5), top_k=5)
        results = repo.search(req)
        assert results[0].source_id == close_id
        assert results[0].similarity == Decimal("1.000000")
    finally:
        db.close()
        _cleanup(doc_id)


def test_min_similarity_excludes_weak_matches():
    db = SessionLocal()
    doc_id = _insert_document(db, name="test: min similarity")
    _insert_chunk(db, document_id=doc_id, chunk_index=0,
                  text_content="orthogonal", embedding=_pad([0, 1]))
    try:
        repo = SqlVectorRetrievalRepository(db, FakeEmbedder(_pad([1, 0])), expected_dimension=_DIM)
        req = RetrievalRequest(
            query="q", filters=RetrievalFilters(top_k=5, min_similarity=Decimal("0.9")), top_k=5,
        )
        results = repo.search(req)
        assert results == ()
    finally:
        db.close()
        _cleanup(doc_id)


# --- gating ----------------------------------------------------------------------


def test_sales_collateral_excluded_by_default():
    db = SessionLocal()
    doc_id = _insert_document(db, name="test: sales gate")
    restricted_id = _insert_chunk(
        db, document_id=doc_id, chunk_index=0, text_content="offering details",
        embedding=_pad([1, 0]), metadata_tags={"content_class": "sales_collateral",
                                                 "retrieval_scope": "recommendation_only"},
    )
    try:
        repo = SqlVectorRetrievalRepository(db, FakeEmbedder(_pad([1, 0])), expected_dimension=_DIM)
        req = RetrievalRequest(query="q", filters=RetrievalFilters(top_k=5), top_k=5)
        results = repo.search(req)
        assert restricted_id not in [c.source_id for c in results]

        req_allowed = RetrievalRequest(
            query="q", filters=RetrievalFilters(top_k=5, allow_sales_collateral=True), top_k=5,
        )
        results_allowed = repo.search(req_allowed)
        assert restricted_id in [c.source_id for c in results_allowed]
    finally:
        db.close()
        _cleanup(doc_id)


def test_unapproved_document_excluded():
    # An exact-match embedding (similarity 1.0) would rank #1 if it were included
    # at all -- so its absence from the top-5, against a live populated corpus, is
    # a reliable exclusion signal (unlike asserting the whole result set is empty).
    db = SessionLocal()
    doc_id = _insert_document(db, name="test: pending doc", review_status="pending")
    chunk_id = _insert_chunk(db, document_id=doc_id, chunk_index=0, text_content="pending content",
                              embedding=_pad([1, 0]))
    try:
        repo = SqlVectorRetrievalRepository(db, FakeEmbedder(_pad([1, 0])), expected_dimension=_DIM)
        req = RetrievalRequest(query="q", filters=RetrievalFilters(top_k=5), top_k=5)
        results = repo.search(req)
        assert chunk_id not in [c.source_id for c in results]
    finally:
        db.close()
        _cleanup(doc_id)


def test_inactive_chunk_excluded():
    db = SessionLocal()
    doc_id = _insert_document(db, name="test: inactive chunk")
    chunk_id = _insert_chunk(db, document_id=doc_id, chunk_index=0, text_content="stale",
                              embedding=_pad([1, 0]), is_active=False)
    try:
        repo = SqlVectorRetrievalRepository(db, FakeEmbedder(_pad([1, 0])), expected_dimension=_DIM)
        req = RetrievalRequest(query="q", filters=RetrievalFilters(top_k=5), top_k=5)
        results = repo.search(req)
        assert chunk_id not in [c.source_id for c in results]
    finally:
        db.close()
        _cleanup(doc_id)


# --- soft stage/industry filters (untagged is never wrongly excluded) ----------


def test_stage_filter_keeps_untagged_document():
    # Exact-match embedding -> guaranteed rank #1 regardless of how much real
    # corpus data also passes the filter, so this is robust as the live corpus
    # grows (unlike asserting an exact result count).
    db = SessionLocal()
    doc_id = _insert_document(db, name="test: untagged stage", stage_relevance=None)
    chunk_id = _insert_chunk(db, document_id=doc_id, chunk_index=0, text_content="general knowledge",
                              embedding=_pad([1, 0]))
    try:
        repo = SqlVectorRetrievalRepository(db, FakeEmbedder(_pad([1, 0])), expected_dimension=_DIM)
        req = RetrievalRequest(
            query="q", filters=RetrievalFilters(top_k=5, stages=("Stage 0",)), top_k=5,
        )
        results = repo.search(req)
        assert results[0].source_id == chunk_id
    finally:
        db.close()
        _cleanup(doc_id)


def test_stage_filter_excludes_different_stage():
    db = SessionLocal()
    doc_id = _insert_document(db, name="test: different stage", stage_relevance="Stage 1→10+")
    chunk_id = _insert_chunk(db, document_id=doc_id, chunk_index=0, text_content="scaling content",
                              embedding=_pad([1, 0]))
    try:
        repo = SqlVectorRetrievalRepository(db, FakeEmbedder(_pad([1, 0])), expected_dimension=_DIM)
        req = RetrievalRequest(
            query="q", filters=RetrievalFilters(top_k=5, stages=("Stage 0",)), top_k=5,
        )
        results = repo.search(req)
        assert chunk_id not in [c.source_id for c in results]
    finally:
        db.close()
        _cleanup(doc_id)


# --- dimension mismatch fails loud, not silently wrong --------------------------


def test_embedding_dimension_mismatch_raises():
    from app.services.retrieval.engine import RetrievalError

    db = SessionLocal()
    try:
        # Deliberately un-padded (2-d) against expected_dimension=1536 -- the point
        # of this test is the mismatch itself.
        repo = SqlVectorRetrievalRepository(db, FakeEmbedder([1, 0]), expected_dimension=_DIM)
        req = RetrievalRequest(query="q", filters=RetrievalFilters(top_k=5), top_k=5)
        try:
            repo.search(req)
            assert False, "expected RetrievalError"
        except RetrievalError:
            pass
    finally:
        db.close()
