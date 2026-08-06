"""The two LLM seams: archetype assignment, and recommendations for root causes
the curated intervention library does not cover.

Both are additive by design and both must stay that way. The archetype LLM may
only choose from the seeded catalogue, and the recommendation fallback may only
fill gaps -- never displace a reviewed intervention, never change ranking. These
tests pin those boundaries, because both would degrade quietly if they slipped:
a generated recommendation reads exactly like a curated one.
"""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.reasoning.engines.archetype import ArchetypeMatch
from app.api.v1.reasoning.engines.archetype_llm import LLMArchetypeAssigner
from app.api.v1.reasoning.engines.recommendation_llm import LLMRecommendationFallback
from app.services.llm.base import LLMError, LLMResponse


class FakeProvider:
    """Returns canned text, or raises. Records how many times it was asked."""

    def __init__(self, text: str = "{}", raises: Exception | None = None):
        self.text = text
        self.raises = raises
        self.calls = 0

    async def generate(self, request):
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        return LLMResponse(text=self.text, model="fake", provider="fake")


def _archetype_row(aid=2, code="ARCH-002", name="Operator"):
    return SimpleNamespace(
        archetype_id=aid, archetype_code=code, archetype_name=name,
        assignment_criteria='Ships relentlessly. Says "I just do it myself".',
        key_traits={"decision_style": "fast", "stress_pattern": "absorbs",
                    "core_motivation": "shipping"},
    )


class FakeArchetypeEngine:
    """Stands in for the deterministic engine and its repository."""

    def __init__(self, rows=None, result=None):
        self.repository = SimpleNamespace(get_archetypes=lambda: rows or [_archetype_row()])
        self._result = result
        self.called = False

    def assign(self, answer_texts):
        self.called = True
        return self._result


# --- archetype --------------------------------------------------------------


def test_llm_assignment_wins_and_is_marked_as_llm():
    provider = FakeProvider(json.dumps(
        {"archetype_code": "ARCH-002", "confidence": 0.82,
         "evidence": ["I just do it myself"]}))
    fallback = FakeArchetypeEngine()
    match = LLMArchetypeAssigner(provider, fallback=fallback).assign(["I just do it myself"])

    assert match.code == "ARCH-002" and match.name == "Operator"
    assert match.assigned_by == "llm"
    assert match.is_confident is True
    assert fallback.called is False, "the deterministic engine ran despite a good LLM reply"


def test_a_low_confidence_assignment_is_still_returned_but_not_confident():
    """A weak read is information; an absent one is not. The report layer decides
    how to hedge, so the score has to reach it."""
    provider = FakeProvider(json.dumps({"archetype_code": "ARCH-002", "confidence": 0.2}))
    match = LLMArchetypeAssigner(provider, fallback=FakeArchetypeEngine()).assign(["hmm"])
    assert match is not None and match.is_confident is False


def test_an_archetype_outside_the_catalogue_is_refused():
    """The model chooses; it does not invent. The archetypes table stays the only
    source of what archetypes exist."""
    determinstic = ArchetypeMatch(2, "ARCH-002", "Operator", None, Decimal("0.4"), (), False)
    fallback = FakeArchetypeEngine(result=determinstic)
    provider = FakeProvider(json.dumps({"archetype_code": "ARCH-999", "confidence": 0.99}))

    match = LLMArchetypeAssigner(provider, fallback=fallback).assign(["text"])
    assert fallback.called is True
    assert match.assigned_by == "deterministic"


@pytest.mark.parametrize("bad", [LLMError("boom"), ValueError("nope")])
def test_provider_failure_falls_back_to_deterministic(bad):
    determinstic = ArchetypeMatch(2, "ARCH-002", "Operator", None, Decimal("0.4"), (), False)
    fallback = FakeArchetypeEngine(result=determinstic)
    match = LLMArchetypeAssigner(FakeProvider(raises=bad), fallback=fallback).assign(["t"])
    assert fallback.called is True and match.assigned_by == "deterministic"


def test_malformed_json_falls_back():
    fallback = FakeArchetypeEngine(result=None)
    assert LLMArchetypeAssigner(FakeProvider("not json"), fallback=fallback).assign(["t"]) is None
    assert fallback.called is True


def test_no_answers_is_not_a_failure():
    """Nothing to classify is not the same as the model failing -- the fallback
    must not be invoked, and no call should be made."""
    provider = FakeProvider()
    fallback = FakeArchetypeEngine()
    assert LLMArchetypeAssigner(provider, fallback=fallback).assign(["", "  "]) is None
    assert provider.calls == 0 and fallback.called is False


# --- recommendation gap filling --------------------------------------------


def _scored(rc_id=7, rank=1, score="0.71", confirmed=False):
    from app.models.enums import ConfirmationStatus
    return SimpleNamespace(
        root_cause_id=rc_id, rank=rank, final_weighted_score=Decimal(score),
        confirmation_status=(ConfirmationStatus.CONFIRMED if confirmed
                             else ConfirmationStatus.NOT_TESTED))


def test_an_unconfirmed_cause_gets_confirm_not_solve():
    """A generated recommendation must not tell a founder to act on a cause the
    diagnosis never confirmed -- same rule the deterministic engine applies."""
    from app.api.v1.reasoning.schemas import RecommendationType
    provider = FakeProvider(json.dumps({"rationale": "r", "next_actions": ["a"]}))
    r = LLMRecommendationFallback(provider).fill([("RC-900", _scored(), "C")])[0]
    assert r.recommendation_type == RecommendationType.CONFIRM

    r2 = LLMRecommendationFallback(provider).fill(
        [("RC-901", _scored(confirmed=True), "C")])[0]
    assert r2.recommendation_type == RecommendationType.SOLVE


def test_fills_an_uncovered_cause_and_marks_it_llm():
    provider = FakeProvider(json.dumps(
        {"rationale": "Because pricing was never tested.",
         "next_actions": ["Interview 5 churned users", "Draft two price points"]}))
    recs = LLMRecommendationFallback(provider).fill(
        [("RC-900", _scored(), "Pricing never validated")])

    assert len(recs) == 1
    r = recs[0]
    assert r.source == "llm"
    assert r.intervention_id == 0, "a generated recommendation must not claim a library row"
    assert r.next_actions and r.rationale


def test_ranking_comes_from_the_cause_not_the_model():
    """The model supplies wording, not standing."""
    provider = FakeProvider(json.dumps(
        {"rationale": "r", "next_actions": ["a"], "priority": 1, "confidence": 0.99}))
    r = LLMRecommendationFallback(provider).fill(
        [("RC-900", _scored(rank=4, score="0.33"), "Cause")])[0]

    assert r.priority == 4, "priority came from the model instead of the cause's rank"
    assert r.confidence == Decimal("0.33")


def test_a_reply_with_no_actions_is_discarded():
    """A recommendation the founder cannot act on is worse than none."""
    provider = FakeProvider(json.dumps({"rationale": "Sounds hard.", "next_actions": []}))
    assert LLMRecommendationFallback(provider).fill([("RC-900", _scored(), "C")]) == ()


def test_failure_leaves_the_cause_uncovered_rather_than_breaking():
    provider = FakeProvider(raises=LLMError("down"))
    assert LLMRecommendationFallback(provider).fill([("RC-900", _scored(), "C")]) == ()


def test_only_the_top_gaps_are_attempted():
    """A gap-filler, not a report: one slow call per uncovered cause would
    dominate the stage."""
    provider = FakeProvider(json.dumps({"rationale": "r", "next_actions": ["a"]}))
    gaps = [(f"RC-{i}", _scored(rc_id=i, rank=i), f"Cause {i}") for i in range(1, 11)]
    recs = LLMRecommendationFallback(provider, max_gaps=3).fill(gaps)
    assert len(recs) == 3 and provider.calls == 3
