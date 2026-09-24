"""Option E: coverage-relative RCCS, and the separation of evidence strength from
diagnostic sufficiency.

Hermetic -- no database, no LLM, no clock. Sections follow the Option E brief's
required validations A-M.

THE CENTRAL PROPERTY these tests exist to protect: RCCS >= 0.80 means "the
evidence for this cause is strong relative to what could be gathered". It does
NOT mean the diagnosis may end. Every test that establishes a strong score also
checks what the FINAL QUALITY GATE does with it.
"""

from decimal import Decimal

import pytest

from app.api.v1.diagnosis.completion import decide_completion, evaluate_quality_gate
from app.api.v1.diagnosis.rccs import (
    RCCS_STRONG_THRESHOLD,
    SIBLING_WEIGHT,
    RCCSState,
    events_for_answer,
)
from app.core.config import settings
from app.models.enums import ScoreLabel

RC_A, RC_B, RC_C = 101, 202, 303
P1, P2, P3 = 1, 2, 3
PROBLEM_OF = {RC_A: 1, RC_B: 1, RC_C: 2}


def add(state, *, aid, band, rc=RC_A, pillar=P1, siblings=(), qid=None):
    state.apply_all(events_for_answer(
        answer_id=aid, question_id=qid if qid is not None else 8000 + aid,
        score_label=band, primary_root_cause_id=rc,
        sibling_root_cause_ids=siblings, pillar_id=pillar, sequence=aid))
    return state.score_for(rc)


def gate(state, anchors=(1,), *, pillars=True, high_value=False):
    return evaluate_quality_gate(
        state=state, anchor_problem_ids=frozenset(anchors),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=pillars,
        high_value_question_available=high_value)


# === A. ONE-QUESTION ROOT CAUSE ==============================================

def test_A_one_question_cause_with_one_red_reaches_the_threshold():
    """The whole point of Option E. 80.3% of the catalogue is this shape, and
    under the previous absolute model every one of them was capped at 0.625."""
    state = RCCSState(askable={RC_A: 1})
    score = add(state, aid=1, band=ScoreLabel.RED)
    assert score.rccs == Decimal("0.8000")
    assert score.is_strong and score.has_supporting_evidence
    assert score.askable_questions == 1 and score.answered_questions == 1
    assert score.coverage == Decimal("1.0000")


def test_A_a_strong_score_does_not_by_itself_end_the_diagnosis():
    """RCCS is evidence strength; the gate decides sufficiency. A cause can be
    strong while the diagnosis correctly continues -- here because a high-value
    question is still unasked."""
    state = RCCSState(askable={RC_A: 1})
    assert add(state, aid=1, band=ScoreLabel.RED).is_strong

    blocked = decide_completion(
        state=state, anchor_problem_ids=frozenset({1}),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
        high_value_question_available=True, candidates_remaining=True,
        answered=1, safety_ceiling=120)
    assert not blocked.complete

    thin = decide_completion(
        state=state, anchor_problem_ids=frozenset({1}),
        problem_of_root_cause=PROBLEM_OF, pillars_sufficient=False,
        high_value_question_available=False, candidates_remaining=True,
        answered=1, safety_ceiling=120)
    assert not thin.complete


# === B. ONE-QUESTION MODERATE EVIDENCE =======================================

def test_B_one_question_cause_with_one_amber_is_moderate_not_strong():
    """AMBER is partial support, so full coverage of a one-question cause with a
    moderate answer lands at half the strong score -- documented, not incidental."""
    state = RCCSState(askable={RC_A: 1})
    score = add(state, aid=1, band=ScoreLabel.AMBER)
    assert score.rccs == Decimal("0.4000")
    assert not score.is_strong
    assert score.coverage == Decimal("1.0000")      # fully probed, weakly supported


def test_B_amber_can_never_reach_strong_on_full_coverage_alone():
    """Closes defect F3 from the adversarial validation: under the absolute model
    eight AMBERs in one pillar reached exactly 0.80. Coverage-relative scoring
    bounds AMBER at half of full coverage however many are asked."""
    for askable in (1, 2, 5, 12):
        state = RCCSState(askable={RC_A: askable})
        for i in range(1, askable + 1):
            add(state, aid=i, band=ScoreLabel.AMBER, qid=9000 + i)
        assert state.score_for(RC_A).rccs <= Decimal("0.5"), askable


# === C. ONE-QUESTION CONTRADICTION ===========================================

def test_C_contradiction_lowers_a_strong_one_question_cause():
    """A one-question cause cannot contradict itself -- one question takes one
    answer -- so the contradiction arrives through the sibling edge."""
    state = RCCSState(askable={RC_A: 1, RC_C: 1})
    before = add(state, aid=1, band=ScoreLabel.RED).rccs
    assert before >= RCCS_STRONG_THRESHOLD

    add(state, aid=2, band=ScoreLabel.GREEN, rc=RC_C, siblings=(RC_A,), pillar=P2)
    after = state.score_for(RC_A).rccs
    assert after < before
    assert state.score_for(RC_A).contradicting_event_count == 1


# --------------------------------------------------------------------------
# DEFECT E1 -- FIXED. Sibling contradiction is no longer subject to the support
# cap, so indirect evidence can challenge a cause even though it can never
# manufacture one.
#
# The support cap (0.25) and the contradiction ceiling serve opposite purposes:
# one stops indirect evidence CREATING a strong cause, the other would stop it
# OVERTURNING one. Applying the support cap to both made a fully-probed cause
# undislodgeable (0.8889 -> 0.8445 at saturation, whatever the volume).
#
# After the fix, at sibling-contradiction saturation:
#   askable=1  0.8000 -> 0.6462     askable=3  0.9231 -> 0.7456
#   askable=2  0.8889 -> 0.7180     askable=5  0.9524 -> 0.7693
#
# The two tests below are the regression. They were strict-xfail while the
# defect stood; they now assert the fixed behaviour directly.
# --------------------------------------------------------------------------


def test_C_completion_can_flip_from_eligible_to_not_eligible():
    """A multi-question cause: fully probed and strong, then contradicted below
    the bar, and the gate's verdict reverses."""
    state = RCCSState(askable={RC_A: 2})
    add(state, aid=1, band=ScoreLabel.RED, qid=1)
    add(state, aid=2, band=ScoreLabel.RED, qid=2)
    assert gate(state).passed

    # Five, not four: four land exactly on 0.8000 and `>= 0.80` still qualifies.
    for aid in (3, 4, 5, 6, 7):
        add(state, aid=aid, band=ScoreLabel.GREEN, rc=RC_C, siblings=(RC_A,), pillar=P2)
    assert state.score_for(RC_A).rccs < RCCS_STRONG_THRESHOLD
    assert not gate(state).passed


# === D. MULTI-QUESTION CAUSE =================================================

def test_D_coverage_relative_behaviour_across_partial_and_full_coverage():
    """Asking MORE of a cause makes it harder to call strong, which is the
    intended reversal: we looked harder and found less."""
    state = RCCSState(askable={RC_A: 5})
    seen = [add(state, aid=i, band=ScoreLabel.RED, qid=6000 + i).rccs
            for i in range(1, 6)]
    assert seen == [Decimal("0.1905"), Decimal("0.3810"), Decimal("0.5714"),
                    Decimal("0.7619"), Decimal("0.9524")]
    assert not any(v >= RCCS_STRONG_THRESHOLD for v in seen[:4])
    assert seen[4] >= RCCS_STRONG_THRESHOLD


def test_D_the_same_evidence_scores_lower_on_a_less_probed_cause():
    thin = RCCSState(askable={RC_A: 1})
    wide = RCCSState(askable={RC_A: 6})
    add(thin, aid=1, band=ScoreLabel.RED)
    add(wide, aid=1, band=ScoreLabel.RED)
    assert thin.score_for(RC_A).rccs > wide.score_for(RC_A).rccs


def test_D_missing_catalogue_count_falls_back_to_answered_questions():
    """No askable map: the denominator becomes what we actually asked, so the
    score degrades to 'everything we knew to ask' rather than to zero."""
    state = RCCSState()
    score = add(state, aid=1, band=ScoreLabel.RED)
    assert score.askable_questions == 1
    assert score.rccs == Decimal("0.8000")


# === E. DIRECT VS SIBLING ====================================================

def test_E_direct_evidence_outweighs_sibling_evidence():
    state = RCCSState(askable={RC_A: 1, RC_B: 1})
    add(state, aid=1, band=ScoreLabel.RED, rc=RC_A, siblings=(RC_B,))
    assert state.score_for(RC_A).rccs > state.score_for(RC_B).rccs


def test_E_sibling_only_evidence_can_never_be_strong():
    state = RCCSState(askable={RC_A: 1, RC_B: 1})
    for i in range(1, 30):
        add(state, aid=i, band=ScoreLabel.RED, rc=RC_B, siblings=(RC_A,), pillar=i % 4)
    score = state.score_for(RC_A)
    assert score.rccs <= SIBLING_WEIGHT
    assert not score.is_strong
    assert score.answered_questions == 0        # never actually asked about


# === F. SIBLING SATURATION ===================================================

def test_F_the_sibling_ceiling_survives_option_e():
    """Regression of the 0.9375 defect, re-run against the new formula."""
    state = RCCSState(askable={RC_A: 1, RC_B: 1})
    for i in range(1, 25):
        add(state, aid=i, band=ScoreLabel.RED, rc=RC_B, siblings=(RC_A,), pillar=i % 2)
    assert state.score_for(RC_A).rccs == SIBLING_WEIGHT


def test_F_sibling_evidence_still_corroborates_a_directly_probed_cause():
    lone = RCCSState(askable={RC_A: 4})
    add(lone, aid=1, band=ScoreLabel.RED)

    helped = RCCSState(askable={RC_A: 4, RC_B: 1})
    add(helped, aid=1, band=ScoreLabel.RED)
    for i in range(2, 8):
        add(helped, aid=i, band=ScoreLabel.RED, rc=RC_B, siblings=(RC_A,), pillar=P2)

    assert helped.score_for(RC_A).rccs > lone.score_for(RC_A).rccs


# === G. NO SUPPORTING EVIDENCE ===============================================

def test_G_a_cause_with_no_supporting_evidence_cannot_pass_the_gate():
    state = RCCSState(askable={RC_A: 1, RC_C: 1})
    add(state, aid=1, band=ScoreLabel.GREEN, rc=RC_C, siblings=(RC_A,))
    assert state.score_for(RC_A).supporting_event_count == 0
    assert not gate(state).passed
    assert state.strong_scores() == ()


# === H. CURRENT-PROBLEM RELEVANCE ============================================

def test_H_a_strong_unrelated_cause_does_not_complete_the_diagnosis():
    state = RCCSState(askable={RC_C: 1})
    assert add(state, aid=1, band=ScoreLabel.RED, rc=RC_C).is_strong   # problem 2
    result = gate(state, anchors=(1,))                                 # founder said 1
    assert not result.passed
    assert result.qualifying_causes == ()
    assert result.unexplained_problem_ids == (1,)


# === I. HIGH-VALUE UNANSWERED QUESTION =======================================

def test_I_a_high_value_unanswered_question_keeps_the_diagnosis_open():
    state = RCCSState(askable={RC_A: 1})
    add(state, aid=1, band=ScoreLabel.RED)
    assert gate(state, high_value=True).failed_checks() == ("no_high_value_question",)
    assert gate(state, high_value=False).passed


# === J. CONTRADICTION AT THE GATE ============================================

def test_J_the_gate_accounts_for_contradiction():
    """Accumulated sibling contradiction eventually takes a fully-probed cause
    below the bar, and the gate follows it down.

    The count matters and is asserted rather than guessed: four contradictions
    land EXACTLY on 0.8000, which still qualifies because the rule is `>= 0.80`.
    It takes a fifth to demote the cause. Pinning both sides of that boundary is
    the point of the test -- an off-by-one here would silently change when a
    diagnosis is allowed to conclude.
    """
    state = RCCSState(askable={RC_A: 2})
    add(state, aid=1, band=ScoreLabel.RED, qid=1)
    add(state, aid=2, band=ScoreLabel.RED, qid=2)
    assert state.score_for(RC_A).rccs == Decimal("0.8889")
    assert gate(state).passed

    for aid in (3, 4, 5, 6):
        add(state, aid=aid, band=ScoreLabel.GREEN, rc=RC_C, siblings=(RC_A,), pillar=P3)
    assert state.score_for(RC_A).rccs == Decimal("0.8000")    # exactly on the bar
    assert gate(state).passed                                 # and >= still qualifies

    add(state, aid=7, band=ScoreLabel.GREEN, rc=RC_C, siblings=(RC_A,), pillar=P3)
    assert state.score_for(RC_A).rccs < RCCS_STRONG_THRESHOLD
    result = gate(state)
    assert not result.passed
    assert "meets_threshold" in result.failed_checks()


# === K. DETERMINISM ==========================================================

def test_K_identical_inputs_produce_identical_scores_and_decisions():
    def run():
        state = RCCSState(askable={RC_A: 3, RC_B: 2, RC_C: 1})
        for i, (band, rc, p) in enumerate(
            [(ScoreLabel.RED, RC_A, P1), (ScoreLabel.GREEN, RC_C, P2),
             (ScoreLabel.AMBER, RC_A, P1), (ScoreLabel.RED, RC_B, P3),
             (ScoreLabel.RED, RC_A, P1)], start=1):
            add(state, aid=i, band=band, rc=rc, pillar=p, siblings=(RC_B,), qid=500 + i)
        d = decide_completion(
            state=state, anchor_problem_ids=frozenset({1}),
            problem_of_root_cause=PROBLEM_OF, pillars_sufficient=True,
            high_value_question_available=False, candidates_remaining=True,
            answered=5, safety_ceiling=120)
        return ([(s.root_cause_id, str(s.rccs)) for s in state.all_scores()],
                d.complete, str(d.reason))

    assert run() == run() == run()


# === L. SAFETY CEILING =======================================================

def test_L_safety_ceiling_remains_separate_from_the_coverage_denominator():
    assert settings.safety_ceiling(None) > settings.question_budget(None)
    assert settings.question_budget(None) == settings.MAX_DIAGNOSIS_QUESTIONS == 30
    for b in (None, 1, 12, 30, 50):
        assert settings.safety_ceiling(b) >= settings.question_budget(b)


# === Bounds and invariants ===================================================

def test_rccs_stays_within_zero_and_one_under_every_extreme():
    for askable in (1, 3, 20):
        state = RCCSState(askable={RC_A: askable, RC_B: 1})
        for i in range(1, 80):
            band = (ScoreLabel.RED, ScoreLabel.GREEN, ScoreLabel.AMBER)[i % 3]
            add(state, aid=i, band=band, rc=RC_A, pillar=i % 5, qid=i)
        for i in range(100, 160):
            add(state, aid=i, band=ScoreLabel.RED, rc=RC_B, siblings=(RC_A,), qid=i)
        assert Decimal(0) <= state.score_for(RC_A).rccs <= Decimal(1)


def test_more_evidence_than_the_catalogue_holds_cannot_exceed_full_coverage():
    """Defensive: if a session somehow answered more questions than the cause
    has, reach is clamped at 1.0 rather than running away."""
    state = RCCSState(askable={RC_A: 1})
    for i in range(1, 6):
        add(state, aid=i, band=ScoreLabel.RED, qid=3000 + i)
    assert state.score_for(RC_A).rccs <= Decimal(1)


def test_C_direct_contradiction_does_reduce_a_cause_correctly():
    """The path that works: a GREEN on one of the cause's OWN questions both
    withholds support mass and contradicts, so it cuts hard."""
    state = RCCSState(askable={RC_A: 2})
    add(state, aid=1, band=ScoreLabel.RED, qid=1)
    add(state, aid=2, band=ScoreLabel.GREEN, qid=2)
    assert state.score_for(RC_A).rccs == Decimal("0.4049")
    assert not state.score_for(RC_A).is_strong


def test_C_a_one_question_cause_is_dislodged_by_sibling_contradiction():
    """Holds because its support sits exactly on the threshold -- see DEFECT E1
    for why this does NOT generalise to multi-question causes."""
    state = RCCSState(askable={RC_A: 1, RC_C: 1})
    assert add(state, aid=1, band=ScoreLabel.RED).rccs == Decimal("0.8000")
    for aid in (2, 3, 4):
        add(state, aid=aid, band=ScoreLabel.GREEN, rc=RC_C, siblings=(RC_A,), pillar=P2)
    assert state.score_for(RC_A).rccs < RCCS_STRONG_THRESHOLD
    assert not gate(state).passed
