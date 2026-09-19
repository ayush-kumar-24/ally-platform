"""CURRENT CAPABILITY STATE + TARGET-STATE REQUIREMENTS -> GAP. A comparison, not a verdict.

WHAT THIS MODULE DOES, EXACTLY: for each capability that is either REQUIRED by
the founder's resolved target context (Step 6) or ASSESSED from their answers
(Step 7C), compare the two and report one of four factual states. It answers
"what capability gap exists relative to the target state" and nothing past
that -- no severity, no priority, no recommendation, no intervention. Those
questions have not been asked yet; this module does not answer questions
nobody asked it.

NEITHER UPSTREAM RESOLVER IS DUPLICATED. `resolve_requirements` (target_state.py)
and `assess_capabilities` (capability_assessment.py) are called exactly as they
already exist, unmodified, and their outputs are read only through their own
public dataclass fields -- `RequiredCapability.required_level`,
`CapabilityAssessment.current_level`, and so on. This module owns none of the
specificity cascade and none of the lowest-confident-reading aggregation; it
owns only the comparison between their two, already-computed answers.

    FounderContext + TargetStateContext
              |
              v
    resolve_requirements(capability_requirement_rows, ...)   [Step 6, untouched]
              |
    current_capability_assessments(session_id)                [Step 7C, untouched]
              |
              v
       compute_capability_gaps(...)                            [THIS MODULE]
              |
              v
       tuple[CapabilityGap, ...]

THE CORE RULE, verbatim from the step brief and nothing else:

    current_level IS NULL              -> UNASSESSED
    current_level <  required_level    -> GAP
    current_level >= required_level    -> SATISFIED

and one more state the rule above does not cover on its own:

    no applicable requirement at all   -> NOT_REQUIRED

UNASSESSED IS NEVER A GAP, and this is enforced by the ORDER of the if/elif
chain in `_compare`: the NULL check runs FIRST, before any `<` or `>=`
comparison is attempted, so there is no code path in which `None < 2` is ever
evaluated. A founder with insufficient evidence for GTM-ACQ is told exactly
that -- insufficient evidence -- never "you are missing GTM-ACQ", which would
be a claim this module has no evidence to support.

REQUIRED LEVEL 0 IS A REQUIREMENT, NOT ITS ABSENCE. A row with
`required_level = 0` still participates in the UNASSESSED/GAP/SATISFIED
comparison exactly like any other -- it is real reference data saying "no
maturity is required here", and `current_level = 0 >= required_level = 0` is
SATISFIED, not a gap and not nothing. It is a DIFFERENT capability entirely,
missing from `resolve_requirements`'s output altogether, that becomes
NOT_REQUIRED -- the two must never be confused, and they cannot be here
because they arrive through different code paths (a present RequiredCapability
vs. its complete absence from the map).

NO SEVERITY, NO PRIORITY, NO LLM. `gap_size` is the plain integer
`required_level - current_level`, computed once, never bucketed into low/
medium/high (no such taxonomy exists anywhere in this codebase to borrow, and
inventing one is explicitly out of scope -- see the step brief's own s7/s14).
Nothing in this module imports an LLM client, a provider, or a prompt; every
input has already been interpreted upstream, in Step 6 and Step 7B/7C.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.api.v1.diagnosis.capability_assessment import CapabilityAssessment
from app.api.v1.diagnosis.capability_levels import UNASSESSED as UNASSESSED_SENTINEL
from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.target_state import RequiredCapability
from app.core.logger import logger

#: The four factual states a capability can be in relative to a target
#: context. Values match `capability_levels.UNASSESSED` exactly (both are the
#: string "unassessed"), so `gap.status == UNASSESSED_SENTINEL` reads the same
#: whichever module a caller imported the sentinel from.
STATUS_UNASSESSED = UNASSESSED_SENTINEL
STATUS_GAP = "gap"
STATUS_SATISFIED = "satisfied"
STATUS_NOT_REQUIRED = "not_required"

_VALID_STATUSES = frozenset(
    {STATUS_UNASSESSED, STATUS_GAP, STATUS_SATISFIED, STATUS_NOT_REQUIRED}
)


@dataclass(frozen=True)
class CapabilityGap:
    """One capability's factual comparison result. Never a verdict about what
    to do -- there is no field here that could be mistaken for a
    recommendation, a priority, or a severity band."""

    capability_id: int
    capability_code: str
    capability_name: str
    status: str                                    # one of the four STATUS_* constants

    #: None exactly when there is no applicable requirement (NOT_REQUIRED).
    required_level: CapabilityLevel | None
    #: None exactly when the capability is UNASSESSED.
    current_level: CapabilityLevel | None

    #: `required_level - current_level`, only when status == GAP. Never
    #: negative -- SATISFIED (current >= required) never sets this.
    gap_size: int | None = None
    #: `current_level - required_level`, only when status == SATISFIED and the
    #: founder EXCEEDS what is required. Optional, additive information; no
    #: new scoring system rides on it.
    surplus_level: int | None = None

    #: Traceability into Step 6: the exact requirement row the resolver
    #: selected, so "why is this required" needs no re-resolution.
    #: None exactly when status == NOT_REQUIRED.
    requirement_id: int | None = None
    necessity: str | None = None

    #: Traceability into Step 7C / 7B: the evidence_id(s) that determined
    #: current_level. Empty whenever status is UNASSESSED or the capability
    #: was never assessed at all.
    supporting_evidence_ids: tuple[int, ...] = ()

    def __post_init__(self):
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"unknown gap status: {self.status!r}")


def _compare(
    capability_id: int,
    capability_code: str,
    capability_name: str,
    requirement: RequiredCapability | None,
    assessment: CapabilityAssessment | None,
) -> CapabilityGap:
    """The core invariant, and nothing else. `requirement` is None exactly when
    `resolve_requirements` produced no applicable row for this capability;
    `assessment` is None exactly when `assess_capabilities` produced no row at
    all (as opposed to one with `current_level = None`, which also means
    unassessed -- both are handled identically below via `current_level`)."""
    current_level = assessment.current_level if assessment is not None else None
    supporting = assessment.supporting_evidence_ids if assessment is not None else ()

    if requirement is None:
        return CapabilityGap(
            capability_id=capability_id, capability_code=capability_code,
            capability_name=capability_name, status=STATUS_NOT_REQUIRED,
            required_level=None, current_level=current_level,
            supporting_evidence_ids=supporting,
        )

    required_level = requirement.required_level

    # UNASSESSED IS CHECKED FIRST, before any ordering comparison is attempted.
    # There is no code path here in which `current_level < required_level` is
    # evaluated while current_level is None.
    if current_level is None:
        return CapabilityGap(
            capability_id=capability_id, capability_code=capability_code,
            capability_name=capability_name, status=STATUS_UNASSESSED,
            required_level=required_level, current_level=None,
            requirement_id=requirement.requirement_id, necessity=requirement.necessity,
            supporting_evidence_ids=(),
        )

    if current_level < required_level:
        return CapabilityGap(
            capability_id=capability_id, capability_code=capability_code,
            capability_name=capability_name, status=STATUS_GAP,
            required_level=required_level, current_level=current_level,
            gap_size=int(required_level) - int(current_level),
            requirement_id=requirement.requirement_id, necessity=requirement.necessity,
            supporting_evidence_ids=supporting,
        )

    # current_level >= required_level: SATISFIED, whether exactly met or
    # exceeded. Exceeding is never a gap in the other direction -- there is no
    # "negative gap" anywhere in this module.
    surplus = int(current_level) - int(required_level)
    return CapabilityGap(
        capability_id=capability_id, capability_code=capability_code,
        capability_name=capability_name, status=STATUS_SATISFIED,
        required_level=required_level, current_level=current_level,
        surplus_level=surplus or None,
        requirement_id=requirement.requirement_id, necessity=requirement.necessity,
        supporting_evidence_ids=supporting,
    )


def compute_capability_gaps(
    requirements: tuple[RequiredCapability, ...],
    assessments: tuple[CapabilityAssessment, ...],
    capability_names: Mapping[int, str],
) -> tuple[CapabilityGap, ...]:
    """The whole Gap Engine. Pure: no database, no model call, no side effect.

    `requirements` and `assessments` are exactly what `resolve_requirements`
    and `current_capability_assessments`/`assess_capabilities` already
    produce -- pass their output straight through, never rebuilt here.
    `capability_names` is a plain `{capability_id: capability_name}` map (one
    bounded query at the call site; see `DiagnosisRepository.capability_names`)
    so this function never queries anything itself.

    ONLY CAPABILITIES THAT ARE RELEVANT APPEAR IN THE RESULT: the union of
    "has an applicable requirement" and "has at least one observation" --
    matching the step brief's own framing ("for each capability relevant to
    the founder's target state"). A capability with neither (most founders will
    never be asked about most of the 34, and most targets do not require most
    of them) is not manufactured a row saying so; there is nothing to report.
    This is why Case E (NOT_REQUIRED) and Case C (UNASSESSED-because-required)
    both surface correctly: the union includes a capability the moment EITHER
    side has something to say about it.

    Ordered by capability_code, matching the stability discipline both
    upstream resolvers already apply to their own output.
    """
    required_by_id: dict[int, RequiredCapability] = {r.capability_id: r for r in requirements}
    assessed_by_id: dict[int, CapabilityAssessment] = {a.capability_id: a for a in assessments}

    capability_ids = set(required_by_id) | set(assessed_by_id)
    gaps = []
    for capability_id in capability_ids:
        requirement = required_by_id.get(capability_id)
        assessment = assessed_by_id.get(capability_id)
        capability_code = (
            requirement.capability_code if requirement is not None
            else assessment.capability_code
        )
        capability_name = capability_names.get(capability_id, capability_code)
        gaps.append(_compare(
            capability_id, capability_code, capability_name, requirement, assessment,
        ))

    gaps.sort(key=lambda g: g.capability_code)

    real_gaps = sum(1 for g in gaps if g.status == STATUS_GAP)
    if gaps:
        logger.info(
            "capability gaps computed",
            extra={
                "stage": "gap_engine",
                "capabilities_considered": len(gaps),
                "gaps": real_gaps,
                "satisfied": sum(1 for g in gaps if g.status == STATUS_SATISFIED),
                "unassessed": sum(1 for g in gaps if g.status == STATUS_UNASSESSED),
                "not_required": sum(1 for g in gaps if g.status == STATUS_NOT_REQUIRED),
            },
        )
    return tuple(gaps)
