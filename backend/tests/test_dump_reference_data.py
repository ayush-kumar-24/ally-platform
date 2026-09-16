"""The reference dump must contain the product, and never a founder.

This directory is committed. A table that holds somebody's answers, email or
report must not reach it because someone added a table and a glob picked it up
-- so the table list is explicit and these tests hold it to that.
"""

import json
from datetime import datetime, timezone

import pytest

from scripts.dump_reference_data import (
    _FOUNDER_DATA,
    _SKIPPED_COLUMNS,
    REFERENCE_TABLES,
    _literal,
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


def test_apostrophes_are_escaped():
    """A single unescaped quote turns the rest of the file into a syntax error,
    and the catalogue is full of prose."""
    assert _literal("O'Brien's threshold") == "'O''Brien''s threshold'"


def test_nulls_are_null_not_the_string_none():
    assert _literal(None) == "null"


def test_booleans_are_sql_booleans():
    assert _literal(True) == "true"
    assert _literal(False) == "false"


def test_numbers_are_unquoted():
    assert _literal(3) == "3"
    assert _literal(0.5) == "0.5"


def test_json_round_trips_and_is_key_sorted():
    """Sorted so the same data produces the same bytes -- otherwise every dump
    is a diff and nobody can see what actually changed."""
    out = _literal({"b": 1, "a": [2, 3]})
    assert out == """'{"a": [2, 3], "b": 1}'"""
    assert json.loads(out[1:-1]) == {"a": [2, 3], "b": 1}


def test_json_containing_an_apostrophe_is_still_escaped():
    assert _literal({"note": "it's fine"}) == """'{"note": "it''s fine"}'"""


def test_timestamps_are_iso_and_quoted():
    value = datetime(2026, 9, 16, 6, 52, 1, tzinfo=timezone.utc)
    assert _literal(value) == "'2026-09-16T06:52:01+00:00'"


def test_inserts_are_idempotent():
    """A restore that is half-finished must be safe to re-run."""
    from app.core.paths import BACKEND_DIR

    source = (BACKEND_DIR / "scripts" / "dump_reference_data.py").read_text(
        encoding="utf-8")
    assert "on conflict do nothing;" in source


def test_rows_are_ordered_by_primary_key():
    """Without a stable order the dump reorders itself between runs and every
    diff is noise."""
    from app.core.paths import BACKEND_DIR

    source = (BACKEND_DIR / "scripts" / "dump_reference_data.py").read_text(
        encoding="utf-8")
    assert "def _key_columns" in source
    assert "indisprimary" in source
