"""LLM stage inference -- the seam stage_detection.py documented.

DeclaredStageStrategy reports `founders.stage_id` and nothing else. When that
column is NULL it returns stage_id=None, and everything downstream that keys
off the stage quietly loses its input:

  * DefaultInterventionRelevance treats `stage_id is None` as "every
    intervention is relevant", so an ideation-stage action can be recommended
    to a founder who shipped a year ago. Observed live on goxlally.ai: a
    founder with a working MVP and three running pilots was told to "create a
    simple problem-solution hypothesis document before writing any code".
  * The Confidence Model's stage-adjusted root-cause priors (get_stage_weights)
    have no stage to look up, so that whole signal is absent.

This is not an edge case. Measured on the live founders table: stage_id is
NULL for 27 of 45 founders -- 60%. The column has no server default and its
ONLY writer is PATCH /profile/business-info, which only guided onboarding
calls, so every founder who reaches the app another way has no stage forever.

Why the model and not a rule over founder_stages.min_criteria, which is what
stage_detection.py's docstring anticipated: the criteria compare against facts
this database does not hold for the founders who need this. Of those 27
stage-less founders, exactly ONE has current_revenue, team_size,
business_model, product_description or problem_statement set, and NONE have
business_reality_signals -- they are all written by the same skipped step. A
deterministic comparator would therefore no-op for 26 of the 27 founders it
exists to serve. What those founders do have is thirty diagnosis answers in
their own words, and "we have three pilots running but nobody is paying yet"
is a stage statement that only a reader can extract.

min_criteria is still the rubric -- it goes into the prompt, so the seeded
business definition of each stage is what the model judges against rather than
whatever it believes a "Series A company" is.

Boundaries, both of them ways this could go wrong quietly:

* The model CHOOSES, it never INVENTS. The prompt carries the eight seeded
  stages and the reply is matched back to a real stage_id; anything not in the
  catalogue is a failed call, not a new stage. founder_stages stays the only
  source of what stages exist.

* It never overrides a DECLARED stage. If the founder said where they are,
  that is the answer and no model call is made. Inference fills a hole; it
  does not second-guess the founder.

On any failure -- provider error, timeout, malformed JSON, unknown stage, no
answers yet -- this returns exactly what DeclaredStageStrategy returns today,
so the worst case is the behaviour that already ships.

`probability` separates an inferred stage from a declared one for every
downstream consumer: DeclaredStageStrategy returns 1 for a stage the founder
stated, and this returns the model's own confidence, which is by construction
lower. Evidence records that it was inferred and why, so a report tracing back
to a stage nobody declared can be told apart from one that was.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from app.api.v1.reasoning.engines.stage_detection import (
    DeclaredStageStrategy,
    StageDetectionStrategy,
)
from app.api.v1.reasoning.interfaces import ReasoningContext
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.schemas import AnswerClassification, StageDetection
from app.core.logger import logger
from app.models.diagnosis import Question
from app.services.llm.base import LLMError, LLMMessage, LLMRequest, LLMRole
from app.services.llm.text import run_sync

_QUANT = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")

_SYSTEM = (
    "You place a startup at exactly one lifecycle stage from a fixed list. "
    "Judge only what the founder's own words show about what EXISTS today -- "
    "whether something is built, whether anyone uses it, whether anyone pays, "
    "how big the team is. Ignore ambition, plans and intentions: a founder "
    "describing what they will launch next quarter is at the stage they are at "
    "now, not the one they are aiming for. Prefer the EARLIER stage when the "
    "evidence is genuinely ambiguous. If their words do not show enough to "
    "place them, say so rather than guessing. "
    "Reply with JSON only: "
    '{"stage_name": "<name from the list, or null>", "confidence": <0.0-1.0>, '
    '"evidence": ["<short quote or paraphrase from their words>", ...]}'
)

#: Below this the inference is not used at all. A stage is not like an
#: archetype, where a weak read still says something: a wrong stage actively
#: mis-filters the founder's recommendations, which is the bug this exists to
#: fix. Under this threshold, returning "unknown" (today's behaviour, which
#: fails open to every intervention) is the safer of the two wrong answers.
_MIN_CONFIDENCE = Decimal("0.5")


def _quant(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


class LLMStageInferenceStrategy:
    """Declared stage when there is one; otherwise infer it from the answers."""

    def __init__(
        self,
        provider,
        *,
        declared: StageDetectionStrategy | None = None,
        timeout_seconds: float = 20.0,
        temperature: float = 0.0,
        max_answers: int = 40,
    ):
        self.provider = provider
        self.declared = declared or DeclaredStageStrategy()
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        #: A long diagnosis would otherwise grow the prompt without bound.
        #: Unlike the archetype prompt, which keeps the HEAD because early
        #: answers carry the most self-description, stage evidence is factual
        #: and spread throughout -- the "how many paying customers" answer can
        #: land anywhere -- so this caps rather than favours either end.
        self.max_answers = max_answers

    # --- strategy ----------------------------------------------------------

    def detect(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
        repository: ReasoningRepository,
    ) -> StageDetection:
        declared = self.declared.detect(classifications, questions, context, repository)
        if declared.stage_id is not None:
            return declared

        inferred = self._infer(context, repository)
        return inferred if inferred is not None else declared

    # --- inference ---------------------------------------------------------

    def _infer(
        self, context: ReasoningContext, repository: ReasoningRepository
    ) -> StageDetection | None:
        """The inferred stage, or None to leave DeclaredStageStrategy's answer
        standing. Never raises -- every failure path is a None."""
        try:
            texts = self._answer_texts(context, repository)
            if not texts:
                return None  # nothing to read; not a failure

            catalogue, by_name = self._catalogue(repository)
            if not by_name:
                return None

            payload = self._ask(catalogue, texts)
            return self._to_detection(payload, by_name, context)
        except (LLMError, asyncio.TimeoutError, json.JSONDecodeError, ValueError,
                TypeError, KeyError, AttributeError) as exc:
            logger.warning(
                "Stage inference failed; leaving the stage undetected",
                extra={
                    "founder_id": getattr(context.founder, "founder_id", None),
                    "error": str(exc),
                },
            )
            return None

    def _answer_texts(
        self, context: ReasoningContext, repository: ReasoningRepository
    ) -> list[str]:
        session_id = getattr(context.session, "session_id", None)
        if session_id is None:
            return []
        answers = repository.get_answers_for_session(session_id)
        texts = [
            (getattr(a, "answer_text", None) or "").strip()
            for a in answers
        ]
        return [t for t in texts if t][: self.max_answers]

    def _catalogue(
        self, repository: ReasoningRepository
    ) -> tuple[str, dict[str, object]]:
        """The stages as prompt text, plus a name -> row lookup.

        Keyed by NAME rather than id: asking a model to return "Prototype /
        MVP" and matching that back is far more reliable than asking it to
        return the integer 3, and the id never has to leave the server.
        min_criteria is rendered verbatim so the seeded business definition of
        each stage is the rubric, not the model's own idea of one.
        """
        by_name: dict[str, object] = {}
        lines: list[str] = []
        for row in repository.get_founder_stages():
            name = (getattr(row, "stage_name", None) or "").strip()
            if not name or getattr(row, "stage_id", None) is None:
                continue
            by_name[name.casefold()] = row
            criteria = getattr(row, "min_criteria", None) or {}
            rendered = ", ".join(f"{k}={v}" for k, v in criteria.items()) or "no criteria recorded"
            lines.append(f"- {name}: {rendered}")
        return "\n".join(lines), by_name

    def _ask(self, catalogue: str, texts: Sequence[str]) -> dict:
        joined = "\n".join(f"- {t}" for t in texts)
        request = LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM),
                LLMMessage(
                    role=LLMRole.USER,
                    content=(
                        f"Stages, earliest first:\n{catalogue}\n\n"
                        f"The founder's own words:\n{joined}"
                    ),
                ),
            ),
            temperature=self.temperature,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        # run_sync, not a bare asyncio.run: this stage of the pipeline is
        # synchronous but is reached from ReasoningService.analyze_session,
        # which is already on a running event loop. See the same note in
        # archetype_llm.py, where a bare asyncio.run raised "cannot be called
        # from a running event loop" every time.
        response = run_sync(
            asyncio.wait_for(self.provider.generate(request), self.timeout_seconds)
        )
        return json.loads(response.text)

    def _to_detection(
        self, payload: dict, by_name: dict[str, object], context: ReasoningContext
    ) -> StageDetection | None:
        name = payload.get("stage_name")
        if not isinstance(name, str) or not name.strip():
            # The model was asked to say so rather than guess, and did.
            return None

        row = by_name.get(name.strip().casefold())
        if row is None:
            logger.warning(
                "Stage inference returned a stage that is not in the catalogue",
                extra={"returned": name[:80]},
            )
            return None

        confidence = self._confidence(payload.get("confidence"))
        if confidence < _MIN_CONFIDENCE:
            logger.info(
                "Stage inference below the confidence floor; leaving undetected",
                extra={
                    "founder_id": getattr(context.founder, "founder_id", None),
                    "stage": name[:80],
                    "confidence": str(confidence),
                },
            )
            return None

        evidence = ["Stage inferred from the founder's answers; none was declared."]
        evidence.extend(self._evidence_lines(payload.get("evidence")))

        return StageDetection(
            stage_id=row.stage_id,
            stage_name=getattr(row, "stage_name", None),
            # Never 1: DeclaredStageStrategy reserves that for a stage the
            # founder stated. An inference is a read, and downstream consumers
            # can tell the two apart by this number alone.
            probability=confidence,
            confidence=confidence,
            evidence=tuple(evidence),
        )

    @staticmethod
    def _confidence(raw) -> Decimal:
        """The model's confidence, clamped to [0,1]. A missing or unparseable
        value is zero, which the floor then rejects -- an inference we cannot
        score is not one to act on."""
        try:
            value = Decimal(str(raw))
        except (ArithmeticError, TypeError, ValueError):
            return _ZERO
        if value.is_nan():
            return _ZERO
        return _quant(max(_ZERO, min(_ONE, value)))

    @staticmethod
    def _evidence_lines(raw) -> list[str]:
        if not isinstance(raw, list):
            return []
        return [item.strip()[:300] for item in raw if isinstance(item, str) and item.strip()][:5]
