# Rebuilding this platform from nothing

If the Supabase project is lost, this is the procedure. It is written to be
followed by someone who did not build the system.

**Read this first: as of today the procedure does not work, because step 3 has
nothing to load.** `scripts/dump_reference_data.py` exists and is tested; the
dump it produces has not been committed yet. Until it is, the live database is
the only copy of the product's content and this document describes an intention
rather than a capability. Generating it is one command — see *Producing the
dump* below.

## What is where

| | Lives in | Safe if the database is lost? |
| --- | --- | --- |
| Schema (tables, indexes, RLS) | `alembic/versions/` | Yes |
| Reference content (questions, root causes, weights, rules) | `data/reference/` | **Only once the dump is committed** |
| Embeddings | Nowhere — derived | Yes, regenerable from the text |
| Founder data (answers, reports, accounts) | The database only | **No. Backups are the only protection.** |

Founder data is deliberately not in git and never should be. Protecting it is a
question of database backups, not of this file.

## The rebuild

```bash
# 1. Schema, up to but not including the seed gate.
#    63340a6e5fdb asserts questions 1-2129 already exist, so it must not run yet.
alembic upgrade c6a4e83f19d7

# 2. Reference content, in filename order -- the numbers are the load order,
#    parents before children, so foreign keys hold throughout.
for f in data/reference/*.sql; do psql "$DATABASE_URL" -f "$f"; done

# 3. The rest of the migrations, which seed questions 2130+ on top.
alembic upgrade head

# 4. Embeddings. Semantic retrieval returns nothing until this finishes.
python -m scripts.embedding_migration.02_regenerate_embeddings
```

Then confirm it: `python -m scripts.verify_seed_data`, and run
`python -m scripts.e2e_journey_check --database-url "..." --stage 1 --confirm-writes`
against the restored database. A journey that completes and produces a report is
the real proof; a table count is not.

## Producing the dump

```bash
python -m scripts.dump_reference_data --database-url "..." --write
git add backend/data/reference && git commit
```

Re-run it whenever the question bank, root causes, weights or scoring rules
change, and commit the diff. The script writes deterministically — same data,
same bytes — so a diff shows what actually changed.

CI, or anyone, can check the dump has not gone stale:

```bash
python -m scripts.dump_reference_data --database-url "..." --check
```

Exit code 1 means the live database and the committed dump disagree. Note that
`scoring_rules` and friends carry a `set_updated_at` trigger, so touching a row
and changing it back still counts as a change — which is correct: the dump is a
snapshot, not a summary.

## Why embeddings are excluded

They are regenerable from the text sitting beside them, and they are almost all
of the bytes: the reference tables total about 104 MB with them and a few MB
without. A 1536-float vector in a diff is also unreadable — a one-word change to
a question would be invisible next to the vector that changed with it.

The cost is that step 4 is not optional. Skip it and the platform comes up
looking healthy while every semantically-retrieved answer is empty.
