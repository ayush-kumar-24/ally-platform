"""Recommendation Engine -- ranked root causes -> interventions.

Deterministic and grounded in the authoritative ranking:

  * Interventions are matched to the ranked root causes through
    interventions.root_cause_ids (which stores root-cause CODES, e.g. "RC-001",
    resolved from root_causes.root_cause_code -- NOT integer ids).
  * Each matched intervention is filtered by stage and industry relevance via an
    injectable strategy (default: membership over the stage_relevance int array
    and industry_relevance string array, treating empty / "all" as universal).
  * priority, confidence and ordering derive ONLY from the ranked ScoredRootCause
    inputs and relevance. Retrieval evidence is attached as supporting context
    and NEVER changes selection or order (requirement 3).

recommendation_type is SOLVE for a confirmed lead cause, CONFIRM otherwise --
producing the recommendation is this engine's job; assembling a report from these
is report generation's (kept separate, requirement 5).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol, runtime_checkable

from app.api.v1.reasoning.interfaces import (
    ReasoningContext,
    RecommendationEngine,
)
from app.api.v1.reasoning.repository import ReasoningRepository
from app.core.logger import logger
from app.api.v1.reasoning.schemas import (
    Recommendation,
    RecommendationResult,
    RecommendationType,
    ScoredRootCause,
)
from app.models.enums import ConfirmationStatus
from app.services.retrieval.evidence import RetrievalEvidence

_QUANT = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")
_UNIVERSAL_INDUSTRY = "all"


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


@runtime_checkable
class InterventionRelevanceStrategy(Protocol):
    """Decides whether an intervention applies to a founder's stage and industry.

    Injectable so the relevance semantics can change without touching the engine.
    """

    def is_relevant(
        self,
        *,
        stage_relevance: Sequence[int] | None,
        industry_relevance: Sequence[str] | None,
        stage_id: int | None,
        industry_code: str | None,
    ) -> bool: ...


class DefaultInterventionRelevance:
    """Membership relevance, matching the seeded data shapes.

    stage_relevance is an int array of stage_ids; industry_relevance is a string
    array of industry codes or ["all"]. Empty relevance, an "all" marker, or an
    unknown founder stage/industry are treated as relevant rather than excluded --
    a missing filter should not silently drop a valid intervention.
    """

    def is_relevant(
        self,
        *,
        stage_relevance: Sequence[int] | None,
        industry_relevance: Sequence[str] | None,
        stage_id: int | None,
        industry_code: str | None,
    ) -> bool:
        stages = list(stage_relevance or [])
        stage_ok = not stages or stage_id is None or stage_id in stages

        industries = list(industry_relevance or [])
        industry_ok = (
            not industries
            or _UNIVERSAL_INDUSTRY in industries
            or industry_code is None
            or industry_code in industries
        )
        return stage_ok and industry_ok


class StandardRecommendationEngine(RecommendationEngine):
    def __init__(
        self,
        repository: ReasoningRepository,
        relevance: InterventionRelevanceStrategy | None = None,
        llm_fallback=None,
    ):
        self.repository = repository
        self.relevance = relevance or DefaultInterventionRelevance()
        #: Optional. Fills root causes the curated library does not cover; see
        #: recommendation_llm.LLMRecommendationFallback. None => uncovered causes
        #: produce nothing, which is the behaviour that predates it.
        self.llm_fallback = llm_fallback

    def recommend(
        self,
        ranked_root_causes: list[ScoredRootCause],
        context: ReasoningContext,
        *,
        semantic_evidence: Mapping[int, Sequence[RetrievalEvidence]] | None = None,
    ) -> RecommendationResult:
        if not ranked_root_causes:
            return RecommendationResult(())

        semantic = semantic_evidence or {}

        # Resolve root_cause_id -> code (interventions match on codes).
        root_causes = self.repository.get_root_causes_by_ids(
            s.root_cause_id for s in ranked_root_causes
        )
        code_to_scored: dict[str, ScoredRootCause] = {}
        for scored in ranked_root_causes:
            rc = root_causes.get(scored.root_cause_id)
            if rc is not None and rc.root_cause_code:
                # Keep the better-ranked cause if a code somehow repeats.
                existing = code_to_scored.get(rc.root_cause_code)
                if existing is None or scored.rank < existing.rank:
                    code_to_scored[rc.root_cause_code] = scored
        if not code_to_scored:
            return RecommendationResult(())

        interventions = self.repository.get_interventions_by_root_cause_codes(
            list(code_to_scored)
        )
        industry_code = self._industry_code(context)

        scored_recs: list[tuple[Decimal, Recommendation]] = []
        for intervention in interventions:
            supporting = self._supporting_causes(intervention, code_to_scored)
            if not supporting:
                continue
            if not self.relevance.is_relevant(
                stage_relevance=intervention.stage_relevance,
                industry_relevance=intervention.industry_relevance,
                stage_id=context.stage_id,
                industry_code=industry_code,
            ):
                continue

            raw_score = max(s.final_weighted_score for s in supporting)
            recommendation = self._build(intervention, supporting, semantic, raw_score)
            scored_recs.append((raw_score, recommendation))

        # Deterministic ordering: best supporting rank first, then stronger raw
        # score, then intervention_id -- independent of DB return order and of
        # semantic evidence.
        scored_recs.sort(key=lambda pair: (pair[1].priority, -pair[0], pair[1].intervention_id))
        recommendations = [rec for _raw, rec in scored_recs]

        # Fill library gaps, if a fallback is wired. Runs last and only for causes
        # the deterministic pass left with nothing, so a curated intervention can
        # never be displaced by a generated one.
        if self.llm_fallback is not None:
            covered = {
                rc_id
                for rec in recommendations
                for rc_id in rec.supporting_root_causes
            }
            uncovered = [
                (code, scored, getattr(root_causes.get(scored.root_cause_id), "root_cause_name", ""))
                for code, scored in code_to_scored.items()
                if scored.root_cause_id not in covered
            ]
            if uncovered:
                uncovered.sort(key=lambda t: t[1].rank)   # best-ranked gaps first
                logger.info("Recommendation library gaps",
                            extra={"uncovered": len(uncovered)})
                recommendations.extend(self.llm_fallback.fill(
                    uncovered,
                    stage_name=getattr(context, "stage_name", None),
                    industry=industry_code,
                ))
                # Re-sort so generated entries land by the same rule as the rest;
                # a gap-filler for rank 1 belongs above a library row for rank 4.
                recommendations.sort(key=lambda r: (r.priority, r.intervention_id))

        return RecommendationResult(tuple(recommendations))

    # --- Internals --------------------------------------------------------

    def _supporting_causes(
        self, intervention, code_to_scored: dict[str, ScoredRootCause]
    ) -> list[ScoredRootCause]:
        codes = intervention.root_cause_ids or []
        supporting = [code_to_scored[c] for c in codes if c in code_to_scored]
        supporting.sort(key=lambda s: s.rank)
        return supporting

    def _build(
        self,
        intervention,
        supporting: list[ScoredRootCause],
        semantic: Mapping[int, Sequence[RetrievalEvidence]],
        raw_score: Decimal,
    ) -> Recommendation:
        lead = supporting[0]  # best-ranked supporting cause
        rec_type = (
            RecommendationType.SOLVE
            if lead.confirmation_status == ConfirmationStatus.CONFIRMED
            else RecommendationType.CONFIRM
        )
        evidence = self._collect_evidence(supporting, semantic)
        next_actions = tuple(
            str(step) for step in (intervention.immediate_next_steps or [])
        )
        return Recommendation(
            intervention_id=intervention.intervention_id,
            recommendation_type=rec_type,
            priority=lead.rank,
            confidence=_q(max(_ZERO, min(_ONE, raw_score))),
            supporting_root_causes=tuple(s.root_cause_id for s in supporting),
            supporting_retrieval_evidence=evidence,
            rationale=self._rationale(intervention, supporting, rec_type, evidence),
            next_actions=next_actions,
            intervention_code=intervention.intervention_code,
            section=intervention.section,
        )

    def _collect_evidence(
        self,
        supporting: list[ScoredRootCause],
        semantic: Mapping[int, Sequence[RetrievalEvidence]],
    ) -> tuple[RetrievalEvidence, ...]:
        """Flatten the supporting causes' semantic evidence in rank order,
        de-duplicated by (source, source_id), preserving first occurrence."""
        seen: set[tuple[str, int]] = set()
        collected: list[RetrievalEvidence] = []
        for cause in supporting:
            for ev in semantic.get(cause.root_cause_id, ()):  # type: ignore[union-attr]
                key = (ev.source.value, ev.source_id)
                if key in seen:
                    continue
                seen.add(key)
                collected.append(ev)
        return tuple(collected)

    def _rationale(
        self,
        intervention,
        supporting: list[ScoredRootCause],
        rec_type: RecommendationType,
        evidence: tuple[RetrievalEvidence, ...],
    ) -> str:
        lead = supporting[0]
        base = (
            f"{rec_type.value.capitalize()} recommendation addressing "
            f"{len(supporting)} ranked root cause(s); lead cause ranked "
            f"#{lead.rank} ({lead.confirmation_status.value}) in section "
            f"'{intervention.section}'."
        )
        if evidence:
            base += f" Supported by {len(evidence)} semantic evidence item(s)."
        return base

    def _industry_code(self, context: ReasoningContext) -> str | None:
        if context.industry_id is None:
            return None
        industry = self.repository.get_industry(context.industry_id)
        return industry.industry_code if industry is not None else None
