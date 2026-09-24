# Rebuilding this platform from nothing

If the Supabase project is lost, this is the procedure. It is written to be
followed by someone who did not build the system.

**This procedure has been run end to end against an empty Postgres and it
works.** Every table comes back and the reasoning engine boots on the result.
It was not obvious that it would: getting here found a broken migration graph,
six pieces of schema that existed only in the database, and a silent row-drop
that would have cost the engine a rule it cannot start without. Those are
fixed; what follows is the tested path.

It has since been run again, from nothing, on other machines, and taken further
than a row count: founder journeys were run against the result and each
produced a report. A database this procedure rebuilds is not merely populated;
it runs the product.

## Read this before you run it

**The snapshot in `data/reference/` can be older than `alembic/versions/`, and
when it is, step 4 below will silently destroy content the migrations just
seeded.** This is not hypothetical. It happened on 2026-09-24:

* the snapshot was last taken on 2026-09-17
* the industry work landed on 2026-09-18 and after
* `02_industries.sql` holds **4** industries; the migrations seed **30**
* `18_questions.sql` has **no `industry_relevance` column at all**, and 3,340
  rows against the migrations' 5,140

Step 4 does `delete from <table>` and then reloads from the snapshot, so a
rebuild following this file exactly came up with 4 industries, every one of the
1,800 industry-specific questions demoted to universal, and the entire
industry-adaptive feature dead. Nothing errored. The feature fails **open** by
design, so a stage-6 SaaS founder was simply asked **zero** questions written
for her industry, and the report looked normal.

### The stopgap, and what it costs

A rebuild done today therefore has no clean path. Skipping the six files the
migrations are ahead on keeps the industry feature alive:

```
02_industries  12_problems  14_root_causes
16_interventions  18_questions  19_question_tag_mapping
```

**Do not mistake that for a fix. It buys the industry feature by breaking
recommendations.** The interventions in those two sources are disjoint by
problem: the migrations cover problems **276-725** (the newer dimension layer),
`16_interventions.sql` covers **1-269** (the original catalogue, 417 rows over
267 distinct problems). Keep either one alone and half the root-cause catalogue
can no longer reach an intervention -- 2,009 of 3,996 skipping the file, 2,023
of 3,996 loading it the documented way.

Problems **270-275** are covered by NEITHER source: 6 problems carrying 36 root
causes, which reach no intervention on any database, the live one included.
That is the 0.9% the threshold in `verify_seed_data` is calibrated around, and
it is a real content gap rather than a rebuild artifact -- worth filling, but
not something a restore can fix. A diagnosis landing there produces a report that names three
root causes and recommends nothing, with `recommended_intervention_ids`,
`priority_actions` and `next_steps` all empty and no error anywhere.

Loading the file *without* the delete does not work either, and it is worth
saying why so nobody loses an afternoon to it: the file's `intervention_id`
values are 45-499 and the migrations already occupy 1-1024, so every row
collides and `on conflict do nothing` silently inserts **zero**. That is the
same surrogate-key collision the delete in step 4 exists to prevent, biting
from the other side.

**The only real fix is to re-run the dump.** The live database holds both sets
reconciled -- 1,440 interventions, ids 45-1522, covering 717 of 723 problems --
so a current snapshot needs no skip list at all, for interventions or for
anything else. Until that dump is re-run, a rebuilt database is good enough to
exercise the engine and not good enough to judge a recommendation.

### What is not optional

1. **Keep the snapshot current.** Re-run the dump whenever the question bank,
   root causes, weights, industries, interventions or scoring rules change --
   see *Producing the dump* at the bottom -- and commit the diff. `--check`
   exits non-zero on drift, so CI can notice the snapshot ageing instead of a
   disaster discovering it.
2. **Always run `verify_seed_data` after step 4 and believe it.** Two of its
   sections exist because of exactly this: `== Industry-adaptive selection ==`
   and `== Interventions reachable from root causes ==`. The second one fails
   on BOTH one-sided intervention loads, by design, because both are wrong. A
   rebuild that passes everything except those sections is a rebuild with a
   dead feature, not a working database with a cosmetic warning.

## What is where

| | Lives in | Safe if the database is lost? |
| --- | --- | --- |
| Schema (tables, indexes, RLS) | `alembic/versions/` | Yes |
| Reference content (questions, root causes, weights, rules, prompts) | `data/reference/` | **Only as of the last dump** |
| Embeddings | Nowhere — derived | Yes, regenerable from the text |
| Founder data (answers, reports, accounts) | The database only | **No. Backups are the only protection.** |

Founder data is deliberately not in git and never should be. Protecting it is a
question of database backups, not of this file.

## Before you start

Create the `ally_app` role. Every migration that creates an RLS policy for it
skips that policy, with a warning, when the role does not exist — and the
warning says skipping is expected on Supabase but **not** on RDS, which is what
production runs. Restoring into a fresh database without the role means the
founder-isolation policies on `founder_goals`, `achievements`, `vision` and
`framework_usage` will not exist. See the `ally_app` section of
`../DEPLOY_AWS.md`.

```sql
CREATE ROLE ally_app LOGIN PASSWORD '<from the secret store>';
```

## The rebuild

The order matters and is not obvious. Migration `63340a6e5fdb` seeds questions
2130+ and *asserts* that 1-2129 already exist, so some reference data has to be
loaded in the middle of the migration run, not after it.

```bash
# 0. Extensions the schema assumes.
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;" \
                     -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 1. Schema up to but not including the seed gate.
alembic upgrade c6a4e83f19d7

# 2. The rows the seeding migrations need in order to run: questions 1-2129 and
#    the foreign-key parents they point at. These files stop short of the ids
#    the migrations seed themselves -- each one says which range and why.
for f in data/reference/00*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "set session_replication_role=replica;" -f "$f"
done

# 3. The rest of the migrations, which seed questions 2130+ on top.
#
#    The weights trigger has to come off for this. Migration d3e8b41c9a52 seeds
#    WEIGHT_EVIDENCE_BREADTH at 0.0000 and then swaps the budget in a single
#    UPDATE, so the invariant holds at every check point -- but only on a
#    database where the four original weights are ALREADY loaded. On a rebuild
#    they are not, the running sum is 0.0000, and check_scoring_weights_sum()
#    rejects the insert:
#      RuntimeError: Scoring weight factors must sum to 1.0. Current sum: 0.0000
#    The rows are validated properly by verify_seed_data in step 5.
psql "$DATABASE_URL" -c "ALTER TABLE scoring_rules DISABLE TRIGGER validate_scoring_weights"
alembic upgrade head
psql "$DATABASE_URL" -c "ALTER TABLE scoring_rules ENABLE TRIGGER validate_scoring_weights"

# 4. The full snapshot. DELETE FIRST: migrations seed some of these tables with
#    DIFFERENT surrogate keys than production uses, and an insert-only load
#    silently skips those rows. That is not hypothetical -- it dropped
#    CAT_RISK_THRESHOLD, without which the reasoning engine will not start,
#    because rule_id 1 was already taken by a different rule.
#
#    READ "The stopgap, and what it costs" AT THE TOP OF THIS FILE FIRST.
#    This step is only safe when the snapshot is at least as new as the
#    migration graph. It is not, today. Step 5 is what tells you whether it
#    was, and with the snapshot as it stands it WILL fail -- on the industry
#    section if you run this loop as written, and on the intervention section
#    if you skip the six stale files instead. Both failures are real. Neither
#    is fixed here; both are fixed by re-running the dump.
for f in data/reference/[0-9][0-9]_*.sql; do
  t=$(basename "$f" .sql | sed 's/^[0-9]*_//')
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
    -c "set session_replication_role=replica;" -c "delete from \"$t\";" -f "$f"
done

# 5. PROVE IT. Not optional, and not a formality -- this is the step that
#    distinguishes a restored database from a populated one. Read every
#    failure as real; none of them is cosmetic, and the two that this
#    procedure currently provokes are described at the top of the file.
python -m scripts.verify_seed_data

# 6. Embeddings. Semantic retrieval returns nothing until this finishes.
python -m scripts.embedding_migration.02_regenerate_embeddings
```

`session_replication_role = replica` disables foreign-key checks and triggers
for the load, the same thing `pg_dump --disable-triggers` does. Without it the
files have to be loaded in dependency order *and* a validation trigger on
`scoring_rules` rejects the table halfway through, because it checks a sum that
is only correct once every row is in.

## Confirming it actually works

`verify_seed_data` (step 5) must exit zero. Then run a real journey, which is
the only proof that counts:

```bash
python -m scripts.e2e_journey_check --database-url "..." --stage 1 --confirm-writes
```

A journey that completes and produces a report is the real proof; a table count
is not. Two things to look at in its output beyond "it finished":

* **`model calls this run`**. Zero means nothing reached a model. Every answer
  then falls back to amber, every pillar scores an identical 50, and the report
  is structurally complete but diagnostically empty. Check `ANTHROPIC_API_KEY`.
* **Whether industry questions were asked.** Run
  `python -m scripts.qa.industry_selection_preflight --preflight` — it reports
  the mapping rows, the linked founders and the industry-owned questions in the
  bank, and says in one line whether the feature is live on that database.

## Producing the dump

```bash
python -m scripts.dump_reference_data --database-url "..." --write
git add backend/data/reference && git commit
```

Re-run it whenever the question bank, root causes, weights, industries, prompts
or scoring rules change, and commit the diff. The script writes
deterministically — same data, same bytes — so a diff shows what actually
changed.

`--check` compares a live database against what is committed and exits non-zero
on drift. Point it at the live database from CI and the snapshot cannot go
stale unnoticed again.

The dump needs a real Postgres connection, not the Supabase REST API. From a
network that cannot open port 5432 or 6543 to the database, it cannot run at
all — which is worth knowing before a disaster, not during one.

### What the next dump is expected to change

Measured against the live Supabase project on 2026-09-24, so the diff can be
read rather than merely trusted:

| File | Committed | Live |
| --- | --- | --- |
| `02_industries.sql` | 4 | **30**, each with `top_pain_point_weights` |
| `18_questions.sql` | 3,340, no `industry_relevance` column | **5,140**, 1,800 carrying an industry |
| `12_problems.sql` | 273 | **723** |
| `14_root_causes.sql` | 2,009 | **3,996** |
| `16_interventions.sql` | 417 | **1,440** |
| `19_question_tag_mapping.sql` | 6,559 | **8,359** |
| `04_scoring_rules.sql` | 47 | 47 |

`24_prompt_library.sql` was added in the same change and is already current —
its 7 rows were verified byte-identical to the live table. Nothing in
`alembic/versions/` seeds that table, so until it was dumped the live databases
were the only copy of the LLM prompts, which is precisely the situation
`dump_reference_data.py` exists to end.

A rebuild done from the committed snapshot before that dump is re-run fails
step 5 whichever way it is done, and that is the guard working rather than a
broken procedure:

* run step 4 as written and it fails on **industries**, **the industry
  questions** and **the orphaned mappings** — the industry feature is dead
* skip the six stale files instead and it fails on **interventions reachable
  from root causes** — half the catalogue can recommend nothing

Re-running the dump is what clears both at once. Nothing else does.
