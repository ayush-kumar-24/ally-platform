"""Step 10A / 10B results -> report `facts`. Shaping only; nothing is computed.

Two new sections ride the existing `Section{key, heading, prose, facts}`
mechanism, so nothing about the report's schema, serialisation, cache or
renderers changes. What this module does is decide which of the engines'
fields land where in the open `facts` dict, under a convention the renderers
already enforce:

    plain keys        founder-facing. Both renderers print only scalars and
                      lists of scalars, so these are labels and lists of the
                      engines' own strings -- capability names, the library's
                      own action steps, Step 5's own criteria -- never numbers
                      the engines did not emit and never composed prose.
    `_provenance`     machine-facing. Underscore-prefixed keys are hidden by
                      the document renderer and the frontend's factList() by
                      documented convention, but they are kept in the JSON API
                      and the cached snapshot. Every id the engines carry
                      (capability, intervention, requirement, criterion,
                      evidence) lives here, so a section can always be traced
                      back to the row that produced it.

NOTHING IS RECOMPUTED. The engines' result objects are read field by field;
no gap, priority, intervention, action or criterion is re-derived here. A
domain state the engines already name (NO_ACTIONABLE_TARGET, NO_TARGET_CONTEXT,
AMBIGUOUS_REQUIREMENTS, an unplaced requirement) is carried as a `status` or a
clearly-labelled list, never hidden behind fallback prose.

UNASSESSED IS NEVER SHOWN AS A GAP. Step 10B's `unplaced` requirements land
under a key that says what they are -- required, not yet assessed -- and are
never counted among, or listed with, the trajectory.

No prose is written here, and none is requested from any narrator: the
sections are emitted with empty slots, so neither the template narrator nor
an LLM narrator produces text for them. What the founder reads is the
engines' own words.
"""

from __future__ import annotations

from typing import Any

from app.api.v1.diagnosis.strategic_direction import StrategicDirection
from app.api.v1.diagnosis.twenty_day_target import TwentyDayTargetResult

#: Report section keys. Not "section" -- that word is an internal fact key the
#: generator strips.
TWENTY_DAY_TARGET_KEY = "twenty_day_target"
STRATEGIC_DIRECTION_KEY = "strategic_direction"


def twenty_day_target_facts(result: TwentyDayTargetResult | None) -> dict[str, Any]:
    """Facts for the 20-day target section, or {} when the engine did not run
    (which omits the section -- absence, not a fabricated target)."""
    if result is None:
        return {}

    skipped = [
        {"capability_id": s.capability_id, "capability_code": s.capability_code,
         "gap_rank": s.gap_rank, "gap_size": s.gap_size, "necessity": s.necessity,
         "reason": s.reason,
         "excluded_intervention_ids": list(s.excluded_intervention_ids)}
        for s in result.skipped_gaps
    ]

    if result.target is None:
        return {
            "status": result.status,
            "gaps_considered": result.considered_gap_count,
            "why_no_target": [f"{s.capability_code}: {s.reason}" for s in result.skipped_gaps],
            "_provenance": {"status": result.status, "skipped_gaps": skipped},
        }

    t = result.target
    return {
        "status": result.status,
        "horizon_days": t.horizon_days,
        "focus": t.primary_capability_name,
        "outcome": t.target_outcome,
        "current_level": t.current_level.label,
        "required_level": t.required_level.label,
        "necessity": t.necessity,
        "intervention": t.source_intervention_code,
        "intervention_section": t.source_section,
        "actions": [a.action for a in t.actions],
        "success_after_20_days": [c.criterion_text for c in t.success_criteria],
        "skipped_higher_priority_gaps": [
            f"{s.capability_code}: {s.reason}" for s in result.skipped_gaps],
        "_provenance": {
            "status": result.status,
            "primary_capability_id": t.primary_capability_id,
            "primary_capability_code": t.primary_capability_code,
            "supporting_capability_ids": list(t.supporting_capability_ids),
            "gap_rank": t.gap_rank,
            "gap_size": t.gap_size,
            "current_level": int(t.current_level),
            "required_level": int(t.required_level),
            "requirement_id": t.requirement_id,
            "supporting_evidence_ids": list(t.supporting_evidence_ids),
            "source_intervention_id": t.source_intervention_id,
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
    """Facts for the strategic direction section, or {} when the engine did
    not run. Order, never dependency; context, never a milestone."""
    if direction is None:
        return {}

    context = {
        "target_revenue_band": direction.target.target_revenue_band,
        "target_time_horizon": direction.target.target_time_horizon,
    }

    if not direction.trajectory:
        facts: dict[str, Any] = {"status": direction.status, **context}
        if direction.ambiguity:
            facts["ambiguity"] = direction.ambiguity
        facts["_provenance"] = {"status": direction.status, **context}
        return facts

    return {
        "status": direction.status,
        **context,
        "trajectory": [
            f"{t.sequence}. {t.capability_name}: {t.transition_label} ({t.necessity})"
            for t in direction.trajectory],
        "why_each_matters": [
            f"{t.sequence}. {t.rationale}" for t in direction.trajectory],
        "required_but_not_yet_assessed": [
            f"{u.capability_name} (needs: {u.required_level_label})"
            for u in direction.unplaced],
        "_provenance": {
            "status": direction.status,
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
        },
    }
