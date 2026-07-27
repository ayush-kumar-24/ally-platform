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
        classifications: list[AnswerClassification] = []
        for answer in answers:
            question = questions.get(answer.question_id)
            try:
                classifications.append(
                    await self.classifier.classify(answer, question, context)
                )
            except DiagnosisDataError:
                logger.warning(
                    "Skipping unscored answer during classification",
                    extra={"answer_id": answer.answer_id},
                )
        return classifications

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

    def distress_signal_count(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> int:
        """Count Red answers on distress-tagged questions (or answers explicitly
        flagged for distress). This is the signal DISTRESS_QUESTIONS_TRIGGER acts
        on."""
        count = 0
        for c in classifications:
            if c.label != ScoreLabel.RED:
                continue
            question = questions.get(c.question_id)
            tagged = c.is_distress_flagged or (
                question is not None and question.is_distress_tagged
            )
            if tagged:
                count += 1
        return count

    def is_distress_mode(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> bool:
        return self.distress_signal_count(classifications, questions, context) >= (
            context.config.distress.distress_questions_trigger
        )
