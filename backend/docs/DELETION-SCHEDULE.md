# Account erasure schedule

When a founder asks to be deleted, the request is *scheduled* 30 days out and
nothing is destroyed until a sweep runs and executes it. This is that sweep's
schedule. It is the one job in this system where "it didn't run" is a
compliance failure rather than a delay.

## What to create

One EventBridge Scheduler schedule, the same shape as the task-reminder and
daily-quote ones, pointing at:

```
POST https://<api-host>/api/v1/internal/jobs/process-deletions
Header: X-Internal-Secret: <INTERNAL_JOB_SECRET>
```

Once a day is enough — the sweep only ever acts on founders whose 30-day window
has **already** closed, so a more frequent schedule buys nothing. Timezone
`Asia/Kolkata`:

```
cron(50 0 * * ? *)
```

or, in UTC, `cron(20 19 * * ? *)`. 00:50 IST: after the quote job at 00:05, and
at an hour when a mistake is noticed by the morning rather than during the
working day.

## Why this needs to move off GitHub Actions

It is in `.github/workflows/internal-job-sweeps.yml` today and that is not good
enough, for two independent reasons.

**It was not on a schedule at all.** Until this was fixed, the erasure step was
gated on `workflow_dispatch` alone while every other step in the file also ran
on the cron. It executed only when a human clicked the button. A founder whose
window closed was simply never erased, and nothing anywhere said so — the
workflow went green every ten minutes doing four other things.

**GitHub disables scheduled workflows after 60 days of repository inactivity.**
A quiet stretch over a holiday silently switches the backstop off. For report
reconciliation that is an inconvenience; for erasure it means a right under the
DPDP Act stops being honoured with no alarm and no log line, because a job that
does not run produces no output to notice.

The workflow now runs it daily as a backstop. Running both is harmless: the
sweep is idempotent and `find_due_for_deletion()` only returns founders who are
due *and* not yet executed, so whichever fires first does the work and the
other finds nothing to do.

## It is safe to run again, and safe to run late

- **Idempotent.** Hard-deletes of already-gone rows are no-ops, and the
  `founders` row is only touched once because `deletion_executed_at` is what
  takes a founder out of the due list.
- **Late is not lossy.** A missed night means erasure happens the next night.
  The request is a row in the database, not a timer in a process.
- **Partial failure does not lie.** If a foreign-key violation means a table
  did not actually empty, the whole attempt for that founder is rolled back and
  `deletion_executed_at` stays null, so the next sweep picks them up again.
  Earlier versions swallowed the error and stamped the erasure complete with
  rows still present.
- **One founder's failure does not stop the sweep.** The rest still run; the
  failure is logged and reported in the response.

## What to watch

The endpoint returns a summary, and each founder logs its own line:

```json
{"due_count": 3, "results": [
  {"founder_id": 41, "status": "executed", "tables_touched": 33},
  {"founder_id": 58, "status": "failed", "error": "..."}
]}
```

Two things are worth an alarm:

1. **Any `"status": "failed"`.** That founder has asked to be erased and has
   not been. It will retry, but a repeat failure is a schema problem somebody
   has to look at — most likely a new founder-scoped table that nobody added to
   `_HARD_DELETE_TABLES` in `app/privacy/deletion_executor.py`.
2. **The job not reporting at all for 48 hours.** A silent job and a job with
   nothing to do look identical from outside, which is exactly the failure mode
   that hid the `workflow_dispatch` gate above. A CloudWatch metric filter on
   `deletion sweep completed` with an alarm on *absence* is the check that
   would have caught it.

To answer "is anyone stuck?" directly, without waiting for a sweep:

```sql
select founder_id, deletion_scheduled_at, deletion_executed_at
  from founders
 where deletion_scheduled_at is not null
   and deletion_executed_at is null
   and deletion_scheduled_at < now() - interval '30 days'
 order by deletion_scheduled_at;
```

Any row this returns is a founder past their window who has not been erased.
The correct number is zero.

## What actually gets deleted

See `RETENTION-SCHEDULE.md` — every table, and which of the three policies
(delete / anonymise / retain) applies to it.
