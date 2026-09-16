"""The reference dump must contain the product, and never a founder.

This directory is committed. A table that holds somebody's answers, email or
report must not reach it because someone added a table and a glob picked it up
-- so the table list is explicit and these tests hold it to that.
"""


import pytest

from scripts.dump_reference_data import (
    _FOUNDER_DATA,
    _SKIPPED_COLUMNS,
    REFERENCE_TABLES,
)

NAMES = [t for t, _ in REFERENCE_TABLES]


# --- what may and may not be dumped ------------------------------------


def test_no_founder_data_table_is_in_the_dump():
    """The one that matters. Committing any of these publishes personal data."""
    assert not set(NAMES) & _FOUNDER_DATA


@pytest.mark.parametrize("table", sorted(_FOUNDER_DATA))
def test_each_founder_table_is_named_individually(table):
    """Parametrised so a failure says WHICH table leaked, not just that one did."""
    assert table not in NAMES


def test_every_table_is_listed_once():
    assert len(NAMES) == len(set(NAMES))


def test_every_table_carries_a_note_saying_what_it_is():
    """A bare list of table names does not tell the next person what they are
    restoring or why it matters."""
    for table, note in REFERENCE_TABLES:
        assert note and len(note) > 15, f"{table} has no useful note"


def test_the_tables_with_no_seed_anywhere_are_all_covered():
    """The measured hole. None of these is seeded by a migration or by any SQL
    in data/, so each one exists solely in the live database until this dump
    is committed. scoring_rules is the sharpest: config.py raises on a missing
    rule, so without it the reasoning engine does not start at all."""
    for table in ("root_cause_weights", "question_tag_mapping", "interventions",
                  "problem_stage_mapping", "scoring_rules", "behaviour_patterns",
                  "blind_spots", "stage_diagnosis_logic",
                  "industry_stage_thresholds", "current_problem_questions"):
        assert table in NAMES, f"{table} would still be unrecoverable"


def test_the_question_bank_is_covered():
    """Migration 63340a6e5fdb asserts questions 1-2129 exist and nothing seeds
    them -- the failure that started this."""
    assert "questions" in NAMES


def test_parents_load_before_children():
    """Files are loaded in filename order, which is this order, with foreign
    keys enforced throughout."""
    def before(a, b):
        return NAMES.index(a) < NAMES.index(b)

    assert before("problems", "root_causes")
    assert before("root_causes", "root_cause_weights")
    assert before("questions", "question_tag_mapping")
    assert before("question_tags", "question_tag_mapping")
    assert before("problems", "problem_stage_mapping")
    assert before("founder_stages", "problem_stage_mapping")


def test_embeddings_are_skipped():
    assert "embedding" in _SKIPPED_COLUMNS


# --- SQL generation ----------------------------------------------------
#
# The literals are built by Postgres `quote_nullable`, not by Python. That
# started as a bug fix: support_bot_answers.links is a text[], and the Python
# formatter rendered it as JSON, which does not load into an array column.
# Dates, numerics, jsonb and timestamps each wanted their own rule too.
#
# Verified against a real Postgres rather than asserted -- dumped, wiped,
# reloaded, and the values came back: an array whose element contains a comma
# ({https://a.example,"b, with comma"}), an apostrophe in prose (It''s fine),
# and a date. These tests hold the decision in place.


def _source() -> str:
    from app.core.paths import BACKEND_DIR

    return (BACKEND_DIR / "scripts" / "dump_reference_data.py").read_text(
        encoding="utf-8")


def test_postgres_quotes_the_literals_not_python():
    source = _source()
    assert "quote_nullable" in source
    assert "def _literal" not in source, (
        "a Python formatter is back -- it has to get arrays, dates, numerics, "
        "jsonb and timestamps all right, and last time it did not")


def test_there_is_exactly_one_formatter():
    """Two would drift, and --check would then report whose Python wrote the
    file rather than whether the data changed. Scoped to the two functions that
    build SQL -- the manifest writer uses json.dumps legitimately."""
    source = _source()
    formatter = source.split("def insert_sql", 1)[1].split("def _columns_raw", 1)[0]
    assert "quote_nullable" in formatter
    for python_formatting in ("json.dumps", "isoformat", "repr(", "replace(\"'\""):
        assert python_formatting not in formatter, (
            f"{python_formatting} is Python formatting a value Postgres should quote")


def test_nulls_use_quote_nullable_not_quote_literal():
    """quote_literal turns NULL into NULL the SQL keyword only via
    quote_nullable; quote_literal returns SQL NULL for a NULL input, which
    would make concat_ws drop the column and shift every later value left."""
    source = _source()
    assert "quote_nullable(" in source
    assert "quote_literal(" not in source


def test_rows_are_concatenated_with_a_separator_that_cannot_vanish():
    """concat_ws skips NULL arguments. quote_nullable never returns one, so
    every column keeps its position -- the two belong together."""
    block = _source().split("def insert_sql", 1)[1].split("def dump_table", 1)[0]
    assert "concat_ws(', '" in block
    assert "quote_nullable" in block


def test_inserts_are_idempotent():
    """A restore that is half-finished must be safe to re-run."""
    assert "on conflict do nothing;" in _source()


def test_rows_are_ordered_by_primary_key():
    """Without a stable order the dump reorders itself between runs and every
    diff is noise."""
    source = _source()
    assert "def _key_columns" in source
    assert "indisprimary" in source


def test_columns_are_ordered_canonically_not_physically():
    """The column order in a dumped INSERT must be a function of the DATA, not
    of how the target database happens to have been built.

    `ordinal_position` is an accident of history: a column added by `alter
    table` lands at the end, so a database built by replaying this repo's
    migrations orders its columns differently from one where the same column
    was added earlier by hand. Dumping in that order made `--check` report
    eleven of twenty-three tables as drifted -- founder_stages, questions,
    root_causes and the rest -- when every one was a pure permutation with not
    a byte of data changed.

    A drift check that fires when nothing has drifted gets ignored, and then it
    is not a drift check. So: sort by name, and never by position.
    """
    source = _source()
    assert "order by column_name" in source, (
        "_columns must sort by name so two databases holding the same rows "
        "dump the same bytes"
    )
    assert "order by ordinal_position" not in source, (
        "ordinal_position is physical column order -- it differs between a "
        "migration-built database and a hand-altered one and is not drift"
    )


def test_the_primary_key_leads_the_column_order():
    """Canonical, and still readable: the key first, then the rest by name.

    Every reference table has a single-column key, so this is exactly as
    reproducible as pure alphabetical order while keeping each row's identity
    at the front of the line -- which both a human reading a diff and
    `test_the_pre_gate_questions_match_the_full_file`'s `values ('<id>'` parse
    depend on.
    """
    source = _source()
    assert "lead + [c for c in cols if c not in lead]" in source


def test_every_dumped_file_leads_with_its_primary_key():
    """The property the two tests above describe, asserted against the bytes
    actually committed rather than against the source that wrote them."""
    import re

    for table, _ in REFERENCE_TABLES:
        matches = list(REFERENCE_DIR.glob(f"[0-9][0-9]_{table}.sql"))
        assert matches, f"no dump file for {table}"
        first = next(
            line for line in matches[0].read_text().splitlines()
            if line.startswith("insert into")
        )
        cols = re.search(r'insert into "[^"]+" \(([^)]*)\)', first).group(1)
        cols = [c.strip().strip('"') for c in cols.split(",")]
        rest = cols[1:]
        assert rest == sorted(rest), (
            f"{table}: columns after the key are not in name order: {rest}"
        )


def test_the_embedding_column_never_reaches_the_sql():
    """It is excluded from the column list, so it is not in the INSERT at all
    -- not written as null, not written as a vector."""
    source = _source()
    assert "_SKIPPED_COLUMNS" in source
    assert "c not in _SKIPPED_COLUMNS" in source


# --- the committed snapshot --------------------------------------------
#
# These read the files in data/reference/ rather than the script, because a
# correct script plus a stale dump restores the wrong thing. Everything here
# is checkable without a database.

from pathlib import Path  # noqa: E402

from app.core.paths import BACKEND_DIR  # noqa: E402

REFERENCE_DIR = BACKEND_DIR / "data" / "reference"


def _rows(path: Path) -> int:
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines()
               if l.startswith("insert into"))


def _ids(path: Path, table: str) -> set[int]:
    import re
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f'insert into "{table}"'):
            out.add(int(re.search(r"values \('(\d+)'", line).group(1)))
    return out


def test_the_snapshot_exists():
    """Without it, docs/RESTORE.md describes an intention."""
    assert REFERENCE_DIR.is_dir()
    assert list(REFERENCE_DIR.glob("*.sql")), "no reference data is committed"


def test_every_listed_table_has_a_file():
    committed = {p.name.split("_", 1)[1].removesuffix(".sql")
                 for p in REFERENCE_DIR.glob("[0-9][0-9]_*.sql")}
    for table in NAMES:
        assert table in committed, f"{table} is listed but not committed"


def test_no_file_carries_founder_data():
    """A direct read of what is actually on disk, not of the allow-list."""
    for path in REFERENCE_DIR.glob("*.sql"):
        head = path.read_text(encoding="utf-8")[:4000]
        for table in _FOUNDER_DATA:
            assert f'insert into "{table}"' not in head, f"{path.name} writes {table}"


def test_the_pre_gate_questions_match_the_full_file():
    """The 00b file is a SEPARATE extract of questions 1-2129, loaded before
    migration 63340a6e5fdb. If someone re-runs --write without regenerating it,
    the two drift and the restore loads a stale bank -- so they are compared
    here, where no database is needed to notice."""
    pre = _ids(REFERENCE_DIR / "00b_questions_pre_gate.sql", "questions")
    full = {i for i in _ids(REFERENCE_DIR / "18_questions.sql", "questions") if i <= 2129}
    assert pre == full, (
        f"pre-gate questions differ from the full dump: "
        f"{len(pre - full)} extra, {len(full - pre)} missing")


def test_the_pre_gate_files_stop_short_of_what_migrations_seed():
    """Migration 74e6b0317802 refuses to run if its own id ranges are already
    present ("Collision detected"), so the pre-gate files must exclude them."""
    for filename, table, first, last in (
        ("00f_question_tags_pre_gate.sql", "question_tags", 79, 88),
        ("00d_problems_pre_gate.sql", "problems", 270, 275),
        ("00e_root_causes_pre_gate.sql", "root_causes", 1976, 2011),
    ):
        ids = _ids(REFERENCE_DIR / filename, table)
        clash = {i for i in ids if first <= i <= last}
        assert not clash, f"{filename} contains {sorted(clash)[:5]}, which the migration seeds"


def test_the_pre_gate_files_cover_the_fk_parents_the_seeding_needs():
    """Measured by running the restore: the seeding migrations fail without
    each of these, one after another."""
    for filename in ("00a_industries.sql", "00c_readiness_pillars_pre_gate.sql",
                     "00d_problems_pre_gate.sql", "00e_root_causes_pre_gate.sql",
                     "00f_question_tags_pre_gate.sql", "00b_questions_pre_gate.sql"):
        assert (REFERENCE_DIR / filename).exists(), f"{filename} is missing"


def test_scoring_rules_carries_every_rule_the_engine_requires():
    """config.py::_require raises on a missing rule, so a dump short of one is
    a database that cannot start the reasoning engine. CAT_RISK_THRESHOLD was
    dropped once already, by an insert-only load colliding on rule_id 1."""
    from app.api.v1.reasoning.config import RuleCode

    body = (REFERENCE_DIR / "04_scoring_rules.sql").read_text(encoding="utf-8")
    missing = [c.value for c in RuleCode if f"'{c.value}'" not in body]
    assert not missing, f"rules the engine needs but the dump lacks: {missing}"


def test_files_are_insert_only_so_running_one_by_hand_cannot_wipe_a_table():
    """The DELETE that makes the snapshot authoritative lives in RESTORE.md,
    visible in the runbook, not hidden inside 23 files someone might run
    against production by accident."""
    for path in REFERENCE_DIR.glob("*.sql"):
        text = path.read_text(encoding="utf-8").lower()
        for destructive in ("delete from", "truncate", "drop table"):
            assert destructive not in text, f"{path.name} contains {destructive}"
