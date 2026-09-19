"""CAPABILITY GAPS -> PRIORITY ORDER. "Which known gaps deserve attention first,"
and nothing past that -- no intervention, no recommendation, no roadmap.

WHAT THIS MODULE DOES, EXACTLY: takes the `CapabilityGap` tuple Step 8 already
produced, keeps only the ones with `status == STATUS_GAP` (a founder is
confidently below the target, not merely unassessed), and orders them by a
small, explicit, documented set of factors. It answers "in what order should
these already-identified gaps be looked at" and answers no other question --
not "how bad is this," not "what should the founder do," not "which
intervention fixes it."

WHY NOT GAP SIZE ALONE (the step brief's own example, verified): a capability
at current=0/required=3 is not automatically more important than one at
current=2/required=3. Distance from target is a fact about the measurement,
not a fact about business impact. This module never treats `gap_size` as
though it already encodes importance -- see "The algorithm" below for the
one, narrow way it is actually used.

WHY NO BORROWED SCORE (inspected before writing any of this, see
docs/GAP-PRIORITIZATION.md section "What was inspected and rejected" for the
full trail): root-cause `detection_score`/`detection_confidence`/`rank`
(app/api/v1/reasoning/) measure evidence severity and confidence for a
DIAGNOSTIC CAUSE keyed by `root_cause_id`/category -- there is no
deterministic join from any of them to a `capability_id` anywhere in this
codebase, and inventing one here would be exactly the kind of unjustified
new relationship the step brief forbids. Business Health
(app/api/v1/reasoning/engines/business_health.py) is a founder-answer score
over `readiness_pillars`, joined to Capability only through the explicitly
non-authoritative `Capability.pillar_id` ("nothing gates on it" --
app/models/capability.py). `capability_domain` (on Capability and, separately,
as 390 near-unique free-text labels on `interventions`) and `domain_order`
are display/grouping metadata, never a documented importance ranking.
`intervention_capabilities` carries no weight or priority column at all. None
of these signals is reused here, because none of them is genuinely, safely
reusable -- not because they were merely inconvenient to wire up.

WHAT IS ACTUALLY USED, and why each one is defensible:

  1. `necessity` (Step 6, `capability_requirements.necessity` verbatim,
     `core` | `contextual`) -- Step 6's own docstring already states this
     column exists so a later step "can prioritise gaps without inventing a
     severity of its own" (target_state.py). `core` means the target state is
     unreachable without this capability; `contextual` means it matters for
     this founder's context but the destination is reachable without it. This
     is the ONE ranking distinction Step 6 already made on purpose, and using
     it is not inventing anything -- it is reading data placed there for
     exactly this reason.

  2. `gap_size` (Step 8, `required_level - current_level`, only defined when
     `status == GAP`) -- used ONLY as a secondary, within-necessity
     tie-breaker, never as the primary signal and never converted into a
     LOW/MEDIUM/HIGH label. Within the same necessity tier, a larger
     numeric distance from the target is a real, if narrow, fact worth
     surfacing before a smaller one -- but it never overrides `necessity`,
     which is why Case A below (core, gap_size=2) always outranks a
     contextual gap of any size.

  3. `capability_id` -- the final, stable tie-break, exactly as the step
     brief recommends, chosen because it is the one field guaranteed present,
     immutable, and totally ordered for every `CapabilityGap` that exists.

NEITHER FACTOR CAN BE "UNKNOWN" FOR A GAP ROW: `_compare` in `gap_engine.py`
only ever sets `status = STATUS_GAP` after resolving both a real
`RequiredCapability` (which always carries a `necessity` value the database
CHECK constraint restricts to exactly `core`/`contextual` -- see the Step 6
migration) and a real numeric `current_level`, so `gap_size` and `necessity`
are always populated together with `status == GAP` by construction. There is
therefore no live case in which this module fabricates a value for a missing
signal -- the "unknown must not become zero" rule (system-wide) has nothing to
guard against here, and adding speculative handling for a case the schema
already forbids would be exactly the kind of premature defensiveness this
codebase avoids elsewhere.

NO NUMERIC "PRIORITY SCORE": `priority_key` is a plain, three-element sort
tuple `(necessity_rank, -gap_size, capability_id)`, not a blended 0-100
number. There is no weighting formula to misread as confidence, and nothing
here could be mistaken for a "Founder Score" -- it exists to make `sorted()`
correct and nothing else. `priority_reasons` is the human-legible restatement
of the same tuple, one string per factor that actually decided this gap's
position.

DETERMINISTIC: pure Python over an already-deterministic input tuple. No
LLM, no embeddings, no RAG, no randomness, no insertion-order sensitivity
(the sort key is a total order over three integers). No intervention is
selected, and no recommendation prose is generated -- see `InterventionCapability`
above: nothing here even reads that table.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.gap_engine import STATUS_GAP, CapabilityGap
from app.api.v1.diagnosis.target_state import NECESSITY_CONTEXTUAL, NECESSITY_CORE
from app.core.logger import logger

#: Lower rank sorts first. `core` (the target is unreachable without this
#: capability) always outranks `contextual` (matters here, but not
#: load-bearing for reachability) -- see the module docstring for why this,
#: and only this, ordinal distinction is drawn from `necessity`.
_NECESSITY_RANK = {NECESSITY_CORE: 0, NECESSITY_CONTEXTUAL: 1}


@dataclass(frozen=True)
class PrioritizedCapabilityGap:
    """One GAP-status capability, plus the explicit reason it sorts where it
    does. Never a verdict about what to build or recommend -- there is no
    intervention field, no recommendation text, and no field that could be
    mistaken for a numeric "founder score"."""

    capability_id: int
    capability_code: str
    capability_name: str
    current_level: CapabilityLevel
    required_level: CapabilityLevel
    gap_size: int
    necessity: str

    #: `(necessity_rank, -gap_size, capability_id)`. Sorting a list of these
    #: ascending reproduces this module's entire ordering decision -- nothing
    #: about it is a magnitude, only a total order.
    priority_key: tuple[int, int, int]
    #: One string per factor in `priority_key`, in the same order, for a
    #: caller (a debugger, a future admin view) to explain a position without
    #: re-deriving it from the tuple.
    priority_reasons: tuple[str, ...]
    #: 1-based position in the final ordering this call produced. An ordinal
    #: label for "this is Nth," not a score and not persisted across calls --
    #: recomputed fresh every time, exactly like `CapabilityGap` itself.
    rank: int

    #: Traceability, carried straight through from the input `CapabilityGap`.
    requirement_id: int | None
    supporting_evidence_ids: tuple[int, ...]


def _priority_key(gap: CapabilityGap) -> tuple[int, int, int]:
    if gap.necessity not in _NECESSITY_RANK:
        # The Step 6 migration's CHECK constraint makes this unreachable
        # today; raising rather than defaulting keeps a future third
        # necessity value from silently sorting into an arbitrary position.
        raise ValueError(f"unknown necessity: {gap.necessity!r}")
    necessity_rank = _NECESSITY_RANK[gap.necessity]
    return (necessity_rank, -gap.gap_size, gap.capability_id)


def _priority_reasons(gap: CapabilityGap) -> tuple[str, ...]:
    return (
        f"necessity={gap.necessity}",
        f"gap_size={gap.gap_size}",
        f"capability_id={gap.capability_id} (stable tie-break)",
    )


def prioritize_capability_gaps(
    gaps: tuple[CapabilityGap, ...],
) -> tuple[PrioritizedCapabilityGap, ...]:
    """Step 9A: `tuple[CapabilityGap, ...]` -> `tuple[PrioritizedCapabilityGap, ...]`,
    ordered, `status == STATUS_GAP` rows only.

    UNASSESSED, SATISFIED, and NOT_REQUIRED gaps are filtered out before
    anything else runs -- an UNASSESSED capability is never promoted into a
    priority merely because its state is unknown; it is simply absent from
    the result, the same way it is absent from Step 8's own "this is a
    problem" framing.
    """
    only_gaps = [gap for gap in gaps if gap.status == STATUS_GAP]
    ordered = sorted(only_gaps, key=_priority_key)

    prioritized = [
        PrioritizedCapabilityGap(
            capability_id=gap.capability_id,
            capability_code=gap.capability_code,
            capability_name=gap.capability_name,
            current_level=gap.current_level,
            required_level=gap.required_level,
            gap_size=gap.gap_size,
            necessity=gap.necessity,
            priority_key=_priority_key(gap),
            priority_reasons=_priority_reasons(gap),
            rank=index,
            requirement_id=gap.requirement_id,
            supporting_evidence_ids=gap.supporting_evidence_ids,
        )
        for index, gap in enumerate(ordered, start=1)
    ]

    if prioritized:
        logger.info(
            "capability gaps prioritized",
            extra={
                "stage": "gap_priority",
                "gaps_prioritized": len(prioritized),
                "core": sum(1 for p in prioritized if p.necessity == NECESSITY_CORE),
                "contextual": sum(
                    1 for p in prioritized if p.necessity == NECESSITY_CONTEXTUAL
                ),
            },
        )
    return tuple(prioritized)
