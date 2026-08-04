"""Adaptive next-question advisor (Hybrid mode).

The deterministic QuestionSelectionEngine still produces the ordered shortlist of
what to ask next. This advisor lets an LLM READ the founder's actual answer, judge
it Green/Amber/Red, and RE-RANK that shortlist -- choosing the most informative next
probe given what they just said.

It is strictly optional and fail-open: when no advisor is wired, or the LLM errors,
times out, or returns an id outside the shortlist, the caller falls back to the
deterministic pick, so the flow always progresses and never dead-ends. The Green/
Amber/Red read is returned too, so the answer can be scored once at submit time
(feeding the reasoning pipeline without a second LLM pass).

Vendor-neutral: it talks only to the injected `LLMProvider` (app.services.llm).
"""

from __future__ import annotations

import abc
import asyncio
import json
from dataclasses import dataclass
from typing import Sequence

from app.core.logger import logger
from app.services.llm import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMRole,
)

_VALID_LABELS = {"green", "amber", "red"}
# answers.score is a 0/1/2 CHECK; score_label is the authoritative band. Higher = better.
_LABEL_TO_SCORE = {"green": 2, "amber": 1, "red": 0}


@dataclass(frozen=True)
class AnswerInsight:
    """The LLM's read of one answer plus its next-question recommendation.

    `next_question_id` is only a suggestion -- the caller MUST validate it against
    the shortlist before honouring it. `score_label` is None when unparseable.
    """

    score_label: str | None
    confidence: float
    next_question_id: int | None
    rationale: str

    @property
    def score(self) -> int | None:
        return _LABEL_TO_SCORE.get(self.score_label) if self.score_label else None


def resolve_next(ordered, shortlist, insight: AnswerInsight | None):
    """Pure hybrid decision: honour the LLM's pick only when it is inside the
    shortlist; otherwise take the deterministic head. `ordered` is every candidate
    in deterministic order; `shortlist` is its bounded head handed to the LLM.

    Deterministic and side-effect free so it can be unit-tested without a DB or a
    provider.
    """
    if not ordered:
        return None
    deterministic = ordered[0]
    if insight is None or insight.next_question_id is None:
        return deterministic
    by_id = {q.question_id: q for q in shortlist}
    return by_id.get(insight.next_question_id, deterministic)


class NextQuestionAdvisor(abc.ABC):
    @abc.abstractmethod
    async def analyze(
        self, *, answered_question, answer_text: str, shortlist: Sequence, history
    ) -> AnswerInsight | None:
        """Read the answer and recommend the next question from `shortlist`.
        Returns None on any failure (caller falls back to deterministic)."""
        raise NotImplementedError


class LLMNextQuestionAdvisor(NextQuestionAdvisor):
    def __init__(
        self,
        provider: LLMProvider,
        *,
        timeout_seconds: float = 20.0,
        max_tokens: int = 512,
    ):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    async def analyze(self, *, answered_question, answer_text, shortlist, history):
        if not shortlist:
            return None
        request = self._build_request(answered_question, answer_text, shortlist, history)
        try:
            response = await asyncio.wait_for(
                self.provider.generate(request), timeout=self.timeout_seconds
            )
        except (LLMProviderError, asyncio.TimeoutError) as exc:
            logger.warning(
                "next-question advisor failed; using deterministic pick",
                extra={"stage": "adaptive_questions"},
                exc_info=exc,
            )
            return None
        return self._parse(response.text)

    # --- prompt -----------------------------------------------------------

    def _build_request(self, answered_question, answer_text, shortlist, history) -> LLMRequest:
        options = "\n".join(
            f"- id {q.question_id} [{q.category}] {q.question_text}" for q in shortlist
        )
        hist = (
            "\n".join(f"Q: {qt}\nA: {at}" for qt, at in history) if history else "(none yet)"
        )
        system = (
            "You are guiding a startup founder's diagnostic interview. Read the "
            "founder's latest answer, judge how strong it is (Green = concrete "
            "evidence/ownership, Amber = partial/vague, Red = no real evidence/"
            "avoidance), then choose which of the CANDIDATE questions to ask next -- "
            "the one that will most improve the diagnosis given what they just said "
            "(e.g. probe deeper on a weak/avoidant answer, move on after a strong one). "
            "You MUST pick next_question_id from the candidate ids listed; never invent "
            "one.\nRespond with a single JSON object and nothing else: "
            '{"score_label":"green|amber|red","confidence":0.0-1.0,'
            '"next_question_id":<candidate id>,"rationale":"one sentence"}'
        )
        user = (
            f"Recent Q&A:\n{hist}\n\n"
            f"Just asked [{getattr(answered_question, 'category', '')}]: "
            f"{getattr(answered_question, 'question_text', '')}\n"
            f"Founder's answer: {answer_text}\n\n"
            f"CANDIDATE next questions (choose exactly one id):\n{options}"
        )
        return LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=system),
                LLMMessage(role=LLMRole.USER, content=user),
            ),
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )

    # --- parsing ----------------------------------------------------------

    def _parse(self, text: str) -> AnswerInsight | None:
        data = self._load_json(text)
        if not isinstance(data, dict):
            logger.warning("advisor response was not a JSON object; deterministic fallback")
            return None

        raw_label = str(data.get("score_label") or "").strip().lower()
        label = raw_label if raw_label in _VALID_LABELS else None

        nid = self._coerce_int(data.get("next_question_id"))
        confidence = self._coerce_confidence(data.get("confidence"))
        rationale = str(data.get("rationale") or "").strip()
        return AnswerInsight(
            score_label=label, confidence=confidence, next_question_id=nid, rationale=rationale
        )

    @staticmethod
    def _coerce_int(value) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value.strip())
        return None

    @staticmethod
    def _coerce_confidence(value) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _load_json(text: str):
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw[:4].lower() == "json":
                raw = raw[4:]
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start : end + 1]
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None
