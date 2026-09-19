"""PRIORITIZED CAPABILITY GAP -> EXISTING INTERVENTIONS. Selection, never creation.

WHAT THIS MODULE DOES, EXACTLY: for each `PrioritizedCapabilityGap` (Step 9A,
`status == GAP` only, already ordered), look up the interventions the curated
`intervention_capabilities` map says BUILD that capability, apply the
eligibility rules the repository already treats as authoritative, and return
the surviving intervention rows. It returns existing intervention ids and
existing content. It writes no intervention text, generates no prose, invents
no action, and calls no model.

THE INTERVENTION LIBRARY IS THE SOURCE OF TRUTH. A gap with no eligible
intervention returns `NO_INTERVENTION_AVAILABLE` and says why -- never a
fabricated suggestion. That outcome is a real, reportable content gap (Step 5
already flagged `GTM-OWN` at 2 interventions, `FND-INDEP` at 3, `OPS-QUALITY`
at 4), and surfacing it honestly is the point.

    PrioritizedCapabilityGap[]            [Step 9A, untouched]
              |
              v
    intervention_capabilities             curated map, 354 pairs / 328 interventions
              |
              v
    eligibility (stage, industry)         the EXISTING relevance strategy, reused verbatim
              |
              v
    InterventionCandidate[] + UncoveredGap[]

ELIGIBILITY IS NOT REIMPLEMENTED HERE. `DefaultInterventionRelevance`
(app/api/v1/reasoning/engines/recommendation.py) is the repository's existing,
documented, injectable relevance test over `interventions.stage_relevance` and
`interventions.industry_relevance`. It is called, not copied -- this module
contains no membership predicate of its own, so the two consumers of the
intervention library can never drift into disagreeing about what "relevant"
means. Its semantics, verified against the live library before this module was
written:

    stage_relevance     int array of stage_ids, populated on 417/417 rows and
                        genuinely discriminating (14 distinct arrays over
                        stages 1-8). Fails OPEN: an empty array, or an unknown
                        founder stage, includes.
    industry_relevance  string array of industry codes or ["all"], populated on
                        417/417 but universal on 412 of them. Fails OPEN when
                        the INTERVENTION is unrestricted; fails CLOSED only
                        when the intervention declares itself non-universal AND
                        the founder's industry is unknown -- a deliberate
                        product decision made by the existing engine after a
                        B2B logistics founder was handed SaaS-presupposing
                        steps. Reusing the strategy means inheriting that
                        decision rather than writing a second, quietly
                        different industry rule.

An intervention's OWN metadata is what is consulted. Nothing is inherited from
the question side: `questions.industry_relevance` is authoritative for whether
a QUESTION may be asked (industry_scope.py) and says nothing about whether an
ACTION applies, so no question-level eligibility crosses into this module.

NO BUSINESS-MODEL FILTER EXISTS, AND NONE IS INVENTED. `interventions` has no
business-model column -- verified column by column against the live schema.
`business_model` exists in this system only on `founders` and on
`capability_requirements`, which means business-model context already acted
UPSTREAM, on which capability is required at all (Step 6's resolver), and has
no authoritative expression at the intervention layer. So this module applies
no business-model test: an unknown business model admits nothing it would not
otherwise admit, and a known one excludes nothing, because there is no
metadata that could justify either. The limitation is reported rather than
papered over -- see docs/GAP-INTERVENTION-SELECTION.md.

NO ROOT-CAUSE JOIN IS INVENTED. There is still no `capability_id <->
root_cause_id` relationship anywhere in this codebase (confirmed again here).
The existing recommendation engine reaches interventions through
`interventions.root_cause_ids` (a jsonb array of root-cause CODES); this module
reaches them through `intervention_capabilities`. Two independent doors into
the same library, sharing only the relevance test. Neither is rewritten.

ONE INTERVENTION, MANY GAPS. 26 of the 328 mapped interventions build two
capabilities each. When both are live gaps, the result is ONE candidate
carrying BOTH supporting gaps -- never the same intervention returned twice as
two unrelated objects, which would lose exactly the relationship that makes it
worth surfacing. Each supporting gap keeps its own rank, gap_size and
necessity.

NO NEW SCORE. Candidates inherit gap priority (the rank of the best-ranked gap
they serve) and are otherwise ordered by `intervention_id`, because no
defensible ordering signal exists among interventions for one capability: the
library has no priority column, `section` and `capability_domain` are
descriptive, and the recommendation engine's own ordering is derived from
root-cause rank, which has no capability join to borrow. A stable identifier
beats an invented weight.

DETERMINISTIC: pure Python over already-fetched rows. No model call, no
embedding, no retrieval, no randomness. Read-only: this module issues no
query and performs no write of any kind.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.api.v1.diagnosis.gap_priority import PrioritizedCapabilityGap
from app.core.logger import logger

#: A candidate that survived every authoritative eligibility test.
ELIGIBLE = "eligible"

#: The one honest answer when the library has nothing to offer for a gap.
#: Never replaced by a generated suggestion.
NO_INTERVENTION_AVAILABLE = "no_intervention_available"

#: Why a gap is uncovered. The distinction matters for content-gap analysis:
#: the first is a LIBRARY gap (nothing was ever written, or nothing was mapped),
#: the second is a FIT gap (content exists but does not apply to this founder).
REASON_NO_MAPPED_INTERVENTION = "no_mapped_intervention"
REASON_ALL_CANDIDATES_FILTERED = "all_candidates_filtered"


def _row_get(row: Any, name: str) -> Any:
    """Read a field off a row that may be an ORM object, a mapping or a double."""
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


@dataclass(frozen=True)
class SupportedGap:
    """The gap that caused an intervention to be selected, with the priority
    context Step 9A established carried through unchanged. Attached per gap, so
    an intervention serving two gaps keeps BOTH of their priorities rather than
    collapsing them into one."""

    capability_id: int
    capability_code: str
    #: `PrioritizedCapabilityGap.rank` -- the gap's position in Step 9A's
    #: ordering. Not recomputed here; intervention priority is not gap priority.
    gap_rank: int
    gap_size: int
    necessity: str


@dataclass(frozen=True)
class InterventionCandidate:
    """One EXISTING intervention, and the gapped capabilities it builds.

    Carries the library's own identifiers and metadata. There is no field here
    for generated text, no rationale prose, and no score -- this object says
    "this existing intervention is relevant to these gaps", nothing more."""

    intervention_id: int
    intervention_code: str
    section: str
    #: Every live gap this ONE intervention addresses, ordered by gap rank.
    supporting_gaps: tuple[SupportedGap, ...]
    eligibility: str
    #: What was actually checked, so "why is this here" needs no re-derivation.
    eligibility_reasons: tuple[str, ...]

    @property
    def supporting_capability_ids(self) -> tuple[int, ...]:
        return tuple(g.capability_id for g in self.supporting_gaps)

    @property
    def supporting_capability_codes(self) -> tuple[str, ...]:
        return tuple(g.capability_code for g in self.supporting_gaps)

    @property
    def best_gap_rank(self) -> int:
        """The rank of the highest-priority gap this intervention serves. The
        inherited gap priority -- NOT a new intervention score."""
        return min(g.gap_rank for g in self.supporting_gaps)


@dataclass(frozen=True)
class UncoveredGap:
    """A real gap the existing library cannot currently address. Deliberately
    rich enough for content-gap analysis, and deliberately empty of advice."""

    capability_id: int
    capability_code: str
    gap_rank: int
    gap_size: int
    necessity: str
    reason: str
    status: str = NO_INTERVENTION_AVAILABLE
    #: Interventions mapped to this capability that did NOT survive eligibility.
    #: Empty when nothing was mapped at all -- the two reasons are distinguishable
    #: from this field alone.
    excluded_intervention_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class GapInterventionSelection:
    """Candidates and uncovered gaps, kept side by side on purpose: a caller
    that reads only the candidates would silently lose the content gaps, which
    are the finding most worth acting on."""

    candidates: tuple[InterventionCandidate, ...]
    uncovered: tuple[UncoveredGap, ...]

    @property
    def covered_capability_ids(self) -> frozenset[int]:
        return frozenset(
            cid for c in self.candidates for cid in c.supporting_capability_ids
        )

    @property
    def uncovered_capability_ids(self) -> frozenset[int]:
        return frozenset(u.capability_id for u in self.uncovered)


def _default_relevance():
    """The existing, injectable relevance strategy -- imported lazily so this
    module can be read and tested without pulling the reasoning package in."""
    from app.api.v1.reasoning.engines.recommendation import DefaultInterventionRelevance

    return DefaultInterventionRelevance()


def select_interventions_for_gaps(
    gaps: Sequence[PrioritizedCapabilityGap],
    interventions_by_capability: Mapping[int, Sequence[Any]],
    *,
    stage_id: int | None,
    industry_code: str | None,
    relevance: Any = None,
) -> GapInterventionSelection:
    """Step 9B. Pure: no database handle, no write, no model call.

    `interventions_by_capability` is `{capability_id: [intervention rows]}`,
    already fetched by the caller in one bounded query (see
    `DiagnosisRepository.interventions_for_capabilities`) so this function
    never issues a query of its own and cannot N+1.

    `stage_id` is a founder_stages.stage_id, NOT a stage_order. The two happen
    to coincide in today's seed data and that coincidence is not relied on --
    the caller resolves the id properly; `None` means unknown, which the
    relevance strategy treats as "do not filter on stage".
    """
    check = relevance if relevance is not None else _default_relevance()

    # One entry per intervention, not per (intervention, gap) pair -- this is
    # what keeps a two-capability intervention from being returned twice.
    supporting: dict[int, list[SupportedGap]] = {}
    rows_by_id: dict[int, Any] = {}
    ineligible: set[int] = set()
    excluded_by_capability: dict[int, list[int]] = {}
    mapped_count_by_capability: dict[int, int] = {}

    for gap in gaps:
        rows = tuple(interventions_by_capability.get(gap.capability_id, ()))
        mapped_count_by_capability[gap.capability_id] = len(rows)
        for row in rows:
            intervention_id = int(_row_get(row, "intervention_id"))
            # Eligibility depends only on the founder and the intervention, not
            # on the gap, so an intervention reached through two gaps is
            # evaluated ONCE and necessarily gets the same verdict both times.
            if intervention_id not in rows_by_id and intervention_id not in ineligible:
                if check.is_relevant(
                    stage_relevance=_row_get(row, "stage_relevance"),
                    industry_relevance=_row_get(row, "industry_relevance"),
                    stage_id=stage_id,
                    industry_code=industry_code,
                ):
                    rows_by_id[intervention_id] = row
                else:
                    ineligible.add(intervention_id)
            if intervention_id in ineligible:
                excluded_by_capability.setdefault(gap.capability_id, []).append(
                    intervention_id
                )
                continue
            supporting.setdefault(intervention_id, []).append(
                SupportedGap(
                    capability_id=gap.capability_id,
                    capability_code=gap.capability_code,
                    gap_rank=gap.rank,
                    gap_size=gap.gap_size,
                    necessity=gap.necessity,
                )
            )

    reasons = (
        f"stage_id={stage_id if stage_id is not None else 'unknown'}",
        f"industry_code={industry_code or 'unknown'}",
        "filters=stage_relevance,industry_relevance",
        "no business-model test applied: the library carries no such metadata",
    )
    candidates = [
        InterventionCandidate(
            intervention_id=intervention_id,
            intervention_code=str(_row_get(rows_by_id[intervention_id], "intervention_code")),
            section=str(_row_get(rows_by_id[intervention_id], "section") or ""),
            supporting_gaps=tuple(sorted(gap_list, key=lambda g: (g.gap_rank, g.capability_id))),
            eligibility=ELIGIBLE,
            eligibility_reasons=reasons,
        )
        for intervention_id, gap_list in supporting.items()
    ]
    # Gap priority is inherited, never recomputed: the best-ranked gap an
    # intervention serves decides where it sits, and intervention_id -- a stable
    # identifier, not an invented weight -- breaks every tie.
    candidates.sort(key=lambda c: (c.best_gap_rank, c.intervention_id))

    covered = {cid for c in candidates for cid in c.supporting_capability_ids}
    uncovered = tuple(
        UncoveredGap(
            capability_id=gap.capability_id,
            capability_code=gap.capability_code,
            gap_rank=gap.rank,
            gap_size=gap.gap_size,
            necessity=gap.necessity,
            reason=(
                REASON_ALL_CANDIDATES_FILTERED
                if mapped_count_by_capability.get(gap.capability_id)
                else REASON_NO_MAPPED_INTERVENTION
            ),
            excluded_intervention_ids=tuple(
                sorted(excluded_by_capability.get(gap.capability_id, ()))
            ),
        )
        for gap in sorted(gaps, key=lambda g: g.rank)
        if gap.capability_id not in covered
    )

    if gaps:
        logger.info(
            "capability gap interventions selected",
            extra={
                "stage": "gap_intervention",
                "gaps": len(gaps),
                "candidates": len(candidates),
                "uncovered": len(uncovered),
                "multi_capability_candidates": sum(
                    1 for c in candidates if len(c.supporting_gaps) > 1
                ),
            },
        )
    return GapInterventionSelection(candidates=tuple(candidates), uncovered=uncovered)
