"""Evidence semantics: what counts as evidence, how much, and how sure.

Four defects found by a three-persona QA pass (Rohan/ideation D2C food,
Arya/early-traction salon, Vikram/growth B2B logistics), all in the scoring
layer rather than the interviewing layer:

  1. NOT_APPLICABLE did not exist, so "this isn't really a product business"
     was classified Red -- the strongest negative signal -- and drove Product to
     maximum risk, three product root causes, and "say no to feature requests"
     as a logistics founder's first action.
  2. Category risk was a MEAN, so one Red read 1.00 while seven answers read
     0.43. The adaptive advisor asks more where it suspects a problem, so the
     scoring layer penalised the interviewing layer's best work.
  3. detection_confidence reached 1.0 on a single Red answer.
  4. Investor questions under the deliberately-ungated FND-005 reached
     non-raising founders at Stage 1->10+.

These tests assert the PROPERTIES, not the tuned numbers, so a later change to
the prior or the threshold does not have to rewrite them.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.context_scope import (
    FUNDRAISING_INTENT,
    ROOT_CAUSE_PRECONDITIONS,
    gated_root_cause_codes,
)
from app.api.v1.reasoning.engines.diagnostic import (
    CATEGORY_RISK_PRIOR,
    StandardDiagnosticEngine,
)
from app.api.v1.reasoning.engines.recommendation import DefaultInterventionRelevance
from app.api.v1.reasoning.engines.root_cause import StandardRootCauseEngine
from app.api.v1.reasoning.schemas import AnswerClassification, CategoryRisk
from app.models.enums import ScoreLabel

D = Decimal
GREEN, AMBER, RED = D("0"), D("1"), D("2")
_SCORE = {ScoreLabel.GREEN: GREEN, ScoreLabel.AMBER: AMBER, ScoreLabel.RED: RED}


def q(qid, rcid, category, problem_id=1):
    return SimpleNamespace(question_id=qid, root_cause_id=rcid, category=category,
                           problem_id=problem_id, is_distress_tagged=False,
                           follow_up_question_id=None)


def ans(aid, qid, label):
    return AnswerClassification(
        answer_id=aid, question_id=qid, label=label,
        score=_SCORE.get(label), is_distress_flagged=False)


def ctx(threshold=D("0.30")):
    return SimpleNamespace(config=SimpleNamespace(
        question_scores=SimpleNamespace(green=GREEN, amber=AMBER, red=RED),
        branching=SimpleNamespace(category_risk_threshold=threshold,
                                  root_cause_min_detection_confidence=D("0"),
                                  root_cause_max_candidates=0,
                                  amber_cluster_trigger=3),
        category_max_scores=None))


def risks(questions, answers, threshold=D("0.30")):
    qmap = {x.question_id: x for x in questions}
    rows = StandardDiagnosticEngine(classifier=None).compute_category_risks(
        list(answers), qmap, ctx(threshold))
    return {r.category: r for r in rows}


def detect(questions, answers, risk_rows=()):
    qmap = {x.question_id: x for x in questions}
    engine = StandardRootCauseEngine(repository=None)
    return {d.root_cause_id: d
            for d in engine.detect(list(answers), list(risk_rows), qmap, ctx())}


# === P0-1 : NOT_APPLICABLE ==================================================

def test_not_applicable_is_an_unscored_label():
    assert ScoreLabel.NOT_APPLICABLE.is_scored is False
    assert all(lbl.is_scored for lbl in
               (ScoreLabel.GREEN, ScoreLabel.AMBER, ScoreLabel.RED))


def test_not_applicable_carries_no_score_not_a_zero():
    """Zero is Green's band. Scoring N/A zero would make it POSITIVE evidence
    that the thing asked about is healthy, which is a different claim."""
    assert ans(1, 101, ScoreLabel.NOT_APPLICABLE).score is None


def test_a_category_answered_only_not_applicable_produces_no_risk_row():
    """The logistics regression. Excluded from numerator AND denominator, so
    the category does not appear at all rather than appearing at zero -- there
    is nothing to report on."""
    questions = [q(101, 1, "Product"), q(102, 1, "Product")]
    answers = [ans(1, 101, ScoreLabel.NOT_APPLICABLE),
               ans(2, 102, ScoreLabel.NOT_APPLICABLE)]
    assert "Product" not in risks(questions, answers)


def test_not_applicable_does_not_raise_risk():
    """Two real Ambers plus two N/A must read the same as two real Ambers."""
    questions = [q(101, 1, "Product"), q(102, 1, "Product"),
                 q(103, 1, "Product"), q(104, 1, "Product")]
    real = [ans(1, 101, ScoreLabel.AMBER), ans(2, 102, ScoreLabel.AMBER)]
    padded = real + [ans(3, 103, ScoreLabel.NOT_APPLICABLE),
                     ans(4, 104, ScoreLabel.NOT_APPLICABLE)]
    assert (risks(questions, real)["Product"].normalised_risk
            == risks(questions, padded)["Product"].normalised_risk)


def test_not_applicable_does_not_lower_risk_either():
    """The other half: it must not dilute a genuine finding by inflating the
    denominator. Guards against 'exclude from numerator only'."""
    questions = [q(101, 1, "Product")] + [q(110 + i, 1, "Product") for i in range(5)]
    one_red = [ans(1, 101, ScoreLabel.RED)]
    with_na = one_red + [ans(10 + i, 110 + i, ScoreLabel.NOT_APPLICABLE)
                         for i in range(5)]
    assert (risks(questions, one_red)["Product"].normalised_risk
            == risks(questions, with_na)["Product"].normalised_risk)


def test_not_applicable_never_creates_a_root_cause():
    questions = [q(101, 7, "Product")]
    assert detect(questions, [ans(1, 101, ScoreLabel.NOT_APPLICABLE)]) == {}


def test_not_applicable_does_not_dilute_a_real_detection():
    """It must not sit in `members` pulling detection_confidence down."""
    questions = [q(101, 7, "Product"), q(102, 7, "Product")]
    alone = detect(questions, [ans(1, 101, ScoreLabel.RED)])
    padded = detect(questions, [ans(1, 101, ScoreLabel.RED),
                                ans(2, 102, ScoreLabel.NOT_APPLICABLE)])
    assert alone[7].detection_confidence == padded[7].detection_confidence
    assert len(padded[7].evidence) == 1


def test_historical_three_band_answers_are_unaffected():
    """Backward compatibility: nothing that did not previously exist is read,
    so a session recorded before this label behaves exactly as before."""
    questions = [q(101, 1, "Product"), q(102, 1, "Product")]
    answers = [ans(1, 101, ScoreLabel.RED), ans(2, 102, ScoreLabel.GREEN)]
    row = risks(questions, answers)["Product"]
    assert row.raw_score == RED
    assert row.max_score == RED * (2 + CATEGORY_RISK_PRIOR)


# === P0-2 : category risk ===================================================

def test_a_single_red_answer_does_not_produce_maximum_risk():
    """The headline defect. One Red used to read 1.0000."""
    row = risks([q(101, 1, "Product")], [ans(1, 101, ScoreLabel.RED)])["Product"]
    assert row.normalised_risk < D("0.5")


def test_more_reds_raise_risk():
    one = risks([q(101, 1, "P")], [ans(1, 101, ScoreLabel.RED)])["P"].normalised_risk
    qs = [q(100 + i, 1, "P") for i in range(3)]
    three = risks(qs, [ans(i, 100 + i, ScoreLabel.RED)
                       for i in range(3)])["P"].normalised_risk
    assert three > one


def test_mixed_amber_and_red_sits_between_all_amber_and_all_red():
    qs = [q(100 + i, 1, "P") for i in range(2)]
    all_amber = risks(qs, [ans(0, 100, ScoreLabel.AMBER),
                           ans(1, 101, ScoreLabel.AMBER)])["P"].normalised_risk
    mixed = risks(qs, [ans(0, 100, ScoreLabel.RED),
                       ans(1, 101, ScoreLabel.AMBER)])["P"].normalised_risk
    all_red = risks(qs, [ans(0, 100, ScoreLabel.RED),
                         ans(1, 101, ScoreLabel.RED)])["P"].normalised_risk
    assert all_amber < mixed < all_red


def test_many_greens_produce_no_risk():
    qs = [q(100 + i, 1, "P") for i in range(5)]
    row = risks(qs, [ans(i, 100 + i, ScoreLabel.GREEN) for i in range(5)])["P"]
    assert row.normalised_risk == D("0")
    assert not row.is_flagged


def test_deeper_investigation_no_longer_beats_a_single_answer():
    """Vikram, reproduced. Founder Psychology carried SEVEN answers summing to
    6.0 and read 0.4286, while Opportunity Evaluation carried ONE Red and read
    1.0000 -- so the category holding his actual bottleneck ranked below one
    that had been asked once. The seven-answer category must now score at least
    as high as the one-answer category on strictly more negative evidence."""
    deep_qs = [q(200 + i, 1, "Founder Psychology") for i in range(7)]
    deep = [ans(0, 200, ScoreLabel.RED)] + [
        ans(i, 200 + i, ScoreLabel.AMBER) for i in range(1, 5)] + [
        ans(i, 200 + i, ScoreLabel.GREEN) for i in range(5, 7)]
    shallow_qs = [q(300, 2, "Opportunity Evaluation")]
    shallow = [ans(99, 300, ScoreLabel.RED)]
    rows = risks(deep_qs + shallow_qs, deep + shallow)
    assert rows["Founder Psychology"].raw_score > rows["Opportunity Evaluation"].raw_score
    assert (rows["Founder Psychology"].normalised_risk
            >= rows["Opportunity Evaluation"].normalised_risk)


def test_arya_team_and_leadership_is_not_silenced_by_one_green():
    """Arya, reproduced. Her single Team & Leadership probe drew an articulate
    admission -- "that gap is still filled by me, which isn't sustainable" --
    scored Green, giving the category 0.0000 and no flag. The scoring half of
    that is legitimate; this pins the arithmetic so a future change cannot make
    a genuinely negative multi-answer category read as clean."""
    qs = [q(400 + i, 1, "Team & Leadership") for i in range(5)]
    answers = [ans(0, 400, ScoreLabel.RED), ans(1, 401, ScoreLabel.RED),
               ans(2, 402, ScoreLabel.AMBER), ans(3, 403, ScoreLabel.AMBER),
               ans(4, 404, ScoreLabel.GREEN)]
    row = risks(qs, answers)["Team & Leadership"]
    assert row.is_flagged


def test_not_every_category_flags_any_more():
    """Across three personas every category was flagged, which carries no
    prioritisation signal. A category probed once and answered Amber must not
    flag at the shipped threshold."""
    row = risks([q(500, 1, "Marketing Execution")],
                [ans(1, 500, ScoreLabel.AMBER)])["Marketing Execution"]
    assert not row.is_flagged


# === P1-5 : confidence ======================================================

def test_one_red_answer_is_not_maximum_confidence():
    d = detect([q(101, 7, "P")], [ans(1, 101, ScoreLabel.RED)])
    assert d[7].detection_confidence < D("1")
    assert d[7].detection_confidence > D("0")


def test_corroboration_raises_confidence():
    one = detect([q(101, 7, "P")], [ans(1, 101, ScoreLabel.RED)])
    qs = [q(100 + i, 7, "P") for i in range(3)]
    three = detect(qs, [ans(i, 100 + i, ScoreLabel.RED) for i in range(3)])
    assert three[7].detection_confidence > one[7].detection_confidence


def test_mixed_evidence_lowers_confidence():
    """A Green is evidence the cause is NOT active."""
    qs = [q(100 + i, 7, "P") for i in range(2)]
    both_red = detect(qs, [ans(0, 100, ScoreLabel.RED), ans(1, 101, ScoreLabel.RED)])
    mixed = detect(qs, [ans(0, 100, ScoreLabel.RED), ans(1, 101, ScoreLabel.GREEN)])
    assert mixed[7].detection_confidence < both_red[7].detection_confidence


def test_confidence_never_reaches_certainty():
    """No finite number of probes makes a diagnosis certain."""
    qs = [q(100 + i, 7, "P") for i in range(12)]
    d = detect(qs, [ans(i, 100 + i, ScoreLabel.RED) for i in range(12)])
    assert d[7].detection_confidence < D("1")


def test_confidence_is_not_merely_severity():
    """The distinction the old formula could not express: identical severity
    (every probe Red), different amounts of corroboration."""
    one = detect([q(101, 7, "P")], [ans(1, 101, ScoreLabel.RED)])
    qs = [q(100 + i, 7, "P") for i in range(4)]
    four = detect(qs, [ans(i, 100 + i, ScoreLabel.RED) for i in range(4)])
    assert one[7].detection_score == four[7].detection_score        # same severity
    assert one[7].detection_confidence < four[7].detection_confidence


# === P1-4 : FND-005 investor questions at Stage 1->10+ ======================

INVESTOR_CAUSES = {"RC-313", "RC-317", "RC-318", "RC-319", "RC-321", "RC-322"}


def test_the_investor_cohort_is_gated_without_intent():
    assert gated_root_cause_codes(frozenset()) == INVESTOR_CAUSES


def test_the_investor_cohort_is_reachable_with_intent():
    assert gated_root_cause_codes(frozenset({FUNDRAISING_INTENT})) == frozenset()


def test_unknown_context_gates_no_root_cause():
    assert gated_root_cause_codes(None) == frozenset()


def test_the_universal_pitch_battery_causes_are_never_gated():
    """RC-311/312/314/315/316/320 carry the Stage 0->1 battery (Q281-Q286),
    written for "someone smart but unfamiliar with it". Gating them would
    reintroduce the category-level gate the problem-grain design avoids."""
    universal = {"RC-311", "RC-312", "RC-314", "RC-315", "RC-316", "RC-320"}
    assert not universal & set(ROOT_CAUSE_PRECONDITIONS)


# === P0-3 : business-model safety ===========================================

_REL = DefaultInterventionRelevance()


def _relevant(industries, industry_code):
    return _REL.is_relevant(stage_relevance=None, industry_relevance=industries,
                            stage_id=None, industry_code=industry_code)


def test_an_unrestricted_intervention_reaches_everyone():
    assert _relevant(["all"], "services")
    assert _relevant(["all"], None)
    assert _relevant([], "services")


def test_a_saas_intervention_does_not_reach_a_services_founder():
    """Vikram, reproduced: INT-376 told a logistics founder to say no to
    feature requests and set up usage tracking for his next feature launch."""
    assert not _relevant(["saas"], "services")
    assert not _relevant(["saas"], "manufacturing")


def test_a_saas_intervention_still_reaches_a_saas_founder():
    assert _relevant(["saas"], "saas")


def test_a_restricted_intervention_is_withheld_when_industry_is_unknown():
    """Fails CLOSED, and only for rows that declare themselves non-universal.
    Admitting feature-backlog advice to a founder whose industry we cannot
    determine is the failure the tag exists to prevent."""
    assert not _relevant(["saas"], None)


def test_unrestricted_rows_still_reach_an_unknown_industry():
    """The fail-closed rule must not cost an un-onboarded founder anything that
    was ever meant to be universal."""
    assert _relevant(["all"], None)


# === P1-6 : breadth influences RANKING, and rewards independence ============
#
# The defect these pin: evidence count had NO influence on final ranking.
# Corroboration lived in detection_confidence, which is not a ranking factor,
# and the evidence_breadth weight was zero -- so in QA a founder-dependency
# cause supported by two corroborating answers ranked below four causes each
# resting on a single answer.
#
# These exercise the real WeightedConfidenceModel with an explicit weight set,
# rather than the live scoring_rules, so they state the property independently
# of whatever the deployed configuration happens to be.

from app.api.v1.reasoning.config import RankingWeights
from app.api.v1.reasoning.engines.confidence import (
    WeightedConfidenceModel,
    evidence_breadth_value,
)
from app.models.enums import ConfirmationStatus

ACTIVE_WEIGHTS = RankingWeights(
    category_risk=D("0.40"), confirmation_status=D("0.25"),
    stage_probability=D("0.20"), industry_probability=D("0.00"),
    evidence_breadth=D("0.15"), expected_sum=D("1.0"))


class _NoPriors:
    """Stage and industry priors absent -- a supported state the model records
    as unavailable, not a fixture cheat. It isolates the factor under test."""

    def get_stage_weights(self, _stage_id):
        return {}

    def get_industry_weights(self, *_a, **_k):
        return None


def _rank(questions, answers):
    qmap = {x.question_id: x for x in questions}
    rows = StandardDiagnosticEngine(classifier=None).compute_category_risks(
        list(answers), qmap, ctx())
    dets = StandardRootCauseEngine(repository=None).detect(
        list(answers), rows, qmap, ctx())
    rctx = SimpleNamespace(
        stage_id=4, industry_id=None,
        config=SimpleNamespace(
            ranking_weights=ACTIVE_WEIGHTS,
            confirmation_multipliers=SimpleNamespace(
                confirmed=D("1.5"), unconfirmed=D("1.0"), not_tested=D("0.5")),
            industry_probability=None,
            branching=SimpleNamespace(root_cause_min_detection_confidence=D("0"),
                                      root_cause_max_candidates=0,
                                      amber_cluster_trigger=3,
                                      top_root_causes_report=3)))
    scored = WeightedConfidenceModel(repository=_NoPriors()).score_and_rank(dets, rctx)
    return {s.root_cause_id: s for s in scored}, {d.root_cause_id: d for d in dets}


def test_breadth_rewards_independent_dimensions_not_raw_answer_count():
    """The distinction the whole factor exists for. Two answers spanning two
    dimensions must earn MORE breadth than six answers in a single dimension,
    or the factor is just a count with extra steps."""
    def det(dims, mass, n):
        return SimpleNamespace(
            independent_signal_count=dims, evidence_mass=D(str(mass)),
            evidence=tuple(SimpleNamespace(directness="direct") for _ in range(n)),
            category_risk_score=D("0.5"))
    six_one_dim = evidence_breadth_value(det(1, 6, 6))
    two_two_dims = evidence_breadth_value(det(2, 2, 2))
    six_six_dims = evidence_breadth_value(det(6, 6, 6))
    assert two_two_dims > six_one_dim
    assert six_six_dims > two_two_dims


def test_converging_evidence_can_outrank_an_isolated_severe_answer():
    """Vikram, reduced. Cause 1: one isolated Red. Cause 2: corroborated across
    several dimensions. Cause 2 must win -- it did not before breadth carried
    weight."""
    questions = [q(101, 1, "Sales & Revenue")] + [
        q(200 + i, 2, c) for i, c in enumerate(
            ["Founder Psychology", "Operations & Systems", "Team & Leadership",
             "Business Planning"], start=1)]
    answers = [ans(1, 101, ScoreLabel.RED)] + [
        ans(10 + i, 200 + i, ScoreLabel.RED) for i in range(1, 5)]
    scored, dets = _rank(questions, answers)
    assert dets[2].independent_signal_count > dets[1].independent_signal_count
    assert scored[2].rank < scored[1].rank, "converging evidence lost to an isolated Red"


def test_repeated_same_dimension_evidence_gains_little_from_breadth():
    """The counter-case, stated as what breadth actually controls.

    Six answers about ONE subject must not earn the breadth of genuinely
    independent corroboration. This asserts the FACTOR, not the final rank:
    scripts/qa/breadth_sensitivity.py shows this fixture's repeated cause
    leading at every weight INCLUDING zero, so its rank is decided by category
    risk, not by breadth, and requiring breadth to overturn it would be
    asserting something the engine never did.

    What matters is that activating breadth does not WIDEN the repeated cause's
    advantage the way it would if breadth were a count.
    """
    questions = [q(300 + i, 3, "Idea & Validation") for i in range(6)] + [
        q(401, 4, "Financial Management")]
    answers = [ans(20 + i, 300 + i, ScoreLabel.AMBER) for i in range(6)] + [
        ans(40, 401, ScoreLabel.RED)]
    _, dets = _rank(questions, answers)
    assert dets[3].independent_signal_count == 1        # one dimension
    assert len(dets[3].evidence) == 6                   # six answers
    repeated = evidence_breadth_value(dets[3])
    isolated = evidence_breadth_value(dets[4])
    # Six repeated answers earn more than one answer -- repetition is not
    # nothing -- but nowhere near the 0.56-0.67 a genuinely multi-dimension
    # cause earns. That ceiling is what stops volume buying rank.
    assert isolated < repeated < D("0.30")


def test_severity_still_beats_breadth_when_the_category_is_far_riskier():
    """The severity guard. Breadth holds 0.15 against category risk's 0.40, so
    a genuinely severe narrow finding must still lead a broad mild one.

    The gap has to be real for this to mean anything: one Red in a category
    probed once (risk 0.33) against four Ambers each alone in their own
    category (risk 0.17 apiece). scripts/qa/breadth_sensitivity.py runs the
    same shape at every candidate weight and severity wins throughout.
    """
    questions = [q(701, 7, "Financial Management"), q(702, 7, "Financial Management")] + [
        q(800 + i, 8, c) for i, c in enumerate(
            ["Product", "Go-To-Market", "Team & Leadership", "Business Planning"],
            start=1)]
    answers = [ans(70, 701, ScoreLabel.RED), ans(71, 702, ScoreLabel.RED)] + [
        ans(80 + i, 800 + i, ScoreLabel.AMBER) for i in range(1, 5)]
    scored, dets = _rank(questions, answers)
    assert dets[8].independent_signal_count > dets[7].independent_signal_count
    assert scored[7].rank < scored[8].rank, "breadth overturned a far riskier finding"


def test_the_industry_factor_is_no_longer_carrying_budget():
    """It could never contribute: root_cause_weights has only stage_weight, so
    an industry prior cannot be read for any cause. Holding 0.15 of the budget
    for it was the reason there was nothing left for breadth."""
    assert ACTIVE_WEIGHTS.industry_probability == D("0")
    assert ACTIVE_WEIGHTS.evidence_breadth == D("0.15")
    total = (ACTIVE_WEIGHTS.category_risk + ACTIVE_WEIGHTS.confirmation_status
             + ACTIVE_WEIGHTS.stage_probability
             + ACTIVE_WEIGHTS.industry_probability
             + ACTIVE_WEIGHTS.evidence_breadth)
    assert total == D("1.00")
