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

### Two log lines, and the difference between them matters

**`deletion sweep completed`** — exactly ONE per run, emitted by the endpoint
unconditionally, including on the days it finds nobody due:

```json
{"message": "deletion sweep completed",
 "due_count": 3, "executed_count": 2, "failed_count": 1}
```

**`founder deletion completed`** — one per founder actually erased, from
`AccountDeletionExecutor.run`, carrying `founder_id` and `tables_touched`.

These were originally the same name, on the per-founder line, and that was
backwards in both directions. A healthy sweep on a day nobody was due logged
nothing, so an absence alarm fired on a job that was working perfectly. And a
dead job on a day somebody WAS due looked identical to a working one, because
that line is the only evidence either way. The heartbeat has to come from the
sweep, not from its outcome.

`tests/test_internal_jobs_deletion_logging.py` pins this: the line on an empty
sweep, exactly one per run, the counts as top-level JSON fields, and the
executor no longer claiming the sweep's name.

The endpoint also returns the same counts plus a per-founder breakdown, for
anyone calling it by hand — EventBridge records no response body anywhere,
which is why the log line and not the response is what the alarms read.

### Alarms

1. **Absence of `deletion sweep completed` for 48 hours.** The failure this job
   has to be watched for is that it stops running, and a job that does not run
   produces no output at all — so an expected line going missing is the only
   thing that can catch it. This is the alarm that would have caught the
   `workflow_dispatch` gate above.
2. **`failed_count` above zero.** Those founders asked to be erased and have
   not been. They are retried on the next sweep, but a number that does not
   come back down is a schema problem somebody has to look at — most likely a
   new founder-scoped table nobody added to `_HARD_DELETE_TABLES` in
   `app/privacy/deletion_executor.py`.

Both alarms read JSON fields, not the formatted message, so a refactor that
interpolated the counts into the string would break them silently. That is what
the last test in that file exists to stop.


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
