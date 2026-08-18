"""LLM fallback for root causes the intervention library does not cover.

The Recommendation Engine matches detected root causes to curated `interventions`
rows and filters those by stage/industry relevance. Anything left over produced
nothing at all: the cause was detected, ranked, shown as a finding, and then the
founder was told nothing about what to do with it. Silently -- there was no
signal that a gap had been hit rather than that no action was warranted.

This fills those gaps only. It runs AFTER the deterministic pass and only for
causes that came out of it empty:

  * It cannot displace a library recommendation. If the library covered a cause,
    the curated row wins and the model is never asked about it.
  * It cannot change ranking. Priority and confidence still come from the root
    cause's own deterministic score, not from anything the model says. The model
    supplies wording, not standing.
  * Everything it produces is marked `source="llm"` with `intervention_id=0`,
    because there is no intervention row behind it. That marker is the point: a
    generated recommendation has not been reviewed and is not tied to anything,
    and it should be distinguishable by whoever reads or audits the report.

Fails open. If the model errors, times out, or returns something unusable, the
affected causes go back to producing nothing -- exactly the behaviour before this
existed. A diagnosis is never blocked on filling a library gap.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.api.v1.reasoning.schemas import (
    Recommendation,
    RecommendationType,
    ScoredRootCause,
)
from app.core.logger import logger
from app.models.enums import ConfirmationStatus
from app.services.llm.base import LLMMessage, LLMRequest, LLMRole
from app.services.llm.text import run_sync

_SYSTEM = (
    "You advise startup founders. You are given a root cause diagnosed in a "
    "founder's business for which no curated intervention exists. Write ONE "
    "practical recommendation they could start this week. Be concrete and "
    "specific to the cause; do not restate the problem, do not hedge, and do not "
    "invent facts about their business beyond what you are told. "
    "Reply with JSON only: "
    '{"rationale": "<2-3 sentences on why this addresses the cause>", '
    '"next_actions": ["<a specific action>", "<another>", "<another>"]}'
)

#: A gap-filler, not a report. Keeps one slow call from dominating the stage.
_MAX_GAPS = 5


class LLMRecommendationFallback:
    """Generates recommendations for uncovered root causes. Never replaces one."""

    def __init__(self, provider, *, timeout_seconds: float = 25.0,
                 temperature: float = 0.2, max_gaps: int = _MAX_GAPS):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        # Slightly above zero: this is prose for a human, and identical phrasing
        # across every founder who hits the same library gap reads as canned.
        self.temperature = temperature
        self.max_gaps = max_gaps

    def fill(
        self,
        uncovered: Sequence[tuple[str, ScoredRootCause, str]],
        *,
        stage_name: str | None = None,
        industry: str | None = None,
    ) -> tuple[Recommendation, ...]:
        """One recommendation per uncovered cause.

        `uncovered` is (root_cause_code, scored_cause, root_cause_name). Ordered
        by the caller; only the first `max_gaps` are attempted, because a founder
        reading their report needs the top gaps filled, not all of them.
        """
        out: list[Recommendation] = []
        for code, scored, name in list(uncovered)[: self.max_gaps]:
            try:
                payload = self._ask(name or code, stage_name, industry)
            # Broad on purpose. The module contract above is "fails open: a
            # diagnosis is never blocked on filling a library gap", and the
            # narrow tuple this used to catch did not honour it -- a RuntimeError
            # from the async seam sailed straight through and cost the founder
            # their entire report. Nothing this helper can raise is worth more
            # than the report it sits inside, so anything short of a cancellation
            # or interpreter shutdown (BaseException) degrades to "cause stays
            # uncovered", which is precisely the pre-fallback behaviour.
            except Exception as exc:
                logger.warning(
                    "Recommendation fallback failed; cause stays uncovered",
                    extra={
                        "root_cause_code": code,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                    exc_info=exc,
                )
                continue

            rationale = str(payload.get("rationale") or "").strip()
            actions = tuple(
                str(a).strip() for a in (payload.get("next_actions") or [])
                if str(a).strip()
            )[:5]
            if not rationale or not actions:
                # Half an answer is worse than none: a recommendation with no
                # actions is a paragraph the founder cannot act on.
                logger.warning("Recommendation fallback returned an unusable reply",
                               extra={"root_cause_code": code})
                continue

            # Same rule the deterministic engine uses: a confirmed cause gets
            # SOLVE (act now), anything else gets CONFIRM (validate first).
            # Mirrored rather than hardcoded so a generated recommendation cannot
            # tell a founder to act on a cause the diagnosis never confirmed.
            rec_type = (
                RecommendationType.SOLVE
                if getattr(scored, "confirmation_status", None) == ConfirmationStatus.CONFIRMED
                else RecommendationType.CONFIRM
            )

            out.append(Recommendation(
                intervention_id=0,             # no library row stands behind this
                recommendation_type=rec_type,
                # Ranking stays deterministic: the cause's own rank and score.
                priority=scored.rank,
                confidence=Decimal(str(scored.final_weighted_score)),
                supporting_root_causes=(scored.root_cause_id,),
                supporting_retrieval_evidence=(),
                rationale=rationale,
                next_actions=actions,
                intervention_code=None,
                section=None,
                source="llm",
            ))
        return tuple(out)

    def _ask(self, cause: str, stage_name: str | None, industry: str | None) -> dict:
        context_bits = [f"Root cause: {cause}"]
        if stage_name:
            context_bits.append(f"Founder's stage: {stage_name}")
        if industry:
            context_bits.append(f"Industry: {industry}")
        request = LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM),
                LLMMessage(role=LLMRole.USER, content="\n".join(context_bits)),
            ),
            temperature=self.temperature,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        # `run_sync`, not a bare `asyncio.run`: this is called from inside the
        # reasoning pipeline, which is `async def` and therefore already has a
        # running loop on this thread. `asyncio.run` raises "cannot be called
        # from a running event loop" there, and because RuntimeError was outside
        # this call's fail-open guard below, that escaped `fill` and rolled the
        # WHOLE diagnosis back -- a completed 30-answer session produced zero
        # founder_reports. Same sync-caller/async-provider seam, and the same
        # fix, as ReasoningTrigger and the report narrator.
        response = run_sync(
            asyncio.wait_for(self.provider.generate(request), self.timeout_seconds)
        )
        return json.loads(response.text)
