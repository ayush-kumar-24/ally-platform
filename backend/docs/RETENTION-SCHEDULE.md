# Retention schedule

What we keep, for how long, and what happens to it when a founder asks to be
erased. Written for the DPDP legal review, which asked for "a practical
retention schedule by data type" in place of the Privacy Policy's mixture of
"while active", a 30-day figure and a seven-year example.

**This document is generated from the code, not from intent.** Every table
below is named in `app/privacy/deletion_executor.py`, which is what actually
runs. If the two ever disagree, the code is right and this file is stale — see
*Keeping this honest* at the end.

Last checked against the code: 22 September 2026.

---

## The lifecycle

1. **While the account is open** — data is kept for as long as the account is
   active, because that is what the service is.
2. **The founder asks to be erased** (Privacy Centre → Delete account, or a
   Supabase `user.deleted` webhook). Nothing is destroyed yet. A row is written
   scheduling erasure **30 days** out, and the founder can cancel during that
   window from the same screen. Processing is restricted immediately.
3. **After 30 days** the sweep runs and applies the table-by-table policy
   below.
4. **Accountability and financial records survive**, deliberately, and are
   described in their own section.

The 30-day window is a recovery window, not a delay in answering the request:
export, correction, withdrawal and restriction all take effect immediately.

---

## Category 1 — Deleted outright

Product-usage and content data with no external retention claim on it. The row
is removed; nothing is kept.

| What it is | Tables |
|---|---|
| Diagnostic answers and sessions | `answers`, `sessions`, `stage_assessments`, `detected_root_causes` |
| Reports | `founder_reports`, `internal_intelligence_reports`, `report_shares` |
| Chat and uploads | `conversations`, `messages`, `file_uploads`, `suggestions`, `suggestion_feedback` |
| What Ally worked out about the founder | `founder_context`, `founder_memory`, `founder_memory_events`, `founder_visual_choices` |
| Planning | `planning_plans`, `planning_goals`, `planning_tasks`, `planning_reminders`, `daily_actions` |
| Calls and case notes | `discovery_calls`, `admin_notes` |
| Feedback and notifications | `founder_feedback`, `notifications` |
| Usage metering | `daily_token_usage`, `plan_call_usage`, `unbilled_usage`, `llm_call_log`, `analytics_events` |
| Search and retrieval text | `rag_retrieval_log` — holds the founder's own query text |
| Cookie choices | `cookie_preferences` |
| Earlier deletion requests | `data_deletion_requests` |

33 tables. The list in the code is explicit rather than "every table with a
`founder_id`", so a new founder-scoped table is only erased once somebody adds
it there on purpose.

## Category 2 — The account row, anonymised

`founders` is the one row that is scrubbed rather than deleted. Every other
table above keeps a live foreign key pointing at it during the sweep, so
removing it would orphan them.

Overwritten: `full_name` → "Deleted Founder", `email` →
`deleted-founder-<id>@erased.ally.local`. Set to null: `founder_motivation`,
`building_summary`, `problem_statement`, `website`, `linkedin_url`,
`customer_segment_other`, `adaptive_reflection`, `first_impression`.
`social_profiles` is emptied.

## Category 3 — The row stays, the identifying columns do not

| Tables | What is nulled | Why the row stays |
|---|---|---|
| `audit_logs`, `consent_history`, `consents` | `ip_address`, `browser` | These are the evidence that consent was given and that an erasure was carried out. Deleting them would destroy the proof of the very right being exercised. |

## Category 4 — Retained

| Tables | Why | Period |
|---|---|---|
| `payments`, `subscriptions`, `credit_transactions` | Financial records under Indian tax and accounting law | **Seven years**, subject to the legal note below |
| `founder_consents`, `privacy_requests` | Accountability: what was consented to, what was requested, when | Retained |

None of these carry a name, email or contact column of their own. They are
ledger rows keyed by `founder_id`, so anonymising `founders` anonymises them by
inheritance — no separate write is needed.

> **This one is a legal call, not an engineering one.** The code assumes
> retention of the financial tables is correct; it does not verify that
> assumption, and the seven-year figure comes from the Privacy Policy rather
> than from a determination anyone has recorded. Get compliance sign-off on the
> period and the basis before quoting it to a regulator.

---

## Data that is not founder-scoped

| What | Where | How long |
|---|---|---|
| Daily quote picks | `founder_daily_quotes` | 60 days, pruned nightly by the quote job |
| Beta registrations on the public site | landing-page database | Up to 24 months from registration, then deleted — see the landing site's own policy |
| Aggregated, de-identified insights | — | Indefinite. Once data has been aggregated across founders and stripped of anything identifying, it is no longer personal data and falls outside the DPDP Act. |

---

## What makes this real rather than a promise

- **The sweep has a consumer.** `POST /api/v1/internal/jobs/process-deletions`
  runs it; see `DELETION-SCHEDULE.md` for how it is scheduled and what happens
  when it does not run.
- **It refuses to lie about completion.** If a foreign-key violation means a
  table did not actually empty, the whole attempt is rolled back and
  `deletion_executed_at` is left null, so the founder is picked up again on the
  next sweep. Earlier versions swallowed that error and stamped the erasure as
  complete with rows still present.
- **It is idempotent.** Re-running costs nothing.

## Keeping this honest

This file is a transcription. It goes stale the moment a table is added to
`deletion_executor.py` without being added here. When you change any of the
three lists in that module, change the matching section above in the same
commit.

To check the transcription is still accurate:

```bash
cd backend && python3 - <<'PY'
import re
src = open('app/privacy/deletion_executor.py').read()
doc = open('docs/RETENTION-SCHEDULE.md').read()
def lst(name):
    m = re.search(name + r'.*?=\s*\((.*?)\)\n', src, re.S)
    return set(re.findall(r'"([a-z_]+)"', m.group(1)))
missing = sorted(t for t in lst('_HARD_DELETE_TABLES') | lst('_SCRUB_COLUMNS_RETAIN_ROW')
                        | lst('_RETAIN_AS_IS_PENDING_LEGAL') if t not in doc)
print("NOT DOCUMENTED:", missing or "none — schedule matches the code")
PY
```
