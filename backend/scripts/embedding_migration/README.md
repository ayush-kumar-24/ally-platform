# Embedding migration: gte-small (384-d) → text-embedding-3-small (1536-d)

Moves every stored embedding from the local gte-small model (384-d) to OpenAI
`text-embedding-3-small` (1536-d), records provenance metadata, and rebuilds the
HNSW indexes. **Retrieval logic is unchanged** — it reads the dimension from
`EMBEDDING_DIMENSION` and searches with the cosine operator, both of which already
work at 1536.

## ⚠️ Read before running

- **Destructive & irreversible.** Step 01 sets every `embedding` to NULL to widen
  the column; the old gte-small vectors are gone. **Take a database backup first**
  (Supabase → Database → Backups, or `pg_dump`).
- **Retrieval is down between step 01 and the end of step 02** — all embeddings
  are NULL in that window. Run 02 immediately after 01.
- **Costs money.** ~1,500 rows are embedded via the paid OpenAI API
  (root_causes ~997, questions ~330, problems ~124, agent_interpretations ~31,
  behaviour_patterns ~27, rag_chunks ~34, archetypes). text-embedding-3-small is
  inexpensive, but it is a real API spend.
- **Shared production DB.** Coordinate with the team; ideally rehearse on a
  staging branch/database first.

## Prerequisites

Set in `backend/.env` (or the environment):

```
DATABASE_URL=postgresql+psycopg://...        # the target database
OPENAI_API_KEY=sk-...
EMBEDDING_PROVIDER=openai
# these default correctly after the config change, override only if needed:
# EMBEDDING_MODEL=text-embedding-3-small
# EMBEDDING_DIMENSION=1536
# EMBEDDING_VERSION=openai-3-small-v1
```

## Run order (from `backend/`)

```bash
# 0. BACKUP THE DATABASE FIRST.

# 1. Schema: resize 384 -> 1536, add metadata columns, rebuild indexes.
psql "$DATABASE_URL" -f scripts/embedding_migration/01_resize_schema.sql

# 2. Data: regenerate every vector with OpenAI (resumable; only NULL rows).
python scripts/embedding_migration/02_regenerate_embeddings.py
#    dry run first if you like:
python scripts/embedding_migration/02_regenerate_embeddings.py --dry-run

# 3. Verify: all vectors 1536-d and text-embedding-3-small.
python scripts/embedding_migration/03_verify_embeddings.py
```

`02` is idempotent — if it's interrupted, just run it again; it picks up the rows
still left as NULL. `03` exits non-zero if anything is wrong, so it can gate CI.

## What changed in code (already applied)

- `app/core/config.py`: `EMBEDDING_MODEL=text-embedding-3-small`,
  `EMBEDDING_DIMENSION=1536`, new `EMBEDDING_VERSION`.
- `app/models/schema.py`: `Vector(384) → Vector(1536)` on all seven embedded
  tables; the `rag_chunks.embedding_model` default is now text-embedding-3-small.
- The OpenAI embedding adapter and retrieval engine already read these settings —
  no retrieval code was modified.

## Notes

- **Alembic:** the schema step is delivered as raw SQL because the project's
  Alembic history currently has two un-merged heads (`055fcff2b6b5` and
  `6d05993bb818`). Once those are merged, wrap `01_resize_schema.sql` in a
  revision (`op.execute(...)`) so the change is tracked. Its downgrade can widen
  back to 384 but **cannot restore the gte-small vectors** (data was dropped).
- **Text represented per table** is defined at the top of
  `02_regenerate_embeddings.py` (`TABLES`). Adjust those expressions if you want a
  different text used for each corpus.
- **`rag_chunks.embedding`** was `NOT NULL`; step 01 relaxes it so the column can
  be cleared. Re-add `NOT NULL` after 02 if you want to enforce it (commented line
  at the end of the SQL).
- **Cross-model note:** 1536-d OpenAI vectors are not comparable to the old
  384-d gte-small vectors — that's exactly why every row is regenerated rather
  than converted.
