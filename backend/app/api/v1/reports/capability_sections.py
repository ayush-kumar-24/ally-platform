"""Step 10A / 10B results -> report `facts`. Shaping only; nothing is computed.

Two new sections ride the existing `Section{key, heading, prose, facts}`
mechanism, so nothing about the report's schema, serialisation, cache or
renderers changes. What this module decides is which of the engines' fields
land where in the open `facts` dict, under a convention the renderers already
enforce:

    plain keys        founder-facing. Both renderers print only scalars and
                      lists of scalars, so these are labels and lists of the
                      engines' own strings -- capability names, the library's
                      own action steps, Step 5's own criteria, level labels,
                      authored rationale. Never a raw enum, never an internal
                      code, never composed prose, never a number the engines
                      did not emit.
    `_provenance`     machine-facing. Underscore-prefixed keys are hidden by
                      the document renderer and the frontend's factList() by
                      documented convention, but kept in the JSON API and the
                      cached snapshot. Every id and every raw state the engines
                      carry lives here -- capability, intervention, requirement,
                      criterion and evidence ids, integer levels, the status
                      string, reason codes, the target band and horizon -- so a
                      section can always be traced back to the row that
                      produced it.

NOTHING IS RECOMPUTED. The engines' result objects are read field by field;
no gap, priority, intervention, action or criterion is re-derived here.

WHEN THERE IS NOTHING TRUE TO SAY, THE SECTION IS LEFT OUT AND NAMED. The
report already has a convention for this, and it is the honest one: the
generator omits a section it has nothing real to put in, records the key in
`unpopulated_sections`, and both renderers tell the founder "Not included in
this report: ... Ally leaves a section out when it does not have enough to say
something true there, rather than filling it in." A builder here returns `{}`
for exactly those states, and the generator names the key:

    NO_TARGET_CONTEXT         the founder has not stated a destination. Absent
                              input, not diagnostic uncertainty.
    AMBIGUOUS_REQUIREMENTS    two curated rules disagree. A curation error the
                              engine already logs at warning for the people who
                              can fix it; not a message for a founder.
    NO_ACTIONABLE_TARGET      with zero gaps considered: nothing was diagnosed.
    a resolved direction with no trajectory and nothing unplaced: nothing to
                              evolve and nothing outstanding.

WHAT IS KEPT is what the founder can act on or should know: a real target; a
resolved trajectory; requirements the destination has and the diagnosis has
not yet assessed (named as exactly that, never as gaps); and gaps that WERE
identified but the library cannot yet serve -- meaningful uncertainty, shown
by capability name with the internal reason codes in `_provenance`.

UNASSESSED IS NEVER SHOWN AS A GAP. Step 10B's `unplaced` requirements land
under a key that says what they are and are never counted among, or listed
with, the trajectory.

No prose is written here, and none is requested from any narrator: the
sections are emitted with empty slots, so neither the template narrator nor
an LLM narrator produces text for them. What the founder reads is the
engines' own words.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.api.v1.diagnosis.strategic_direction import StrategicDirection
from app.api.v1.diagnosis.twenty_day_target import TwentyDayTargetResult

#: Report section keys. Not "section" -- that word is an internal fact key the
#: generator strips.
TWENTY_DAY_TARGET_KEY = "twenty_day_target"
STRATEGIC_DIRECTION_KEY = "strategic_direction"

ENGINE_SECTION_KEYS = (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY)


def _name(names: Mapping[int, str], capability_id: int, fallback: str) -> str:
    return str(names.get(capability_id) or fallback)


def twenty_day_target_facts(
    result: TwentyDayTargetResult | None,
    capability_names: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    """Facts for the 20-day target section. `{}` leaves the section out and
    named -- never a fabricated target."""
    if result is None:
        return {}
    names = capability_names or {}

    skipped = [
        {"capability_id": s.capability_id, "capability_code": s.capability_code,
         "gap_rank": s.gap_rank, "gap_size": s.gap_size, "necessity": s.necessity,
         "reason": s.reason,
         "excluded_intervention_ids": list(s.excluded_intervention_ids)}
        for s in result.skipped_gaps
    ]
    skipped_names = [
        _name(names, s.capability_id, s.capability_code) for s in result.skipped_gaps]

    if result.target is None:
        if result.considered_gap_count == 0:
            return {}                       # nothing diagnosed: left out and named
        # Gaps were found but the library cannot yet act on them. That is
        # worth knowing, so it stays -- by name, with the codes underneath.
        return {
            "gaps_identified": result.considered_gap_count,
            "not_yet_addressable": skipped_names,
            "_provenance": {
                "status": result.status,
                "considered_gap_count": result.considered_gap_count,
                "skipped_gaps": skipped,
            },
        }

    t = result.target
    return {
        "focus": t.primary_capability_name,
        "outcome": t.target_outcome,
        "current_level": t.current_level.label,
        "required_level": t.required_level.label,
        "focus_area": t.source_section,
        "actions": [a.action for a in t.actions],
        "success_after_20_days": [c.criterion_text for c in t.success_criteria],
        "not_yet_addressable": skipped_names,
        "_provenance": {
            "status": result.status,
            "horizon_days": t.horizon_days,
            "primary_capability_id": t.primary_capability_id,
            "primary_capability_code": t.primary_capability_code,
            "supporting_capability_ids": list(t.supporting_capability_ids),
            "gap_rank": t.gap_rank,
            "gap_size": t.gap_size,
            "necessity": t.necessity,
            "current_level": int(t.current_level),
            "required_level": int(t.required_level),
            "requirement_id": t.requirement_id,
            "supporting_evidence_ids": list(t.supporting_evidence_ids),
            "source_intervention_id": t.source_intervention_id,
            "source_intervention_code": t.source_intervention_code,
            "actions": [
                {"sequence": a.sequence, "action": a.action,
                 "source_intervention_id": a.source_intervention_id}
                for a in t.actions],
            "success_criteria": [
                {"criterion_id": c.criterion_id, "criterion_order": c.criterion_order,
                 "criterion_text": c.criterion_text}
                for c in t.success_criteria],
            "skipped_gaps": skipped,
        },
    }


def strategic_direction_facts(direction: StrategicDirection | None) -> dict[str, Any]:
    """Facts for the strategic direction section. `{}` leaves the section out
    and named. Order, never dependency; context, never a milestone."""
    if direction is None:
        return {}

    context = {
        "status": direction.status,
        "target_revenue_band": direction.target.target_revenue_band,
        "target_time_horizon": direction.target.target_time_horizon,
    }

    if not direction.trajectory and not direction.unplaced:
        # NO_TARGET_CONTEXT, AMBIGUOUS_REQUIREMENTS, or resolved with nothing
        # to evolve and nothing outstanding: left out and named.
        return {}

    facts: dict[str, Any] = {}
    if direction.trajectory:
        facts["trajectory"] = [
            f"{t.sequence}. {t.capability_name}: {t.transition_label}"
            for t in direction.trajectory]
        facts["why_each_matters"] = [
            f"{t.sequence}. {t.rationale}" for t in direction.trajectory]
    facts["required_but_not_yet_assessed"] = [
        f"{u.capability_name} (needs: {u.required_level_label})"
        for u in direction.unplaced]
    facts["_provenance"] = {
        **context,
        "trajectory": [
            {"sequence": t.sequence, "capability_id": t.capability_id,
             "capability_code": t.capability_code,
             "current_level": int(t.current_level),
             "required_level": int(t.required_level),
             "gap_size": t.gap_size, "necessity": t.necessity,
             "requirement_id": t.requirement_id,
             "supporting_evidence_ids": list(t.supporting_evidence_ids)}
            for t in direction.trajectory],
        "unplaced": [
            {"capability_id": u.capability_id, "capability_code": u.capability_code,
             "required_level": int(u.required_level), "necessity": u.necessity,
             "requirement_id": u.requirement_id}
            for u in direction.unplaced],
    }
    return facts
