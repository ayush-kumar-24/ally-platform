"""Revenue gating: whether money has changed hands yet.

Found auditing the Validation bank. Validation, Prototype/MVP and Early
Traction share one question bank and one set of rules, and nothing withholds a
subject at any of them -- so a founder at Validation, still testing whether
anyone wants this, is a valid candidate for "Have you hit your sales targets
for the last quarter?" and "Last month, was your business profitable or just
generating revenue?". They answer nothing, and the blank scores as a gap, so
not having launched reads back as weak finances.

`founders.current_revenue` has been collected since onboarding was written,
with a real `pre_revenue` band, and nothing that chooses questions ever read
it. The same blind spot `team_size` had.

Two sources decide, and the order matters: the STAGE settles Ideation and
Validation, because neither is asked for a figure and neither can have one --
reading that absence as unknown would leave ungated the exact two stages the
gate exists for.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.revenue_scope import (
    PRE_REVENUE,
    PRE_REVENUE_STAGE_ORDERS,
    gate,
    is_trading,
)

IDEATION, VALIDATION, PROTOTYPE, EARLY, GROWTH = 1, 2, 3, 4, 5


def _q(qid, requires_trading=False):
    return SimpleNamespace(question_id=qid, requires_trading=requires_trading)


def _founder(stage_order=None, current_revenue=None):
    stage = SimpleNamespace(stage_order=stage_order) if stage_order else None
    return SimpleNamespace(founder_id=1, stage=stage, current_revenue=current_revenue)


ANY_A, ANY_B = 101, 102          # answerable before a first sale
SOLD_A, SOLD_B = 201, 202        # "what was your close rate last quarter?"
BANK = [_q(ANY_A), _q(ANY_B), _q(SOLD_A, True), _q(SOLD_B, True)]


def _kept(founder):
    return {q.question_id for q in gate(list(BANK), founder)}


# --- the defect ------------------------------------------------------------

def test_a_validation_founder_is_not_asked_about_sales_they_never_made():
    assert _kept(_founder(VALIDATION)) == {ANY_A, ANY_B}


def test_an_ideation_founder_is_not_either():
    assert _kept(_founder(IDEATION)) == {ANY_A, ANY_B}


def test_a_founder_who_said_pre_revenue_is_not_either():
    """Prototype/MVP and Early Traction ARE asked for a figure, and
    'Pre-revenue (Rs 0)' is a real answer a founder picks deliberately."""
    for order in (PROTOTYPE, EARLY, GROWTH):
        assert _kept(_founder(order, PRE_REVENUE)) == {ANY_A, ANY_B}


def test_a_founder_who_is_trading_gets_everything():
    for band in ("under_1L", "1L_5L", "5L_25L", "25L_1Cr", "above_1Cr"):
        assert _kept(_founder(EARLY, band)) == {q.question_id for q in BANK}


# --- the stage settles the two stages that are never asked -----------------

def test_the_stage_decides_before_the_column_for_ideation_and_validation():
    """A stale revenue figure from an earlier, later stage must not re-admit
    the questions. The founder moved back; the figure did not follow."""
    for order in PRE_REVENUE_STAGE_ORDERS:
        assert is_trading(_founder(order, "5L_25L")) is False
        assert _kept(_founder(order, "5L_25L")) == {ANY_A, ANY_B}


def test_the_pre_revenue_stages_are_the_two_never_asked_for_a_figure():
    """Ideation was never asked; Validation stopped when onboarding gained
    minStageOrder. If that boundary moves, this set moves with it."""
    from app.services.profile_progress import STAGE_ORDER_REQUIRED

    asked_from = {
        column: minimum for minimum, column, _l, _s in STAGE_ORDER_REQUIRED
    }["current_revenue"]
    assert PRE_REVENUE_STAGE_ORDERS == frozenset(range(1, asked_from))


# --- fail open -------------------------------------------------------------

def test_an_unknown_revenue_beyond_validation_withholds_nothing():
    """Every founder who onboarded before the question existed, and anyone who
    skipped it. Narrowing them would shrink diagnoses on a guess."""
    assert is_trading(_founder(EARLY, None)) is None
    assert _kept(_founder(EARLY, None)) == {q.question_id for q in BANK}


def test_an_unknown_stage_and_unknown_revenue_withholds_nothing():
    assert is_trading(_founder(None, None)) is None
    assert _kept(_founder(None, None)) == {q.question_id for q in BANK}


@pytest.mark.parametrize("value", ["", "  ", "none", "PRE_REVENUE", "0", 5, object()])
def test_an_unreadable_revenue_withholds_nothing(value):
    assert is_trading(_founder(EARLY, value)) is None
    assert _kept(_founder(EARLY, value)) == {q.question_id for q in BANK}


def test_the_gate_never_empties_the_candidate_set():
    only_trading = [_q(SOLD_A, True), _q(SOLD_B, True)]
    assert len(gate(only_trading, _founder(VALIDATION))) == 2


def test_an_empty_candidate_set_stays_empty():
    assert gate([], _founder(VALIDATION)) == []


def test_a_question_with_no_flag_is_for_everyone():
    assert gate([SimpleNamespace(question_id=1)], _founder(VALIDATION))


# --- wired into the engine -------------------------------------------------

def test_the_engine_applies_the_gate_outside_the_stage_scope_shortcut():
    import inspect

    from app.api.v1.diagnosis.engine import QuestionSelectionEngine

    source = inspect.getsource(QuestionSelectionEngine._in_scope)
    assert source.index("revenue_gate(") < source.index(
        "if scope is None or scope.withholds_nothing"
    ), "the revenue gate runs after the stage-scope short-circuit"


# --- the catalogue ---------------------------------------------------------

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
        rows = _rows("SELECT count(*) FROM questions WHERE requires_trading")
    except Exception as exc:
        pytest.skip(f"no database available: {exc}")
    if not rows or not rows[0][0]:
        pytest.skip("no seeded questions tagged as needing a trading business")
    return rows[0][0]


def test_a_validation_founder_still_has_a_bank_to_be_asked_from(catalogue):
    """The gate must narrow the bank, not gut it."""
    total, gated = _rows(
        "SELECT count(*), count(*) FILTER (WHERE requires_trading) FROM questions "
        "WHERE primary_stage_group = :g",
        g="Stage 0→1",
    )[0]
    assert gated > 0, "nothing is tagged in the bank this gate was built for"
    assert gated < total * 0.2, (
        f"{gated} of {total} Validation-bank questions need a trading business; "
        "that is more than a narrowing, check the tagging"
    )


def test_no_ideation_question_needs_a_trading_business(catalogue):
    """An ideation founder can never satisfy one, so a tagged question there is
    simply unreachable -- it belongs in a later bank instead."""
    stranded = _rows(
        "SELECT question_code FROM questions "
        "WHERE primary_stage_group = :g AND requires_trading ORDER BY question_code",
        g="Stage 0",
    )
    assert not stranded, f"unreachable tagged questions on the ideation bank: {stranded}"
