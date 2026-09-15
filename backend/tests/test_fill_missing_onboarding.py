"""The repair script fills what is empty and never overwrites an answer.

It exists because seeded accounts carry `profile_completed = true` without the
fields that flag is supposed to certify, so `/founder-dna/start` rejects them
with ProfileIncompleteError. It used to refuse whenever ANY of its five fields
held a value -- which is every seeded founder past Ideation, since they all
have invisible_gaps set and the other four empty. The script written to unblock
them declined all of them.
"""

import re

import pytest

from app.core.paths import BACKEND_DIR
from scripts.fill_missing_onboarding import (
    FIELDS,
    REVENUE_BY_STAGE_ORDER,
)


def _allowed_revenue_values() -> set[str]:
    """Straight off founders_current_revenue_check, so a band this script
    writes can never be one the database refuses."""
    schema = (BACKEND_DIR / "app" / "models" / "schema.py").read_text(encoding="utf-8")
    match = re.search(r"name='founders_current_revenue_check'", schema)
    assert match, "the constraint moved; this test needs updating"
    clause = schema[:match.start()].rsplit("CheckConstraint", 1)[1]
    return set(re.findall(r"'(\w+)'::character varying", clause))


def test_every_stage_maps_to_a_band_the_database_allows():
    allowed = _allowed_revenue_values()
    assert allowed, "no values parsed out of the check constraint"
    unknown = set(REVENUE_BY_STAGE_ORDER.values()) - allowed
    assert not unknown, f"current_revenue values the DB would reject: {unknown}"


def test_the_default_is_also_a_value_the_database_allows():
    assert FIELDS["current_revenue"] in _allowed_revenue_values()


def test_all_eight_stages_are_covered():
    """founder_stages runs 1..8; a gap means a founder silently keeps the
    Ideation-shaped default."""
    assert set(REVENUE_BY_STAGE_ORDER) == set(range(1, 9))


def test_revenue_never_decreases_as_the_stage_advances():
    """A Growth-stage founder billing under a lakh is a contradiction the
    diagnosis is then asked to account for."""
    order = ["pre_revenue", "under_1L", "1L_5L", "5L_25L", "25L_1Cr", "above_1Cr"]
    seen = [order.index(REVENUE_BY_STAGE_ORDER[s]) for s in range(1, 9)]
    assert seen == sorted(seen), f"bands go backwards across stages: {seen}"


def test_the_earliest_stages_are_pre_revenue():
    assert REVENUE_BY_STAGE_ORDER[1] == "pre_revenue"
    assert REVENUE_BY_STAGE_ORDER[2] == "pre_revenue"


def test_a_populated_field_is_filtered_out_not_a_refusal():
    """The behaviour change, read off the source: `to_write` excludes what is
    already set, and the old blanket `return 1` on any populated field is gone.
    """
    source = (BACKEND_DIR / "scripts" / "fill_missing_onboarding.py").read_text(
        encoding="utf-8")
    assert "to_write = {c: v for c, v in FIELDS.items() if c not in already_set}" in source
    body = source.split("already_set = {", 1)[1].split("print(\"\\nwill write:\")", 1)[0]
    assert "if already_set:\n            print" in body, (
        "a populated field must be reported and skipped, not refused")


def test_the_update_only_names_columns_it_is_filling():
    """The statement is built from to_write, so a populated column cannot
    appear in it even by accident."""
    source = (BACKEND_DIR / "scripts" / "fill_missing_onboarding.py").read_text(
        encoding="utf-8")
    assert "for i, (col, val) in enumerate(to_write.items())" in source
    assert "update founders set founder_reality_signals" not in source, (
        "the fixed five-column UPDATE would overwrite fields that already "
        "have a value")


@pytest.mark.parametrize("column", [
    "founder_reality_signals", "business_reality_signals", "invisible_gaps",
])
def test_json_columns_are_cast_not_stringified(column):
    source = (BACKEND_DIR / "scripts" / "fill_missing_onboarding.py").read_text(
        encoding="utf-8")
    assert column in source.split("jsonb_columns = {", 1)[1].split("}", 1)[0]
