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
| 1 | `fix_schema_widen_answers_score_label.sql` | **Skip if `alembic_version` is already `d4a91c7e2b83`.** Widens `answers.score_label` varchar(10) → varchar(20). | 3 KB |
| 2 | `fix_original_catalogue_interventions.sql` | 417 interventions for problems in the 1–275 range, which had none. Independent of the batches. | 546 KB |
| 3 | `batch1_industries_1to5.sql` | Content: agritech, automotive, fintech, beauty & personal care, proptech. 810 rows. | 424 KB |
| 4 | `fix_batch1_stage_weights.sql` | 1,080 `root_cause_weights` rows (135 causes × 8 stages). | 36 KB |
| 5 | `batch2_industries_6to10.sql` | Content: consumer electronics, e-commerce/D2C, edtech, cleantech & energy, media. 810 rows. | 423 KB |
| 6 | `fix_batch2_stage_weights.sql` | 1,080 rows. | 36 KB |
| 7 | `batch3_industries_11to15.sql` | Content: fashion & apparel, food & beverage, gaming, healthcare, hospitality & travel. 810 rows. | 425 KB |
| 8 | `fix_batch3_stage_weights.sql` | 1,080 rows. | 36 KB |
| 9 | `batch4_industries_16to20.sql` | Content: HRTech, import/export, manufacturing, SaaS, LegalTech. 810 rows. | 423 KB |
| 10 | `fix_batch4_stage_weights.sql` | 1,080 rows. | 36 KB |
| 11 | `batch5_industries_21to25.sql` | Content: logistics, marketing/AdTech, NGO, pharma/biotech, professional services. 810 rows. | 422 KB |
| 12 | `fix_batch5_stage_weights.sql` | 1,080 rows. | 316 KB |
| 13 | `batch6_industries_26to30.sql` | Content: retail, sports & fitness, telecom, textiles, transport & delivery. 810 rows. **Completes all 30.** | 425 KB |
| 14 | `fix_batch6_stage_weights.sql` | 1,080 rows. | 316 KB |

Every content file is followed immediately by its own weight file, so a staged
rollout can verify one batch before starting the next.

### Two files you may not need

- **`fix_schema_widen_answers_score_label.sql`** (file 1) — skip it if
  `alembic_version` already reads `d4a91c7e2b83`.
- **`fix_stage_weight_curves.sql`** — **not needed on a fresh load.** It exists
  only to correct databases that received the earlier flat-curve weight files.
  Files 4, 6, 8, 10, 12 and 14 already carry the corrected per-dimension curve,
  so on a database with no batch content it changes nothing. Verified: the md5
  of every batch stage_weight value is identical before and after running it on
  a freshly loaded database.
- **`fix_batch_stage_weights.sql`** (no number) is **superseded — do not run
  it.** It was the original combined batch 1 + 2 file, 2,160 statements across
  ten industry prefixes, which could not be deployed one batch at a time.
  Files 4 and 6 replace it.

  It also has a defect the numbered files do not: its final check asks whether
  any matching root cause is missing weight rows, and against a database with
  **no** batch root causes that question has no failures to find, so it
  reports "stage weights ok" having inserted nothing. Verified. Do not read a
  pass from that file as proof of anything. Found by the AWS team in review.

### Sequence privileges — read this before running anything

Every file that inserts rows used to open with plain `setval()` calls to repair
its sequences. **`setval()` needs UPDATE on the sequence. `INSERT` needs only
USAGE, through `nextval()`.** So a migration role holding INSERT on the tables
and USAGE on the sequences — an ordinary least-privilege arrangement, and the
one in use here — could not run them, and the load died at the first statement:

```
ERROR: permission denied for sequence interventions_intervention_id_seq
```

before a single row was inserted. This affected **thirteen files**: all six
content batches (five `setval` calls each), the interventions file, and all six
weight files. The AWS team hit it on the interventions file and flagged it.

Every one of those files now checks each sequence first and only calls
`setval()` where the sequence genuinely sits behind `max(id)` — which happens
only where rows arrived with explicit ids, as the original catalogue did.
Three outcomes, all tested against a role with INSERT + USAGE and no sequence
UPDATE:

- **every sequence already ahead** → skipped entirely, **no privilege needed**,
  load proceeds. This is the normal case.
- **behind, and the role may `setval`** → repaired, with a notice saying how
  many.
- **behind, and the role may not** → **fails before changing anything**, and
  lists each affected sequence with its highest id, plus both remedies: the
  `GRANT USAGE, UPDATE ON ALL SEQUENCES IN SCHEMA public TO current_user` or
  the exact `SELECT setval(…)` statements for the table owner to run.

Verified by running the complete set — interventions, then all six content
batches each followed by its weight file — as that restricted role, start to
finish. All thirteen succeeded, and the sequences ended level with their
tables (problems max 1374 / sequence 1374; questions 8649 / 8649;
root_cause_weights 22737 / 22737), so nothing is left primed to collide.

---|---|---|---|
| problems | +45 | +135 | +270 |
| root causes | +135 | +405 | +810 |
| questions | +270 | +810 | +1,620 |
| interventions | +90 | +270 | +540 |
| industry mappings | +270 | +810 | +1,620 |
| stage-weight rows | +1,080 | +3,240 | +6,480 |

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

**If your database is already at alembic revision `d4a91c7e2b83`, this change
is DONE — skip file 1 entirely.** That revision IS this fix
(`widen_answers_score_label`) and it is the current head.

`c9f41b8e3a07` is its PARENT, not a version you should be on. An earlier draft
of this document mentioned it as a `down_revision` and that read as "the
expected production version", which it is not. Being at `d4a91c7e2b83` means
you are ahead of it and correct.

Check with:

```sql
select version_num from alembic_version;
```

- `d4a91c7e2b83` → the schema fix is applied. Skip file 1. **Do not run
  `alembic upgrade head`** — there is nothing to upgrade to.
- anything older → apply file 1 (the SQL), or the migration as a one-off ECS
  task. Not both, though both are idempotent so doing both is harmless.

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

## 4a. Batch 3 (industries 11–15)

`batch3_industries_11to15.sql` and `fix_batch3_stage_weights.sql`.

Same shape as batches 1 and 2 — 45 problems, 135 root causes, 270 questions, 90
interventions, 270 mapping rows — with two differences worth knowing:

- The stage weights were written **with** the content this time, rather than
  after a failed diagnosis run found them missing. Same relevance curve as
  batches 1–2.
- Evidence concentration is built in, not retrofitted: the emitter puts both of
  a stage's questions on the same root cause, so `fix_concentrate_batch_evidence.sql`
  has no batch 3 work to do. Measured after loading: exactly 2.00 questions per
  (root cause, stage), min 2, max 2.

Verified after loading, per industry: 9 problems across all 9 dimension codes
and all 3 previously-starved pillars, 18 of roughly 38 own-industry Stage 0→1
questions coming from this batch, and the selection engine returning a full
12-question opening block with every pillar covered.

## 4b. Batch 4 (industries 16–20), and a correction to my own stage weights

`batch4_industries_16to20.sql`, `fix_batch4_stage_weights.sql`, and
`fix_stage_weight_curves.sql`.

Batch 4 is the same shape as the others — 810 rows, 9 dimensions per industry,
evidence concentration built in at 2.00 questions per (root cause, stage).

It is also the batch that finally allowed the detection chain to be tested end
to end, because SaaS is the one industry with a human-written answer bank. That
run found a mistake in my own work, which file 11 corrects.

**What was wrong.** All three stage-weight files wrote the same eight values for
every cause: `1.0, 2.0, 2.0, 2.0, 1.5, 1.0, 0.5, 0.5`. That put every one of
the 540 batch causes at the maximum `2.00` at Early Traction, while the original
catalogue is spread 0.50–2.00 there with a mean of 1.557 and only 20% of causes
at the top value.

**What it did.** A real SaaS founder run at Early Traction returned batch causes
at ranks 1, 2, 3, 4 and 5, with all three top findings from batch content, each
carrying `stage_probability` 1.0000 against 0.6667 for the original causes below
them. The intent was to remove a handicap; the effect was to hand the new
content an advantage. A ranking that looks like new content winning on merit,
when it is winning on a weight I chose, is worse than the handicap it replaced.

**The correction.** `stage_weight` answers "how relevant is this cause at this
stage", which is a property of the **dimension**, not of the batch the content
arrived in. File 11 replaces the flat curve with one curve per dimension,
reasoned from what each dimension is — role clarity cannot be wrong before there
is a team; founder dependency is exactly what binds at Expansion. At Early
Traction this lands the batch mean on 1.556 against the catalogue's 1.557.

**And the content still surfaces.** Re-running the same diagnosis after the
correction: batch causes still hold ranks 1–5, but now at the same
`stage_probability` as the causes below them (0.6667), with the margin between
rank 5 and rank 6 narrowing from 0.089 to 0.022. It survived losing the
advantage, which is the only version of that result worth reporting.

## 4c. Batch 5 (industries 21–25)

`batch5_industries_21to25.sql` and `fix_batch5_stage_weights.sql`.

Same shape as the others. The one difference worth knowing: **batch 5 uses the
per-dimension stage curve from the start**, so it is the first batch that never
needed correcting. Its own self-check refuses to commit if the Early Traction
mean comes out above 1.7, which is the signature of the flat curve returning.

Measured on load: 9 problems per industry across all 9 dimension codes and 3
pillars, 2.00 questions per (root cause, stage), Early Traction weight mean
1.556 against the catalogue's 1.557. All five industries return a full
12-question opening block with every pillar covered and zero foreign-industry
leakage.

## 4d. Batch 6 (industries 26–30) — the last one

`batch6_industries_26to30.sql` and `fix_batch6_stage_weights.sql`.

Retail, Sports & Fitness, Telecom, Textiles, Transport & Delivery. **This
completes all 30 industries.** Like batch 5, it uses the per-dimension stage
curve from the start and refuses to commit if its Early Traction mean exceeds
1.7, so file 11 has nothing of batch 6's to correct.

Once files 1–15 are applied, the whole set measures:

```
industries with all 9 dimensions across all 3 previously-starved pillars:  30 of 30
stage weight mean at Early Traction:   batch 1.556   catalogue 1.557
questions per (root cause, stage):     2.00 (min 2, max 2)
```

And the real selection engine, run for every one of the 30 industries at Early
Traction, returns a full 12-question opening block, `ALL PILLARS COVERED`, and
`OTHER INDUSTRIES' QUESTIONS STILL ELIGIBLE: 0` — 30 for 30, no exceptions.

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
[PASS] problems = 893
[PASS] root_causes = 4506
[PASS] interventions = 1781
[PASS] root_cause_weights = 13016
[PASS] questions = 6160
[PASS] question_industry_mapping is populated -- 2820 rows
[PASS] readiness_pillars weightage sums to 100 -- got 100.00
[PASS] root-cause ranking weights sum to 1.0 -- got 1.0000
[PASS] root causes can reach an intervention -- 36/4506 (0.8%) cannot
[INFO] problems carrying root causes but no intervention: 6
RESULT: all hard checks passed
```

Then check that a founder in one of the new industries is actually asked the
new questions, which the counts above cannot tell you:

```bash
python -m scripts.qa.industry_selection_preflight --industry gaming --stage 4
```

This runs the real selection engine read-only. Expect a 12-question industry
opening block, `ALL PILLARS COVERED`, and
`OTHER INDUSTRIES' QUESTIONS STILL ELIGIBLE: 0`. If the last line is not zero,
`question_industry_mapping` did not load and the industry gate is off.

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
