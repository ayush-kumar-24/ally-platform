"""An idea-stage founder must not be asked about a business they have not started.

Reported from a live diagnosis. A founder whose idea existed only in their head
was asked "How do you handle customer support or service requests?", "How many
active users or customers do you currently have?" and "How do you typically
react when your startup hits a major setback?". No customers, no users, no
startup -- and `business_health` scores the blank answer as a gap.

The same shape as the team-size defect, on a different axis. `stage_scope`
withholds whole pillars and categories and does that correctly, but the
presupposition varies WITHIN a category: under `Product`, "What's the simplest
version of this you could put in front of someone today?" is written for
someone with nothing built, and "Rate how well your product currently solves
the problem" cannot be answered by them. A category filter takes both or
neither.

Migration c58d1e7b0a94 fixes seventeen questions three ways -- ten retagged off
the ideation bank, five reworded to drop the premise, two gated on team size.
These tests pin the rules rather than the seventeen, so a question added later
with the same flaw is caught.
"""

import re

import pytest

MIGRATION = "c58d1e7b0a94"
IDEATION_GROUP = "Stage 0"


def _migration():
    import importlib.util
    from pathlib import Path

    from app.core.paths import BACKEND_DIR

    matches = sorted(Path(BACKEND_DIR, "alembic", "versions").glob(f"*{MIGRATION}*.py"))
    assert len(matches) == 1, f"expected one {MIGRATION} migration, found {matches}"
    spec = importlib.util.spec_from_file_location(f"_mig_{MIGRATION}", matches[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(sql, **params):
    from sqlalchemy import text

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return db.execute(text(sql), params).all()
    finally:
        db.close()


@pytest.fixture
def catalogue():
    try:
        rows = _rows(
            "SELECT count(*) FROM questions WHERE primary_stage_group = :g",
            g=IDEATION_GROUP,
        )
    except Exception as exc:                  # no database configured for this run
        pytest.skip(f"no database available: {exc}")
    if not rows or not rows[0][0]:
        pytest.skip("no seeded ideation questions to test against")
    return rows[0][0]


# --- the reviewed lists are sound ------------------------------------------

def test_the_three_fixes_do_not_overlap():
    """A question retagged off the bank should not also be reworded for the
    bank; the outcome would depend on statement order."""
    mig = _migration()
    reworded = {code for code, _old, _new in mig._REWORD}
    assert not (set(mig._RETAG) & reworded)
    assert not (set(mig._RETAG) & set(mig._NEEDS_A_TEAM))
    assert not (reworded & set(mig._NEEDS_A_TEAM))


def test_every_retag_records_why_it_cannot_be_answered():
    for code, why in _migration()._RETAG.items():
        assert len(why.strip()) > 20, f"{code}: {why!r} is not a reason"


def test_a_reword_actually_changes_the_text():
    for code, old, new in _migration()._REWORD:
        assert old.strip() and new.strip()
        assert old != new, f"{code} is listed as reworded but the text is identical"


def test_the_rewordings_drop_the_premise_rather_than_restating_it():
    """The point of a reword is that the founder has not started. Text still
    claiming they have would defeat it."""
    PRESUMES = re.compile(
        r"\b(your startup|this business|your company|the venture|your product)\b", re.I
    )
    for code, _old, new in _migration()._REWORD:
        assert not PRESUMES.search(new), (
            f"{code} was reworded to {new!r}, which still assumes the business exists"
        )


def test_the_rewordings_stay_short_and_plain():
    """Question text is held to plain, short wording -- the standing rule for
    this bank. A reword is a chance to comply, not an excuse to grow."""
    for code, old, new in _migration()._REWORD:
        assert len(new) <= max(110, len(old)), (
            f"{code} grew to {len(new)} characters: {new!r}"
        )


# --- the catalogue ---------------------------------------------------------

def test_no_ideation_question_asks_for_a_count_of_users_or_customers(catalogue):
    """The narrowest, least arguable version of the defect: a question whose
    answer is zero for every founder who can be asked it tells us nothing and
    reads as an accusation."""
    bad = _rows(
        """
        SELECT question_code, question_text FROM questions
        WHERE primary_stage_group = :g
          AND question_text ~* '(how many|number of).{0,30}(active users|paying customers|customers do you)'
        """,
        g=IDEATION_GROUP,
    )
    assert not bad, f"ideation questions asking for a customer count: {bad}"


def test_no_ideation_question_asks_how_the_founder_handles_something_running(catalogue):
    bad = _rows(
        """
        SELECT question_code, question_text FROM questions
        WHERE primary_stage_group = :g
          AND question_text ~* 'how do you (handle|manage) (customer support|service requests)'
        """,
        g=IDEATION_GROUP,
    )
    assert not bad, f"ideation questions about running a support function: {bad}"


def test_the_questions_needing_other_people_are_gated_wherever_they_sit(catalogue):
    """RSK-006 and IVA-060 ask about a team and about employees but sit under
    Strategic Clarity and Market Clarity, so the Team & Leadership defaults
    never reached them. Without a band, `team_scope` admits them to a founder
    working alone at every stage."""
    codes = list(_migration()._NEEDS_A_TEAM)
    ungated = _rows(
        "SELECT question_code FROM questions "
        "WHERE question_code = ANY(:codes) AND min_team_size IS NULL",
        codes=codes,
    )
    assert not ungated, (
        f"questions about a team that nothing withholds from a solo founder: {ungated}"
    )


def test_the_purpose_written_ideation_bank_was_left_alone(catalogue):
    """988 of the 1,171 questions reachable at ideation carry an `S0-` code and
    were written for that bank on purpose. The fix is confined to the legacy
    codes; touching the rest would be a content rewrite wearing a bug fix's
    clothes."""
    mig = _migration()
    touched = set(mig._RETAG) | {c for c, _o, _n in mig._REWORD} | set(mig._NEEDS_A_TEAM)
    assert not [c for c in touched if c.startswith("S0-")], (
        "the fix reaches into the purpose-written Stage 0 bank"
    )
