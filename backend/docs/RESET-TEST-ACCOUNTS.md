# Resetting test accounts — onboarding and diagnosis

**For whoever has access to the production RDS database.**
Everything here **writes and deletes**. Read the whole page before running any of it.

Context: production runs on **AWS RDS** (see `DEPLOY_AWS.md` — not Supabase, and
RDS has no SQL console in the AWS web UI). Either connect with `psql`, or run a
one-off ECS task against the same task definition the deploy uses for
`alembic upgrade head`.

---

## Prefer the admin panel

For **one founder**, do not use this page. The panel has both actions, they are
permission-checked, and every use is written to the audit log with who did it and
when:

| Button | What it does |
|---|---|
| **Reset onboarding** | Clears every onboarding answer and sets `profile_completed = false`, so Ally asks the eleven questions again. Diagnosis, report and chat are kept. |
| **Reset diagnosis** | Deletes the diagnosis sessions, answers, Founder DNA, Current Problem answers, report, and any share links to it. Onboarding and chat are kept. |
| **Reset conversations** | Deletes chat history with Ally. |

SQL below is for the case the panel is not built for: **a batch of accounts at
once**, which is what a testing round usually needs.

---

## What lives where

Onboarding answers are **columns on `founders`**. There is no separate table, so
resetting onboarding is an `UPDATE`, never a `DELETE`.

The diagnosis is **rows across ten tables**. Delete order matters:

```
report_shares  internal_intelligence_reports  founder_reports
detected_root_causes  answers  stage_assessments
founder_dna_answers  current_problem_answers  rag_retrieval_log
sessions            <- last: cascades to four of the above
```

Three of those are keyed to the **founder**, not the session —
`founder_dna_answers`, `current_problem_answers`, `stage_assessments` — so
deleting `sessions` alone leaves them behind. And `report_shares` has no foreign
key to `founder_reports`, so its rows survive as live share links pointing at a
report that no longer exists.

### Two things that are easy to get wrong

**`profile_completed = false` is not optional.** Everywhere in the application
that flag is recomputed on the way past (`FounderRepository.update`), but raw SQL
does not go through it. Leave it `true` and `GuidedLayout` and the login redirect
send the founder straight to `/app` — they never see the questions whose answers
you just deleted.

**`diagnosis_used` / `diagnosis_locked_at` are display only.** The lifetime cap
counts COMPLETED rows in `sessions` (`count_completed_sessions`). Clearing those
two columns without deleting the session rows leaves the founder refused with
`DiagnosisAlreadyCompletedError` the moment they try again.

### Never cleared

`full_name` and `email` — both `NOT NULL`, both from signup rather than
onboarding. Accounts, plans, credits, subscriptions and payments are untouched
by everything on this page, as are chat history and Plan Your Day.

---

## The script

Run the whole thing in **one `psql` session**. Nothing is written until you type
`COMMIT`, so any checkpoint that looks wrong is a `ROLLBACK` away from nothing
having happened. **Take an RDS snapshot first.**

```sql
BEGIN;

-- ---------- the list, in one place ----------
CREATE TEMP TABLE wanted(email text) ON COMMIT DROP;
INSERT INTO wanted(email) VALUES
  ('someone@example.com'),
  ('someone.else@example.com');

CREATE TEMP TABLE targets ON COMMIT DROP AS
SELECT f.founder_id, f.email
FROM founders f
JOIN wanted w ON lower(f.email) = lower(btrim(w.email));

-- ---------- CHECK A: does this match the number you expect? ----------
SELECT count(*) AS matched_founders FROM targets;

-- ---------- CHECK B: typos and accounts that do not exist ----------
SELECT w.email AS not_found_in_db
FROM wanted w
LEFT JOIN founders f ON lower(f.email) = lower(btrim(w.email))
WHERE f.founder_id IS NULL;
-- Any row here: ROLLBACK and fix the list. Gmail ignores dots in addresses,
-- this database does not -- d.viraj2@ and dviraj2@ are different strings.

-- ---------- CHECK C: what is about to go ----------
SELECT t.email,
       (SELECT count(*) FROM sessions                s WHERE s.founder_id=t.founder_id) AS sessions,
       (SELECT count(*) FROM answers                 a WHERE a.founder_id=t.founder_id) AS answers,
       (SELECT count(*) FROM founder_dna_answers     d WHERE d.founder_id=t.founder_id) AS dna,
       (SELECT count(*) FROM current_problem_answers c WHERE c.founder_id=t.founder_id) AS problem,
       (SELECT count(*) FROM founder_reports         p WHERE p.founder_id=t.founder_id) AS reports
FROM targets t ORDER BY t.email;

-- ================= DIAGNOSIS (children first, sessions last) =================
DELETE FROM report_shares                 WHERE founder_id IN (SELECT founder_id FROM targets);
DELETE FROM internal_intelligence_reports WHERE founder_id IN (SELECT founder_id FROM targets);
DELETE FROM founder_reports               WHERE founder_id IN (SELECT founder_id FROM targets);
DELETE FROM detected_root_causes          WHERE founder_id IN (SELECT founder_id FROM targets);
DELETE FROM answers                       WHERE founder_id IN (SELECT founder_id FROM targets);
DELETE FROM stage_assessments             WHERE founder_id IN (SELECT founder_id FROM targets);
DELETE FROM founder_dna_answers           WHERE founder_id IN (SELECT founder_id FROM targets);
DELETE FROM current_problem_answers       WHERE founder_id IN (SELECT founder_id FROM targets);
DELETE FROM rag_retrieval_log             WHERE founder_id IN (SELECT founder_id FROM targets);
DELETE FROM sessions                      WHERE founder_id IN (SELECT founder_id FROM targets);

-- ================= ONBOARDING =================
UPDATE founders SET
  stage_id = NULL, experience_level = NULL, current_revenue = NULL,
  building_summary = NULL, product_description = NULL, problem_statement = NULL,
  industry = NULL, industry_mapped_id = NULL,
  customer_segment = NULL, customer_segment_other = NULL,
  founder_reality_signals = NULL, business_reality_signals = NULL,
  invisible_gaps = NULL,
  current_challenges = NULL, current_challenges_other = NULL,
  goal_90_day = NULL, vision_1_year = NULL,
  linkedin_url = NULL,
  profile_completed = false,
  diagnosis_used = 0, diagnosis_locked_at = NULL,
  -- tour_seen_at = NULL,        -- uncomment to replay the product tour too
  updated_at = now()
WHERE founder_id IN (SELECT founder_id FROM targets);
-- Should report the same number as CHECK A.

-- ---------- CHECK D: re-run CHECK C. Every count must be 0. ----------
SELECT t.email,
       (SELECT count(*) FROM sessions                s WHERE s.founder_id=t.founder_id) AS sessions,
       (SELECT count(*) FROM answers                 a WHERE a.founder_id=t.founder_id) AS answers,
       (SELECT count(*) FROM founder_dna_answers     d WHERE d.founder_id=t.founder_id) AS dna,
       (SELECT count(*) FROM current_problem_answers c WHERE c.founder_id=t.founder_id) AS problem,
       (SELECT count(*) FROM founder_reports         p WHERE p.founder_id=t.founder_id) AS reports,
       (SELECT profile_completed FROM founders f WHERE f.founder_id=t.founder_id)       AS profile_completed
FROM targets t ORDER BY t.email;

COMMIT;   -- or ROLLBACK; if anything above looks wrong
```

### Onboarding only

Delete the whole `DIAGNOSIS` block and drop `diagnosis_used` /
`diagnosis_locked_at` from the `UPDATE`.

### Diagnosis only

Keep the `DIAGNOSIS` block and replace the `UPDATE` with just:

```sql
UPDATE founders
   SET diagnosis_used = 0, diagnosis_locked_at = NULL, updated_at = now()
 WHERE founder_id IN (SELECT founder_id FROM targets);
```

---

## Afterwards

Tell the founders to **sign out and sign back in**. The browser caches the
founder record, and a fresh sign-in re-fetches it.

## Keeping this page honest

The table list mirrors `_DIAGNOSIS_TABLES` and the column list mirrors
`_ONBOARDING_COLUMNS`, both in `app/admin/users_db_repository.py`, which is what
the admin panel buttons use. **Change those and change this page.** If they ever
disagree, the code is right and this page is stale.
