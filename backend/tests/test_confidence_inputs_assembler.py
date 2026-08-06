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
    def __init__(self, *, in_scope=40, reliability=D("0.95"), stage_orders=None):
        self._in_scope = in_scope
        self._reliability = reliability
        self._stage_orders = stage_orders or {}

    def get_in_scope_question_count(self, stage_id):
        return self._in_scope

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


def test_distress_override_by_session_score_zeroes_reliability():
    repo = FakeRepo(reliability=D("0.95"))
    model = WeightedConfidenceModel(repo)
    diagnosis = make_diagnosis(category_risks=[make_category("0.6", True)])
    ctx = make_context(distress_score=D("40"))  # >= high_distress 36
    got = model.build_confidence_inputs(
        diagnosis=diagnosis, scored=[make_scored(1, "1")],
        questions_answered=20, context=ctx,
    )
    assert got.distress_override is True
    # Distress says "discount this entirely" with an explicit zero. It used to
    # say it with None, which the strategy also produced for an unresolvable
    # lookup -- so a config miss was indistinguishable from maximum distress
    # and silently zeroed a healthy score.
    assert got.reliability_factor == D("0")


def test_distress_override_by_diagnosis_flag():
    model = WeightedConfidenceModel(FakeRepo())
    diagnosis = make_diagnosis(category_risks=[make_category("0.6", True)], distress_mode=True)
    ctx = make_context(distress_score=D("5"))  # low score, but flag set
    got = model.build_confidence_inputs(
        diagnosis=diagnosis, scored=[make_scored(1, "1")],
        questions_answered=20, context=ctx,
    )
    assert got.distress_override is True
    # Distress says "discount this entirely" with an explicit zero. It used to
    # say it with None, which the strategy also produced for an unresolvable
    # lookup -- so a config miss was indistinguishable from maximum distress
    # and silently zeroed a healthy score.
    assert got.reliability_factor == D("0")


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
