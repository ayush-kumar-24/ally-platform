"""The industry opening block: the first N questions are the founder's own.

Why it exists. As a ranking preference alone (the fourth sort term, see
test_industry_relevance_ranking) industry is too quiet to be felt -- it only
separates questions the two coverage terms have already tied, so a founder can
answer eight or ten before meeting one written for their industry. The
diagnosis reads as generic exactly where the first impression is formed.

Why it ends, and this is the part these tests exist to hold. Measured on the
seeded banks, the industry datasets do NOT cover the six pillars:

    SaaS,          Stage 0->1   20 questions: 19 Product & Execution, 1 Team.
                                Founder Readiness, Market Clarity, Revenue
                                Maturity and Strategic Clarity: nothing.
    Manufacturing, Stage 1->10+ 25 questions: 21 Revenue Maturity, 4 Product.
                                Four pillars absent.

And the bank is large against the budget: 15 questions at Ideation (budget 14),
20 at Validation (budget 20), 25 at Growth (budget 30). An uncapped
industry-first pass would spend an entire Ideation diagnosis inside two or three
pillars, and Founder Readiness and Strategic Clarity -- motivation clarity, idea
conviction, delegation anxiety, leadership identity -- would go unasked at every
stage in every industry. Those pillars are scored and reported; a pillar with no
answers renders as not assessed.

So the block is bounded three ways and the tests below check each bound
separately, then check the arithmetic against the real per-stage budgets.
"""

import contextlib
from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.engine import QuestionSelectionEngine
from app.api.v1.diagnosis.industry_scope import (
    MIN_QUESTIONS_PER_PILLAR,
    opening_block_size,
)
from app.core.config import settings

SAAS_ID = 3
SALES, OPERATIONS = 4, 3

SAS_A, SAS_B = 9001, 9002
U_SALES, U_OPS = 101, 102

_APPLICABILITY = {SAS_A: "primary", SAS_B: "supporting"}
_PILLAR_MAP = {21: SALES, 22: SALES, 11: SALES, 12: OPERATIONS}


def _q(qid, problem_id, category="Sales & Revenue", priority="CORE", difficulty=1):
    return SimpleNamespace(
        question_id=qid, problem_id=problem_id, root_cause_id=None,
        category=category, priority=priority, difficulty_level=difficulty,
    )


#: U_OPS sits in an UNASKED pillar, so outside the block the round-robin puts it
#: first. Inside the block the industry pair must jump it -- that contrast is
#: what these tests measure.
_BANK = [
    _q(SAS_A, 21), _q(SAS_B, 22),
    _q(U_SALES, 11), _q(U_OPS, 12, "Operations & Systems"),
]

#: Sales already has answers, Operations has none. Without this every pillar
#: sits at round 0, the coverage terms tie, and the relevance rank decides --
#: which would make the industry pair win outside the block too, and the
#: contrast these tests rest on would be measuring nothing.
_SALES_ALREADY_COVERED = {(SALES, "Sales & Revenue"): 2}


def _founder(industry_mapped_id=SAAS_ID, stage_order=5, question_budget=None):
    return SimpleNamespace(
        founder_id=1,
        stage=SimpleNamespace(stage_order=stage_order, question_budget=question_budget),
        industry_mapped_id=industry_mapped_id,
    )


def _session(answered=0, founder_industry_id=SAAS_ID, routing_state="continue"):
    return SimpleNamespace(
        session_id=1, routing_state=routing_state,
        founder_industry_id=founder_industry_id,
        questions_answered_count=answered,
    )


def _engine(*, bank=None, applicability=None, answered_per_cat=None, raises=False):
    def guard(value):
        if raises:
            raise RuntimeError("db down")
        return value

    fake_db = SimpleNamespace(begin_nested=lambda: contextlib.nullcontext())
    return QuestionSelectionEngine(SimpleNamespace(
        db=fake_db,
        list_candidate_questions=lambda **kw: list(_BANK if bank is None else bank),
        problem_to_pillar=lambda: dict(_PILLAR_MAP),
        problem_to_dimension=lambda: {},
        problem_to_code=lambda: {},
        root_cause_to_code=lambda: {},
        question_owned_by_industry=lambda: {
            SAS_A: frozenset({"saas"}), SAS_B: frozenset({"saas"})},
        industry_code=lambda industry_id: guard("saas"),
        question_applicability_for_industry=lambda code: guard(
            dict(_APPLICABILITY if applicability is None else applicability)),
        industry_pain_point_weights=lambda industry_id: {},
        answered_count_per_pillar_category=lambda session_id: dict(
            _SALES_ALREADY_COVERED if answered_per_cat is None else answered_per_cat),
        get_detected_root_cause_ids=lambda session_id: set(),
    ))


def _order(session=None, founder=None, **kw):
    engine = _engine(**kw)
    founder = founder if founder is not None else _founder()
    session = session if session is not None else _session()
    return [q.question_id
            for q in engine.order_candidates(
                engine.candidate_questions(session, founder), session, founder)]


# --- inside the block ----------------------------------------------------


def test_the_diagnosis_opens_with_the_founders_own_industry_questions():
    assert _order(session=_session(answered=0))[:2] == [SAS_A, SAS_B]


def test_inside_the_block_industry_outranks_an_unasked_pillar():
    """The deliberate inversion. Outside the block U_OPS wins, because its
    pillar has not been asked about; inside it, the founder's own questions
    come first. This is the whole point of the block and the one place
    coverage is knowingly deferred."""
    inside = _order(session=_session(answered=0))
    outside = _order(session=_session(answered=99))
    assert inside[0] == SAS_A
    assert outside[0] == U_OPS


def test_the_block_promotes_and_never_filters():
    """Every candidate survives it -- a founder whose industry bank runs dry
    mid-block simply continues with the normal order."""
    assert set(_order(session=_session(answered=0))) == {q.question_id for q in _BANK}


def test_only_the_industrys_own_questions_open_the_diagnosis():
    """A universal question whose problem the industry merely weights heavily
    is not what makes a founder feel read, so it does not get the block."""
    order = _order(session=_session(answered=0))
    assert set(order[:2]) == {SAS_A, SAS_B}


# --- the block closes ----------------------------------------------------


def test_coverage_resumes_the_moment_the_block_closes():
    """budget 30 x share 1/3 = 10, capped at 2 by the size of the bank. So the
    block is 2 questions long and the third question is coverage's again."""
    assert _order(session=_session(answered=2))[0] == U_OPS


def test_pillar_coverage_is_guaranteed_after_the_block():
    assert _order(session=_session(answered=99))[0] == U_OPS


@pytest.mark.parametrize("answered", [0, 1, 2, 3, 10, 29])
def test_every_question_stays_reachable_at_every_point_in_the_session(answered):
    assert set(_order(session=_session(answered=answered))) == {
        q.question_id for q in _BANK}


# --- degrade paths -------------------------------------------------------


def test_a_founder_with_no_industry_gets_no_block():
    got = _order(session=_session(answered=0, founder_industry_id=None),
                 founder=_founder(None))
    assert got[0] == U_OPS


def test_a_database_failure_disables_the_block_not_the_diagnosis():
    assert _order(session=_session(answered=0), raises=True)[0] == U_OPS


def test_an_empty_industry_bank_gives_no_block():
    assert _order(session=_session(answered=0), applicability={})[0] == U_OPS


def test_an_unreadable_answer_count_keeps_the_block_open():
    """The safe direction: the block only reorders, and the size limits still
    bound it, so a missing counter must not silently skip the opening."""
    session = SimpleNamespace(
        session_id=1, routing_state="continue", founder_industry_id=SAAS_ID)
    assert _order(session=session)[:2] == [SAS_A, SAS_B]


def test_the_share_setting_can_switch_the_block_off(monkeypatch):
    """0.0 must return selection to the ranking preference alone -- the escape
    hatch if the block ever misbehaves in production."""
    monkeypatch.setattr(settings, "INDUSTRY_OPENING_SHARE", 0.0)
    assert _order(session=_session(answered=0))[0] == U_OPS


# --- the arithmetic, against the real per-stage budgets ------------------

#: stage_order -> question_budget, from migration 8f3a1c92d7b4.
_REAL_BUDGETS = {1: 14, 2: 20, 3: 24, 4: 30, 5: 30, 6: 32, 7: 32, 8: 30}

#: Industry questions actually seeded per stage group, counted off the seed
#: migrations: 15 at Stage 0, 20 at Stage 0->1, 25 at Stage 1->10+.
_BANK_AT_STAGE = {1: 15, 2: 20, 3: 20, 4: 20, 5: 25, 6: 25, 7: 25, 8: 25}


@pytest.mark.parametrize("stage_order", sorted(_REAL_BUDGETS))
def test_every_stage_keeps_two_questions_per_pillar_for_coverage(stage_order):
    """The guarantee, checked against the numbers that actually ship rather
    than a fixture. Six pillars x 2 = 12 reserved; at Ideation only two pillars
    are in scope, so the reservation is smaller there and the block larger."""
    budget = _REAL_BUDGETS[stage_order]
    for pillars in range(1, 7):
        size = opening_block_size(
            budget=budget, pillars_in_scope=pillars,
            share=1 / 3, available=_BANK_AT_STAGE[stage_order])
        left = budget - size
        assert left >= pillars * MIN_QUESTIONS_PER_PILLAR, (
            f"stage {stage_order}: block {size} of {budget} leaves {left} "
            f"for {pillars} pillars")


def test_the_block_is_never_larger_than_the_bank():
    """Reserving ten slots when the bank holds four would idle six. The block
    is a head start, not a quota."""
    assert opening_block_size(budget=30, pillars_in_scope=6, share=1 / 3,
                              available=4) == 4


def test_the_share_is_the_binding_limit_when_the_bank_is_deep():
    assert opening_block_size(budget=30, pillars_in_scope=6, share=1 / 3,
                              available=25) == 10


def test_coverage_is_the_binding_limit_at_ideation():
    """Ideation: budget 14, bank 15, six pillars would reserve 12 and leave 2.
    Coverage wins over the share here, which is exactly the case that would
    otherwise spend the whole diagnosis on one or two pillars."""
    assert opening_block_size(budget=14, pillars_in_scope=6, share=1 / 3,
                              available=15) == 2
    # Two pillars in scope (the real Ideation scope) reserves only 4, so the
    # share's 4 binds instead and the founder gets a proper industry opening.
    assert opening_block_size(budget=14, pillars_in_scope=2, share=1 / 3,
                              available=15) == 4


def test_opening_block_size_never_raises_on_nonsense():
    for kwargs in (
        dict(budget=0, pillars_in_scope=6, share=1 / 3, available=25),
        dict(budget=-5, pillars_in_scope=6, share=1 / 3, available=25),
        dict(budget=30, pillars_in_scope=6, share=0.0, available=25),
        dict(budget=30, pillars_in_scope=6, share=-1.0, available=25),
        dict(budget=30, pillars_in_scope=6, share=1 / 3, available=0),
        dict(budget=30, pillars_in_scope=-2, share=1 / 3, available=25),
        dict(budget=5, pillars_in_scope=6, share=1 / 3, available=25),
    ):
        assert opening_block_size(**kwargs) >= 0


def test_a_share_above_one_cannot_consume_the_whole_budget():
    size = opening_block_size(budget=30, pillars_in_scope=6, share=5.0,
                              available=25)
    assert 30 - size >= 6 * MIN_QUESTIONS_PER_PILLAR


def test_the_shipped_default_share_is_a_third():
    assert settings.INDUSTRY_OPENING_SHARE == pytest.approx(1 / 3)
