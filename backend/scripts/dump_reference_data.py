"""Write the platform's reference data to `data/reference/` so it can be rebuilt.

THE PROBLEM THIS SOLVES. Run the migrations against an empty Postgres and you
get 92 tables and then a hard stop:

    RuntimeError: Expected MAX(question_id)=2129, found None

Migration 63340a6e5fdb seeds questions 2130+ and asserts the first 2129 are
already there. Nothing in this repository puts them there. Measured across
every reference table, the hole is wider than the question bank -- these have
no seed in any migration and no SQL in data/:

    root_cause_weights      9776   the weights behind every diagnosis
    question_tag_mapping    6559
    problem_stage_mapping    553
    interventions            416   the action plans founders are given
    scoring_rules             46   every threshold the engine reads AT BOOT
    industry_stage_thresholds 32
    behaviour_patterns        27
    blind_spots               20
    stage_diagnosis_logic      3

`scoring_rules` is the sharpest: `config.py::_require` raises on a missing rule,
so without it the reasoning engine does not start. A restored environment would
come up with a schema, no content, and no obvious explanation.

So today the live Supabase project is the only copy of the product's content.
Not the only BACKUP -- the only copy. This script ends that.

WHAT IS NOT DUMPED, and why the list is explicit rather than a wildcard:

  * Founder data. Never. Every table below is content we authored; a new table
    holding somebody's answers must not join this dump because someone added it
    and the glob picked it up. _FOUNDER_DATA is checked against the allow-list
    at start-up and the script refuses if they ever intersect.
  * `embedding` columns. Regenerable from the text beside them
    (scripts/embedding_migration/02_regenerate_embeddings.py) and they are the
    bulk of the bytes -- 104MB of reference tables becomes a few MB without
    them. A vector in a diff is also unreadable, so a change to a question's
    text would be invisible next to 1536 floats that changed with it.

    RESTORING THEREFORE HAS A THIRD STEP. Load the schema, load this data,
    regenerate the embeddings. Semantic retrieval is dead until you do; see
    docs/RESTORE.md.

USAGE

    python -m scripts.dump_reference_data --database-url "..." --write
    python -m scripts.dump_reference_data --database-url "..." --check

`--check` compares the live database against what is committed and exits
non-zero on drift, so the dump ageing quietly is something CI can notice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

#: Reference tables, in load order -- parents before children, so a restore can
#: run the files in filename order with foreign keys enforced.
#:
#: Ordered, not alphabetical, and not discovered. Discovery is how founder data
#: ends up in a public dump.
REFERENCE_TABLES: tuple[tuple[str, str], ...] = (
    ("founder_stages", "The 8 stages every other scope rule keys off."),
    ("industries", "FK parent of industry_stage_thresholds; missed on the first pass."),
    ("readiness_pillars", "The 6 pillars, their weights and score bands."),
    ("scoring_rules", "Every threshold the reasoning engine reads AT BOOT."),
    ("stage_diagnosis_logic", "Framework S5: symptom -> what it hides -> tone."),
    ("industry_stage_thresholds", "Stage detection bounds per industry."),
    ("archetypes", "Founder archetypes the DNA report names."),
    ("behaviour_patterns", "Named behaviour patterns the reasoning layer cites."),
    ("blind_spots", "Named blind spots, likewise."),
    ("psychological_state_signals", "Distress detection vocabulary."),
    ("frameworks", "The frameworks recommendations draw on."),
    ("problems", "The problem catalogue questions hang off."),
    ("problem_stage_mapping", "Which problems apply at which stage."),
    ("root_causes", "The root-cause database -- the diagnosis itself."),
    ("root_cause_weights", "Scoring weights. The largest table here."),
    ("interventions", "The action plans a founder is actually given."),
    ("question_tags", "The tag vocabulary questions are classified against."),
    ("questions", "The diagnosis bank, INCLUDING 1-2129 which exist nowhere else."),
    ("question_tag_mapping", "Question -> tag."),
    # The capability taxonomy (f2a91c3d7b58). Ordered after questions and
    # interventions because the two mapping tables are their children.
    ("capability_domains", "Capability taxonomy: the seven domains."),
    ("capabilities", "Capability taxonomy: what a business can or cannot do."),
    ("capability_evidence_criteria", "Observable statements per capability."),
    ("intervention_capabilities", "Intervention -> capability it builds."),
    ("capability_requirements", "Target-state knowledge base: what a destination needs."),
    # question_capabilities is NOT dumped: it is deliberately empty until the
    # Step-8 curation pass, and a dump file with no rows has no `insert into`
    # line for test_every_dumped_file_leads_with_its_primary_key to check. The
    # migration creates the table; there is simply nothing to seed yet.
    ("founder_dna_questions", "The Founder DNA journey."),
    ("current_problem_questions", "The Current Problem phase."),
    ("notification_types", "Notification catalogue."),
    ("support_bot_answers", "Support bot content."),
)

#: Tables that hold a FOUNDER's data. None of these may ever be dumped: they
#: carry names, emails, answers and reports, and this directory is committed.
#: Checked against the allow-list below, so the two lists cannot drift into
#: agreement by accident.
_FOUNDER_DATA = frozenset({
    "founders", "founder_consents", "sessions", "answers", "founder_dna_answers",
    "current_problem_answers", "founder_reports", "detected_root_causes",
    "conversations", "suggestions", "founder_memory", "founder_memory_events",
    "credit_transactions", "privacy_requests", "file_uploads", "revoked_tokens",
    "daily_token_usage", "llm_call_log", "report_shares", "planning_plans",
    "planning_goals", "planning_tasks", "agent_interpretations", "subscriptions",
    "cookie_preferences", "stage_assessments", "waitlist_registrations",
})

#: Regenerable, and the bulk of the bytes. See the module docstring.
_SKIPPED_COLUMNS = frozenset({"embedding"})

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "reference"
MANIFEST = OUT_DIR / "manifest.json"

_names = [t for t, _ in REFERENCE_TABLES]
assert len(_names) == len(set(_names)), "a table is listed twice"
_overlap = set(_names) & _FOUNDER_DATA
assert not _overlap, f"founder data in the reference dump: {sorted(_overlap)}"


def _columns(conn, sa, table: str, keys: list[str] | None = None) -> list[str]:
    """The dumped columns in a CANONICAL order -- deliberately not the table's
    own: primary key first, then the rest alphabetically.

    Physical column order is an accident of history, not part of the data. A
    column added by `alter table` lands at the end, so a database built by
    replaying this repo's migrations orders its columns differently from one
    where the same column was added years earlier by hand. Both hold identical
    rows; only `ordinal_position` disagrees.

    Ordering by position made `--check` report that difference as drift. Eleven
    of twenty-three tables failed that way -- founder_stages, questions,
    root_causes and the rest -- every one of them a pure permutation with not a
    byte of data changed. A drift check that fires on eleven tables when
    nothing has drifted is worse than no check at all: the first thing anyone
    does with it is stop believing it.

    A name-sorted order gives the same column list for any database holding the
    same table, so the file becomes a function of the DATA alone.

    The primary key is lifted to the front of that order rather than left to
    fall wherever its name sorts. Every reference table here has a
    single-column key, so "the key, then the rest by name" is just as
    reproducible as pure alphabetical -- and it keeps each row's identity as
    the first thing on the line, for both the human skimming a diff and the
    `values ('<id>'` parse that the pre-gate consistency test does.
    """
    rows = conn.execute(sa.text(
        "select column_name from information_schema.columns "
        "where table_schema='public' and table_name=:t order by column_name"
    ), {"t": table}).scalars().all()
    cols = [c for c in rows if c not in _SKIPPED_COLUMNS]
    lead = [k for k in (keys or []) if k in cols]
    return lead + [c for c in cols if c not in lead]


def _key_columns(conn, sa, table: str) -> list[str]:
    """Primary key, for a stable row order. Without one the dump reorders itself
    between runs and every diff is noise."""
    return conn.execute(sa.text("""
        select a.attname
          from pg_index i
          join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey)
         where i.indrelid = ('public.' || :t)::regclass and i.indisprimary
         order by array_position(i.indkey, a.attnum)
    """), {"t": table}).scalars().all()


def insert_sql(conn, sa, table: str, cols: list[str], keys: list[str]) -> list[str]:
    """One ready-made INSERT per row, with POSTGRES doing the quoting.

    The literals are built by `quote_nullable` inside the database rather than
    by Python here, because Python was guessing at types and got one wrong:
    `support_bot_answers.links` is a text[], and a Python list rendered as JSON
    does not load into an array column. Dates, numerics, jsonb and timestamps
    each wanted their own rule too, and each was a chance to be subtly wrong in
    a file nobody reads until a restore.

    Postgres already knows how to write a literal for its own types, so it
    writes them. Integers come out quoted ('7' rather than 7), which INSERT
    casts back on the way in -- a small cosmetic price for never maintaining a
    type table.

    One formatter also means any two connections produce byte-identical output,
    so `--check` compares data rather than whose Python wrote it. `_columns`
    carries the other half of that promise: the column ORDER is alphabetical,
    so two databases holding the same rows dump the same bytes even when their
    physical column order differs.
    """
    quoted = ", ".join(f'quote_nullable("{c}")' for c in cols)
    collist = ", ".join(f'"{c}"' for c in cols)
    order = ", ".join(f'"{k}"' for k in keys)
    return list(conn.execute(sa.text(
        f"""select 'insert into "{table}" ({collist}) values ('
                || concat_ws(', ', {quoted})
                || ') on conflict do nothing;'
              from "{table}" order by {order}"""
    )).scalars().all())


def dump_table(conn, sa, table: str, note: str) -> tuple[str, int]:
    keys = _key_columns(conn, sa, table)
    cols = _columns(conn, sa, table, keys)
    keys = keys or cols[:1]
    statements = insert_sql(conn, sa, table, cols, keys)
    skipped = "embedding" in _columns_raw(conn, sa, table)

    lines = [
        f"-- {table}: {note}",
        f"-- {len(statements)} rows, {len(cols)} columns"
        + (", embedding omitted (regenerate after load)" if skipped else ""),
        "-- Generated by scripts/dump_reference_data.py. Do not hand-edit:",
        "-- change the database, re-run the dump, commit the diff.",
        "",
        *statements,
        "",
    ]
    return "\n".join(lines), len(statements)


def _columns_raw(conn, sa, table: str) -> list[str]:
    return conn.execute(sa.text(
        "select column_name from information_schema.columns "
        "where table_schema='public' and table_name=:t"), {"t": table}).scalars().all()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def run(args) -> int:
    os.environ["DATABASE_URL"] = args.database_url
    os.environ.setdefault("SECRET_KEY", "dump-reference-data-not-a-real-secret")

    import sqlalchemy as sa

    from app.db.session import engine

    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(),
                "embeddings": "omitted -- regenerate after load", "tables": {}}
    written = drift = 0

    with engine.connect() as conn:
        for index, (table, note) in enumerate(REFERENCE_TABLES, 1):
            exists = conn.execute(sa.text("select to_regclass(:t)"),
                                  {"t": f"public.{table}"}).scalar()
            if exists is None:
                print(f"  SKIP {table}: not in this database")
                continue

            sql, count = dump_table(conn, sa, table, note)
            path = OUT_DIR / f"{index:02d}_{table}.sql"
            manifest["tables"][table] = {"rows": count, "sha256_16": _digest(sql),
                                         "file": path.name}

            if args.check:
                if not path.exists():
                    print(f"  MISSING {path.name}: {count} rows live, nothing committed")
                    drift += 1
                elif _digest(path.read_text(encoding="utf-8")) != _digest(sql):
                    print(f"  DRIFT   {path.name}: live data differs from the dump")
                    drift += 1
                continue

            OUT_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(sql, encoding="utf-8")
            size = path.stat().st_size / 1024
            print(f"  {path.name:42s} {count:6d} rows  {size:8.1f} KB")
            written += count

    if args.check:
        if drift:
            print(f"\n{drift} table(s) differ from the committed dump. "
                  "Re-run with --write and commit the result.")
            return 1
        print("\nThe committed dump matches the live database.")
        return 0

    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(f"\n{written} rows across {len(manifest['tables'])} tables -> {OUT_DIR}")
    print("Embeddings are NOT included. After restoring, regenerate them:")
    print("  python -m scripts.embedding_migration.02_regenerate_embeddings")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the dump")
    mode.add_argument("--check", action="store_true",
                      help="compare live against the committed dump; non-zero on drift")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
