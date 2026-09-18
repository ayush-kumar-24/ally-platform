"""The onboarding label -> industry_code bridge, and the guarantee it stays complete.

The test that earns its place here is `test_every_onboarding_option_has_a_deliberate_decision`:
it reads the actual dropdown out of the frontend and fails when an option has no
entry in the map. Without it, adding an industry to the dropdown silently ships a
label that resolves to nothing, and the founders who pick it get an UNKNOWN
industry forever -- which is exactly how the column got into its current state.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import engine

from app.services.industry_mapping import (
    INDUSTRY_LABEL_TO_CODE,
    JUDGEMENT_CALLS,
    resolve_industry_code,
    resolve_industry_id,
    unmapped_labels,
)

@pytest.fixture
def db_session():
    """A session on a transaction that is always rolled back.

    Local rather than in conftest.py: these tests only read the `industries`
    catalogue, and adding a shared fixture is a change every other test would
    inherit. Mirrors the connection/rollback pattern the existing suites use.
    """
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


ONBOARDING_QUESTIONS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "data" / "onboardingQuestions.js"
)


def _dropdown_options() -> list[str]:
    """The industry dropdown's options, read from the frontend source.

    Parsed rather than duplicated: a copy in this file would agree with itself
    forever while the real dropdown drifted, which is the failure this test
    exists to prevent.
    """
    source = ONBOARDING_QUESTIONS.read_text()
    block = re.search(
        r"key: 'industry'.*?options:\s*\[(.*?)\]", source, re.S
    )
    assert block, "industry question or its options list not found in onboardingQuestions.js"
    return re.findall(r"'([^']+)'", block.group(1))


# --- A. label -> canonical code ---------------------------------------------
@pytest.mark.parametrize("label,code", [
    ("Agriculture", "agritech"),
    ("SaaS", "saas"),
    ("Fintech", "fintech"),
    ("Manufacturing", "manufacturing"),
    ("Healthcare", "healthtech"),
    ("Education", "edtech"),
    ("Services", "services"),
    ("Logistics", "logistics"),
    ("Real Estate", "proptech"),
    ("AI", "saas"),
    ("D2C", "ecommerce_d2c"),
])
def test_each_dropdown_label_resolves_to_its_canonical_code(label, code):
    assert resolve_industry_code(label) == code


def test_other_is_deliberately_unmapped():
    # "Other" is the founder saying the list does not describe them. Mapping it
    # anywhere would invent a fact they declined to give.
    assert "Other" in INDUSTRY_LABEL_TO_CODE
    assert INDUSTRY_LABEL_TO_CODE["Other"] is None
    assert resolve_industry_code("Other") is None


def test_matching_is_case_and_whitespace_insensitive():
    for variant in ("agriculture", "AGRICULTURE", "  Agriculture  ", "aGrIcUlTuRe"):
        assert resolve_industry_code(variant) == "agritech"


def test_matching_is_never_fuzzy():
    # A wrong industry filters a founder's questions to somebody else's; not
    # knowing fails open. So no substring, prefix or near-miss matching.
    for near_miss in ("Agri", "Agriculture Tech", "SaaS platform", "Fin", "Real"):
        assert resolve_industry_code(near_miss) is None


@pytest.mark.parametrize("junk", [None, 42, [], {}, "", "   ", object()])
def test_unusable_input_resolves_to_none_and_never_raises(junk):
    assert resolve_industry_code(junk) is None


# --- the completeness guarantee ---------------------------------------------
def test_every_onboarding_option_has_a_deliberate_decision():
    options = _dropdown_options()
    assert options, "parsed no options out of the industry dropdown"
    missing = [o for o in options if o not in INDUSTRY_LABEL_TO_CODE]
    assert not missing, (
        f"onboarding offers industry options with no entry in "
        f"INDUSTRY_LABEL_TO_CODE: {missing}. Add each one -- map it to a code, "
        f"or to None if mapping it would be a guess."
    )


def test_the_map_does_not_claim_options_the_dropdown_no_longer_offers():
    # The other direction: a stale entry is harmless but misleading, and makes
    # the judgement-call list look bigger than the decision surface really is.
    options = set(_dropdown_options())
    stale = sorted(set(INDUSTRY_LABEL_TO_CODE) - options)
    assert not stale, f"INDUSTRY_LABEL_TO_CODE has labels the dropdown no longer offers: {stale}"


def test_judgement_calls_are_declared_and_have_not_quietly_grown():
    # Both are documented in the module. If a third appears, it should be a
    # decision somebody made, not one that arrived with a diff.
    assert JUDGEMENT_CALLS == {"AI", "D2C"}
    for label in JUDGEMENT_CALLS:
        assert INDUSTRY_LABEL_TO_CODE[label] is not None


def test_unmapped_labels_reports_exactly_what_it_cannot_map():
    assert unmapped_labels(["Agriculture", "Other", "Quantum Widgets", "SaaS"]) == [
        "Other", "Quantum Widgets",
    ]
    assert unmapped_labels([]) == []
    assert unmapped_labels(None) == []


def test_the_migration_snapshot_agrees_with_the_live_map():
    # The backfill migration inlines a snapshot of this map on purpose (a
    # migration must do the same thing every time it runs). This test is what
    # stops the snapshot and the live map diverging unnoticed.
    migration = next(
        Path(__file__).resolve().parents[1].joinpath("alembic", "versions").glob(
            "*a4e1f70c9d22*.py"
        )
    ).read_text()
    snapshot = dict(re.findall(r'\("([a-z0-9 ]+)", "([a-z0-9_]+)"\)', migration))
    live = {
        label.lower(): code
        for label, code in INDUSTRY_LABEL_TO_CODE.items()
        if code is not None
    }
    assert snapshot == live


# --- B. resolution to industry_mapped_id (needs the catalogue) --------------
def test_resolve_industry_id_finds_a_seeded_industry(db_session):
    row = db_session.execute(
        text("SELECT industry_id, industry_code, industry_name FROM industries ORDER BY industry_id LIMIT 1")
    ).first()
    assert row, "no industries seeded in the test database"
    industry_id, code, name = row

    # ...by code, and by name -- the two shapes already sitting in the column.
    assert resolve_industry_id(db_session, code) == industry_id
    assert resolve_industry_id(db_session, code.upper()) == industry_id
    assert resolve_industry_id(db_session, name) == industry_id


def test_resolve_industry_id_returns_none_for_an_unknown_label(db_session):
    assert resolve_industry_id(db_session, "Quantum Widgets") is None
    assert resolve_industry_id(db_session, "Other") is None
    assert resolve_industry_id(db_session, None) is None
    assert resolve_industry_id(db_session, "") is None


def test_a_label_mapping_to_an_unseeded_code_is_none_not_an_error(db_session):
    # Whether a given industry is seeded is environment-dependent: the local
    # fixture database carries the original four, production carries thirty.
    # Either way an absent code must resolve to None quietly rather than raise.
    seeded = {
        c for (c,) in db_session.execute(text("SELECT industry_code FROM industries")).all()
    }
    absent = next(
        (code for code in INDUSTRY_LABEL_TO_CODE.values() if code and code not in seeded),
        None,
    )
    if absent is None:
        pytest.skip("every mapped industry code is seeded here; nothing to assert")
    label = next(l for l, c in INDUSTRY_LABEL_TO_CODE.items() if c == absent)
    assert resolve_industry_id(db_session, label) is None
