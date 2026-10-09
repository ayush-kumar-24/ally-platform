# Architecture documents

Two generated reference documents, plus the scripts that produce them.

| Document | What it answers |
| --- | --- |
| [`ER_Diagram.md`](ER_Diagram.md) | What columns does this table have, what type, what key, and what does it point at |
| [`Entity_Mapping.md`](Entity_Mapping.md) | What is this entity, who writes it, who reads it, which screen does it reach |

Both are **textual** rather than drawn, deliberately: a text ER diffs in git,
survives a paste into Word, and can be searched for a column name. None of
those is true of a picture.

## Regenerating

Both documents are generated. Re-run after any migration:

```bash
cd backend
export DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ally"
export SECRET_KEY="<any 32 chars>"

python3 -m alembic upgrade head          # the documents describe the DB, so migrate first

python3 scripts/docs/extract_schema.py                > /tmp/schema.json
python3 scripts/docs/extract_usage.py  /tmp/schema.json > /tmp/usage.json
python3 scripts/docs/render_er.py      /tmp/schema.json > ../docs/architecture/ER_Diagram.md
python3 scripts/docs/render_mapping.py /tmp/schema.json /tmp/usage.json \
                                                      > ../docs/architecture/Entity_Mapping.md
```

`extract_schema.py` **exits non-zero if any table is unassigned to a part.**
That is the guard that keeps these honest: the previous versions of these
documents went stale by describing 47 tables of a schema that had grown past
them, silently. Now a new table fails the build until somebody files it and
writes one line about what it is. It has already caught one — `gateway_plans`,
added by `5b8e2f4a7c19` the day these were written.

## Word versions

`ER_Diagram.docx` and `Entity_Mapping.docx` are the same content as the
Markdown, for circulating to anyone who would rather read in Word. They are
generated too, so regenerate them in the same pass:

```bash
pandoc docs/architecture/ER_Diagram.md     -o docs/architecture/ER_Diagram.docx \
       --toc --toc-depth=2 --standalone
pandoc docs/architecture/Entity_Mapping.md -o docs/architecture/Entity_Mapping.docx \
       --toc --toc-depth=2 --standalone
python3 backend/scripts/docs/fix_docx_tables.py docs/architecture/*.docx
```

The last step is not optional. Pandoc gives every table equal column widths,
which in these documents puts `Notes` -- a sentence -- on the same width as
`Req`, which holds the word "Yes", and leaves the table occupying 5.50 of the
6.27 inches available. `fix_docx_tables.py` picks a width profile from each
table's own header row and uses the full page. It re-laid out 221 tables
across the two documents.

Pass `--reference-doc=<an existing .docx>` to pandoc to inherit house styles
from a previous version of the document.

## Where the words come from

Types, keys, relationships, row counts and constraints are read from the
database and are exact.

Descriptions are **hand-written**, in `backend/scripts/docs/descriptions.py`.
They have to be: only 2 of 105 tables and 3 of 1,194 columns carry a `COMMENT`
in the database, so nothing machine-readable says what any of it is *for*. A
table with no description renders as `-- not yet described --` rather than
getting a guess.

If those descriptions ever move into the schema as real `COMMENT ON`
statements, delete `descriptions.py` and let the extractor pick them up — a
description that lives in the schema cannot drift from it.

## Why the database and not the ORM

There is no single metadata object that covers this schema:

- `app/models/schema.py` alone registers 69 of 105 tables
- all eighteen model modules together reach 81
- 23 tables have no SQLAlchemy model at all

So no import gives the whole schema, and a document built from one would omit
whatever its `Base` could not see. The migrated database is the only complete
answer.
