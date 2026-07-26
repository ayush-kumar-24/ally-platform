"""Vector similarity search helper, against the real seeded embeddings (read-only)."""

import json

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.retrieval import similarity_search


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_search_returns_self_as_top_match(db):
    # a vector that IS in the set should rank itself first with score ~1.0
    row = db.execute(text(
        "select root_cause_id, embedding::text from root_causes where embedding is not null limit 1"
    )).first()
    rid, emb = row
    results = similarity_search(db, "root_causes", json.loads(emb), k=3)
    assert len(results) == 3
    assert results[0]["id"] == rid
    assert results[0]["score"] > 0.99
    # scores are sorted descending
    assert results[0]["score"] >= results[1]["score"] >= results[2]["score"]


def test_unknown_table_rejected(db):
    with pytest.raises(ValueError, match="not searchable"):
        similarity_search(db, "founders", [0.0] * 384, k=5)


def test_wrong_dimension_rejected(db):
    with pytest.raises(ValueError, match="dims"):
        similarity_search(db, "root_causes", [0.0] * 10, k=5)
