# Where the industry batch SQL comes from

The `../batch*_industries_*.sql` files are generated, not hand-written. This
directory holds what generates them.

```
b1/  industries 1-5    agritech, automotive, fintech, beauty_personal_care, proptech
b2/  industries 6-10   consumer_electronics, ecommerce_d2c, edtech, cleantech_energy, media_entertainment
b3/  industries 11-15  fashion_apparel, foodtech, gaming, healthtech, travel_hospitality
```

Each batch directory has:

- `schema.py` — the pillar/dimension map, the nine `dimension_code` values in
  the order every industry supplies them, and the batch's five industries with
  their `problem_code` prefixes.
- `iNN_<industry>.py` — the content: nine entries per industry, one per
  dimension, each carrying the problem, three root causes, two interventions
  and eighteen questions (two per stage group, three stage groups).
- `emit_portable.py` — writes the SQL.

```bash
cd b3 && python3 emit_portable.py     # writes ally_batch3_PORTABLE_no_ids.sql beside itself
```

## Why this is committed

It was not, for batches 1 and 2. They were written in a session scratchpad,
which is reclaimed when the container is. The 1,620 rows of batch 1–2 content
would have survived only as generated SQL: loadable, but not amendable and not
reviewable as prose. Rewording a question would have meant editing 810 INSERT
statements by hand.

All three batches were regenerated from these files and diffed against the
committed SQL before this was added. All three are byte-identical, so what is
here is genuinely the source of what ships.

## The question language standard

The pillar and dimension names stay technical because the engine reads them.
The founder never sees those. Every *question* is written to be answered by a
founder reading it once, on a phone, at the end of a long day:

- one idea, usually under fifteen words
- everyday words — no "unit economics", "contribution margin", "ICP", "CAC"
- asks about something that happened, not about a concept
- says "how many" or "how much" when a number is wanted

Batch 3 measured: 270 questions, mean 9.1 words, longest 13, no banned terms,
no duplicate question text anywhere in the batch.

Duplicates deserve a word. A founder only ever sees their own industry's
mapped questions, so the same question text in two industries is harmless in
principle. In practice it reads as boilerplate — a founder can tell when a
question was written for nobody in particular. Batch 3 started with 20 such
repeats across its five industries and each was rewritten to name its own
trade, so the check is now zero within an industry *and* zero across the batch.

## Two things the emitter does on purpose

**No hardcoded ids.** Every insert lets the sequence assign the primary key and
resolves each foreign key by code at insert time (`where problem_code = ...`).
Production RDS cannot be read from a build environment, so its id maxima are
unknown; a file with explicit primary keys either collides or needs a
pre-check and a re-emit. The emitter also pushes each sequence above its
table's max first, which repairs the case where an earlier explicit-id load
left a sequence behind its own table.

**Evidence concentration.** Both of a stage's two questions point at the *same*
root cause, and which cause it is rotates by stage group.

They used to rotate per question, so each cause collected one question per
stage. Measured consequence: an E-Commerce founder was asked ten batch
questions, they mapped to ten distinct root causes with one piece of evidence
each, and not one reached the candidate set — `ROOT_CAUSE_MAX_CANDIDATES` is 8
and the original catalogue's causes carry several questions apiece, so they
filled every slot. `detection_score` is the mean severity of a cause's negative
evidence, so a single answer cannot outrank three.

Batches 1–2 needed `fix_concentrate_batch_evidence.sql` to repair this after
the fact. Batch 3 has it built in, and measures 2.00 questions per
(root cause, stage) — min 2, max 2 — straight after loading.
