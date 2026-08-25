"""Stage inference fills a NULL stage; it never overrides a declared one.

founders.stage_id has no server default and its only writer is
PATCH /profile/business-info, which only guided onboarding calls. Measured on
the live founders table: NULL for 27 of 45 founders. An unknown stage is not
neutral -- DefaultInterventionRelevance reads `stage_id is None` as "every
intervention is relevant", which is how a founder with a shipped MVP and three
running pilots was told to write a hypothesis document "before writing any
code".

These pin the three things that make this safe to switch on: a declared stage
is never touched, every failure path lands back on exactly today's answer, and
the model chooses from the seeded catalogue rather than inventing a stage.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.reasoning.engines.stage_detection_llm import LLMStageInferenceStrategy
from app.api.v1.reasoning.schemas import StageDetection
from app.services.llm.base import LLMError


class _Provider:
    """Returns a canned payload, or raises. Records whether it was called."""

    def __init__(self, payload=None, raises=None):
        self._payload = payload
        self._raises = raises
        self.calls = 0

    async def generate(self, request):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        text = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)
        return SimpleNamespace(text=text)


class _Repo:
    """Only what the strategy touches."""

    def __init__(self, answers=("We have three pilots running but nobody pays yet.",)):
        self._answers = list(answers)

    def get_founder_stages(self):
        return [
            SimpleNamespace(stage_id=1, stage_name="Ideation", stage_order=1,
                            min_criteria={"has_idea": True, "has_prototype": False}),
            SimpleNamespace(stage_id=3, stage_name="Prototype / MVP", stage_order=3,
                            min_criteria={"has_mvp": True, "active_customers_min": 1}),
            SimpleNamespace(stage_id=5, stage_name="Growth / Scaling", stage_order=5,
                            min_criteria={"arr_min": 100000}),
        ]

    def get_answers_for_session(self, session_id):
        return [SimpleNamespace(answer_text=t) for t in self._answers]


class _DeclaredStub:
    """Stands in for DeclaredStageStrategy."""

    def __init__(self, stage_id=None):
        self._stage_id = stage_id

    def detect(self, classifications, questions, context, repository):
        return StageDetection(
            stage_id=self._stage_id,
            stage_name="Declared name" if self._stage_id else None,
            probability=Decimal("1") if self._stage_id else Decimal("0"),
            confidence=Decimal("1") if self._stage_id else Decimal("0"),
            evidence=("declared",),
        )


def _context():
    return SimpleNamespace(
        session=SimpleNamespace(session_id=99, founder_stage_id=None),
        founder=SimpleNamespace(founder_id=7, stage_id=None),
    )


def _detect(provider, *, declared_stage_id=None, repo=None):
    strategy = LLMStageInferenceStrategy(provider, declared=_DeclaredStub(declared_stage_id))
    return strategy.detect([], {}, _context(), repo or _Repo())


# --- a declared stage wins outright ------------------------------------------

def test_a_declared_stage_is_never_inferred_over():
    """Inference fills a hole; it does not second-guess the founder."""
    provider = _Provider({"stage_name": "Growth / Scaling", "confidence": 0.99})
    result = _detect(provider, declared_stage_id=4)

    assert result.stage_id == 4
    assert provider.calls == 0, "the model must not even be asked"


# --- the inference itself ------------------------------------------------------

def test_a_null_stage_is_inferred_from_the_answers():
    """THE FIX."""
    provider = _Provider({
        "stage_name": "Prototype / MVP",
        "confidence": 0.8,
        "evidence": ["three pilots running, nobody pays yet"],
    })
    result = _detect(provider)

    assert result.stage_id == 3
    assert result.stage_name == "Prototype / MVP"
    assert provider.calls == 1


def test_an_inferred_stage_is_distinguishable_from_a_declared_one():
    """probability is how a downstream consumer tells a read from a statement.
    DeclaredStageStrategy reserves 1 for a stage the founder actually gave."""
    provider = _Provider({"stage_name": "Prototype / MVP", "confidence": 0.8})
    result = _detect(provider)

    assert result.probability == Decimal("0.8000")
    assert result.probability < Decimal("1")
    assert any("inferred" in line.lower() for line in result.evidence)


def test_the_stage_name_match_is_case_and_space_insensitive():
    provider = _Provider({"stage_name": "  prototype / mvp  ", "confidence": 0.9})
    assert _detect(provider).stage_id == 3


# --- every failure lands on today's behaviour ---------------------------------

@pytest.mark.parametrize("provider", [
    _Provider(raises=LLMError("provider down")),
    _Provider(raises=asyncio.TimeoutError()),
    _Provider("not json at all"),
    _Provider({"confidence": 0.9}),                                  # no stage_name
    _Provider({"stage_name": "Series Q Unicorn", "confidence": 0.9}),  # not in catalogue
    _Provider({"stage_name": "Prototype / MVP", "confidence": "banana"}),
    _Provider({"stage_name": "Prototype / MVP"}),                     # no confidence
])
def test_any_failure_leaves_the_stage_exactly_as_it_is_today(provider):
    result = _detect(provider)
    assert result.stage_id is None
    assert result.evidence == ("declared",), "must be the declared strategy's own answer"


def test_a_stage_below_the_confidence_floor_is_not_used():
    """A wrong stage actively mis-filters recommendations, which is the bug this
    exists to fix. Unknown is the safer of the two wrong answers."""
    provider = _Provider({"stage_name": "Growth / Scaling", "confidence": 0.4})
    assert _detect(provider).stage_id is None


def test_a_founder_with_no_answers_yet_is_not_guessed_at():
    provider = _Provider({"stage_name": "Growth / Scaling", "confidence": 0.99})
    result = _detect(provider, repo=_Repo(answers=()))

    assert result.stage_id is None
    assert provider.calls == 0, "nothing to read; do not spend a call"


def test_an_empty_catalogue_does_not_invent_a_stage():
    class _NoStages(_Repo):
        def get_founder_stages(self):
            return []

    provider = _Provider({"stage_name": "Prototype / MVP", "confidence": 0.9})
    result = _detect(provider, repo=_NoStages())

    assert result.stage_id is None
    assert provider.calls == 0


# --- the prompt carries the seeded rubric --------------------------------------

def test_the_prompt_carries_the_seeded_min_criteria():
    """min_criteria is the business definition of each stage. If it does not
    reach the prompt, the model judges against its own idea of a stage."""
    captured = {}

    class _Capturing(_Provider):
        async def generate(self, request):
            captured["content"] = request.messages[-1].content
            return await super().generate(request)

    provider = _Capturing({"stage_name": "Prototype / MVP", "confidence": 0.9})
    _detect(provider)

    content = captured["content"]
    assert "Prototype / MVP" in content
    assert "has_mvp=True" in content
    assert "active_customers_min=1" in content
    assert "three pilots running" in content, "the founder's words must reach the prompt"


def test_confidence_is_clamped_into_range():
    provider = _Provider({"stage_name": "Prototype / MVP", "confidence": 4.2})
    assert _detect(provider).confidence == Decimal("1.0000")
