# Bringing `founder_dna_questions` up to date on production (RDS)

**For:** whoever holds the production `DATABASE_URL`
**Est. time:** ~5 minutes, mostly waiting on OpenAI
**Risk:** low — every step below is either read-only or insert/update-only

---

## Do NOT copy the table from Supabase

The obvious-sounding plan — dump `founder_dna_questions` out of Supabase and
overwrite it on RDS — would break production. Three reasons, each sufficient
on its own:

**1. It would orphan real founders' answers.**
`founder_dna_answers.founder_dna_question_id` is a foreign key with
`ON DELETE NO ACTION`. Postgres will refuse to delete the parent rows while
answers reference them. Forcing it through with `CASCADE` would delete real
founders' answers permanently.

**2. The IDs do not line up and cannot be made to.**
`founder_dna_question_id` defaults to `nextval(...)` — it is assigned by
insertion order in each database independently. Supabase's run 98–154;
RDS's will be whatever its own history produced. Importing Supabase's IDs
would point every existing RDS answer at the wrong question.

**3. Supabase is not the source of truth.**
All 57 questions are defined in code, in
`backend/scripts/seed_founder_dna_questions.py`. Supabase's table is just
that script's output. There is nothing in Supabase that isn't in git — so
there is nothing to copy.

The correct approach is to bring RDS to the same state by running the same
two scripts against it. Same content, same embeddings, and **no ID is ever
moved**, so nothing that references them can break.

---

## Before you start

Run from `backend/`, with the environment pointed at **production**:

```bash
export DATABASE_URL='<production RDS URL>'
export OPENAI_API_KEY='<the production key>'
export EMBEDDING_PROVIDER=openai
```

`EMBEDDING_MODEL` / `EMBEDDING_DIMENSION` / `EMBEDDING_VERSION` already
default correctly (`text-embedding-3-small` / `1536` / `openai-3-small-v1`).

---

## Step 1 — See what RDS actually has (read-only)

```bash
python -m scripts.embedding_migration.03_verify_embeddings
```

Read the `founder_dna_questions` row. Expect `null` to be **57** (nothing
embedded) or **0** (already done). Anything under `bad_dim` or `bad_model`
means a previous run used a different model — stop and say so before
continuing.

This is also your confirmation that `DATABASE_URL` points where you think it
does: the row counts for `questions` and `root_causes` will look nothing like
a dev database's.

## Step 2 — Make sure all 57 questions exist (insert-only)

```bash
python -m scripts.seed_founder_dna_questions
```

Idempotent, keyed on `(dimension_code, stage_group, question_text)`. If RDS
already has all 57, this inserts nothing and says so. It never updates or
deletes an existing row.

**Do not pass `--replace`.** That flag refreshes the bank wholesale and is
designed to refuse when answers reference it — on production, with real
answers present, it will either refuse or do something you don't want.

## Step 3 — Generate the embeddings

```bash
# Look first — reports how many rows would be embedded, writes nothing:
python -m scripts.embedding_migration.02_regenerate_embeddings \
    --tables founder_dna_questions --dry-run

# Then, if the number matches what step 1 told you:
python -m scripts.embedding_migration.02_regenerate_embeddings \
    --tables founder_dna_questions
```

Only touches rows where `embedding IS NULL`, so it is resumable — if it dies
part-way, run it again and it finishes the remainder. It embeds through the
app's own OpenAI adapter and aborts if the provider's dimension doesn't match
`EMBEDDING_DIMENSION`, so a misconfigured model can't quietly write unusable
vectors.

Roughly one API call per row: expect ~30 seconds for 57, and a few cents.

## Step 4 — Verify

```bash
python -m scripts.embedding_migration.03_verify_embeddings
```

`founder_dna_questions` should now read `embedded 57 / bad_dim 0 /
bad_model 0 / null 0` and the script should exit 0.

---

## Note on the code

Two small changes are needed for the above and are already in the repo:

* `02_regenerate_embeddings.py` and `03_verify_embeddings.py` now include
  `founder_dna_questions` in their table lists — it was missing from both,
  which is why the bank was never embedded anywhere.
* `02_regenerate_embeddings.py` had a real bug: the update used
  `:vec::vector`, and SQLAlchemy's `text()` does not bind `:vec` when a `::`
  cast follows it immediately — Postgres answered *"syntax error at or near
  :"*. Now `CAST(:vec AS vector)`. This affected **every** table, so that
  script could not have run successfully in its previous form.

Make sure the deployed checkout includes those before running.

---

## Why the IDs still won't match, and why that's fine

After this, RDS and Supabase will hold the same 57 questions with the same
text and equivalent embeddings — but **different `founder_dna_question_id`
values**. That is correct and should not be "fixed".

The id is a local surrogate key. Nothing outside its own database refers to
it: answers join to questions *within* one database. Forcing the two to agree
would mean rewriting primary keys under live foreign keys, which is how you
lose data. Matching content is what matters; matching integers is not.
