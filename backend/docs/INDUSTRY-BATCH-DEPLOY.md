# Handover: applying the industry content batches to production

For the AWS / DBA team. Forward this as-is.

**Two files come with this.** This document is instructions only and carries no data:

| File | What it is |
|---|---|
| `ally_batch1_PORTABLE_no_ids.sql` | **The data.** All 810 rows. This is the file to run. |
| this `.md` | How to run it, how to check it, how to undo it. |

**What this is:** new reference content (questions, problems, root causes, interventions)
for the diagnosis engine. It is **insert-only**. No schema change, no migration of existing
rows, nothing dropped or altered.

---

## 1. There is no id pre-check to do

The data file uses **no hardcoded primary keys**. Every id comes from the table's own
sequence, and every foreign key is resolved by code at insert time. So there is nothing
that can collide with what production already holds, and the file needs no edits for
your database.

It also pushes each sequence above its table's current max before inserting, which
repairs the common case where an earlier explicit-id load left a sequence behind its
own table.

Verified: applied to a database whose `problems` sequence had been deliberately set to 5,
and to one that already had the same content. It self-repaired, inserted the right rows,
and a second run inserted nothing and raised no error.

The file checks itself inside the transaction and refuses to commit a partial load:

```
NOTICE:  batch 1 ok: 45 problems, 135 root causes, 270 questions, 90 interventions, 270 mappings
COMMIT
```

If any count is short it raises and the whole batch rolls back.

Worth confirming once, before you start, that the target has the industry feature live —
otherwise the content has nothing to attach to:

```sql
select count(*) as industries from industries;                       -- expect 30
select count(*) as industry_mapped from question_industry_mapping;   -- expect 1800+
select version_num from alembic_version;                             -- expect c9f41b8e3a07
```

---

## 2. Migrations do NOT run on deploy — this is the part that catches people

The Dockerfile's `CMD` starts with `alembic upgrade head`, but the ECS task definition sets
an explicit `command` that **replaces** it:

```
Dockerfile CMD:   sh -c "alembic upgrade head && uvicorn app.main:app ..."
task definition:  uvicorn app.main:app --host 0.0.0.0 --port 8000
```

So shipping a deploy does **not** apply the migration. The schema silently stays as it was and
the failures show up later as missing-row or missing-column errors nobody connects back to the
deploy. This is documented in `DEPLOY.md` §1 and is on the go-live checklist.

Migrations must be run as a **one-off ECS task**.

---

## 3. Route A (preferred) — alembic, as a one-off ECS task

Version controlled, shows in `alembic_version`, has a working `downgrade()`.

**We place in the repo:**

| File | Path |
|---|---|
| The SQL | `backend/data/question_batches/batch1_industries_1to5.sql` |
| The migration | `backend/alembic/versions/<timestamp>-<rev>_batch1_industries_1to5.py` |

`down_revision` is `c9f41b8e3a07`. The migration reads the SQL file next to it and executes it
statement by statement.

**You run**, after the image containing those files is built and pushed:

```bash
aws ecs run-task --region ap-south-1 \
  --cluster ally-backend-cluster \
  --task-definition ally_backend_task:<rev> \
  --launch-type FARGATE --count 1 \
  --network-configuration "awsvpcConfiguration={subnets=[<subnet-a>,<subnet-b>],securityGroups=[<sg>],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"Main","command":["alembic","upgrade","head"]}]}'
```

This reuses the service's own image and secrets, so it reaches RDS with the same
`DATABASE_URL` and needs no credentials of your own.

Then: read the result from CloudWatch (`/ecs/ally-backend-task`, stream `ecs/Main/<task-id>`)
and **confirm the container `exitCode` is 0** before updating the service.

---

## 4. Route B (simplest) — apply the SQL directly

No image build needed. Same rows, same result. The only thing you give up is the
`alembic_version` audit trail, so use Route A if you want this recorded as a migration.

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f ally_batch1_industries_1to5.sql
```

The file is one `BEGIN … COMMIT`. `ON_ERROR_STOP=1` plus the single transaction means you get
all of it or none of it. It is safe to run twice — every insert is `ON CONFLICT DO NOTHING` on
its unique code.

RDS is in a VPC, so this needs to run from somewhere with network access to it — a bastion,
a one-off ECS task with `psql`, or your usual DBA path.

---

## 5. Verify after applying

The file verifies itself and refuses to commit a short load, so this is confirmation
rather than a real risk. Counts are by code, not by id.

```sql
select count(*) from problems
  where problem_code ~ '^(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]$';                       -- 45

select count(*) from root_causes
  where root_cause_code ~ '^RC-(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]-[0-9]$';           -- 135

select count(*) from questions
  where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]-[0-9]$';     -- 270

select count(*) from interventions
  where intervention_code ~ '^INT-(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]-[0-9]$';        -- 90

-- All nine dimension codes present for each of the five industries: expect 9 each.
select industry_relevance->>0 as industry, count(distinct dimension_code) as dims
from problems where problem_code ~ '^(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]$'
group by 1 order by 1;

-- No orphans: both must be 0.
select count(*) from root_causes
  where root_cause_code ~ '^RC-(AGR|AUT|BFS|BPC|PRP)-2' and problem_id is null;
select count(*) from questions
  where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP)-2'
    and (problem_id is null or root_cause_id is null);
```

Then the repo's own checks, from the backend directory:

```bash
python -m scripts.verify_seed_data                             # must exit 0
python -m scripts.qa.industry_selection_preflight --preflight  # 30 industries, 1800+ mapped
```

---

## 6. Rollback

By code, so it works whatever ids the sequences assigned.

```sql
begin;
delete from question_industry_mapping
 where question_id in (select question_id from questions
   where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]-[0-9]$');
delete from questions
 where question_code ~ '^S(0|01|10)-(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]-[0-9]$';
delete from interventions
 where intervention_code ~ '^INT-(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]-[0-9]$';
delete from root_causes
 where root_cause_code ~ '^RC-(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]-[0-9]$';
delete from problems
 where problem_code ~ '^(AGR|AUT|BFS|BPC|PRP)-2[0-9][0-9]$';
commit;
```

Nothing pre-existing is touched. Route A's `alembic downgrade -1` does the same thing.

---

## 7. Target

**RDS is production. Supabase is local testing only** and is not part of this handover.
Batch 1 goes to RDS.

---

## 8. What we can and cannot do from the build environment

| | |
|---|---|
| Apply to **Supabase** | Yes, but it is test-only and not part of this handover. |
| Apply to **RDS** | **No.** RDS sits in a VPC and is not reachable from here, and this environment has no valid AWS credentials (`sts:GetCallerIdentity` returns `InvalidClientTokenId` — the keys present are placeholders for a local S3 config). |
| Trigger the one-off ECS task | **No** — same reason. Needs `ecs:RunTask` and `iam:PassRole` with real credentials. |

So **every batch needs one action from your side**: the `aws ecs run-task` in §3, or the psql
in §4. We hand you each batch as one SQL file that needs no edits and no id check, already
applied and verified against a from-zero rebuild and against a database that already had it.

If you would rather it not need a person each time, the options are a deploy-time migration
task in the pipeline (note the two-task race warning in `DEPLOY.md` §1) or a CI job with
scoped `ecs:RunTask` permission. Your call — we are not proposing to change your deploy
process unasked.

---

## 9. What is coming

Six batches of five industries each, in A–Z order. Batch 1 (Agriculture, Automotive,
BFSI/FinTech, Beauty, Construction/PropTech) is ready now — 810 rows. Each later batch is
the same shape and size, and each uses the same code-resolved, id-free form, so there is
nothing to reconcile between batches either.
