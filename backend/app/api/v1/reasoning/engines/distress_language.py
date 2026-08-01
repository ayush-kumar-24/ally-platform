"""Distress Language Detection (#11) -- replaces the deterministic distress proxy.

Reads the founder's own words and detects which of the seeded
`psychological_state_signals` (States A/B/C/D) are present, then scores them into a
DistressAssessment.

FAILS CLOSED. A detector error is NEVER indistinguishable from a clean result:
  * On any provider error, timeout, or unparseable response, `detect` returns a
    result with status="error" (not an empty "no signals found").
  * `build_distress_assessment` maps status="error" to HIGH DISTRESS + override
    (the session routes to wellbeing support) -- because a missed distress signal
    is the worst failure this system can produce and over-detection is merely
    annoying. It does NOT fall back to the deterministic proxy or retry a weaker
    path. The `detector_status` on the result records that it was error-induced.

State-D (crisis) signals trigger the override immediately, independently of the
cumulative 36-point threshold, exactly as the deterministic proxy did.
"""

from __future__ import annotations

import abc
import asyncio
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Mapping, Sequence

from app.api.v1.reasoning.engines.psychological_state import (
    _STATE_PROTOCOL,
    DistressAssessment,
)
from app.core.logger import logger
from app.services.llm import LLMMessage, LLMProvider, LLMProviderError, LLMRequest, LLMRole

_ACUTE_STATE = "D"
_STATE_SEVERITY = {"A": 1, "B": 2, "C": 3, "D": 4}


@dataclass(frozen=True)
class DistressLanguageResult:
    status: str                              # "measured" | "error"
    present_ids: frozenset[int] = field(default_factory=frozenset)
    error: str | None = None


class DistressDetector(abc.ABC):
    @abc.abstractmethod
    async def detect(self, answer_texts: Sequence[str]) -> DistressLanguageResult: ...


class LLMDistressDetector(DistressDetector):
    def __init__(
        self,
        provider: LLMProvider,
        catalog: Sequence[Mapping],
        *,
        timeout_seconds: float = 30.0,
        max_tokens: int = 600,
    ):
        self.provider = provider
        self.catalog = list(catalog)
        self._valid_ids = {int(s["signal_id"]) for s in self.catalog}
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    async def detect(self, answer_texts: Sequence[str]) -> DistressLanguageResult:
        text = "\n\n".join(t for t in answer_texts if t and t.strip())
        if not text:
            # No language at all -> genuinely nothing to detect (measured empty).
            return DistressLanguageResult(status="measured", present_ids=frozenset())
        try:
            response = await asyncio.wait_for(
                self.provider.generate(self._request(text)), timeout=self.timeout_seconds
            )
        except (LLMProviderError, asyncio.TimeoutError) as exc:
            logger.error(
                "distress detector call failed -> FAIL CLOSED (assume high distress)",
                extra={"stage": "distress_detection"}, exc_info=exc,
            )
            return DistressLanguageResult(status="error", error=str(exc)[:300])
        present = self._parse(response.text)
        if present is None:  # unparseable == indistinguishable from clean -> fail closed
            logger.error("distress detector response unparseable -> FAIL CLOSED")
            return DistressLanguageResult(status="error", error="unparseable response")
        return DistressLanguageResult(status="measured", present_ids=frozenset(present))

    # --- prompt / parse ---------------------------------------------------

    def _request(self, text: str) -> LLMRequest:
        lines = [
            f"- id {s['signal_id']} [State {s['state_code']}] {s['signal_type']}: "
            f"{s['observable_indicator']} (e.g. {s['example_phrases']})"
            for s in self.catalog
        ]
        system = (
            "You are a psychological-safety monitor reading a startup founder's own "
            "words for signs of acute distress. Below is a catalogue of distress "
            "signals. Identify which signals are PRESENT in the founder's text. Under-"
            "detection is dangerous and over-detection is acceptable: when a signal is "
            "plausibly present, INCLUDE it. State D signals are crisis-level.\n"
            "SIGNAL CATALOGUE:\n" + "\n".join(lines) + "\n"
            'Return a single JSON object and nothing else: {"present_signal_ids": [<ids>]}'
        )
        return LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=system),
                LLMMessage(role=LLMRole.USER, content=f"FOUNDER'S WORDS:\n{text}"),
            ),
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )

    def _parse(self, text: str) -> set[int] | None:
        data = self._load_json(text)
        if not isinstance(data, dict) or "present_signal_ids" not in data:
            return None
        raw = data.get("present_signal_ids")
        if not isinstance(raw, list):
            return None
        out: set[int] = set()
        for v in raw:
            try:
                sid = int(v)
            except (TypeError, ValueError):
                continue
            if sid in self._valid_ids:  # only known signals
                out.add(sid)
        return out

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


def build_distress_assessment(
    result: DistressLanguageResult,
    catalog: Sequence[Mapping],
    *,
    scorer,
    high_distress_score: Decimal,
    empathy_lookup: Callable[[str], str | None],
) -> DistressAssessment:
    """Map a detector result to a DistressAssessment. FAIL-CLOSED on error."""
    if result.status == "error":
        code = _STATE_PROTOCOL[_ACUTE_STATE]
        return DistressAssessment(
            session_distress_score=high_distress_score,   # floored to the threshold
            signal_occurrences={},
            is_high_distress=True,                         # closed: assume distress
            distress_override=True,
            distress_red_count=0,
            empathy_protocol_code=code,
            empathy_protocol_text=empathy_lookup(code),
            detector_status="error",
        )

    state_by_id = {int(s["signal_id"]): s["state_code"] for s in catalog}
    present = result.present_ids
    occ = {str(sid): 1 for sid in present}
    cumulative = scorer.session_distress_score(occ)
    acute = any(state_by_id.get(sid) == _ACUTE_STATE for sid in present)
    # State-D fires immediately; cumulative >= threshold fires independently.
    is_high = acute or cumulative >= high_distress_score
    score = max(cumulative, high_distress_score) if is_high else cumulative

    code = None
    if is_high and present:
        top_state = max(
            (state_by_id.get(sid) for sid in present if state_by_id.get(sid)),
            key=lambda st: _STATE_SEVERITY.get(st, 0),
            default=None,
        )
        code = _STATE_PROTOCOL.get(top_state) if top_state else _STATE_PROTOCOL[_ACUTE_STATE]

    return DistressAssessment(
        session_distress_score=score,
        signal_occurrences=occ,
        is_high_distress=is_high,
        distress_override=is_high,
        distress_red_count=sum(1 for sid in present if state_by_id.get(sid) == _ACUTE_STATE),
        empathy_protocol_code=code,
        empathy_protocol_text=(empathy_lookup(code) if code else None),
        detector_status="measured",
    )
