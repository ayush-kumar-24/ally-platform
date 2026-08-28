"""Unit tests for the confidence-inputs assembler on WeightedConfidenceModel.

The assembler resolves the five evidence signals, the reliability modifier and the
hard-rule facts from the pipeline outputs plus a handful of DB reads. Here the DB
reads are supplied by a fake repository, so the tests stay hermetic while still
exercising the real signal maths (confirmation ratio, separation, coverage, stage
distance, distress detection).
"""

from decimal import Decimal
from types import SimpleNamespace

from app.core.config import settings

import pytest

from app.api.v1.reasoning.config import ConfirmationMultipliers
from app.api.v1.reasoning.engines.confidence import WeightedConfidenceModel
from app.api.v1.reasoning.schemas import CategoryRisk, ScoredRootCause
from app.models.enums import ConfirmationStatus

D = Decimal
MULTIPLIERS = ConfirmationMultipliers(confirmed=D("1.5"), unconfirmed=D("1.0"), not_tested=D("0.5"))


class FakeRepo:
    def __init__(self, *, in_scope=40, reliability=D("0.95"), stage_orders=None,
                 question_budget=None, budget_raises=False):
        self._in_scope = in_scope
        self._reliability = reliability
        self._stage_orders = stage_orders or {}
        self._question_budget = question_budget
        self._budget_raises = budget_raises

    def get_in_scope_question_count(self, stage_id):
        return self._in_scope

    def get_question_budget(self, stage_id):
        # None is the shipped state: the column exists and no stage has a number
        # yet, so every caller falls back to MAX_DIAGNOSIS_QUESTIONS.
        if self._budget_raises:
            raise RuntimeError("budget lookup exploded")
        return self._question_budget

    def get_reliability_factor(self, distress_score):
        return self._reliability

    def get_stage_order(self, stage_id):
        return self._stage_orders.get(stage_id)


def make_scored(rank, score, status=ConfirmationStatus.CONFIRMED, top=True) -> ScoredRootCause:
    return ScoredRootCause(
        root_cause_id=rank,
        category_risk_score=D("0.5"),
        confirmation_status=status,
        confirmation_multiplier=D("1.0"),
        stage_probability=D("0.5"),
        industry_probability=D("0"),
        final_weighted_score=D(str(score)),
        rank=rank,
        is_top_finding=top,
    )


def make_category(risk, flagged) -> CategoryRisk:
    return CategoryRisk(
        category="Cat",
        raw_score=D(str(risk)),
        max_score=D("1"),
        normalised_risk=D(str(risk)),
        is_flagged=flagged,
    )


def make_context(*, stage_id=1, detected_stage=1, distress_score=D("15"), stage_orders=None):
    config = SimpleNamespace(
        confirmation_multipliers=MULTIPLIERS,
        distress=SimpleNamespace(high_distress_score=D("36")),
    )
    return SimpleNamespace(
        config=config,
        founder=SimpleNamespace(stage_id=stage_id),
        stage_id=detected_stage,
        session=SimpleNamespace(session_distress_score=distress_score),
    )


def make_diagnosis(*, category_risks, distress_mode=False):
    return SimpleNamespace(category_risks=category_risks, distress_mode=distress_mode)


# --- Confirmation ratio ----------------------------------------------------


@pytest.mark.parametrize(
    "statuses, expected",
    [
        ([ConfirmationStatus.CONFIRMED], D("1.0000")),          # (1.5-0.5)/1.0
        ([ConfirmationStatus.UNCONFIRMED], D("0.5000")),        # (1.0-0.5)/1.0
        ([ConfirmationStatus.NOT_TESTED], D("0.0000")),         # (0.5-0.5)/1.0
        ([ConfirmationStatus.CONFIRMED, ConfirmationStatus.NOT_TESTED], D("0.5000")),
    ],
)
def test_confirmation_ratio(statuses, expected):
    model = WeightedConfidenceModel(FakeRepo())
    top = [make_scored(i + 1, "1", s) for i, s in enumerate(statuses)]
    assert model._confirmation_ratio(top, MULTIPLIERS) == expected


def test_confirmation_ratio_empty_is_zero():
    model = WeightedConfidenceModel(FakeRepo())
    assert model._confirmation_ratio([], MULTIPLIERS) == D("0")


# --- Separation ------------------------------------------------------------


def test_separation_gap():
    model = WeightedConfidenceModel(FakeRepo())
    scored = [make_scored(1, "1.0"), make_scored(2, "0.5")]
    assert model._separation(scored) == D("0.5000")  # (1-0.5)/1


def test_separation_tie_is_zero():
    model = WeightedConfidenceModel(FakeRepo())
    scored = [make_scored(1, "0.8"), make_scored(2, "0.8")]
    assert model._separation(scored) == D("0")


def test_separation_top_zero_is_zero():
    model = WeightedConfidenceModel(FakeRepo())
    scored = [make_scored(1, "0"), make_scored(2, "0")]
    assert model._separation(scored) == D("0")


def test_separation_single_cause_is_fully_separated():
    model = WeightedConfidenceModel(FakeRepo())
    assert model._separation([make_scored(1, "0.9")]) == D("1.0000")  # (0.9-0)/0.9


def test_separation_empty_is_zero():
    model = WeightedConfidenceModel(FakeRepo())
    assert model._separation([]) == D("0")


# --- Stage distance --------------------------------------------------------


def test_stages_away_uses_stage_order():
    repo = FakeRepo(stage_orders={1: 1, 5: 5})
    model = WeightedConfidenceModel(repo)
    ctx = make_context(stage_id=1, detected_stage=5)
    assert model._stages_away(ctx) == 4


def test_stages_away_none_when_stage_unknown():
    repo = FakeRepo(stage_orders={1: 1})  # detected stage 5 missing
    model = WeightedConfidenceModel(repo)
    ctx = make_context(stage_id=1, detected_stage=5)
    assert model._stages_away(ctx) is None


# --- Full assembly ---------------------------------------------------------


def test_build_inputs_happy_path():
    repo = FakeRepo(in_scope=40, reliability=D("0.95"), stage_orders={1: 1})
    model = WeightedConfidenceModel(repo)
    diagnosis = make_diagnosis(
        category_risks=[make_category("0.6", True), make_category("0.2", False)]
    )
    scored = [
        make_scored(1, "1.0", ConfirmationStatus.CONFIRMED),
        make_scored(2, "0.5", ConfirmationStatus.NOT_TESTED, top=False),
    ]
    ctx = make_context(stage_id=1, detected_stage=1, distress_score=D("15"))

    got = model.build_confidence_inputs(
        diagnosis=diagnosis, scored=scored, questions_answered=20, context=ctx
    )

    assert got.category_signal == D("0.6")            # max normalised risk
    # Coverage is answered / MAX_DIAGNOSIS_QUESTIONS, not answered / the whole
    # in-scope bank. Dividing by the bank made the score's own 80 threshold
    # unreachable once diagnoses were capped at 30 questions: 30/569 on a
    # 25%-weight input capped the achievable total at 76.
    assert got.evidence_coverage == D(20) / D(settings.MAX_DIAGNOSIS_QUESTIONS)
    # Contradiction detector not implemented -> consistency marked UNAVAILABLE
    # (not defaulted to a numeric score); the strategy excludes + renormalises it.
    assert got.consistency_available is False
    assert got.consistency_score is None
    assert got.confirmation_ratio == D("1.0000")      # only top finding is CONFIRMED
    assert got.separation == D("0.5000")              # (1.0-0.5)/1.0
    assert got.reliability_factor == D("0.95")
    assert got.questions_answered == 20
    assert got.flagged_category_count == 1
    assert got.any_category_flagged is True
    assert got.distress_override is False
    assert got.stages_away == 0


def test_coverage_capped_at_one():
    repo = FakeRepo(in_scope=10)
    model = WeightedConfidenceModel(repo)
    diagnosis = make_diagnosis(category_risks=[make_category("0.4", True)])
    got = model.build_confidence_inputs(
        diagnosis=diagnosis, scored=[make_scored(1, "1")],
        questions_answered=50, context=make_context(),  # 50/10 -> capped 1.0
    )
    assert got.evidence_coverage == D("1")


def test_coverage_no_longer_depends_on_the_in_scope_bank():
    """An empty question bank used to zero coverage outright. Coverage now
    measures progress through the diagnosis budget, which exists regardless of
    how many questions the founder's stage happens to have."""
    repo = FakeRepo(in_scope=0)
    model = WeightedConfidenceModel(repo)
    diagnosis = make_diagnosis(category_risks=[make_category("0.4", True)])
    got = model.build_confidence_inputs(
        diagnosis=diagnosis, scored=[make_scored(1, "1")],
        questions_answered=20, context=make_context(),
    )
    assert got.evidence_coverage == D(20) / D(settings.MAX_DIAGNOSIS_QUESTIONS)


def test_coverage_caps_at_one_when_the_budget_is_spent():
    repo = FakeRepo(in_scope=0)
    model = WeightedConfidenceModel(repo)
    diagnosis = make_diagnosis(category_risks=[make_category("0.4", True)])
    got = model.build_confidence_inputs(
        diagnosis=diagnosis, scored=[make_scored(1, "1")],
        questions_answered=settings.MAX_DIAGNOSIS_QUESTIONS + 5,
        context=make_context(),
    )
    assert got.evidence_coverage == D("1")


def test_category_signal_zero_when_no_categories():
    model = WeightedConfidenceModel(FakeRepo())
    got = model.build_confidence_inputs(
        diagnosis=make_diagnosis(category_risks=[]),
        scored=[make_scored(1, "1")], questions_answered=20, context=make_context(),
    )
    assert got.category_signal == D("0")
    assert got.any_category_flagged is False


def test_distress_override_by_session_score_leaves_reliability_alone():
    repo = FakeRepo(reliability=D("0.95"))
    model = WeightedConfidenceModel(repo)
    diagnosis = make_diagnosis(category_risks=[make_category("0.6", True)])
    ctx = make_context(distress_score=D("40"))  # >= high_distress 36
    got = model.build_confidence_inputs(
        diagnosis=diagnosis, scored=[make_scored(1, "1")],
        questions_answered=20, context=ctx,
    )
    assert got.distress_override is True
    # Distress no longer discounts reliability at all (product decision,
    # 2026-08-20). The 0.70 discount was half of a double penalty -- combined
    # with the now-removed hard cap it turned an 84% evidence base into a
    # reported 59. Reliability now comes purely from the configured lookup for
    # the measured distress score, so `distress_override` is still reported
    # (routing and the report still use it) without rewriting the number.
    assert got.reliability_factor == D("0.95")   # the repo's configured value
    assert got.reliability_factor > D("0")


def test_distress_override_by_diagnosis_flag():
    model = WeightedConfidenceModel(FakeRepo())
    diagnosis = make_diagnosis(category_risks=[make_category("0.6", True)], distress_mode=True)
    ctx = make_context(distress_score=D("5"))  # low score, but flag set
    got = model.build_confidence_inputs(
        diagnosis=diagnosis, scored=[make_scored(1, "1")],
        questions_answered=20, context=ctx,
    )
    assert got.distress_override is True
    # Distress no longer discounts reliability at all (product decision,
    # 2026-08-20). The 0.70 discount was half of a double penalty -- combined
    # with the now-removed hard cap it turned an 84% evidence base into a
    # reported 59. Reliability now comes purely from the configured lookup for
    # the measured distress score, so `distress_override` is still reported
    # (routing and the report still use it) without rewriting the number.
    assert got.reliability_factor > D("0")
    assert got.reliability_factor > D("0")


def test_flagged_category_count():
    model = WeightedConfidenceModel(FakeRepo())
    diagnosis = make_diagnosis(category_risks=[
        make_category("0.6", True), make_category("0.5", True),
        make_category("0.4", True), make_category("0.1", False),
    ])
    got = model.build_confidence_inputs(
        diagnosis=diagnosis, scored=[make_scored(1, "1")],
        questions_answered=20, context=make_context(),
    )
    assert got.flagged_category_count == 3
    assert got.any_category_flagged is True


# --- The stage's own budget ------------------------------------------------
# Coverage is answered / budget, and the budget is the STAGE's. A global 30 for
# everyone is the same defect the 569-question bank was, one scale down: a
# founder for whom twelve questions is enough scores 0.40 on a 25%-weight
# signal, cannot reach the report threshold, and so never finishes early.


def _coverage(repo, answered):
    got = WeightedConfidenceModel(repo).build_confidence_inputs(
        diagnosis=make_diagnosis(category_risks=[make_category("0.5", True)]),
        scored=[make_scored(1, "1")],
        questions_answered=answered,
        context=make_context(),
    )
    return got.evidence_coverage


def test_an_unset_stage_budget_falls_back_to_the_global_constant():
    """The shipped state: the column exists and no stage has a number yet, so
    nothing about any diagnosis changes until one is set."""
    assert _coverage(FakeRepo(question_budget=None), 20) == D(20) / D(
        settings.MAX_DIAGNOSIS_QUESTIONS
    )


def test_a_stage_budget_replaces_the_global_constant():
    assert _coverage(FakeRepo(question_budget=12), 6) == D("0.5")


def test_a_short_stage_reaches_full_coverage_where_the_global_budget_would_not():
    """The whole point. Twelve answers is 40% of 30 but 100% of 12 -- and 40%
    on a quarter of the score is what kept an idea-stage founder below the
    report threshold no matter how well they answered."""
    assert _coverage(FakeRepo(question_budget=12), 12) == D("1")
    assert _coverage(FakeRepo(question_budget=None), 12) < D("1")


def test_coverage_never_exceeds_one_even_past_the_stage_budget():
    assert _coverage(FakeRepo(question_budget=12), 40) == D("1")


def test_a_zero_budget_does_not_divide_by_zero():
    """A CHECK constraint refuses a 0 at the database. This refuses one that
    arrives anyway -- a ZeroDivisionError here would take out the confidence
    score and the whole report with it."""
    assert _coverage(FakeRepo(question_budget=0), 20) == D(20) / D(
        settings.MAX_DIAGNOSIS_QUESTIONS
    )


def test_an_unreadable_budget_falls_back_instead_of_failing():
    """Confidence must never fail on an optional lookup: losing the budget is a
    reason to use the default, not to lose the founder's diagnosis."""
    assert _coverage(FakeRepo(budget_raises=True), 20) == D(20) / D(
        settings.MAX_DIAGNOSIS_QUESTIONS
    )
