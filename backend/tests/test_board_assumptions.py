"""No question may assume a founder has investors or a board.

Found auditing the Growth bank. Twenty questions there named investors or a
board. Seven sit under Fundraising problems and `context_scope` already
withholds those from a founder who has not said they are raising. The other
thirteen were filed under Product, Sales, Financial Management, Founder
Psychology and Scaling, where nothing gates them -- so a bootstrapped founder,
which is most of the founders this product serves, was asked how they report to
a board they do not have.

REWORDED RATHER THAN GATED, which is the decision these tests protect. A gate
would have needed a fact nobody collects: whether a founder HAS investors.
`FUNDRAISING_INTENT` cannot stand in for it -- a founder who raised years ago
and never will again has a board and no intent, and one preparing a first round
has intent and no board -- so gating meant a new onboarding question, and then
withholding these questions from the majority who answered no.

But none of the thirteen is about a board. They ask whether the founder softens
bad news, whether they can justify a plan with numbers, whether anyone checks
their figures. All true of a founder with no investors. The board was scenery,
and it was the only part that excluded anyone.
"""

import re

import pytest

MIGRATION = "f0b82e4d5a19"

#: A registered non-profit has a board or trustee body by law, so there the
#: premise is the subject rather than scenery.
ALLOWED_TO_ASSUME_A_BOARD = frozenset({"S10-NGO-007", "S10-NGO-008"})

NAMES_A_BOARD = re.compile(r"(your board|your investors)", re.I)


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
        rows = _rows("SELECT count(*) FROM questions")
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")
    if not rows or not rows[0][0]:
        pytest.skip("no seeded questions to test against")
    return rows[0][0]


# --- the reviewed list is sound --------------------------------------------

#: What a listed question assumed before it was reworded. Wider than
#: NAMES_A_BOARD because one of them assumed a funding ROUND rather than a
#: board -- S10-SAS-106-1, "What did your last round buy, and did it buy it?",
#: where the premise is the question and could only be made conditional.
ASSUMES_OUTSIDE_MONEY = re.compile(
    r"(your board|your investors|last round|co-founders asked)", re.I
)


def test_every_rewording_started_from_a_real_assumption():
    """Nothing belongs on this list that was not actually assuming something
    the founder may not have -- otherwise it is a wording change wearing a
    correctness fix's clothes, and it belongs in the plain-language pass."""
    for code, old, _new in _migration()._REWORD:
        assert ASSUMES_OUTSIDE_MONEY.search(old), (
            f"{code} was reworded but its old text assumed nothing: {old!r}"
        )


def test_no_rewording_leaves_a_board_behind():
    for code, _old, new in _migration()._REWORD:
        assert not NAMES_A_BOARD.search(new), (
            f"{code} was reworded to {new!r}, which still names a board"
        )


def test_the_one_that_could_not_lose_its_premise_was_made_conditional():
    """"What did your last round buy?" cannot drop the round -- the round IS
    the question. So it asks conditionally instead, which gives a founder who
    never raised something true to say rather than a blank."""
    new = dict((c, n) for c, _o, n in _migration()._REWORD)["S10-SAS-106-1"]
    assert new.lower().startswith("if you have raised"), new


def test_a_rewording_actually_changes_the_text():
    for code, old, new in _migration()._REWORD:
        assert old.strip() and new.strip() and old != new, code


def test_the_kept_questions_are_the_ones_where_a_board_is_the_subject():
    kept = {code for code, _why in _migration()._LEFT_ALONE}
    assert kept == ALLOWED_TO_ASSUME_A_BOARD


def test_nothing_is_both_reworded_and_kept():
    mig = _migration()
    reworded = {code for code, _o, _n in mig._REWORD}
    assert not reworded & {code for code, _w in mig._LEFT_ALONE}


# --- the catalogue ---------------------------------------------------------

def test_no_question_outside_fundraising_assumes_a_board(catalogue):
    """The rule, stated so a question added later with the same flaw is caught.

    Fundraising questions are exempt because `context_scope` withholds that
    whole family from a founder who has not said they are raising -- there the
    premise is checked before the question is ever asked.
    """
    stray = _rows(
        """
        SELECT q.question_code, q.question_text FROM questions q
        JOIN problems p ON p.problem_id = q.problem_id
        WHERE q.question_text ~* '(your board|your investors)'
          AND q.question_code <> ALL(:kept)
          AND p.problem_code NOT LIKE 'FND-%'
        ORDER BY q.question_code
        """,
        kept=sorted(ALLOWED_TO_ASSUME_A_BOARD),
    )
    assert not stray, (
        "questions assuming a board, outside Fundraising and outside the NGO "
        f"set: {[c for c, _t in stray]}"
    )


def test_the_fundraising_family_is_still_gated_on_intent():
    """The exemption above is only safe while that gate exists."""
    from app.api.v1.diagnosis.context_scope import (
        FUNDRAISING_INTENT,
        PROBLEM_PRECONDITIONS,
    )

    gated = {c for c, token in PROBLEM_PRECONDITIONS.items()
             if token == FUNDRAISING_INTENT}
    assert gated >= {"FND-001", "FND-002", "FND-004", "FND-006"}, (
        "the Fundraising problems carrying board questions are no longer gated "
        "on intent, so the exemption in the test above is unsafe"
    )


def test_the_ngo_pair_still_exists_and_still_names_a_board(catalogue):
    """If those two are ever reworded or retired, the exemption should go with
    them rather than sitting here protecting nothing."""
    rows = _rows(
        "SELECT question_code, question_text FROM questions "
        "WHERE question_code = ANY(:codes)",
        codes=sorted(ALLOWED_TO_ASSUME_A_BOARD),
    )
    assert len(rows) == len(ALLOWED_TO_ASSUME_A_BOARD)
    for code, text in rows:
        assert NAMES_A_BOARD.search(text), (
            f"{code} no longer names a board; drop it from the exemption"
        )
