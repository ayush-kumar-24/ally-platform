"""Embedding migration 03/03 -- verify the migration.

For every embedded table, confirms:
  * every non-null vector is exactly 1536 dimensions,
  * every embedded row records embedding_model = 'text-embedding-3-small',
and reports how many rows are still un-embedded (embedding IS NULL).

Exit code 0 = all good; 1 = at least one wrong dimension or wrong model; 2 = usage
error. Safe to run any time (read-only).

Usage (from backend/):
    python -m scripts.embedding_migration.03_verify_embeddings
"""

from __future__ import annotations

import pathlib
import sys

# Make `app` importable when run directly (this file lives in backend/scripts/...).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text

from app.core.config import settings

EXPECTED_DIM = 1536
EXPECTED_MODEL = "text-embedding-3-small"

TABLES = [
    "root_causes", "problems", "questions", "agent_interpretations",
    "behaviour_patterns", "archetypes", "rag_chunks",
]


def main() -> int:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    failures = 0

    print(f"Verifying: dim=={EXPECTED_DIM}, model=='{EXPECTED_MODEL}'\n")
    print(f"{'table':<24} {'embedded':>9} {'bad_dim':>8} {'bad_model':>10} {'null':>6}  status")
    print("-" * 72)

    with engine.connect() as conn:
        for table in TABLES:
            row = conn.execute(text(f"""
                SELECT
                  count(*) FILTER (WHERE embedding IS NOT NULL) AS embedded,
                  count(*) FILTER (WHERE embedding IS NOT NULL
                                   AND vector_dims(embedding) <> :dim) AS bad_dim,
                  count(*) FILTER (WHERE embedding IS NOT NULL
                                   AND embedding_model IS DISTINCT FROM :model) AS bad_model,
                  count(*) FILTER (WHERE embedding IS NULL) AS remaining_null
                FROM {table}
            """), {"dim": EXPECTED_DIM, "model": EXPECTED_MODEL}).mappings().one()

            ok = row["bad_dim"] == 0 and row["bad_model"] == 0
            if not ok:
                failures += 1
            status = "OK" if ok else "FAIL"
            print(f"{table:<24} {row['embedded']:>9} {row['bad_dim']:>8} "
                  f"{row['bad_model']:>10} {row['remaining_null']:>6}  {status}")

    print("-" * 72)
    if failures:
        print(f"\n{failures} table(s) FAILED verification.")
        return 1
    print("\nAll tables passed: every vector is 1536-d and text-embedding-3-small.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
