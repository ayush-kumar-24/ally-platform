# Rebuilding this platform from nothing

If the Supabase project is lost, this is the procedure. It is written to be
followed by someone who did not build the system.

**This procedure has been run end to end against an empty Postgres and it
works.** Every table comes back at production's row count and the reasoning
engine boots on the result. It was not obvious that it would: getting here
found a broken migration graph, six pieces of schema that existed only in the
database, and a silent row-drop that would have cost the engine a rule it
cannot start without. Those are fixed; what follows is the tested path.

It has since been run a second time, from nothing, on a different machine,
and taken further than a row count: four complete founder journeys were run
against the result — two personas at Ideation and two at Early Traction —
and each produced a report, the stage-4 pair assessing all six pillars. A
database this procedure rebuilds is not merely populated; it runs the product.

That second run also turned up something a table count cannot see. Every
migration that creates an RLS policy for the `ally_app` role skips it, with a
warning, when the role does not exist — and says in the warning that skipping
is expected on Supabase but **not on RDS**, which is what production runs on.
Restoring into a fresh database means creating that role first, or the
founder-isolation policies on `founder_goals`, `achievements`, `vision` and
`framework_usage` will not exist. See the `ally_app` section of
`../DEPLOY_AWS.md`.

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

The order matters and is not obvious. Migration `63340a6e5fdb` seeds questions
2130+ and *asserts* that 1-2129 already exist, so some reference data has to be
loaded in the middle of the migration run, not after it.

```bash
# 1. Schema up to but not including the seed gate.
alembic upgrade c6a4e83f19d7

# 2. The rows the seeding migrations need in order to run: questions 1-2129 and
#    the foreign-key parents they point at. These files stop short of the ids
#    the migrations seed themselves -- each one says which range and why.
for f in data/reference/00*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "set session_replication_role=replica;" -f "$f"
done

# 3. The rest of the migrations, which seed questions 2130+ on top.
alembic upgrade head

# 4. The full snapshot. DELETE FIRST: migrations seed some of these tables with
#    DIFFERENT surrogate keys than production uses, and an insert-only load
#    silently skips those rows. That is not hypothetical -- it dropped
#    CAT_RISK_THRESHOLD, without which the reasoning engine will not start,
#    because rule_id 1 was already taken by a different rule.
for f in data/reference/[0-9][0-9]_*.sql; do
  t=$(basename "$f" .sql | sed 's/^[0-9]*_//')
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
    -c "set session_replication_role=replica;" -c "delete from \"$t\";" -f "$f"
done

# 5. Embeddings. Semantic retrieval returns nothing until this finishes.
python -m scripts.embedding_migration.02_regenerate_embeddings
```

`session_replication_role = replica` disables foreign-key checks and triggers
for the load, the same thing `pg_dump --disable-triggers` does. Without it the
files have to be loaded in dependency order *and* a validation trigger on
`scoring_rules` rejects the table halfway through, because it checks a sum that
is only correct once every row is in.

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
