# Handover: the fix set for production RDS

This is the companion to `INDUSTRY-BATCH-DEPLOY.md`. That document covers the
industry *content* batches. This one covers the **fixes** — one schema change
and three data repairs — found while running the diagnosis engine end to end
against a rebuilt database.

Everything here is in `backend/data/question_batches/`. Every file is
idempotent: running it twice is a no-op, and each one self-checks inside its
own transaction and rolls back rather than half-applying.

---

## 1. Run these five files, in this order

| # | File | What it is | Size |
|---|------|-----------|------|
| 1 | `fix_schema_widen_answers_score_label.sql` | **The one schema change.** Widens `answers.score_label` varchar(10) → varchar(20). | 3 KB |
| 2 | `batch1_industries_1to5.sql` | Content: agritech, automotive, fintech, beauty & personal care, proptech. 810 rows. | 424 KB |
| 3 | `batch2_industries_6to10.sql` | Content: consumer electronics, e-commerce/D2C, edtech, cleantech & energy, media & entertainment. 810 rows. | 423 KB |
| 4 | `fix_original_catalogue_interventions.sql` | 417 interventions for problems in the 1–275 range, which had none. | 546 KB |
| 5 | `fix_batch_stage_weights.sql` | 2,160 `root_cause_weights` rows — the 270 batch root causes × 8 founder stages. | 657 KB |
| 6 | `fix_concentrate_batch_evidence.sql` | An UPDATE that remaps batch questions so evidence concentrates instead of scattering. | 2 KB |

Order matters in two places only: the schema change (1) must land before any
session writes a `not_applicable` answer, and 5 and 6 reference rows that 2 and
3 insert. 4 is independent of the batches and can go any time after 1.

```bash
cd /path/to/sql
for f in \
  fix_schema_widen_answers_score_label.sql \
  batch1_industries_1to5.sql \
  batch2_industries_6to10.sql \
  fix_original_catalogue_interventions.sql \
  fix_batch_stage_weights.sql \
  fix_concentrate_batch_evidence.sql
do
  echo "== $f"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f" || break
done
```

`-v ON_ERROR_STOP=1` is not optional. Without it psql keeps going past a failed
statement and you get a partially applied file with a clean exit code.

---

## 2. The schema change, and why it is needed

This is the only DDL in the set, and it is the one that was silently breaking
completed sessions.

An answer can carry one of four bands: `green`, `amber`, `red`, or
`not_applicable`. The fourth one means "this question genuinely does not apply
to my business" — no free tier, no sales team, no channel partners. It exists as
a separate band precisely so it is excluded from scoring rather than being
folded into Amber, because "does not apply" is not a mild problem.

Migration `c7d18a3f420b` added `not_applicable` to the CHECK constraint on
`answers.score_label` and **left the column at varchar(10)**. The value is
fourteen characters. So every write of it failed:

```
StringDataRightTruncation: value too long for type character varying(10)
```

The band has therefore been unwritable since the day it was introduced. The
failure was not visible to founders as an error — it surfaced as a session that
reached the end and produced no report, with the exception recorded in
`reasoning_error`.

Widening a varchar in PostgreSQL 16 is a **catalogue-only change**: no table
rewrite, no data movement, no long `ACCESS EXCLUSIVE` hold. It is safe on the
live `answers` table. The existing CHECK constraint is not dropped or
recreated — it already permits the four values.

**If you apply migrations with alembic instead of SQL**, this same change is
revision `d4a91c7e2b83` (`widen_answers_score_label`), whose `down_revision` is
`c9f41b8e3a07`. Apply it *or* the SQL file, not both — though both are
idempotent, so doing both is harmless rather than wrong.

Two application bugs were downstream of this, and are fixed in the same
branch's Python (nothing for you to run):

- `diagnostic.py` raised `KeyError: <ScoreLabel.NOT_APPLICABLE>` when mapping
  the band to a score, because the mapping had only three keys.
- `business_health.py` counted a `not_applicable` answer in the pillar's
  denominator, which quietly pulled the pillar's risk ratio down as though an
  inapplicable question were a healthy one — defeating the whole reason the
  band is separate from Amber.

---

## 3. The interventions file

`fix_original_catalogue_interventions.sql` — 417 rows.

The diagnosis engine found root causes correctly and then recommended nothing,
for one reason: **problems 1–275 in the original catalogue had zero
interventions between them.** A report with a confident diagnosis and an empty
plan is worse than no report, and that is what those problems produced.

Before: 275 problems in that range with root causes and no intervention.
After: 6. (Those 6 carry root causes that no authored intervention addresses
yet — they are content still to be written, not a loading failure.)

Note on the reference dump: `data/reference/16_interventions.sql` does **not**
fix this. I checked, having first assumed it would. Its `intervention_id`
values 45–499 collide with 455 interventions that already exist and are
different rows — id 45 in that file is `INT-AUT-011` on problem 295. Loading it
inserts zero rows.

`fix_original_catalogue_interventions.sql` carries **no hardcoded ids at all**.
The sequence assigns primary keys; every foreign key is resolved by code
(`where problem_id = (select problem_id from problems where problem_code = ...)`).
That is what makes it safe against an RDS whose sequences have drifted from
Supabase's. It was tested against a deliberately desynced sequence.

---

## 4. Stage weights

`fix_batch_stage_weights.sql` — 2,160 rows (270 batch root causes × 8 stages).

`root_cause_weights.stage_weight` is a four-level relevance scale (0.50, 1.00,
1.50, 2.00) that feeds `WEIGHT_STAGE_PROBABILITY` (0.20) in root-cause ranking.
A cause with no row for the founder's stage loses that factor — the ranker
records it unavailable and renormalises over the rest, so nothing breaks, but
the new content ranked with a fifth of its signal missing.

One deliberate difference from the original catalogue, worth knowing before you
read the data: the original gives each cause rows only for the stages it is
relevant to (3 to 6 of the 8), so a missing row means "not relevant here". This
file gives all 8, using 0.50 for the stages where a cause barely applies. Both
are valid readings of the column; the explicit low value is the one I chose,
because "barely relevant" and "we never said" are different claims and the
ranker treats them differently.

---

## 5. Evidence concentration

`fix_concentrate_batch_evidence.sql` — an UPDATE, no inserts.

With the batch content loaded, an E-Commerce founder's 10 batch questions mapped
to 10 *distinct* root causes with one piece of evidence each.
`ROOT_CAUSE_MAX_CANDIDATES` is 8, and the original causes — which carry several
questions apiece — filled every slot. The new content was reachable and ranked
last, every time.

This remaps the batch questions to 2 per (cause, stage), so a batch cause
arrives with the same evidence mass as an original one and competes on merit.

It is an UPDATE and not a delete-and-reload because
`answers_question_id_fkey` refuses to let a question that has been answered be
deleted — correctly.

---

## 6. Verify after applying

```bash
python backend/scripts/verify_seed_data.py
```

Expected after all six files, against the rebuilt reference database:

```
[PASS] industries = 30
[PASS] problems = 848
[PASS] root_causes = 4371
[PASS] interventions = 1691
[PASS] root_cause_weights = 11936
[PASS] questions = 5890
[PASS] readiness_pillars weightage sums to 100 -- got 100.00
[PASS] root-cause ranking weights sum to 1.0 -- got 1.0000
[PASS] root causes can reach an intervention -- 36/4371 (0.8%) cannot
[INFO] problems carrying root causes but no intervention: 6
RESULT: all hard checks passed
```

And the schema change directly:

```sql
select character_maximum_length
  from information_schema.columns
 where table_name = 'answers' and column_name = 'score_label';
-- expect 20
```

---

## 7. Rollback

Files 2–6 are additive (5 and 6 aside, which are weights and a remap). Each is
wrapped in a single transaction, so a failure leaves nothing behind.

The schema change is not worth rolling back — a wider varchar breaks nothing —
but if you must, note that any row already carrying `not_applicable` will not
fit back into varchar(10). The alembic `downgrade()` nulls those rows first, on
purpose; a bare `alter column ... type varchar(10)` will fail instead.
