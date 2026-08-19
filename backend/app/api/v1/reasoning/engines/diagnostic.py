"""Diagnosis Engine -- deterministic category scoring, follow-up triggering and
distress detection.

Green/Amber/Red classification is read from the stored answer scores
(answers.score / answers.score_label). The LLM classifier populates those scores
at answer time (a later step); this engine consumes them, so the whole path is
deterministic and needs no provider.

All thresholds and band scores come from the configuration layer (scoring_rules);
none are hardcoded. Category maxima come from the injected CategoryMaxScoreProvider
when configured, and otherwise from the answered-question count -- see
`compute_category_risks`.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.api.v1.reasoning.errors import DiagnosisDataError, LLMClassificationError
from app.api.v1.reasoning.interfaces import (
    AnswerClassifier,
    DiagnosticEngine,
    ReasoningContext,
)
from app.api.v1.reasoning.schemas import (
    AnswerClassification,
    CategoryRisk,
    ConversationTurn,
    FollowUpReason,
    FollowUpTrigger,
    LLMClassification,
)
from app.core.config import settings
from app.core.logger import logger
from app.models.diagnosis import Answer, Question
from app.models.enums import ScoreLabel
from app.services.llm import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMRole,
)

_QUANT = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


class StoredScoreAnswerClassifier(AnswerClassifier):
    """Deterministic classifier: reads the Green/Amber/Red band already stored on
    the answer. No model call. Raises DiagnosisDataError for an unscored answer --
    it never guesses a score."""

    async def classify(
        self,
        answer: Answer,
        question: Question,
        context: ReasoningContext,
        *,
        previous_conversation: Sequence[ConversationTurn] | None = None,
    ) -> AnswerClassification:
        bands = context.config.question_scores
        label: ScoreLabel | None = None
        if answer.score_label is not None:
            label = ScoreLabel(answer.score_label)

        score = answer.score
        if label is None and score is not None:
            label = self._label_for_score(Decimal(score), bands)

        if label is None:
            raise DiagnosisDataError(
                f"Answer {answer.answer_id} has neither score nor score_label."
            )
        if score is None:
            score = self._score_for_label(label, bands)

        return AnswerClassification(
            answer_id=answer.answer_id,
            question_id=answer.question_id,
            label=label,
            score=Decimal(score),
            is_distress_flagged=answer.is_distress_flagged,
            is_follow_up=answer.is_follow_up,
            triggered_follow_up_id=answer.triggered_follow_up_id,
        )

    def _label_for_score(self, score: Decimal, bands) -> ScoreLabel:
        if score >= bands.red:
            return ScoreLabel.RED
        if score >= bands.amber:
            return ScoreLabel.AMBER
        return ScoreLabel.GREEN

    def _score_for_label(self, label: ScoreLabel, bands) -> Decimal:
        return {
            ScoreLabel.GREEN: bands.green,
            ScoreLabel.AMBER: bands.amber,
            ScoreLabel.RED: bands.red,
        }[label]


class StoredFirstAnswerClassifier(AnswerClassifier):
    """Reuse the label an answer already carries; only call the LLM for answers
    that have none.

    This exists because the diagnosis path classifies every answer TWICE.
    `ADAPTIVE_QUESTIONS=true` makes the submit-time advisor score each answer and
    persist the band to `answers.score_label` (DiagnosisService._apply_insight).
    With `ANSWER_CLASSIFIER=llm`, the reasoning pipeline then handed all thirty of
    those already-labelled answers to LLMAnswerClassifier, which re-derived the
    same labels from scratch: thirty provider calls per diagnosis producing values
    already sitting in the database. Profiled on a real session, that made the
    `diagnosis` stage 161s of a 203s pipeline -- 79% of the founder's wait after
    their final answer, spent re-deriving what was already known.

    `.env.example` documents the intended pairing ("Keep ANSWER_CLASSIFIER=stored
    when this is on -- the submit-time scores are reused by the reasoning
    pipeline"), but nothing enforced it, so getting it wrong cost real money and
    real latency silently. Composing here makes reuse structural rather than a
    configuration the operator has to get right: whichever way the flags are set,
    a stored label is never re-derived.

    Not simply "always use stored": an answer with no label still has to be
    classified, or it is dropped from the evidence set entirely (see
    StandardDiagnosticEngine.classify_answers). So this delegates rather than
    short-circuits, which also means the mixed case -- some answers labelled at
    submit time, some not, e.g. a session that spanned a config change -- comes
    out fully classified instead of half-empty.

    Deterministic side effect worth knowing: the submit-time label wins over what
    the pipeline would have decided. The advisor sees one answer plus five turns
    of history; the pipeline classifier sees the whole set and could in principle
    judge better. But the submit-time label is ALREADY what drives the confidence
    loop, and therefore when the diagnosis ends -- so the two disagreeing was
    never a feature, it was two sources of truth for one number.
    """

    def __init__(self, stored: AnswerClassifier, fallback: AnswerClassifier):
        self.stored = stored
        self.fallback = fallback

    async def classify(
        self,
        answer: Answer,
        question: Question,
        context: ReasoningContext,
        *,
        previous_conversation: Sequence[ConversationTurn] | None = None,
    ) -> AnswerClassification:
        try:
            return await self.stored.classify(
                answer, question, context,
                previous_conversation=previous_conversation,
            )
        except DiagnosisDataError:
            # No stored band -- this answer genuinely needs classifying.
            return await self.fallback.classify(
                answer, question, context,
                previous_conversation=previous_conversation,
            )


class _ClassificationParseError(Exception):
    """Internal, retryable: the model response was not a usable classification."""


class LLMAnswerClassifier(AnswerClassifier):
    """Answer-time classifier that scores free text via a provider-agnostic LLM.

    Vendor-neutral: it only talks to the injected `LLMProvider`; no vendor SDK is
    referenced. The model supplies the Green/Amber/Red label, a confidence, an
    explanation and reasoning steps; the numeric score is resolved from the label
    via the configured bands (not the model's arithmetic), keeping scores
    consistent with the deterministic rules. `is_distress_flagged` and the
    follow-up linkage come from the stored Answer, unchanged.

    Robustness: each call is retried up to `max_retries` on provider errors,
    timeouts, or malformed responses. When all attempts fail, it falls back to the
    injected deterministic classifier (if the answer has a stored score); if that
    is unavailable too, it raises LLMClassificationError.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        fallback: AnswerClassifier | None = None,
        max_retries: int = 2,
        timeout_seconds: float = 30.0,
        temperature: float = 0.0,
    ):
        self.provider = provider
        self.fallback = fallback
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    async def classify(
        self,
        answer: Answer,
        question: Question,
        context: ReasoningContext,
        *,
        previous_conversation: Sequence[ConversationTurn] | None = None,
    ) -> AnswerClassification:
        request = self._build_request(answer, question, context, previous_conversation)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    self.provider.generate(request), timeout=self.timeout_seconds
                )
                parsed = self._parse(response.text, context)
                return self._to_classification(answer, parsed)
            except (LLMProviderError, asyncio.TimeoutError, _ClassificationParseError) as exc:
                last_error = exc
                logger.warning(
                    "LLM answer classification attempt failed",
                    extra={"answer_id": answer.answer_id, "attempt": attempt + 1},
                    exc_info=exc,
                )

        return await self._fallback_or_raise(
            answer, question, context, previous_conversation, last_error
        )

    # --- Fallback ---------------------------------------------------------

    async def _fallback_or_raise(
        self, answer, question, context, previous_conversation, cause: Exception | None
    ) -> AnswerClassification:
        if self.fallback is not None:
            try:
                return await self.fallback.classify(
                    answer, question, context,
                    previous_conversation=previous_conversation,
                )
            except DiagnosisDataError:
                pass  # no stored score to fall back to
        raise LLMClassificationError(
            f"LLM classification failed for answer {answer.answer_id}: {cause}"
        ) from cause

    # --- Prompt -----------------------------------------------------------

    def _build_request(
        self, answer, question, context, previous_conversation
    ) -> LLMRequest:
        bands = context.config.question_scores
        system = (
            "You classify a startup founder's answer to a diagnostic question as "
            "Green, Amber or Red.\n"
            f"- Green (score {bands.green}): concrete evidence, specificity, ownership.\n"
            f"- Amber (score {bands.amber}): partial evidence, vague or incomplete.\n"
            f"- Red (score {bands.red}): no real evidence, assumption or avoidance.\n"
            "Respond with a single JSON object and nothing else, with keys: "
            '"score_label" (one of "green","amber","red"), "confidence" (0.0-1.0), '
            '"explanation" (one sentence), "reasoning_steps" (array of short strings).'
        )
        user = self._user_prompt(answer, question, previous_conversation)
        return LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=system),
                LLMMessage(role=LLMRole.USER, content=user),
            ),
            temperature=self.temperature,
            response_format={"type": "json_object"},
            metadata={
                "answer_id": answer.answer_id,
                "question_id": getattr(question, "question_id", None),
            },
        )

    def _user_prompt(self, answer, question, previous_conversation) -> str:
        parts: list[str] = []
        if previous_conversation:
            history = "\n".join(
                f"- Q: {t.question_text}\n  A: {t.answer_text}"
                for t in previous_conversation
            )
            parts.append(f"Previous conversation:\n{history}\n")
        if question is not None:
            parts.append(f"Category: {question.category}")
            parts.append(f"Question type: {question.question_type}")
            parts.append(f"Question: {question.question_text}")
        parts.append(f"Founder's answer: {answer.answer_text}")
        return "\n".join(parts)

    # --- Parsing ----------------------------------------------------------

    def _parse(self, text: str, context: ReasoningContext) -> LLMClassification:
        data = self._load_json(text)
        if not isinstance(data, dict):
            raise _ClassificationParseError("response JSON is not an object")

        raw_label = str(data.get("score_label") or data.get("label") or "").strip().lower()
        try:
            label = ScoreLabel(raw_label)
        except ValueError:
            raise _ClassificationParseError(f"invalid score_label: {raw_label!r}")

        bands = context.config.question_scores
        score = {
            ScoreLabel.GREEN: bands.green,
            ScoreLabel.AMBER: bands.amber,
            ScoreLabel.RED: bands.red,
        }[label]

        steps_raw = data.get("reasoning_steps") or []
        if not isinstance(steps_raw, list):
            raise _ClassificationParseError("reasoning_steps must be a list")

        return LLMClassification(
            score_label=label,
            score=score,
            confidence=self._parse_confidence(data.get("confidence")),
            explanation=str(data.get("explanation") or "").strip(),
            reasoning_steps=tuple(str(s) for s in steps_raw),
        )

    def _parse_confidence(self, value) -> Decimal:
        if value is None:
            return Decimal("0")
        try:
            confidence = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise _ClassificationParseError(f"invalid confidence: {value!r}")
        return max(Decimal("0"), min(Decimal("1"), confidence))

    def _load_json(self, text: str):
        raw = self._strip_fences(text)
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start : end + 1]
        try:
            return json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise _ClassificationParseError(f"response is not valid JSON: {exc}")

    def _strip_fences(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`").strip()
            if stripped[:4].lower() == "json":
                stripped = stripped[4:].strip()
        return stripped

    def _to_classification(
        self, answer, parsed: LLMClassification
    ) -> AnswerClassification:
        return AnswerClassification(
            answer_id=answer.answer_id,
            question_id=answer.question_id,
            label=parsed.score_label,
            score=parsed.score,
            is_distress_flagged=answer.is_distress_flagged,
            is_follow_up=answer.is_follow_up,
            triggered_follow_up_id=answer.triggered_follow_up_id,
            rationale=parsed.explanation or None,
            llm_classification=parsed,
        )


class StandardDiagnosticEngine(DiagnosticEngine):
    """Category scoring, follow-up decisions and distress detection over the
    classified answers."""

    def __init__(self, classifier: AnswerClassifier):
        self.classifier = classifier

    async def classify_answers(
        self,
        answers: list[Answer],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> list[AnswerClassification]:
        # Bounded-concurrent, not sequential. Each answer is classified
        # independently, but this awaited them one at a time: profiled on a real
        # 30-answer session the `diagnosis` stage was 161s of a 203s pipeline --
        # 79% of what the founder waits through after their final answer, spent
        # entirely on serialisation the work never required.
        #
        # Order is preserved: results come back indexed, so a founder's
        # classifications stay in answer order regardless of completion order.
        # An unscored answer is still skipped rather than failing the batch,
        # exactly as before -- see DIAGNOSIS_CLASSIFY_CONCURRENCY for the width.
        width = max(1, int(settings.DIAGNOSIS_CLASSIFY_CONCURRENCY or 1))
        limit = asyncio.Semaphore(width)

        async def _classify(answer: Answer) -> AnswerClassification | None:
            question = questions.get(answer.question_id)
            async with limit:
                try:
                    return await self.classifier.classify(answer, question, context)
                except DiagnosisDataError:
                    logger.warning(
                        "Skipping unscored answer during classification",
                        extra={"answer_id": answer.answer_id},
                    )
                    return None

        results = await asyncio.gather(*(_classify(a) for a in answers))
        return [c for c in results if c is not None]

    def compute_category_risks(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> list[CategoryRisk]:
        """Accumulate per-category score and normalise to risk in [0,1].

        Denominator = the configured per-category maximum when a
        CategoryMaxScoreProvider is present; otherwise the maximum attainable by
        the answered questions (red band * answered count). A category is flagged
        when its risk reaches CAT_RISK_THRESHOLD.
        """
        red_band = context.config.question_scores.red
        threshold = context.config.branching.category_risk_threshold
        provider = context.config.category_max_scores

        by_category: dict[str, list[AnswerClassification]] = defaultdict(list)
        for c in classifications:
            question = questions.get(c.question_id)
            if question is not None:
                by_category[question.category].append(c)

        risks: list[CategoryRisk] = []
        for category in sorted(by_category):
            members = by_category[category]
            raw = sum((m.score for m in members), _ZERO)
            # Per-session category maximum (CATEGORY_MAX_COMPUTED_PER_SESSION): the
            # worst the answered questions in this category could have scored. An
            # explicit provider (Doc 12) overrides it when configured. (A full
            # question-bank denominator was trialled and rejected in validation --
            # it was so large that no category ever crossed the flag threshold.)
            max_score = (
                provider.max_score(category)
                if provider is not None
                else red_band * len(members)
            )
            normalised = (
                _q(min(_ONE, max(_ZERO, raw / max_score))) if max_score > 0 else _ZERO
            )
            risks.append(
                CategoryRisk(
                    category=category,
                    raw_score=raw,
                    max_score=max_score,
                    normalised_risk=normalised,
                    is_flagged=normalised >= threshold,
                )
            )
        return risks

    def follow_up_triggers(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> list[FollowUpTrigger]:
        """Which follow-ups the configured rules call for: a single probe on each
        original Red answer that has a follow-up question, and a category-level
        clarifier when a category has >= AMBER_CLUSTER_TRIGGER ambers and no red."""
        triggers: list[FollowUpTrigger] = []

        for c in sorted(classifications, key=lambda c: c.question_id):
            if c.is_follow_up or c.label != ScoreLabel.RED:
                continue
            question = questions.get(c.question_id)
            if question is None or question.follow_up_question_id is None:
                continue
            triggers.append(
                FollowUpTrigger(
                    reason=FollowUpReason.RED_SINGLE_PROBE,
                    question_id=c.question_id,
                    follow_up_question_id=question.follow_up_question_id,
                )
            )

        amber = defaultdict(int)
        red = defaultdict(int)
        for c in classifications:
            if c.is_follow_up:
                continue
            question = questions.get(c.question_id)
            if question is None:
                continue
            if c.label == ScoreLabel.AMBER:
                amber[question.category] += 1
            elif c.label == ScoreLabel.RED:
                red[question.category] += 1

        cluster_threshold = context.config.branching.amber_cluster_trigger
        for category in sorted(amber):
            if red[category] == 0 and amber[category] >= cluster_threshold:
                triggers.append(
                    FollowUpTrigger(reason=FollowUpReason.AMBER_CLUSTER, category=category)
                )
        return triggers

    def distress_signal_answers(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> list[int]:
        """The answer ids that count as distress signals: Red answers on
        distress-tagged questions, or answers explicitly flagged for distress.

        Returned as ids rather than only a count so the decision can be audited.
        A live session reached distress_mode=True while the persisted
        score_labels said no answer qualified -- with only a count there was no
        way to tell whether the engine saw different classifications than the
        ones on disk, or whether the flag came from somewhere else entirely.
        """
        signals = []
        for c in classifications:
            if c.label != ScoreLabel.RED:
                continue
            question = questions.get(c.question_id)
            tagged = c.is_distress_flagged or (
                question is not None and question.is_distress_tagged
            )
            if tagged:
                signals.append(c.answer_id)
        return signals

    def distress_signal_count(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> int:
        """How many answers count as distress signals -- the number
        DISTRESS_QUESTIONS_TRIGGER acts on."""
        return len(self.distress_signal_answers(classifications, questions, context))

    def is_distress_mode(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> bool:
        return self.distress_signal_count(classifications, questions, context) >= (
            context.config.distress.distress_questions_trigger
        )
