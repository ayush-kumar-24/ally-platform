"""Embedding migration 02/03 -- regenerate every vector with OpenAI.

Reads each row that has never been embedded, generates a new
text-embedding-3-small (1536-d) vector via the existing OpenAI embedding adapter,
and writes back the vector plus its metadata (embedding_model,
embedding_dimension, embedding_version).

"Never been embedded" means `embedding IS NULL OR embedding_model IS NULL`. The
second half matters as much as the first: several of these columns are NOT NULL,
so a seed file inserting new reference rows must supply a placeholder vector
(`array_fill(0, ARRAY[1536])`), and a zero vector is not NULL. Selecting on the
vector alone therefore skipped every seeded row while reporting nothing to do --
found on 1,213 questions that had been sitting unembedded and unnoticed.

Idempotent / resumable, and now genuinely so: progress commits every `_BATCH`
rows rather than once per table, so a killed run keeps what it finished. Run
01_resize_schema.sql first (it nulls and widens the columns), then this, then
03_verify_embeddings.py. Seeded rows need no 01 step -- they arrive already
needing 02.

Requires (env / .env):
    DATABASE_URL, OPENAI_API_KEY, EMBEDDING_PROVIDER=openai
    (EMBEDDING_MODEL / EMBEDDING_DIMENSION / EMBEDDING_VERSION default to
     text-embedding-3-small / 1536 / openai-3-small-v1)

Usage (from backend/):
    python -m scripts.embedding_migration.02_regenerate_embeddings            # all tables
    python -m scripts.embedding_migration.02_regenerate_embeddings --tables root_causes,problems
    python -m scripts.embedding_migration.02_regenerate_embeddings --dry-run  # embed nothing, just report counts
"""

from __future__ import annotations

import argparse
import pathlib
import sys

# Make `app` importable when run directly (this file lives in backend/scripts/...).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.services import embeddings

#: Rows per commit. Small enough that a killed run loses seconds of work, large
#: enough that the commit overhead stays invisible beside the provider call that
#: dominates each iteration.
_BATCH = 25

# table -> (primary key column, SQL expression for the text to embed).
# Adjust the text expressions to match how you want each corpus represented.
TABLES: dict[str, tuple[str, str]] = {
    "root_causes": ("root_cause_id", "COALESCE(root_cause_name,'') || ' — ' || COALESCE(explanation,'')"),
    "problems": ("problem_id", "COALESCE(problem_name,'') || ' — ' || COALESCE(description,'')"),
    "questions": ("question_id", "COALESCE(question_text,'')"),
    "agent_interpretations": ("interpretation_id", "COALESCE(founder_statement,'') || ' — ' || COALESCE(likely_root_cause,'')"),
    "behaviour_patterns": ("pattern_id", "COALESCE(pattern_name,'') || ' — ' || COALESCE(description,'')"),
    "archetypes": ("archetype_id", "COALESCE(archetype_name,'') || ' — ' || COALESCE(description,'')"),
    "rag_chunks": ("chunk_id", "COALESCE(chunk_text,'')"),
    # Added 2026-08-23: all 57 rows shipped with a NULL embedding, so the
    # founder-DNA bank was invisible to any similarity lookup. Same shape as
    # `questions` above -- the question text is the whole content.
    "founder_dna_questions": ("founder_dna_question_id", "COALESCE(question_text,'')"),
}


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(v):.8g}" for v in vector) + "]"


def migrate_table(engine, provider, table: str, dry_run: bool) -> tuple[int, int]:
    pk, text_expr = TABLES[table]
    with engine.connect() as conn:
        rows = conn.execute(
            # `embedding_model IS NULL` is the real "needs embedding" marker,
            # not `embedding IS NULL`. Seed files must supply a placeholder
            # zero-vector to satisfy the NOT NULL constraint, and a zero vector
            # is not NULL -- so the old predicate silently skipped every seeded
            # row. embedding_model is only ever written by this script (see the
            # UPDATE below), so it is null exactly when a row has never been
            # embedded here: true for a NULL vector and a placeholder alike.
            text(f"SELECT {pk} AS id, {text_expr} AS content FROM {table} "
                 f"WHERE embedding IS NULL OR embedding_model IS NULL "
                 f"ORDER BY {pk}")
        ).mappings().all()

    pending = len(rows)
    if dry_run:
        print(f"  {table}: {pending} row(s) would be embedded (dry-run)")
        return pending, 0

    done = 0
    # Committed in batches, not once per table. The whole table used to be one
    # transaction, which made "resumable" true only if the process was allowed
    # to finish -- a run embedding 1,213 questions was killed partway and every
    # one rolled back, discarding 20 minutes of paid-for provider calls.
    with engine.connect() as conn:
        for row in rows:
            vector = provider.embed(row["content"] or "")
            conn.execute(
                text(
                    # CAST(...), not `:vec::vector`. SQLAlchemy's text() parser
                    # does not bind `:vec` when a `::` cast follows it
                    # immediately -- it left the token in the SQL verbatim and
                    # Postgres answered "syntax error at or near :". Every other
                    # parameter in the same statement bound correctly, which is
                    # what made this look like a pgvector problem rather than a
                    # parsing one. Affected every table, not just one.
                    f"UPDATE {table} SET embedding = CAST(:vec AS vector), "
                    "embedding_model = :model, embedding_dimension = :dim, "
                    f"embedding_version = :ver WHERE {pk} = :id"
                ),
                {
                    "vec": _vector_literal(vector),
                    "model": settings.EMBEDDING_MODEL,
                    "dim": settings.EMBEDDING_DIMENSION,
                    "ver": settings.EMBEDDING_VERSION,
                    "id": row["id"],
                },
            )
            done += 1
            if done % _BATCH == 0:
                conn.commit()
                print(f"  {table}: {done}/{pending}", flush=True)
        conn.commit()          # whatever the last partial batch left
    print(f"  {table}: {done}/{pending} embedded", flush=True)
    return pending, done


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate embeddings with OpenAI.")
    parser.add_argument("--tables", help="comma-separated subset of tables (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="report counts, embed nothing")
    args = parser.parse_args()

    selected = (
        [t.strip() for t in args.tables.split(",")] if args.tables else list(TABLES)
    )
    unknown = [t for t in selected if t not in TABLES]
    if unknown:
        print(f"Unknown table(s): {unknown}. Known: {list(TABLES)}", file=sys.stderr)
        return 2

    provider = None
    if not args.dry_run:
        # OpenAI adapter, built from settings (needs OPENAI_API_KEY).
        provider = embeddings.get_provider("openai")
        if provider.dimension != settings.EMBEDDING_DIMENSION:
            print(
                f"Provider dimension {provider.dimension} != EMBEDDING_DIMENSION "
                f"{settings.EMBEDDING_DIMENSION}; aborting.",
                file=sys.stderr,
            )
            return 2
        print(f"Provider: {provider.name}/{provider.model} ({provider.dimension}-d)")

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    total_pending = total_done = 0
    for table in selected:
        pending, done = migrate_table(engine, provider, table, args.dry_run)
        total_pending += pending
        total_done += done

    verb = "would embed" if args.dry_run else "embedded"
    print(f"\nDone. {verb} {total_done if not args.dry_run else total_pending} row(s) "
          f"across {len(selected)} table(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
