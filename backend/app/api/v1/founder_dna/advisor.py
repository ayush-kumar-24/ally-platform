"""Adaptive dimension-resolution advisor.

Mirrors app/api/v1/diagnosis/advisor.py's LLMNextQuestionAdvisor pattern
closely: one LLM call, judging one thing, fully fail-open. Where that
advisor re-ranks a shortlist, this one judges a single yes/no -- "has this
dimension's Q&A so far said enough to stop asking about it" -- which is the
actual "adaptive" behaviour the doc and the project decision call for
(GoXL_Founder_DNA_Decoding_Journey.docx Section 3, "Adaptive skipping").

Deliberately NOT a confidence-score table: the judgment is recomputed from
the live Q&A transcript every time it's asked, same as
app/api/v1/diagnosis/incremental_confidence.py recomputes fresh rather than
accumulating. Only the RESULT (resolved or not) persists, on
founders.founder_dna_resolved_dimensions -- see that column's comment for
why that's a progress marker, not a rubric table.
"""

from __future__ import annotations

import abc
import asyncio
import json
from dataclasses import dataclass

from app.core.logger import logger
from app.services.llm import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMRole,
)


@dataclass(frozen=True)
class ResolutionVerdict:
    resolved: bool
    rationale: str


class DimensionResolutionAdvisor(abc.ABC):
    @abc.abstractmethod
    async def judge(
        self, *, dimension_code: str, qa_history: list[tuple[str, str]]
    ) -> ResolutionVerdict | None:
        """Judge whether `dimension_code` has enough signal to stop asking
        about. Returns None on any failure -- caller falls back to the
        deterministic pool-exhaustion stop, never blocks the flow."""
        raise NotImplementedError


class LLMDimensionResolutionAdvisor(DimensionResolutionAdvisor):
    def __init__(
        self,
        provider: LLMProvider,
        *,
        timeout_seconds: float = 20.0,
        max_tokens: int = 256,
    ):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    async def judge(self, *, dimension_code, qa_history):
        if not qa_history:
            return None
        request = self._build_request(dimension_code, qa_history)
        try:
            response = await asyncio.wait_for(
                self.provider.generate(request), timeout=self.timeout_seconds
            )
        except (LLMProviderError, asyncio.TimeoutError) as exc:
            logger.warning(
                "founder DNA resolution advisor failed; falling back to pool "
                "exhaustion",
                extra={"stage": "founder_dna_resolution", "dimension": dimension_code},
                exc_info=exc,
            )
            return None
        return self._parse(response.text)

    def _build_request(
        self, dimension_code: str, qa_history: list[tuple[str, str]]
    ) -> LLMRequest:
        hist = "\n".join(f"Q: {qt}\nA: {at}" for qt, at in qa_history)
        system = (
            "You are deciding whether enough is known about one facet of a "
            "startup founder's identity to stop asking about it in this "
            "interview. The facet is: " + dimension_code.replace("_", " ") + ". "
            "Say resolved=true only when the founder's answers give a clear, "
            "specific, non-generic picture of this facet -- a vague or "
            "surface-level answer is NOT resolved, ask more. Do not invent "
            "anything not in the transcript.\n"
            'Respond with a single JSON object and nothing else: '
            '{"resolved": true|false, "rationale": "one sentence"}'
        )
        user = f"Transcript so far for this facet:\n{hist}"
        return LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=system),
                LLMMessage(role=LLMRole.USER, content=user),
            ),
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )

    def _parse(self, text: str) -> ResolutionVerdict | None:
        data = self._load_json(text)
        if not isinstance(data, dict):
            logger.warning(
                "founder DNA resolution advisor response was not a JSON "
                "object; falling back to pool exhaustion"
            )
            return None
        resolved = bool(data.get("resolved"))
        rationale = str(data.get("rationale") or "").strip()
        return ResolutionVerdict(resolved=resolved, rationale=rationale)

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
