# Ally help content — export

Two files, both generated from `backend/data/help_content/answers/*.json`.
Regenerate rather than hand-edit: the per-group JSON files are the source of
truth.

| File | For | Size |
|---|---|---|
| `ally-help-answers.json` | The app, and anyone reading the content | ~460 KB |
| `ally_help_content.sql` | **Hand this to the AWS teammate** — schema + all data | ~506 KB |

**285 questions of the 300 in the Founder Question Bank. 270 are cleared to
publish.** The other 15 are deliberately unanswered and each says why; ids
180–194 (group 15, paying and invoices) are not written at all because checkout
does not exist yet.

---

## For the AWS teammate

One command. Nothing else in the database is touched.

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f ally_help_content.sql
```

It creates one table, `support_bot_answers`, two indexes, a search function and
an `updated_at` trigger, then loads all 285 rows.

**It is safe to run twice.** The table is created only if absent and every row is
an UPSERT keyed on `question_id`, so re-running refreshes the content and never
duplicates it. This was tested — two consecutive runs produce identical counts.

Expected at the end:

```
 total | published | open_for_team | held | groups
   285 |       270 |            14 |    1 |     24
```

The script prints that itself, plus a per-group breakdown.

---

## Why one table

So the team can edit an answer, add a question or take one offline **without a
deploy**. Content in rows, not in code.

`question_id` is the stable id from the Founder Question Bank. Never renumber
one — answers reference each other by it. New questions continue from 301.

### Reading it

```sql
SELECT * FROM support_bot_search('I forgot my password');
SELECT * FROM support_bot_search('how much is a discovery call', 3);
```

Use the function rather than writing a `tsquery` by hand. The obvious version
(`plainto_tsquery`) ANDs every word, so a founder typing a whole sentence gets
**zero rows** — verified against this exact content. The function ORs the words,
ranks the results, and weights a match in the *question* above one in the answer
body.

Being straight about what it is: this is keyword matching. It misses things a
person would catch — "forgot my password" nearly misses the answer titled "I've
forgotten my password", because the English stemmer does not join *forgot* to
*forgotten*. Good as a lookup and a fallback. The bot itself should put an LLM in
front of these rows.

### Two columns that must never reach a founder

`finding` and `note` hold internal product observations — defects noticed while
writing the answer. `support_bot_search()` does not return them. Anything else
querying this table directly must exclude them.

### Editing an answer

```sql
UPDATE support_bot_answers
   SET answer       = 'the new wording',
       verified_on  = current_date,
       verified_how = 'what you checked it against'
 WHERE question_id = 143;
```

Please fill in `verified_how`. Every answer here was walked against the running
product, and that is the only reason any of it can be trusted — the live FAQ went
wrong precisely because nobody could tell when it had last been true.

### Taking one offline

```sql
UPDATE support_bot_answers
   SET is_published = false, status = 'retired'
 WHERE question_id = 42;
```

Prefer this to `DELETE`. The row keeps its history and can come back.

---

## The guards in the schema

Four check constraints, each tested:

* a row cannot be **published without an answer**
* a row cannot be **published unless its status is `answered`** — so nothing
  still with the team can leak out
* an **unanswered row must say why** (`blocked_by`)
* `status` and `answer_type` only accept known values

## Regenerating

```bash
python scripts/build_help_export.py     # rebuilds both files
```

The generator refuses to run if two source files claim the same `question_id`.
