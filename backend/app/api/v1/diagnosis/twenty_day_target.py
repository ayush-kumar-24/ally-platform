"""PRIORITIZED GAPS + ELIGIBLE INTERVENTIONS -> ONE 20-DAY EXECUTION TARGET.

WHAT THIS MODULE DOES, EXACTLY: picks the highest-priority gap the library can
actually act on, attaches the existing intervention that acts on it, and states
what "done" looks like in 20 days. One focused outcome, not a to-do list and
not a roadmap. Everything it emits is COPIED from reference data -- the
capability, the intervention's own next steps, the capability's own evidence
criteria. Nothing in the deterministic core is composed, phrased or invented.

    PrioritizedCapabilityGap[]        [Step 9A]
    GapInterventionSelection          [Step 9B]
              |
              v
      first ACTIONABLE gap by rank            <- selection, not scoring
              |
              v
      TwentyDayTarget  |  NO_ACTIONABLE_TARGET

WHY EVERY FIELD IS DETERMINISTIC. The library turned out to carry all four
things a target needs, so none of them needs a model:

    objective   `capabilities.capability_name` + `.description`. The capability
                IS the outcome -- "Repeatable Sales System", "A defined,
                teachable sales process rather than a series of
                improvisations." Verbatim reference data.
    actions     `interventions.immediate_next_steps`. Populated on 417/417 rows,
                1-4 concrete steps each. Copied verbatim, exactly as the
                existing recommendation engine already copies them into
                `Recommendation.next_actions`.
    success     `capability_evidence_criteria`. Exactly 4 per capability, 136 in
                all, written as observable statements ("A sales process exists
                and is written down", "A new seller could follow the process
                without the founder"). They answer "did this happen?" directly.
    horizon     20 days. Fixed.

NO SECOND EVIDENCE TAXONOMY. Success criteria ARE the Step 5 evidence criteria,
carried with their `criterion_id`s. That is what closes the loop: the target
tells the founder which criteria to produce evidence for, and the NEXT
diagnosis's Step 7B extractor cites those same criterion_ids when it reads
their next answers. One vocabulary end to end, not two.

TARGET IS NOT ACTION. The target is the capability outcome; the actions are the
intervention's steps toward it. "Write a document" is never the target unless
documentation is itself the capability -- which is why the outcome is read off
the CAPABILITY and the steps off the INTERVENTION, from different tables, and
never conflated.

COMPLETION IS NOT EVIDENCE. Nothing here mutates `current_level` or writes
`capability_evidence`. A founder finishing the 20 days does not upgrade their
capability; only a later answer, read by Step 7B, can do that. This module
performs no write of any kind.

NO PROMISE OF A LEVEL. `current_level` and `required_level` are carried for
context, and the target moves toward the requirement. It never asserts the
founder will reach `required_level` in 20 days, because only later evidence
could establish that.

DETERMINISTIC CORE, OPTIONAL GENERATIVE EDGE. Layer A (this module's functions)
decides which gap, which capability, which intervention, which criteria, what
was skipped and why -- all without a model. Layer B (`TargetNarrator`) may
only rephrase. It is structurally incapable of changing a decision:
`TargetNarration` carries no capability id, no intervention id, no level and no
criterion id, so there is nothing in it that could redirect the target. A
narrator that raises leaves the structured target exactly as it was.

THE HORIZON IS 20 DAYS AND IS NOT CONFIGURABLE. No plan object in this codebase
carries a duration field -- the planning domain dates individual tasks, and the
report's "Your next 2 weeks" is a heading string -- so nothing in the existing
architecture asks for a generic horizon here. `target_time_horizon` (Step 6) is
a DIFFERENT concept: the founder's 6/12-month ambition, used as a lookup key
for which requirements apply, never an execution window.

NO BILLING. The engine knows nothing about plans, tiers or prices. Entitlement
in this codebase is enforced at the router by a FastAPI dependency
(`app/api/v1/entitlement_gates.py`: "APPLIED AT THE ROUTER, NOT PER ENDPOINT"),
and no diagnosis engine checks it. All three paid plans consume this same
engine unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Protocol, Sequence

from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.gap_intervention import GapInterventionSelection
from app.api.v1.diagnosis.gap_priority import PrioritizedCapabilityGap
from app.core.logger import logger

#: The execution window. Fixed by the product, not configurable -- see the
#: module docstring. There is deliberately no 30/60/90-day variant.
HORIZON_DAYS = 20

TARGET_SELECTED = "target_selected"
#: No prioritized gap had an eligible intervention. The honest answer, with the
#: gaps considered attached -- never a fabricated target.
NO_ACTIONABLE_TARGET = "no_actionable_target"


def _row_get(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


@dataclass(frozen=True)
class TargetAction:
    """One step, copied verbatim from the selected intervention. `sequence` is
    the library's own ordering, not a re-prioritization."""

    sequence: int
    action: str
    source_intervention_id: int


@dataclass(frozen=True)
class SuccessCriterion:
    """An observable completion statement, copied verbatim from
    `capability_evidence_criteria` -- the SAME criterion Step 7B cites when it
    records evidence, carried with its id so the loop can close."""

    criterion_id: int
    criterion_order: int
    criterion_text: str


@dataclass(frozen=True)
class SkippedGap:
    """A gap that outranked the selected one but had nothing to act on. Kept so
    the founder's most urgent problem never silently disappears from the
    record just because the library cannot serve it yet."""

    capability_id: int
    capability_code: str
    gap_rank: int
    gap_size: int
    necessity: str
    reason: str
    excluded_intervention_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class TargetNarration:
    """Layer B output. Deliberately carries NO identifier of any kind -- no
    capability id, no intervention id, no level, no criterion id -- so a
    narrator is structurally unable to change what was selected. It may only
    say the same thing in better words."""

    focus: str
    why_now: str
    actions: tuple[str, ...]
    success: str


class TargetNarrator(Protocol):
    """Optional founder-friendly phrasing. May return None; may raise. Either
    way the structured target stands unchanged."""

    def narrate(self, target: "TwentyDayTarget") -> TargetNarration | None: ...


@dataclass(frozen=True)
class TwentyDayTarget:
    """One focused outcome for the next 20 days, and its complete provenance.

    Every string on this object other than `narration` is reference data copied
    from `capabilities`, `interventions` or `capability_evidence_criteria`."""

    # --- the outcome, read off the CAPABILITY (never the intervention) -------
    primary_capability_id: int
    primary_capability_code: str
    #: `capabilities.capability_name`, e.g. "Repeatable Sales System".
    primary_capability_name: str
    #: `capabilities.description` -- an outcome statement in the library's own
    #: words, e.g. "A defined, teachable sales process rather than a series of
    #: improvisations." Not composed here.
    target_outcome: str

    # --- why this one, carried unchanged from Steps 8 and 9A ----------------
    current_level: CapabilityLevel
    required_level: CapabilityLevel
    gap_size: int
    necessity: str
    gap_rank: int

    # --- how, read off the INTERVENTION -------------------------------------
    source_intervention_id: int
    source_intervention_code: str
    source_section: str
    actions: tuple[TargetAction, ...]

    # --- what "done" looks like ---------------------------------------------
    success_criteria: tuple[SuccessCriterion, ...]

    # --- traceability --------------------------------------------------------
    #: Step 6's winning requirement row.
    requirement_id: int | None
    #: Step 7B evidence ids behind `current_level`.
    supporting_evidence_ids: tuple[int, ...]
    #: Every gapped capability the selected intervention builds. The primary is
    #: always among them; a second appears only when ONE intervention genuinely
    #: addresses two live gaps -- unrelated gaps are never bundled.
    supporting_capability_ids: tuple[int, ...]

    horizon_days: int = HORIZON_DAYS
    narration: TargetNarration | None = None

    @property
    def is_joint(self) -> bool:
        return len(self.supporting_capability_ids) > 1


@dataclass(frozen=True)
class TwentyDayTargetResult:
    """The target, or an explicit statement that there could not be one."""

    status: str
    target: TwentyDayTarget | None
    #: Higher-priority gaps passed over for want of an eligible intervention.
    #: On NO_ACTIONABLE_TARGET this is every gap considered.
    skipped_gaps: tuple[SkippedGap, ...]
    considered_gap_count: int

    @property
    def has_target(self) -> bool:
        return self.target is not None


def _skipped(gap: PrioritizedCapabilityGap, selection: GapInterventionSelection) -> SkippedGap:
    """Why this gap could not be acted on, taken from Step 9B's own finding
    rather than re-derived."""
    uncovered = next(
        (u for u in selection.uncovered if u.capability_id == gap.capability_id), None
    )
    return SkippedGap(
        capability_id=gap.capability_id,
        capability_code=gap.capability_code,
        gap_rank=gap.rank,
        gap_size=gap.gap_size,
        necessity=gap.necessity,
        reason=uncovered.reason if uncovered is not None else "not_actionable",
        excluded_intervention_ids=(
            uncovered.excluded_intervention_ids if uncovered is not None else ()
        ),
    )


def build_twenty_day_target(
    gaps: Sequence[PrioritizedCapabilityGap],
    selection: GapInterventionSelection,
    capability_detail: Mapping[int, Any],
    criteria_by_capability: Mapping[int, Sequence[Any]],
    steps_by_intervention: Mapping[int, Sequence[str]],
) -> TwentyDayTargetResult:
    """Layer A. Pure: no database handle, no write, no model call.

    Walks Step 9A's ordering and takes the FIRST gap Step 9B could serve. Gaps
    that outrank it but had no eligible intervention are preserved as
    `skipped_gaps` -- they are not deleted and not fabricated around.
    """
    ordered = sorted(gaps, key=lambda g: g.rank)
    actionable = selection.covered_capability_ids

    skipped: list[SkippedGap] = []
    primary: PrioritizedCapabilityGap | None = None
    for gap in ordered:
        if gap.capability_id in actionable:
            primary = gap
            break
        skipped.append(_skipped(gap, selection))

    if primary is None:
        # Every prioritized gap was unserviceable. Say so, with the record.
        logger.info(
            "no actionable 20-day target",
            extra={"stage": "twenty_day_target", "gaps": len(ordered)},
        )
        return TwentyDayTargetResult(
            status=NO_ACTIONABLE_TARGET, target=None,
            skipped_gaps=tuple(skipped), considered_gap_count=len(ordered),
        )

    # Step 9B already ordered candidates by (best_gap_rank, intervention_id).
    # Taking the first that serves the primary capability introduces no new
    # ordering signal -- there is none in the library to introduce.
    candidate = next(
        c for c in selection.candidates
        if primary.capability_id in c.supporting_capability_ids
    )

    detail = capability_detail.get(primary.capability_id)
    steps = tuple(steps_by_intervention.get(candidate.intervention_id, ()))
    criteria = tuple(criteria_by_capability.get(primary.capability_id, ()))

    target = TwentyDayTarget(
        primary_capability_id=primary.capability_id,
        primary_capability_code=primary.capability_code,
        primary_capability_name=str(_row_get(detail, "capability_name") or primary.capability_code),
        target_outcome=str(_row_get(detail, "description") or ""),
        current_level=primary.current_level,
        required_level=primary.required_level,
        gap_size=primary.gap_size,
        necessity=primary.necessity,
        gap_rank=primary.rank,
        source_intervention_id=candidate.intervention_id,
        source_intervention_code=candidate.intervention_code,
        source_section=candidate.section,
        actions=tuple(
            TargetAction(sequence=index, action=str(step),
                         source_intervention_id=candidate.intervention_id)
            for index, step in enumerate(steps, start=1)
        ),
        success_criteria=tuple(
            SuccessCriterion(
                criterion_id=int(_row_get(row, "criterion_id")),
                criterion_order=int(_row_get(row, "criterion_order")),
                criterion_text=str(_row_get(row, "criterion_text")),
            )
            for row in sorted(criteria, key=lambda r: int(_row_get(r, "criterion_order")))
        ),
        requirement_id=primary.requirement_id,
        supporting_evidence_ids=primary.supporting_evidence_ids,
        supporting_capability_ids=candidate.supporting_capability_ids,
    )

    logger.info(
        "20-day target selected",
        extra={
            "stage": "twenty_day_target",
            "capability": primary.capability_code,
            "intervention_id": candidate.intervention_id,
            "gap_rank": primary.rank,
            "skipped": len(skipped),
            "actions": len(target.actions),
            "criteria": len(target.success_criteria),
        },
    )
    return TwentyDayTargetResult(
        status=TARGET_SELECTED, target=target,
        skipped_gaps=tuple(skipped), considered_gap_count=len(ordered),
    )


def narrate_target(
    result: TwentyDayTargetResult, narrator: TargetNarrator | None,
) -> TwentyDayTargetResult:
    """Layer B, applied as a strictly additive step.

    Fail-open by construction: a narrator that raises, returns None, or returns
    the wrong number of action lines leaves the structured target untouched.
    Nothing it returns can redirect the target, because `TargetNarration`
    carries no identifier to redirect it with.
    """
    if narrator is None or result.target is None:
        return result
    try:
        narration = narrator.narrate(result.target)
    except Exception:                                          # noqa: BLE001
        logger.warning("target narration failed; structured target stands",
                       extra={"stage": "twenty_day_target"})
        return result
    if narration is None:
        return result
    if len(narration.actions) != len(result.target.actions):
        # A narrator that drops or adds steps is rewriting the intervention,
        # which is Layer A's decision and not its to make.
        logger.warning("target narration changed the action count; discarded",
                       extra={"stage": "twenty_day_target"})
        return result
    return replace(result, target=replace(result.target, narration=narration))
