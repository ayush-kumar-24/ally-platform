# Scheduling the Plan Your Day reminder sweep

**Who this is for:** whoever manages AWS. Everything below is console/CLI work
outside the repo. The application side is already done and deployed.

---

## What needs to run

One HTTP POST, on a schedule:

```
POST https://api.goxlally.ai/api/v1/internal/jobs/send-task-reminders
Header: X-Internal-Secret: <INTERNAL_JOBS_SECRET>
Body:   none
```

**Cadence: every 1 minute** (every 2 is acceptable; every 5 is the outside
limit).

### Why the cadence is tighter than the other sweeps

A founder picks their own reminder offset in Plan Your Day, and the smallest
one is **5 minutes before**. There is also an "at the time" option, where the
reminder moment is the task's own moment.

The sweep only sends reminders whose moment has already passed, so a founder's
nudge is late by however long the gap between runs is. On a 15-minute sweep, a
"5 minutes before" reminder arrives up to 10 minutes *after* the task was due —
at which point the staleness check correctly discards it and the founder gets
nothing. One minute makes every offset in the picker work as advertised.

The job is idempotent and cheap: it does one indexed query and, on the vast
majority of runs, sends nothing and returns `{"sent": 0, ...}`. Running it
every minute is not expensive.

---

## Setting it up (EventBridge Scheduler)

EventBridge Scheduler cannot POST to an arbitrary HTTPS URL directly — it needs
an **API destination**, which is where the secret header lives.

**1. Create a Connection** (EventBridge → API destinations → Connections)

| Field | Value |
|---|---|
| Name | `ally-internal-jobs` |
| Authorization type | API key |
| API key name | `X-Internal-Secret` |
| Value | the same string as the backend's `INTERNAL_JOBS_SECRET` |

The value is stored in Secrets Manager by EventBridge automatically. It must
match the backend env var exactly or every call returns 401.

**2. Create an API destination**

| Field | Value |
|---|---|
| Name | `ally-send-task-reminders` |
| Endpoint | `https://api.goxlally.ai/api/v1/internal/jobs/send-task-reminders` |
| Method | `POST` |
| Connection | `ally-internal-jobs` |
| Invocation rate limit | 60 per minute or higher |

**3. Create the schedule** (EventBridge Scheduler → Schedules)

| Field | Value |
|---|---|
| Name | `ally-task-reminders` |
| Schedule type | Recurring, rate-based |
| Rate | `1 minute` |
| Flexible time window | **Off** — a reminder is time-critical |
| Target | EventBridge API destination → `ally-send-task-reminders` |
| Retry policy | Max 2 retries, max age 60 seconds |
| Dead-letter queue | Optional but useful |

Keep the retry age short. A retry that lands ten minutes later is a reminder
the founder no longer wants; the next scheduled run picks up anything missed
anyway.

---

## Confirming it works

A healthy run returns 200 with counts:

```json
{"sent": 0, "in_app": 0, "skipped_pref": 0,
 "stale": 0, "orphaned": 0, "failed": 0, "email_configured": true}
```

`sent` is reminders emailed to Pro founders. `in_app` is the same reminder
delivered to the notification bell for founders on every other plan — they get
the feature, email is the part that is sold. Both are deliveries; neither is a
skip.

Check these three things:

1. **`email_configured` is `true`.** If it is `false`, `EMAIL_HOST` is not set
   on the backend and no Pro founder can be emailed, no matter how often this
   runs — bell reminders still work. The field exists precisely so a green
   schedule cannot hide that.
2. **`stale` stays at 0.** Anything above zero means reminders are arriving too
   late to be worth sending — the sweep is not running often enough, or is not
   running at all between long gaps.
3. **`failed` stays at 0.** Non-zero means individual sends are erroring; the
   backend logs carry the reason per founder.

**Alarm on:** any non-200 response, or `stale` above 0 for a sustained period.
A 401 means the secret does not match. A 5xx means the API is unhealthy.

### Alarming on the counts, not just the status code

EventBridge Scheduler does not store a target's response body anywhere, so the
JSON above is not something a CloudWatch alarm can reach. The same counts are
therefore **logged** as well as returned. Every completed run emits one INFO
line to the backend's log group:

```json
{"timestamp": "2026-09-15T09:55:37.113125+00:00", "level": "INFO",
 "logger": "app", "message": "task reminder job complete",
 "sent": 3, "in_app": 1, "skipped_pref": 0, "stale": 2,
 "orphaned": 0, "failed": 0, "email_configured": true}
```

Each count is its own top-level JSON field, so metric filters read them
directly — no parsing of a message string:

| Alarm | Metric filter pattern | Fires when |
|---|---|---|
| Schedule not keeping up | `{ $.message = "task reminder job complete" && $.stale > 0 }` | sustained > 0 |
| Email not configured | `{ $.message = "task reminder job complete" && $.email_configured IS FALSE }` | any datapoint |
| Sends erroring | `{ $.message = "task reminder job complete" && $.failed > 0 }` | sustained > 0 |

A run that sends nothing is the normal case and logs all zeroes, so the
absence of this line is itself meaningful: it means the schedule is not firing
at all. An alarm on `SampleCount < 1` over ~15 minutes catches that, and is the
one thing none of the filters above can tell you.

This line is covered by `tests/test_internal_jobs_task_reminder_logging.py`,
including that the counts render as top-level JSON fields — a refactor that
logged them inside a formatted message would keep every test green except that
one, while silently breaking all three filters.

---

## What is already in place, and what this replaces

The GitHub Actions workflow `.github/workflows/internal-job-sweeps.yml` already
calls this endpoint and stays as a **backstop only**. It is not sufficient on
its own: its cron says every 10 minutes, and the actual scheduled runs measured
over three days were 2–5 hours apart —

```
Sep 12   01:12  05:53  10:11  13:37
Sep 11   01:10  06:05  11:14  15:03  18:26  21:10  23:15
Sep 10   01:25  06:25  11:41  15:12  18:31  21:09  23:10
```

GitHub throttles scheduled workflows and there is no repo-side fix. That gap is
why task reminder emails were switched off on 2026-09-11; EventBridge is what
makes turning them back on safe.

Nothing needs to be removed from the GitHub workflow — running the sweep twice
is harmless, because every row it examines moves off `scheduled` whether it was
sent, skipped or dropped.
