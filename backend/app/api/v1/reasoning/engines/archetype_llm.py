"""LLM founder-archetype assignment -- the seam ArchetypeEngine documented.

The deterministic engine matches a founder's words against each archetype's
signature phrases by lexical overlap. That is a heuristic and its own docstring
says so: archetype fit is a semantic judgement ("this founder avoids delegating
because they do not trust the output" is an Operator signal whether or not the
word "delegate" appears), which token counting cannot reach.

This classifier asks the model to choose from the SAME seeded catalogue and
returns the SAME `ArchetypeMatch`, so `ReasoningService` and the report layer are
unchanged.

Two boundaries worth stating, because both are ways this could go wrong quietly:

* The model CHOOSES, it never INVENTS. The prompt carries the eight seeded
  archetypes and the reply is matched back to a real archetype_id; anything not
  in the catalogue is treated as a failed call, not as a new archetype. The
  archetypes table stays the only source of what archetypes exist.

* It falls back to the deterministic engine on any failure -- provider error,
  timeout, malformed JSON, unknown archetype. A founder always gets an archetype;
  what varies is whether a model or a lexical heuristic picked it. Which one it
  was is recorded on the match (`assigned_by`) rather than left indistinguishable,
  for the same reason report sections carry narrator provenance: advice a founder
  reads should be traceable to how it was produced.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from decimal import Decimal

from app.api.v1.reasoning.engines.archetype import ArchetypeEngine, ArchetypeMatch
from app.core.logger import logger
from app.services.llm.base import LLMError, LLMMessage, LLMRequest, LLMRole
from app.services.llm.text import run_sync

_SYSTEM = (
    "You classify a startup founder into exactly one archetype from a fixed list. "
    "Judge how they think, decide and describe pressure -- not the industry they "
    "are in. Choose the single best fit even when several are plausible. "
    "Reply with JSON only: "
    '{"archetype_code": "<code from the list>", "confidence": <0.0-1.0>, '
    '"evidence": ["<short quote or paraphrase from their words>", ...]}'
)

#: Below this the assignment is not marked confident. The archetype is still
#: returned -- a weak read is information, an absent one is not -- but the report
#: layer can present it with appropriate hedging.
_CONFIDENT_AT = Decimal("0.6")


class LLMArchetypeAssigner:
    """Assigns an archetype via the model, deterministically as a fallback."""

    def __init__(
        self,
        provider,
        *,
        fallback: ArchetypeEngine,
        timeout_seconds: float = 20.0,
        temperature: float = 0.0,
        max_answers: int = 40,
    ):
        self.provider = provider
        self.fallback = fallback
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        #: Long diagnoses would otherwise grow the prompt without bound. The
        #: earliest answers carry the most archetype signal (how they describe
        #: themselves before the questions narrow), so this keeps the head.
        self.max_answers = max_answers

    # --- prompt ------------------------------------------------------------

    def _catalogue(self) -> tuple[str, dict[str, object]]:
        """The archetypes, as prompt text plus a code -> row lookup."""
        rows = self.fallback.repository.get_archetypes()
        by_code: dict[str, object] = {}
        lines: list[str] = []
        for row in rows:
            code = getattr(row, "archetype_code", None) or getattr(row, "code", None)
            if not code:
                continue
            by_code[code] = row
            traits = getattr(row, "key_traits", None) or {}
            name = getattr(row, "archetype_name", None) or getattr(row, "name", "")
            bits = " | ".join(
                f"{k}: {traits[k]}" for k in
                ("decision_style", "stress_pattern", "core_motivation")
                if traits.get(k)
            )
            criteria = (getattr(row, "assignment_criteria", None) or "").strip()
            lines.append(f"- {code} ({name}): {bits}\n  {criteria[:400]}")
        return "\n".join(lines), by_code

    # --- assignment --------------------------------------------------------

    def assign(self, answer_texts: Sequence[str]) -> ArchetypeMatch | None:
        texts = [t for t in answer_texts if t and t.strip()][: self.max_answers]
        if not texts:
            return None                       # nothing to classify; not a failure

        catalogue, by_code = self._catalogue()
        if not by_code:
            return self.fallback.assign(answer_texts)

        try:
            payload = self._ask(catalogue, texts)
            match = self._to_match(payload, by_code)
            if match is not None:
                return match
            logger.warning("Archetype LLM returned an unknown archetype; using fallback")
        except (LLMError, asyncio.TimeoutError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Archetype LLM failed; using deterministic fallback",
                           extra={"error": str(exc)})
        return self.fallback.assign(answer_texts)

    def _ask(self, catalogue: str, texts: Sequence[str]) -> dict:
        joined = "\n".join(f"- {t}" for t in texts)
        request = LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM),
                LLMMessage(
                    role=LLMRole.USER,
                    content=(f"Archetypes:\n{catalogue}\n\n"
                             f"The founder's own words:\n{joined}"),
                ),
            ),
            temperature=self.temperature,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        # The pipeline stage is synchronous; the provider interface is not.
        # `run_sync` (not a bare asyncio.run) because this is reached from
        # ReasoningService.analyze_session, itself already running on an
        # active event loop -- confirmed live: a bare asyncio.run() here
        # raised "cannot be called from a running event loop" every time,
        # even after fixing the same bug one level up in trigger.py.
        response = run_sync(
            asyncio.wait_for(self.provider.generate(request), self.timeout_seconds)
        )
        return json.loads(response.text)

    def _to_match(self, payload: dict, by_code: dict) -> ArchetypeMatch | None:
        code = str(payload.get("archetype_code") or "").strip()
        row = by_code.get(code)
        if row is None:
            return None                       # not in the catalogue -> not an archetype

        try:
            score = Decimal(str(payload.get("confidence", 0))).quantize(Decimal("0.0001"))
        except Exception:                     # noqa: BLE001
            score = Decimal("0")
        score = max(Decimal("0"), min(Decimal("1"), score))

        evidence = payload.get("evidence") or []
        terms = tuple(str(e)[:120] for e in evidence if str(e).strip())[:6]

        traits = getattr(row, "key_traits", None) or {}
        return ArchetypeMatch(
            archetype_id=getattr(row, "archetype_id"),
            code=code,
            name=getattr(row, "archetype_name", None) or getattr(row, "name", ""),
            core_motivation=traits.get("core_motivation"),
            score=score,
            matched_terms=terms,
            is_confident=score >= _CONFIDENT_AT,
            assigned_by="llm",
        )
