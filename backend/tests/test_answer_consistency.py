"""Answer-consistency detector + its entry into the confidence score. Hermetic."""

import asyncio
from collections import namedtuple
from decimal import Decimal
from types import SimpleNamespace

from app.api.v1.reasoning.engines.confidence import WeightedConfidenceModel
from app.api.v1.reasoning.engines.consistency import ConsistencyResult, LLMConsistencyDetector
from app.api.v1.reasoning.schemas import CategoryRisk
from app.services.llm.base import LLMProviderError, LLMResponse, LLMUsage

D = Decimal
QA = namedtuple("QA", "question_id answer_text")
Q = namedtuple("Q", "question_id question_text")


class _P:
    name = "fake"
    def __init__(self, text=None, err=None): self._t, self._e = text, err
    async def generate(self, req):
        if self._e: raise self._e
        return LLMResponse(text=self._t, model="claude-sonnet-5", provider="fake",
                           usage=LLMUsage(input_tokens=5, output_tokens=5))


def _answers(n): return [QA(i, f"answer {i}") for i in range(n)]
def _questions(n): return {i: Q(i, f"q{i}") for i in range(n)}


# --- detector ---------------------------------------------------------------

def test_detector_parses_score_and_contradictions():
    det = LLMConsistencyDetector(_P(text='{"consistency":0.4,"contradictions":["recurring revenue vs never sold"]}'))
    r = asyncio.run(det.assess(_answers(3), _questions(3)))
    assert r.available and r.score == D("0.4") and len(r.contradictions) == 1


def test_detector_fails_to_unavailable_not_one():
    det = LLMConsistencyDetector(_P(err=LLMProviderError("boom")))
    r = asyncio.run(det.assess(_answers(3), _questions(3)))
    assert r.available is False and r.score is None  # NEVER a false 1.0


def test_detector_unparseable_is_unavailable():
    det = LLMConsistencyDetector(_P(text="the model rambled with no json"))
    r = asyncio.run(det.assess(_answers(3), _questions(3)))
    assert r.available is False and r.score is None


def test_detector_trivially_consistent_below_two_answers():
    det = LLMConsistencyDetector(_P(text="unused -- no LLM call for <2"))
    r = asyncio.run(det.assess(_answers(1), _questions(1)))
    assert r.available and r.score == D("1")


# --- entry into the confidence score ----------------------------------------

class _Repo:
    def get_in_scope_question_count(self, stage_id): return 40
    def get_reliability_factor(self, distress_score): return D("0.95")
    def get_stage_order(self, stage_id): return stage_id  # coherent (founder==detected)


def _ctx():
    cfg = SimpleNamespace(
        confirmation_multipliers=SimpleNamespace(confirmed=D("1.5"), unconfirmed=D("1.0"), not_tested=D("0.5")),
        distress=SimpleNamespace(high_distress_score=D("36")),
    )
    return SimpleNamespace(config=cfg, founder=SimpleNamespace(stage_id=1), stage_id=1,
                           session=SimpleNamespace(session_distress_score=D("15")))


def _diag():
    return SimpleNamespace(
        category_risks=[CategoryRisk(category="Cat", raw_score=D("0.5"), max_score=D("1"),
                                     normalised_risk=D("0.5"), is_flagged=True)],
        distress_mode=False,
    )


def _inputs(consistency="__unset__"):
    m = WeightedConfidenceModel(_Repo())
    kw = {} if consistency == "__unset__" else {"consistency": consistency}
    return m.build_confidence_inputs(diagnosis=_diag(), scored=[], questions_answered=10, context=_ctx(), **kw)


def test_confidence_uses_consistency_when_available():
    inp = _inputs(ConsistencyResult(available=True, score=D("0.4")))
    assert inp.consistency_available is True and inp.consistency_score == D("0.4")


def test_confidence_excludes_consistency_when_unavailable():
    inp = _inputs(ConsistencyResult.unavailable())
    assert inp.consistency_available is False and inp.consistency_score is None


def test_confidence_defaults_unavailable_without_detector():
    inp = _inputs()  # no consistency passed -- prior four-input path unchanged
    assert inp.consistency_available is False and inp.consistency_score is None
