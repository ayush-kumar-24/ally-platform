# Production RDS — checks to run

**For whoever has access to the production RDS database.**
Everything here is **read-only**. Nothing writes, nothing locks, nothing changes.
Please run all of it in one session and send the output back — it answers several
separate questions at once.

Context: production runs on **AWS RDS**. The Supabase project is a different
database. A share token that is valid in Supabase returns "not available" from
production, which is how we know they are separate. So anything verified against
Supabase has **not** been verified against production.

---

## Check 1 — the broken share link (the immediate bug)

A founder created a share link from the report page and got
`goxlally.ai/r/yqM04F363fb98VUGS5nUff7Az5DdAGvj`, which returns
*"This shared report is not available."*

```sql
select s.share_id,
       s.founder_id,
       s.report_id,
       s.is_active                as share_active,
       s.expires_at,
       s.expires_at > now()       as not_expired,
       s.access_count,
       s.created_at,
       r.report_id                as report_found,
       r.is_active                as report_active
from report_shares s
left join founder_reports r on r.report_id = s.report_id
where s.share_token = 'yqM04F363fb98VUGS5nUff7Az5DdAGvj';
```

**How to read the result**

| Result | What it means | What to do |
|---|---|---|
| **No rows at all** | The share was never written to RDS, even though the API handed the founder a link. A write that is not committing, or the API reading and writing different places. | Most serious outcome. Check DB routing / pooler config and whether the create path commits in production. |
| Row exists, `report_active` = false | The share is fine; the report behind it was deactivated, so the link died with it. | Decide whether deactivating a report should also revoke its links, and say so in the UI. |
| Row exists, `not_expired` = false | Simply expired. Links last 30 days. | No bug. Improve the message so it says "expired" rather than "not available". |
| Row exists, `share_active` = false | Revoked. | No bug, same message improvement. |
| Row exists and everything valid | Then the read path is at fault, not the data. | Deploy the new logging (below) and reproduce. |

## Check 2 — is sharing working in production at all?

```sql
select count(*)                                             as total_shares,
       count(*) filter (where created_at > now() - interval '7 days')  as last_7_days,
       count(*) filter (where is_active and expires_at > now())        as live_now,
       max(created_at)                                      as newest_share
from report_shares;
```

If `last_7_days` is 0 but founders have been clicking Share, shares are not being
written in production — which points at the same root cause as an empty Check 1.

## Check 3 — how far behind is production's schema?

This is more important than the share bug. The Supabase database was found to be
several migrations behind its own version marker, with two migrations that had
never run. Production may be in a similar state, and nobody can safely deploy a
schema change until this is known.

```sql
select version_num from alembic_version;
```

Compare against the current head in the repo:

```bash
cd ally-platform/backend && python -m alembic heads
```

**Do not run `alembic upgrade head` on production based on the version number
alone.** On Supabase the marker was wrong in both directions — data migrations
had been applied by hand without stamping, while two schema migrations had never
run at all. Run Check 4 first to see what is actually in the database.

## Check 4 — what is actually applied, regardless of the version marker

```sql
select
  -- migration 8f3a1c92d7b4: per-stage diagnosis question budget
  (select count(*) from founder_stages where question_budget is not null)   as stages_with_budget,
  (select count(*) from founder_stages)                                     as total_stages,

  -- migration d5b81e37c9a2: the `monitor` routing state
  (select count(*) from pg_constraint
    where conrelid = 'public.sessions'::regclass and contype = 'c'
      and pg_get_constraintdef(oid) ilike '%monitor%')                      as monitor_state_present,
  (select count(*) from scoring_rules where rule_code ilike '%MONITOR%')    as monitor_rule_present,

  -- migration a3f81c05e6d7: Risk Appetite, the 15th Founder DNA dimension
  (select count(distinct dimension_code) from founder_dna_questions)        as founder_dna_dimensions,

  -- migration f2c7a91d4e83: split privacy request audit labels
  (select count(*) from pg_constraint
    where conrelid = 'public.privacy_requests'::regclass
      and pg_get_constraintdef(oid) ilike '%delete_account%')               as privacy_labels_split,

  -- seed migrations
  (select count(*) from questions)                                          as questions_total;
```

**Expected on a fully up-to-date database**

| Column | Expected |
|---|---|
| `stages_with_budget` / `total_stages` | 8 / 8 |
| `monitor_state_present` | 1 |
| `monitor_rule_present` | 1 |
| `founder_dna_dimensions` | 15 |
| `privacy_labels_split` | 1 |
| `questions_total` | 3340 |

Anything short of that is a migration that has not reached production. Send the
row back rather than acting on it — the safe remediation depends on which
combination is missing, and the Supabase case needed a stamp before an upgrade,
not an upgrade alone.

## Check 5 — the privacy audit trail (only if `privacy_labels_split` = 0)

Before the fix, account deletion, cancelling a deletion, and withdrawing consent
were all recorded under the single label `withdraw_consent`, so the audit trail
could not tell them apart. This shows how many production rows are affected:

```sql
select request_type,
       case
         when request_details like 'Account erasure requested%'  then 'really a deletion request'
         when request_details like 'Account deletion cancelled%' then 'really a cancellation'
         else 'genuinely a consent withdrawal'
       end as actual_event,
       count(*) as rows
from privacy_requests
group by 1, 2
order by 1, 3 desc;
```

The migration `f2c7a91d4e83` reclassifies these from `request_details`, so
whatever this returns is what it will correct.

---

## Not a SQL check — worth confirming at the same time

- **Report PDFs live in S3** (`founder_reports.pdf_storage_key` points into the
  object store). If PDFs are failing in production, check the bucket and the
  task role's permissions, not the database.
- **Chat attachments also use S3**, under the attachment bucket settings.

## Code change waiting to deploy

The share endpoints returned the same sentence for three different failures —
unknown token, revoked or expired share, and a live share whose report is
inactive — which is correct for a visitor (it stops anyone probing which tokens
exist) but left us guessing.

They now log the real reason server-side while the visitor-facing response stays
byte-identical. The token itself is never logged. After deploying, a failure like
this one appears as:

```
WARNING share_link_rejected  reason=report_inactive  route=view  share_id=… report_id=…
```

Deploying that first would make Check 1 unnecessary next time.
