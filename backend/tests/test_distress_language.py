"""Distress language detector (#11) + fail-closed mapping. Hermetic.

Encodes the safety contract: a single State-D signal triggers the override
immediately; the cumulative threshold fires independently; and a detector ERROR
fails CLOSED to high distress (never a clean 'no signals')."""

import asyncio
from decimal import Decimal

from app.api.v1.reasoning.engines.distress_language import (
    DistressLanguageResult,
    LLMDistressDetector,
    build_distress_assessment,
)
from app.services.llm.base import LLMProviderError, LLMResponse, LLMUsage

D = Decimal
HIGH = D("36")

# Test catalogue: A/B/C signals + one State-D crisis signal (16). Weights chosen
# so the two A signals alone can exceed 36 (to prove the cumulative branch).
CATALOG = [
    {"signal_id": 1, "state_code": "A", "signal_type": "t", "observable_indicator": "i", "example_phrases": "p", "score_per_instance": 20},
    {"signal_id": 2, "state_code": "A", "signal_type": "t", "observable_indicator": "i", "example_phrases": "p", "score_per_instance": 20},
    {"signal_id": 8, "state_code": "B", "signal_type": "t", "observable_indicator": "i", "example_phrases": "p", "score_per_instance": 3},
    {"signal_id": 16, "state_code": "D", "signal_type": "t", "observable_indicator": "i", "example_phrases": "p", "score_per_instance": 5},
]
WEIGHTS = {s["signal_id"]: D(s["score_per_instance"]) for s in CATALOG}


class _Scorer:
    def session_distress_score(self, occ):
        return sum((WEIGHTS.get(int(k), D(0)) * int(v) for k, v in occ.items()), D(0))


def _lookup(code):
    return f"guidance for {code}"


class _P:
    name = "fake"
    def __init__(self, text=None, err=None): self._t, self._e = text, err
    async def generate(self, req):
        if self._e: raise self._e
        return LLMResponse(text=self._t, model="claude-sonnet-5", provider="fake",
                           usage=LLMUsage(input_tokens=5, output_tokens=5))


def _map(result):
    return build_distress_assessment(result, CATALOG, scorer=_Scorer(),
                                     high_distress_score=HIGH, empathy_lookup=_lookup)


# --- detector ---------------------------------------------------------------

def test_detector_parses_present_ids_and_validates():
    det = LLMDistressDetector(_P(text='{"present_signal_ids":[16, 1, 999]}'), CATALOG)
    r = asyncio.run(det.detect(["I can't do this anymore"]))
    assert r.status == "measured" and r.present_ids == frozenset({16, 1})  # 999 dropped


def test_detector_fails_closed_on_provider_error():
    det = LLMDistressDetector(_P(err=LLMProviderError("boom")), CATALOG)
    r = asyncio.run(det.detect(["some text"]))
    assert r.status == "error"  # NOT measured-empty


def test_detector_fails_closed_on_unparseable():
    det = LLMDistressDetector(_P(text="the model rambled, no json"), CATALOG)
    r = asyncio.run(det.detect(["some text"]))
    assert r.status == "error"


def test_detector_empty_text_is_measured_empty():
    det = LLMDistressDetector(_P(text="unused"), CATALOG)
    r = asyncio.run(det.detect(["", "   "]))
    assert r.status == "measured" and r.present_ids == frozenset()


# --- fail-closed mapping (the safety contract) ------------------------------

def test_error_fails_closed_to_high_distress():
    a = _map(DistressLanguageResult(status="error", error="boom"))
    assert a.is_high_distress is True and a.distress_override is True
    assert a.session_distress_score == HIGH            # floored, not clean 0
    assert a.detector_status == "error"                # distinguishable from measured
    assert a.empathy_protocol_code == "PROMPT-EMPATHY-DISTRESS"


def test_single_state_d_triggers_override_below_threshold():
    # Only signal 16 (State D, weight 5) -> cumulative 5 < 36, but STILL override.
    a = _map(DistressLanguageResult(status="measured", present_ids=frozenset({16})))
    assert a.is_high_distress is True and a.distress_override is True
    assert a.session_distress_score == HIGH            # floored to threshold
    assert a.distress_red_count == 1 and a.detector_status == "measured"


def test_cumulative_threshold_fires_without_state_d():
    # Two State-A signals (20+20=40 >= 36), no State D -> high distress independently.
    a = _map(DistressLanguageResult(status="measured", present_ids=frozenset({1, 2})))
    assert a.is_high_distress is True and a.distress_override is True
    assert a.session_distress_score == D("40") and a.distress_red_count == 0


def test_clean_measured_is_not_distress():
    a = _map(DistressLanguageResult(status="measured", present_ids=frozenset()))
    assert a.is_high_distress is False and a.distress_override is False
    assert a.session_distress_score == D("0") and a.empathy_protocol_code is None
    assert a.detector_status == "measured"
