# -*- coding: utf-8 -*-
"""Rebuild the two help-content export files from the per-group answer JSON.

    python scripts/build_help_export.py

Writes data/help_content/export/ally-help-answers.json  (one row per question)
and data/help_content/export/ally_help_content.sql      (schema + all the data)

The per-group files in data/help_content/answers/ are the source of truth; both
exports are generated and should never be hand-edited. Superseded entries are
dropped, so every question appears exactly once from its canonical group file --
and the build FAILS LOUDLY if two files ever claim the same question_id, which is
the one mistake that would silently corrupt the export.
"""
import json, io, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data", "help_content", "answers")
OUT = os.path.join(ROOT, "data", "help_content", "export")
EXPORT = OUT
os.makedirs(OUT, exist_ok=True)



rows, seen, groups = [], {}, {}

for path in sorted(glob.glob(os.path.join(SRC, "*.json"))):
    d = json.load(io.open(path, encoding="utf-8"))
    gnum = d.get("group_number")
    gslug = d.get("group")
    gtitle = d.get("group_title")
    if gnum is not None:
        groups[gnum] = {"group_number": gnum, "group_slug": gslug, "group_title": gtitle,
                        "source_file": os.path.basename(path)}
    for a in d["answers"]:
        if a.get("status") == "superseded":
            continue
        qid = a["id"]
        if qid in seen:
            raise SystemExit(f"DUPLICATE question {qid}: {seen[qid]} and {os.path.basename(path)}")
        seen[qid] = os.path.basename(path)
        v = a.get("verified") or {}
        rows.append({
            "question_id": qid,
            "group_number": gnum,
            "group_slug": gslug,
            "group_title": gtitle,
            "question": a["question"],
            "answer": a.get("answer"),
            "answer_type": a.get("answer_type"),
            "status": a.get("status"),
            "is_published": bool(a.get("answer")) and a.get("status") == "answered",
            "blocked_by": a.get("blocked_by"),
            "links": a.get("links") or [],
            "verified_on": v.get("walked_on"),
            "verified_how": v.get("how"),
            "finding": a.get("finding"),
            "note": a.get("note"),
            "source_file": os.path.basename(path),
        })

rows.sort(key=lambda r: r["question_id"])
answered = sum(1 for r in rows if r["is_published"])

export = {
    "schema_version": "1.0",
    "export_name": "ally_help_answers",
    "generated_on": "2026-09-05",
    "source": "backend/data/help_content/answers/*.json",
    "about": (
        "Every founder-facing help question for Ally, with its answer where one exists. "
        "One row per question; superseded drafts are excluded, so each question appears "
        "exactly once from its canonical group file. Answers were walked against the "
        "running product rather than written from memory -- `verified_how` records what "
        "each one was checked against."),
    "counts": {
        "bank_total": 300,
        "questions_written": len(rows),
        "published": answered,
        "open_for_team": sum(1 for r in rows if r["status"] == "open_for_team"),
        "held_pending_product_change": sum(
            1 for r in rows if r["status"] == "answered_pending_product_change"),
        "retired": sum(1 for r in rows if r["status"] == "retired"),
        "not_yet_written": 300 - len(rows),
        "groups_written": len(groups),
    },
    "coverage_note": (
        "All 300 questions from the Founder Question Bank are now present. Group 15 "
        "(paying, invoices, cancelling) was written on 2026-09-06: three answers are live "
        "on settled policy -- GST included, the refund window, what a downgrade keeps -- "
        "and eleven stay unanswered until checkout is built, because they describe how a "
        "payment behaves and guessing at that would be a promise we could not keep."),
    "field_notes": {
        "question_id": "Stable id from the Founder Question Bank v3. Never reuse or renumber.",
        "answer": "null means deliberately unanswered -- see blocked_by.",
        "answer_type": "walked = checked against the running product. policy = needs a stated position, not a test.",
        "status": ("answered = live. open_for_team = waiting on a decision, see blocked_by. "
                   "answered_pending_product_change = written but held until the product "
                   "changes, see note. retired = deliberately withdrawn; the id is reserved "
                   "so the question is not re-added."),
        "is_published": "True only when there is an answer AND status is answered. This is the flag a bot should filter on.",
        "blocked_by": "Why an unanswered question is unanswered. Set only when answer is null.",
        "links": "In-app paths the answer points at.",
        "verified_on / verified_how": "When it was walked, and what against. Kept so an answer can be re-checked rather than trusted.",
        "finding": "A product defect or gap noticed while answering. Internal -- never shown to a founder.",
        "note": "Maintenance context. Internal -- never shown to a founder.",
    },
    "groups": [groups[k] for k in sorted(groups)],
    "answers": rows,
}

p = os.path.join(OUT, "ally-help-answers.json")
io.open(p, "w", encoding="utf-8").write(json.dumps(export, indent=2, ensure_ascii=False) + "\n")
print(f"wrote {p}")
print(f"  {len(rows)} questions, {answered} published, {len(rows)-answered} open, {len(groups)} groups")
print(f"  id range {rows[0]['question_id']}-{rows[-1]['question_id']}")
missing = sorted(set(range(1, 301)) - set(seen))
print(f"  ids from 1-300 with no row: {len(missing)}" + (f" -> {missing[:20]}" if missing else ""))


# =====================================================================
#  Second half: the SQL file, built from the JSON just written.
# =====================================================================

d = json.load(io.open(os.path.join(EXPORT, "ally-help-answers.json"), encoding="utf-8"))


def q(v):
    """Quote a value as a Postgres literal."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        if not v:
            return "'{}'"
        inner = ",".join('"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"' for x in v)
        return "'{" + inner.replace("'", "''") + "}'"
    return "'" + str(v).replace("'", "''") + "'"

c = d["counts"]
L = []
w = L.append

w("-- =====================================================================")
w("--  Ally - Help & Support bot content")
w("--  ONE table holding every founder-facing question and its answer.")
w("-- ")
w("--  Generated  : %s  (from backend/data/help_content/answers/*.json)" % d["generated_on"])
w("--  Questions  : %d written of %d in the bank" % (c["questions_written"], c["bank_total"]))
w("--  Publishable: %d" % c["published"])
w("--  Target     : PostgreSQL 12+ / AWS RDS")
w("-- ")
w("--  HOW TO RUN")
w("--    psql \"$DATABASE_URL\" -v ON_ERROR_STOP=1 -f ally_help_content.sql")
w("-- ")
w("--  It is SAFE TO RUN TWICE. The table is created only if absent, and every")
w("--  row is an UPSERT keyed on question_id -- so re-running refreshes the")
w("--  content and never duplicates it. Nothing is dropped and nothing else in")
w("--  the database is touched.")
w("-- ")
w("--  WHY ONE TABLE. Content lives in rows rather than in code so the team can")
w("--  edit an answer, add a question or take one offline without a deploy.")
w("--  question_id is the stable id from the Founder Question Bank -- never")
w("--  renumber it; new questions continue from 301.")
w("-- =====================================================================")
w("")
w("BEGIN;")
w("")
w("-- ---------------------------------------------------------------------")
w("-- 1. Schema")
w("-- ---------------------------------------------------------------------")
w("")
w("CREATE TABLE IF NOT EXISTS support_bot_answers (")
w("    question_id     integer      PRIMARY KEY,")
w("        -- Stable id from the Founder Question Bank v3. Never reused,")
w("        -- never renumbered: answers reference each other by it.")
w("")
w("    group_number    smallint     NOT NULL,")
w("    group_slug      text         NOT NULL,")
w("    group_title     text         NOT NULL,")
w("        -- The 25 founder-facing groups. Denormalised on purpose: this table")
w("        -- is read far more than it is written, and a join to fetch a group")
w("        -- name earns nothing.")
w("")
w("    question        text         NOT NULL,")
w("    answer          text,")
w("        -- NULL means deliberately unanswered. blocked_by says why.")
w("")
w("    answer_type     text         NOT NULL DEFAULT 'walked',")
w("    status          text         NOT NULL DEFAULT 'answered',")
w("    is_published    boolean      NOT NULL DEFAULT false,")
w("        -- THE FLAG THE BOT FILTERS ON. True only when there is an answer")
w("        -- AND it is cleared to be shown. Set by the check constraint below,")
w("        -- so an answer cannot be published by accident.")
w("")
w("    blocked_by      text,")
w("        -- Why an unanswered question is unanswered. Internal.")
w("")
w("    links           text[]       NOT NULL DEFAULT '{}',")
w("        -- In-app paths the answer points at, e.g. {/app/profile}.")
w("")
w("    verified_on     date,")
w("    verified_how    text,")
w("        -- When this answer was last walked against the running product, and")
w("        -- what against. Kept so an answer can be re-checked rather than")
w("        -- trusted -- the live FAQ was wrong precisely because nobody could")
w("        -- tell when it had last been true.")
w("")
w("    finding         text,")
w("    note            text,")
w("        -- Internal only. A product defect noticed while answering, and")
w("        -- maintenance context. NEVER show either to a founder.")
w("")
w("    source_file     text,")
w("    created_at      timestamptz  NOT NULL DEFAULT now(),")
w("    updated_at      timestamptz  NOT NULL DEFAULT now(),")
w("")
w("    CONSTRAINT support_bot_answers_status_check")
w("        CHECK (status IN ('answered', 'open_for_team',")
w("                          'answered_pending_product_change', 'retired')),")
w("    CONSTRAINT support_bot_answers_type_check")
w("        CHECK (answer_type IN ('walked', 'policy', 'generated')),")
w("    -- A published row must actually have an answer. This is the guard that")
w("    -- stops an empty or team-blocked row ever reaching a founder.")
w("    CONSTRAINT support_bot_answers_publishable_check")
w("        CHECK (NOT is_published OR (answer IS NOT NULL AND status = 'answered')),")
w("    -- An unanswered row must say why. A RETIRED row is exempt: it has been")
w("    -- deliberately withdrawn rather than left pending, and its reason lives")
w("    -- in `note`. Retired rows are kept so their question_id is reserved and")
w("    -- nobody re-adds the question by accident.")
w("    CONSTRAINT support_bot_answers_blocked_check")
w("        CHECK (answer IS NOT NULL OR blocked_by IS NOT NULL")
w("               OR status = 'retired')")
w(");")
w("")
w("COMMENT ON TABLE support_bot_answers IS")
w("    'Founder-facing help content for the Ally support bot. One row per question. "
  "Edit answers here rather than in code -- no deploy needed.';")
w("")
w("-- The bot's own query is: published rows, by group, in question order.")
w("CREATE INDEX IF NOT EXISTS support_bot_answers_published_idx")
w("    ON support_bot_answers (group_number, question_id)")
w("    WHERE is_published;")
w("")
w("-- Free-text search over the question and the answer together, which is how a")
w("-- founder actually arrives: they type a sentence, not a question id.")
w("CREATE INDEX IF NOT EXISTS support_bot_answers_search_idx")
w("    ON support_bot_answers")
w("    USING gin (to_tsvector('english', question || ' ' || coalesce(answer, '')));")
w("")
w("-- ---------------------------------------------------------------------")
w("-- Search.")
w("--")
w("-- The obvious query -- plainto_tsquery -- ANDs every word, so a founder")
w("-- typing a whole sentence gets NOTHING back. Tested against this content:")
w("-- 'how much is a discovery call' and 'why cant I do another diagnosis'")
w("-- both returned zero rows, because no single answer contains every one of")
w("-- those words. That is the wrong failure for a support bot: a real question")
w("-- is a sentence, not a keyword.")
w("--")
w("-- This function ORs the words instead and ranks the results, so a long")
w("-- question finds the answer that matches most of it. Use it rather than")
w("-- writing the query by hand.")
w("-- ---------------------------------------------------------------------")
w("")
w("CREATE OR REPLACE FUNCTION support_bot_search(q text, max_rows integer DEFAULT 5)")
w("RETURNS TABLE (question_id integer, question text, answer text,")
w("               links text[], rank real) AS $$")
w("    WITH terms AS (")
w("        -- Lexemes of the founder's question, OR-ed together.")
w("        SELECT to_tsquery('english',")
w("                   nullif(array_to_string(")
w("                       ARRAY(SELECT unnest(tsvector_to_array(")
w("                                 to_tsvector('english', q)))), ' | '), '')) AS tsq")
w("    )")
w("    SELECT a.question_id, a.question, a.answer, a.links,")
w("           ts_rank(")
w("               -- The QUESTION carries more weight than the answer body. A")
w("               -- founder typing 'it keeps signing me out' should get the")
w("               -- answer to that question first, not one that happens to")
w("               -- mention signing out halfway down.")
w("               setweight(to_tsvector('english', a.question), 'A') ||")
w("               setweight(to_tsvector('english', a.answer),   'B'),")
w("               t.tsq) AS rank")
w("      FROM support_bot_answers a, terms t")
w("     WHERE a.is_published")
w("       AND t.tsq IS NOT NULL")
w("       AND (setweight(to_tsvector('english', a.question), 'A') ||")
w("            setweight(to_tsvector('english', a.answer),   'B')) @@ t.tsq")
w("     ORDER BY rank DESC, a.question_id")
w("     LIMIT max_rows;")
w("$$ LANGUAGE sql STABLE;")
w("")
w("COMMENT ON FUNCTION support_bot_search(text, integer) IS")
w("    'Rank published answers against a founder question. ORs the words rather "
  "than ANDing them, so a full sentence still finds something.';")
w("")
w("-- Keep updated_at honest without the application having to remember.")
w("CREATE OR REPLACE FUNCTION support_bot_answers_touch()")
w("RETURNS trigger AS $$")
w("BEGIN")
w("    NEW.updated_at := now();")
w("    RETURN NEW;")
w("END;")
w("$$ LANGUAGE plpgsql;")
w("")
w("DROP TRIGGER IF EXISTS support_bot_answers_touch_trg ON support_bot_answers;")
w("CREATE TRIGGER support_bot_answers_touch_trg")
w("    BEFORE UPDATE ON support_bot_answers")
w("    FOR EACH ROW EXECUTE FUNCTION support_bot_answers_touch();")
w("")
w("-- ---------------------------------------------------------------------")
w("-- 2. Content  (%d rows)" % len(d["answers"]))
w("-- ---------------------------------------------------------------------")
w("--")
w("-- UPSERT on question_id: re-running this file refreshes every answer in")
w("-- place and inserts nothing twice. created_at is preserved on an update;")
w("-- the trigger above moves updated_at.")
w("")

COLS = ("question_id", "group_number", "group_slug", "group_title", "question",
        "answer", "answer_type", "status", "is_published", "blocked_by", "links",
        "verified_on", "verified_how", "finding", "note", "source_file")

current_group = None
for r in d["answers"]:
    if r["group_number"] != current_group:
        current_group = r["group_number"]
        w("")
        w("-- ---- Group %02d - %s " % (current_group, r["group_title"]) + "-" * max(
            0, 46 - len(r["group_title"])))
    w("INSERT INTO support_bot_answers (%s) VALUES (" % ", ".join(COLS))
    w("    " + ", ".join(q(r[c]) for c in COLS[:5]) + ",")
    w("    " + q(r["answer"]) + ",")
    w("    " + ", ".join(q(r[c]) for c in ("answer_type", "status", "is_published")) + ",")
    w("    " + q(r["blocked_by"]) + ", " + q(r["links"]) + ", " + q(r["verified_on"]) + ",")
    w("    " + q(r["verified_how"]) + ",")
    w("    " + q(r["finding"]) + ",")
    w("    " + q(r["note"]) + ", " + q(r["source_file"]))
    w(")")
    w("ON CONFLICT (question_id) DO UPDATE SET")
    w("    group_number = EXCLUDED.group_number,")
    w("    group_slug   = EXCLUDED.group_slug,")
    w("    group_title  = EXCLUDED.group_title,")
    w("    question     = EXCLUDED.question,")
    w("    answer       = EXCLUDED.answer,")
    w("    answer_type  = EXCLUDED.answer_type,")
    w("    status       = EXCLUDED.status,")
    w("    is_published = EXCLUDED.is_published,")
    w("    blocked_by   = EXCLUDED.blocked_by,")
    w("    links        = EXCLUDED.links,")
    w("    verified_on  = EXCLUDED.verified_on,")
    w("    verified_how = EXCLUDED.verified_how,")
    w("    finding      = EXCLUDED.finding,")
    w("    note         = EXCLUDED.note,")
    w("    source_file  = EXCLUDED.source_file;")
    w("")

w("COMMIT;")
w("")
w("-- ---------------------------------------------------------------------")
w("-- 3. Check it landed")
w("-- ---------------------------------------------------------------------")
w("--")
w("-- Expected after a clean run:")
w("--   total %d, published %d, open_for_team %d, held %d, groups %d" % (
    c["questions_written"], c["published"], c["open_for_team"],
    c["held_pending_product_change"], c["groups_written"]))
w("")
w("SELECT count(*)                                   AS total,")
w("       count(*) FILTER (WHERE is_published)       AS published,")
w("       count(*) FILTER (WHERE status = 'open_for_team')")
w("                                                  AS open_for_team,")
w("       count(*) FILTER (WHERE status = 'answered_pending_product_change')")
w("                                                  AS held,")
w("       count(DISTINCT group_number)               AS groups")
w("  FROM support_bot_answers;")
w("")
w("-- Per group, so a short group is obvious at a glance.")
w("SELECT group_number,")
w("       group_title,")
w("       count(*)                             AS questions,")
w("       count(*) FILTER (WHERE is_published) AS published")
w("  FROM support_bot_answers")
w(" GROUP BY group_number, group_title")
w(" ORDER BY group_number;")
w("")
w("-- ---------------------------------------------------------------------")
w("-- 4. Notes for whoever maintains this")
w("-- ---------------------------------------------------------------------")
w("--")
w("-- READING IT (what the bot should run):")
w("--")
w("--   SELECT * FROM support_bot_search('I forgot my password');")
w("--   SELECT * FROM support_bot_search('how much is a discovery call', 3);")
w("--")
w("--   Use the function, not a hand-written tsquery. plainto_tsquery ANDs every")
w("--   word, so a founder typing a full sentence gets zero rows -- verified")
w("--   against this exact content before shipping. The function ORs and ranks,")
w("--   and weights a match in the QUESTION above one in the answer body.")
w("--")
w("--   BE REALISTIC ABOUT WHAT THIS IS. It is keyword matching, so it misses")
w("--   what a person would catch: 'forgot my password' does not match the")
w("--   answer titled 'I have forgotten my password', because the English")
w("--   stemmer does not join forgot to forgotten. Good enough as a lookup and")
w("--   as a fallback; not a substitute for putting an LLM in front of these")
w("--   rows, which is what the bot should actually do.")
w("--")
w("--   It returns only published rows, and only the four columns a founder may")
w("--   see. NEVER select finding or note into anything founder-facing: both")
w("--   hold internal product notes.")
w("--")
w("-- EDITING AN ANSWER:")
w("--")
w("--   UPDATE support_bot_answers")
w("--      SET answer = 'the new wording',")
w("--          verified_on = current_date,")
w("--          verified_how = 'what you checked it against'")
w("--    WHERE question_id = 143;")
w("--")
w("--   Please fill in verified_how. Every answer in here was walked against the")
w("--   running product, and that is the only reason it can be trusted. An")
w("--   answer edited from memory is how the last FAQ went stale.")
w("--")
w("-- TAKING ONE OFFLINE (rather than deleting it):")
w("--")
w("--   UPDATE support_bot_answers")
w("--      SET is_published = false, status = 'retired'")
w("--    WHERE question_id = 42;")
w("--")
w("-- ADDING A NEW QUESTION:")
w("--")
w("--   Continue question_id from 301. Ids 1-300 are the Founder Question Bank")
w("--   v3 and are referenced by other answers, so never reuse one.")
w("--")
w("-- STILL TO COME:")
w("--")
w("--   Ids 180-194 (group 15, 'Paying, invoices, cancelling') are absent on")
w("--   purpose. Checkout is not built, so every answer there would be either")
w("--   'not yet' or a promise we cannot keep. They arrive the day Razorpay")
w("--   does.")
w("--")
w("--   15 rows here have no answer yet -- they are waiting on decisions the")
w("--   team has to make, not on work. blocked_by on each says which.")
w("-- ---------------------------------------------------------------------")

out = os.path.join(EXPORT, "ally_help_content.sql")
io.open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
size = os.path.getsize(out)
print("wrote", out)
print("  %d lines, %.0f KB, %d rows" % (len(L), size / 1024, len(d["answers"])))
