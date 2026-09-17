# Daily quote schedule

Each founder gets two lines chosen for them — one on the Compass, one on Plan
Your Day — fixed from midnight to midnight. This is the schedule that chooses
them.

## What to create

One EventBridge Scheduler schedule, same shape as the task-reminder one
(`TASK-REMINDER-SCHEDULE.md`), pointing at:

```
POST https://<api-host>/api/v1/internal/jobs/assign-daily-quotes
Header: X-Internal-Secret: <INTERNAL_JOB_SECRET>
```

Cron, in UTC, for **00:05 IST**:

```
cron(35 18 * * ? *)
```

IST is UTC+5:30 and does not observe daylight saving, so this is a fixed offset
and does not need revisiting twice a year. Alternatively set the schedule's
timezone to `Asia/Kolkata` and use `cron(5 0 * * ? *)`, which is easier to read
and is what a person debugging this at 1am would prefer.

**Five past, not on the hour.** Nothing breaks at 00:00, but a founder awake at
midnight would see their card change under them; five minutes later nobody is
mid-sentence.

## Why not the GitHub Actions sweep

`.github/workflows/internal-job-sweeps.yml` exists and could call this. Don't.
Its own header comment records the measurement: runs scheduled every ten minutes
actually land two to five hours apart. A quote job that fires at 03:00 is fine;
one that fires at 15:00 changes a founder's card halfway through their afternoon,
which is the single thing this design exists to prevent.

## It is safe to run again

Every write is `on conflict do nothing`, and a founder who already has today's
two lines is skipped *before* any model call. So:

- Running it twice costs nothing.
- Running it late fills in whoever is missing without disturbing anyone served.
- A missed night self-heals: the first page load picks deterministically and
  stores that, and the next night's run leaves it alone.

Firing it by hand after a missed night is a normal thing to do, not a recovery
procedure.

## What to watch

The endpoint logs one structured line when it finishes:

```
daily quote job complete  founders=45 already_done=0 by_model=45 by_fallback=0 pruned=0
```

EventBridge does not record a target's response body anywhere, so these are
logged as well as returned — CloudWatch metric filters read the log line.

**`by_fallback` is the number that matters.** A fallback pick is deliberately
invisible: it comes from the same shortlist, it is stable for the day, it reads
like any other line. Which means a provider that has been failing all week looks
exactly like one that is working, and this is the only place the difference
shows.

Worth an alarm:

- **`by_model` at zero** with `founders` in the dozens — the OpenAI key, the
  `daily_quote_selection` routing row, or `DAILY_QUOTES_LLM` is not what you
  think it is.
- **`founders` at zero** — the sweep ran but matched nobody, which means the
  query or the database connection is wrong, not that the platform is empty.

## Configuration

| Setting | Where | Note |
|---|---|---|
| `DAILY_QUOTES_LLM` | backend env | `false` by default. Off = the deterministic pick, which is still per-founder and still stage-filtered. |
| `OPENAI_API_KEY` | backend env | Already set. Without it the task falls back for everyone. |
| `daily_quote_selection` | `model_task_routing` | Seeded by migration `b4f2a91c7e63` to `openai` / `gpt-5.4-nano`. |
| `INTERNAL_JOB_SECRET` | backend env | Same secret the other sweeps use. |

Turning the flag off is a safe instant rollback: the next night's run — and
every page load in the meantime — falls back to the deterministic pick, and no
founder sees a blank card at any point.
