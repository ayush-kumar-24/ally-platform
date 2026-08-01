"""Answer Consistency detector -- input (c) of the confidence score.

Reads the founder's answers and looks for genuine contradictions (e.g. claims
recurring revenue in one answer, says the product has never sold in another),
producing a 0..1 consistency signal (1.0 = fully consistent).

FAILS TO UNAVAILABLE, never to a false 1.0. On any error the result is
`available=False`, so the confidence strategy EXCLUDES it and renormalises the
remaining weights (CONFIDENCE_UNAVAILABLE_INPUT_HANDLING) -- an unmeasured signal
neither rewards nor penalises the founder. A clean pass returns available=True
with score 1.0; only a real error returns unavailable.
"""

from __future__ import annotations

import abc
import asyncio
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.core.logger import logger
from app.services.llm import LLMMessage, LLMProvider, LLMProviderError, LLMRequest, LLMRole

_ONE = Decimal("1")
_ZERO = Decimal("0")


@dataclass(frozen=True)
class ConsistencyResult:
    available: bool
    score: Decimal | None                 # 1.0 = consistent; lower = contradictions
    contradictions: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def unavailable(cls) -> "ConsistencyResult":
        return cls(available=False, score=None)


class ConsistencyDetector(abc.ABC):
    @abc.abstractmethod
    async def assess(self, answers, questions) -> ConsistencyResult: ...


class LLMConsistencyDetector(ConsistencyDetector):
    """LLM-backed contradiction detector. `answers` is a sequence of Answer;
    `questions` maps question_id -> Question (for context)."""

    def __init__(self, provider: LLMProvider, *, timeout_seconds: float = 30.0, max_tokens: int = 500):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    async def assess(self, answers, questions) -> ConsistencyResult:
        pairs = self._pairs(answers, questions)
        if len(pairs) < 2:
            # Nothing to contradict against -> trivially consistent, and MEASURED
            # (available), so it contributes at full weight rather than dropping out.
            return ConsistencyResult(available=True, score=_ONE)
        try:
            response = await asyncio.wait_for(
                self.provider.generate(self._request(pairs)), timeout=self.timeout_seconds
            )
        except (LLMProviderError, asyncio.TimeoutError) as exc:
            logger.warning(
                "consistency detector failed -> UNAVAILABLE (excluded, renormalised)",
                extra={"stage": "answer_consistency"}, exc_info=exc,
            )
            return ConsistencyResult.unavailable()
        return self._parse(response.text)

    # --- internals --------------------------------------------------------

    def _pairs(self, answers, questions):
        out = []
        for a in answers:
            q = questions.get(a.question_id)
            qt = getattr(q, "question_text", "") if q is not None else ""
            out.append((qt, a.answer_text))
        return out

    def _request(self, pairs) -> LLMRequest:
        body = "\n".join(f"Q: {qt}\nA: {at}" for qt, at in pairs)
        system = (
            "You check a founder's diagnostic answers for GENUINE contradictions -- "
            "statements that cannot both be true (e.g. 'we have recurring revenue' vs "
            "'we've never made a sale'). Vague, incomplete, or evolving answers are NOT "
            "contradictions. Return a single JSON object and nothing else: "
            '{"consistency": <0.0-1.0, 1.0 = fully consistent>, '
            '"contradictions": [<short description of each real contradiction>]}'
        )
        return LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=system),
                LLMMessage(role=LLMRole.USER, content=body),
            ),
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )

    def _parse(self, text: str) -> ConsistencyResult:
        data = self._load_json(text)
        if not isinstance(data, dict) or "consistency" not in data:
            logger.warning("consistency response unparseable -> UNAVAILABLE")
            return ConsistencyResult.unavailable()
        try:
            score = Decimal(str(data["consistency"]))
        except (InvalidOperation, ValueError, TypeError):
            return ConsistencyResult.unavailable()
        score = max(_ZERO, min(_ONE, score))
        contradictions = tuple(
            str(c) for c in (data.get("contradictions") or []) if str(c).strip()
        )
        return ConsistencyResult(available=True, score=score, contradictions=contradictions)

    @staticmethod
    def _load_json(text: str):
        raw = (text or "").strip().strip("`")
        if raw[:4].lower() == "json":
            raw = raw[4:]
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e > s:
            raw = raw[s : e + 1]
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None
