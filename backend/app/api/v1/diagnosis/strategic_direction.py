"""CURRENT CAPABILITY STATE + TARGET-STATE REQUIREMENTS -> CAPABILITY TRAJECTORY.

WHAT THIS MODULE DOES, EXACTLY: says which capabilities have to evolve for the
founder to become what they are trying to become, in what direction each one
must move, and in what order those moves are worth thinking about. It is a
description of a trajectory, assembled entirely from canonical taxonomy and
target-state reference data.

IT IS NOT A THREE-YEAR PLAN. There is no year, no quarter, no month, no date
and no milestone anywhere in this module, and there is no field on its output
that could hold one. The product calls this the "3-Year Strategic Direction"
because that is the horizon a founder is thinking on; the ENGINE attaches no
time to anything, because nothing in the data supports doing so. The only
horizon values this system holds are `target_time_horizon` (6 or 12 months --
a requirement lookup key, see Step 6) and Step 10A's fixed 20-day execution
window. Neither is three years, so a three-year schedule would be invented,
and inventing it is the single largest fabrication risk in this step.

    FounderContext + TargetStateContext
              |
    resolve_requirements(...)          [Step 6, called, never duplicated]
              |
    compute_capability_gaps(...)       [Step 8, consumed]
              |
    prioritize_capability_gaps(...)    [Step 9A, called for its ordering]
              |
              v
       StrategicDirection

EVERY WORD IS REFERENCE DATA. Nothing here is composed, phrased or inferred:

    what the capability is      `capabilities.capability_name` + `.description`
    where the founder is        `CapabilityLevel.label` for the assessed level
    where they need to be       `CapabilityLevel.label` for the required level
    why the destination needs it `capability_requirements.rationale` -- 55 rows,
                                55 distinct hand-authored explanations, one per
                                requirement. This is the strategic argument, and
                                it was written by a curator, not by this module.

THE DIRECTION IS THE LEVEL TRANSITION. The capability scale measures exactly
one axis -- founder dependence (absent -> founder-dependent -> documented ->
owned by someone else) -- so "what must change" is fully expressed by the move
from the current label to the required one. `transition_label` joins two
existing labels with an arrow. It asserts nothing the scale does not already
assert.

SEQUENCE IS ORDER, NOT DEPENDENCY. This is the rule this module guards hardest.
There is NO capability dependency, prerequisite or causal-relationship data
anywhere in this codebase -- no such table, no such column, no such mapping.
So `sequence` is a deterministic reading order and nothing more. It must never
be read as "this must happen before that". `CapabilityTrajectory` deliberately
carries no `depends_on`, no `prerequisite`, no `blocks` and no `phase`, so a
dependency claim is not representable here even by accident.

The ordering itself is Step 9A's, reused by calling it rather than restating
it: necessity first, then gap magnitude, then a stable capability_id
tie-break. That is items 1 and 2 of the brief's own permitted ordering list,
already implemented, already tested. `capability_domains.domain_order` was
inspected and rejected as the tie-break: Step 9A already established it is a
display ordinal rather than an importance ranking, and using it here would put
two contradicting orders in one product.

UNASSESSED IS NEVER PLACED ON THE TRAJECTORY. A capability the target state
requires but which the founder has no confident evidence for is named in
`unplaced` -- never given a direction, because a direction would require
asserting a current state nobody measured. This is the same rule Steps 7C, 8,
9A and 10A already hold: UNKNOWN is not a value.

SATISFIED CAPABILITIES PRODUCE NO DIRECTION either, whether the founder exactly
meets the requirement or exceeds it. There is nothing to evolve.

NO FABRICATED MILESTONES FROM THE DESTINATION. `target_revenue_band` and
`target_time_horizon` decide WHICH requirements apply, through Step 6's
resolver, and are carried on the output so the reader knows what destination
this was computed for. They are never turned into a number to hit or a date to
hit it by. A band of `5Cr_25Cr` selects requirements; it does not mean "reach
Rs 10Cr by month 18", and no code path here could say so.

AMBIGUITY IS PRESERVED, NOT RESOLVED. When Step 6's resolver finds two equally
specific requirement rows that disagree it raises rather than picking one. This
module reports that verbatim as `AMBIGUOUS_REQUIREMENTS` with the resolver's own
message. It never falls back to a guess, and it never silently drops the
capability.

NO BILLING. The engine knows nothing about plans, tiers or prices. All plans
that are shown a direction are shown one computed exactly this way; whether to
show it is decided at the router, which is where entitlement lives in this
codebase.

SEPARATE FROM STEP 10A. The 20-day target and the strategic direction read the
same capability state and neither depends on the other. Nothing here reads,
writes or waits on a 20-day target, and completing one changes nothing here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Protocol, Sequence

from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.gap_engine import STATUS_UNASSESSED, CapabilityGap
from app.api.v1.diagnosis.gap_priority import prioritize_capability_gaps
from app.api.v1.diagnosis.target_state import RequiredCapability, TargetStateContext
from app.core.logger import logger

#: A trajectory was produced.
DIRECTION_RESOLVED = "resolved"
#: Step 6 resolved no requirement at all for this destination, so there is no
#: target state to move toward. Today this is what an unknown target revenue
#: band produces: every seeded requirement row constrains at least the band,
#: so a founder who has not said where they are going has no resolvable
#: destination -- and saying so is the honest answer, not a generic direction.
NO_TARGET_CONTEXT = "no_target_context"
#: Two equally specific requirement rows disagree. Reported, never guessed.
AMBIGUOUS_REQUIREMENTS = "ambiguous_requirements"


def _row_get(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


@dataclass(frozen=True)
class CapabilityTrajectory:
    """One capability that has to evolve, and the evidence for saying so.

    Deliberately carries no `depends_on`, `prerequisite`, `blocks`, `phase`,
    `year` or `date` field: none of those is supported by any data in this
    system, so none of them is representable here."""

    capability_id: int
    capability_code: str
    capability_name: str
    #: `capabilities.description` -- what this capability is, verbatim.
    capability_description: str

    current_level: CapabilityLevel
    required_level: CapabilityLevel
    gap_size: int
    necessity: str
    #: `capability_requirements.rationale` -- why the DESTINATION needs this,
    #: verbatim from the winning requirement row. Authored by a curator.
    rationale: str

    #: Reading order only. NOT a dependency and NOT a schedule -- see the
    #: module docstring.
    sequence: int

    requirement_id: int | None
    supporting_evidence_ids: tuple[int, ...]

    @property
    def current_level_label(self) -> str:
        return self.current_level.label

    @property
    def required_level_label(self) -> str:
        return self.required_level.label

    @property
    def transition_label(self) -> str:
        """The direction, as a join of two existing labels. Asserts nothing the
        capability scale does not already assert."""
        return f"{self.current_level_label} -> {self.required_level_label}"

    @property
    def leaves_founder_dependence(self) -> bool:
        """True where the move crosses out of founder dependence -- the axis the
        scale itself measures, read rather than invented."""
        return self.current_level.is_founder_dependent and not self.required_level.is_founder_dependent


@dataclass(frozen=True)
class UnplacedRequirement:
    """The target state requires this, but there is no confident reading of
    where the founder is today, so no direction can be stated. Named, never
    placed -- a trajectory would mean asserting a current level nobody
    measured."""

    capability_id: int
    capability_code: str
    capability_name: str
    required_level: CapabilityLevel
    necessity: str
    rationale: str
    requirement_id: int | None

    @property
    def required_level_label(self) -> str:
        return self.required_level.label


@dataclass(frozen=True)
class DirectionNarration:
    """Optional founder-facing phrasing. Carries NO identifier, level, sequence
    or requirement id, so a narrator is structurally unable to change what the
    deterministic core selected. It may only say the same thing in better
    words."""

    summary: str
    trajectory_lines: tuple[str, ...]


class DirectionNarrator(Protocol):
    def narrate(self, direction: "StrategicDirection") -> DirectionNarration | None: ...


@dataclass(frozen=True)
class StrategicDirection:
    """The capability trajectory, or an explicit statement of why there is none."""

    status: str
    #: Ordered by Step 9A's priority. Order, not dependency, not schedule.
    trajectory: tuple[CapabilityTrajectory, ...]
    #: Required capabilities with no confident current reading.
    unplaced: tuple[UnplacedRequirement, ...]
    #: The destination this was computed for. Carried so the reader knows which
    #: requirements applied; never converted into a milestone.
    target: TargetStateContext
    #: Step 6's own message when two equally specific rules disagree.
    ambiguity: str | None = None
    narration: DirectionNarration | None = None

    @property
    def has_direction(self) -> bool:
        return bool(self.trajectory)

    @property
    def capability_ids(self) -> tuple[int, ...]:
        return tuple(t.capability_id for t in self.trajectory)


def ambiguous_direction(target: TargetStateContext, message: str) -> StrategicDirection:
    """Step 6 could not decide, so neither does this. The resolver's own message
    is carried verbatim rather than summarised into something vaguer."""
    logger.warning(
        "strategic direction blocked by ambiguous requirements",
        extra={"stage": "strategic_direction"},
    )
    return StrategicDirection(
        status=AMBIGUOUS_REQUIREMENTS, trajectory=(), unplaced=(),
        target=target, ambiguity=message,
    )


def build_strategic_direction(
    gaps: Sequence[CapabilityGap],
    requirements: Sequence[RequiredCapability],
    capability_detail: Mapping[int, Any],
    target: TargetStateContext,
) -> StrategicDirection:
    """Pure: no database handle, no write, no model call.

    `gaps` is Step 8's output with ALL four statuses -- GAP rows become the
    trajectory, UNASSESSED rows become `unplaced`, and SATISFIED and
    NOT_REQUIRED rows produce nothing, because there is no evolution to
    describe. `requirements` is Step 6's output, consulted only for each
    winning row's authored `rationale`.
    """
    rationale_by_capability = {r.capability_id: r for r in requirements}

    if not requirements:
        # No destination resolved -- see NO_TARGET_CONTEXT.
        logger.info(
            "no target-state requirements; no strategic direction",
            extra={"stage": "strategic_direction", **target.describe()},
        )
        return StrategicDirection(
            status=NO_TARGET_CONTEXT, trajectory=(), unplaced=(), target=target,
        )

    # Ordering is Step 9A's, obtained by CALLING it. Nothing about necessity
    # ranking or gap magnitude is restated here.
    ordered = prioritize_capability_gaps(tuple(gaps))

    trajectory = []
    for position, gap in enumerate(ordered, start=1):
        requirement = rationale_by_capability.get(gap.capability_id)
        detail = capability_detail.get(gap.capability_id)
        trajectory.append(CapabilityTrajectory(
            capability_id=gap.capability_id,
            capability_code=gap.capability_code,
            capability_name=str(_row_get(detail, "capability_name") or gap.capability_code),
            capability_description=str(_row_get(detail, "description") or ""),
            current_level=gap.current_level,
            required_level=gap.required_level,
            gap_size=gap.gap_size,
            necessity=gap.necessity,
            rationale=str(getattr(requirement, "rationale", "") or ""),
            sequence=position,
            requirement_id=gap.requirement_id,
            supporting_evidence_ids=gap.supporting_evidence_ids,
        ))

    placed = {t.capability_id for t in trajectory}
    unplaced = tuple(
        UnplacedRequirement(
            capability_id=gap.capability_id,
            capability_code=gap.capability_code,
            capability_name=str(
                _row_get(capability_detail.get(gap.capability_id), "capability_name")
                or gap.capability_code),
            required_level=gap.required_level,
            necessity=gap.necessity or "",
            rationale=str(getattr(
                rationale_by_capability.get(gap.capability_id), "rationale", "") or ""),
            requirement_id=gap.requirement_id,
        )
        for gap in sorted(gaps, key=lambda g: g.capability_code)
        if gap.status == STATUS_UNASSESSED and gap.capability_id not in placed
    )

    logger.info(
        "strategic direction resolved",
        extra={
            "stage": "strategic_direction",
            **target.describe(),
            "required": len(requirements),
            "trajectory": len(trajectory),
            "unplaced": len(unplaced),
            "leaving_founder_dependence": sum(
                1 for t in trajectory if t.leaves_founder_dependence),
        },
    )
    return StrategicDirection(
        status=DIRECTION_RESOLVED, trajectory=tuple(trajectory),
        unplaced=unplaced, target=target,
    )


def narrate_direction(
    direction: StrategicDirection, narrator: DirectionNarrator | None,
) -> StrategicDirection:
    """Optional phrasing layer, applied as a strictly additive step.

    Fail-open by construction: a narrator that raises, returns None, or returns
    the wrong number of trajectory lines leaves the deterministic direction
    untouched. Nothing it returns can change a selection, because
    `DirectionNarration` carries no identifier to change one with.
    """
    if narrator is None or not direction.trajectory:
        return direction
    try:
        narration = narrator.narrate(direction)
    except Exception:                                          # noqa: BLE001
        logger.warning("direction narration failed; structured direction stands",
                       extra={"stage": "strategic_direction"})
        return direction
    if narration is None:
        return direction
    if len(narration.trajectory_lines) != len(direction.trajectory):
        logger.warning("direction narration changed the trajectory length; discarded",
                       extra={"stage": "strategic_direction"})
        return direction
    return replace(direction, narration=narration)
