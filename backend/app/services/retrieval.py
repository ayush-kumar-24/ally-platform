"""Vector similarity search over the embedded reference tables (pgvector).

Cosine similarity using the hnsw indexes. The caller supplies the query vector;
the diagnosis engine will generate it from text via the embedding model, so this
layer stays model-agnostic and testable on its own.

Table names are whitelisted (SEARCHABLE) and never taken from user input, so the
table/column names interpolated into SQL are always safe; the query vector is a
bound parameter.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

# table -> (id column, human-readable label column). Only these are searchable.
SEARCHABLE: dict[str, tuple[str, str]] = {
    "root_causes": ("root_cause_id", "root_cause_name"),
    "problems": ("problem_id", "problem_name"),
    "questions": ("question_id", "question_text"),
    "agent_interpretations": ("interpretation_id", "founder_statement"),
    "behaviour_patterns": ("pattern_id", "pattern_name"),
}

EMBEDDING_DIM = 384


def to_vector_literal(vec) -> str:
    """Render a Python vector as the pgvector text form '[v1,v2,...]'."""
    if not isinstance(vec, (list, tuple)):
        raise ValueError("query_vector must be a list of floats")
    if len(vec) != EMBEDDING_DIM:
        raise ValueError(f"query_vector must have {EMBEDDING_DIM} dims, got {len(vec)}")
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def similarity_search(db: Session, table: str, query_vector, k: int = 5) -> list[dict]:
    """Top-k nearest rows in `table` by cosine similarity.

    Returns dicts of {id, label, score} where score is cosine similarity in
    [0, 1] (1 = identical). Uses `<=>` (cosine distance) to hit the hnsw index.
    """
    if table not in SEARCHABLE:
        raise ValueError(f"{table!r} is not searchable (allowed: {sorted(SEARCHABLE)})")
    if k < 1:
        raise ValueError("k must be >= 1")

    id_col, label_col = SEARCHABLE[table]
    qv = to_vector_literal(query_vector)

    stmt = text(
        f"SELECT {id_col} AS id, {label_col} AS label, "
        f"       1 - (embedding <=> CAST(:qv AS vector)) AS score "
        f"FROM {table} "
        f"WHERE embedding IS NOT NULL "
        f"ORDER BY embedding <=> CAST(:qv AS vector) "
        f"LIMIT :k"
    )
    rows = db.execute(stmt, {"qv": qv, "k": k}).mappings().all()
    return [dict(r) for r in rows]
