"""ReportNarrativeGenerator -- assembles the fixed template, enforcing the hard rules.

Order of sections is chosen by variant + the hard rules; the NARRATOR only fills
prose. Facts on each section are engine-owned and pass through untouched.

Numeric-score decision (made explicit, per the brief):
  * EXPOSED: business-health overall score + per-pillar scores (0-100). These are
    the Business-DNA product itself (the score cards), not an ad-hoc grade.
  * NOT EXPOSED: an overall "clarity score", a root-cause "confidence %", and the
    archetype fit_score. Those read as grades and are deliberately omitted from the
    founder-facing report (see the flag in the module report).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.api.v1.reports.narrator import SectionNarrator, TemplateNarrator, ToneGuidance
from app.api.v1.reports.payload import ReportPayload
from app.api.v1.reports.variants import ReportVariant, select_variant

_HEADINGS = {
    "founder_summary": "Founder summary",
    "founder_dna": "Founder DNA",
    "psychological_note": "Psychological state note",
    "business_dna": "Business DNA",
    "problem_path": "Root cause",
    "areas_to_monitor": "Areas to monitor",
    "priority_actions": "Priority actions",
    "acknowledgement": "Before we begin",
    "support_recommendation": "A first step for you",
    "hedge": "A note on certainty",
}

# Frontend sections with NO backend source -- surfaced empty, never fabricated.
UNPOPULATED_SECTIONS = ("supporting_evidence", "recommended_roadmap", "why_steps")


@dataclass(frozen=True)
class Section:
    key: str
    heading: str
    prose: str
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportNarrative:
    report_id: int
    variant: ReportVariant
    tone_persona: str | None
    sections: tuple[Section, ...]
    exposes_numeric_scores: bool = True   # business-health/pillar scores only
    unpopulated_sections: tuple[str, ...] = UNPOPULATED_SECTIONS

    def as_dict(self) -> dict:
        return {
            "variant": self.variant.value,
            "tone_persona": self.tone_persona,
            "sections": [
                {"key": s.key, "heading": s.heading, "prose": s.prose, "facts": s.facts}
                for s in self.sections
            ],
            "unpopulated_sections": list(self.unpopulated_sections),
        }


class ReportNarrativeGenerator:
    def __init__(self, narrator: SectionNarrator | None = None):
        self.narrator = narrator or TemplateNarrator()

    def generate(
        self,
        payload: ReportPayload,
        *,
        session_framing: str | None = None,
        distress_protocol: str | None = None,
        separate_identity: bool = False,
    ) -> ReportNarrative:
        tone = ToneGuidance(
            persona=payload.tone_persona,
            session_framing=session_framing,
            distress_protocol=distress_protocol,
        )
        variant = select_variant(payload)
        order = self._section_order(payload, variant)

        sections: list[Section] = []
        for key in order:
            slots, facts = self._slots_and_facts(key, payload, separate_identity)
            prose = self.narrator.narrate(key, slots, tone)
            if not prose and not facts:
                continue  # missing value -> omit the section, never guess
            sections.append(Section(key, _HEADINGS.get(key, key.title()), prose, facts))

        return ReportNarrative(
            report_id=payload.report_id, variant=variant,
            tone_persona=payload.tone_persona, sections=tuple(sections),
        )

    # --- ordering (hard rules 1 + distress) -------------------------------
    def _section_order(self, p: ReportPayload, variant: ReportVariant) -> list[str]:
        show_psych = p.psychology_flagged or bool(p.red_flag_pillars)

        if variant is ReportVariant.DISTRESS:
            # Acknowledgement FIRST; a support recommendation BEFORE any business.
            head = ["acknowledgement", "support_recommendation"]
            body = ["founder_dna", "business_dna", "problem_path", "priority_actions"]
            if show_psych:
                body.insert(0, "psychological_note")
            return head + body

        if variant is ReportVariant.NO_CLEAR_DIAGNOSIS:
            order = ["founder_summary", "founder_dna", "business_dna",
                     "areas_to_monitor", "priority_actions"]
        elif variant is ReportVariant.LOW_CONFIDENCE:
            order = ["hedge", "founder_summary", "founder_dna", "business_dna",
                     "problem_path", "priority_actions"]
        else:  # STANDARD
            order = ["founder_summary", "founder_dna", "business_dna",
                     "problem_path", "priority_actions"]

        # Hard rule 1: Founder Psychology leads the narrative when flagged --
        # place the psychological note before Business DNA + Root cause.
        if show_psych:
            insert_at = 2 if p.psychology_flagged else order.index("business_dna") + 1
            order.insert(insert_at, "psychological_note")
        return order

    # --- slots + facts per section ---------------------------------------
    def _slots_and_facts(self, key: str, p: ReportPayload, separate_identity: bool):
        if key == "founder_summary":
            return {"founder_name": p.founder_name}, {}

        if key == "founder_dna":
            if not p.archetype:
                return {}, {}
            a = p.archetype
            slots = {"archetype": {
                "name": a.name, "core_motivation": a.core_motivation,
                "is_confident": a.is_confident,
            }}
            # facts: NO fit_score (a grade) in the founder-facing report.
            facts = {"archetype": {
                "name": a.name, "code": a.code,
                "core_motivation": a.core_motivation, "is_confident": a.is_confident,
                "tentative": not a.is_confident,
            }}
            return slots, facts

        if key == "psychological_note":
            # Hard rule 2: the Founder Readiness red-flag note surfaces (Section H)
            # regardless of the overall score. Identity fusion -> separation language.
            fr = next((p for p in p.pillars if p.name == "Founder Readiness"
                       and p.red_flag_triggered), None)
            note = fr.red_flag_note if fr else None
            slots = {"red_flag_note": note, "separate_identity": separate_identity}
            facts = {"psychology_flagged": p.psychology_flagged,
                     "red_flag_pillars": [rp.name for rp in p.red_flag_pillars]}
            if not note and not p.psychology_flagged and not p.red_flag_pillars:
                return {}, {}
            return slots, facts

        if key == "business_dna":
            pillars = [{"pillar_name": pf.name, "score": pf.score, "band": pf.band,
                        "red_flag_triggered": pf.red_flag_triggered,
                        "red_flag_note": pf.red_flag_note} for pf in p.pillars]
            slots = {"overall_score": p.business_health_overall,
                     "band": p.business_health_band, "pillars": pillars}
            # Hard rule 2 in the facts: red-flag pillars are listed even when the
            # overall number is healthy.
            facts = {"overall_score": p.business_health_overall,
                     "band": p.business_health_band, "pillars": pillars,
                     "red_flag_pillars": [rp.name for rp in p.red_flag_pillars]}
            if p.business_health_overall is None and not pillars:
                return {}, {}
            return slots, facts

        if key == "problem_path":
            rcs = [{"name": rc.name, "category": rc.category,
                    "confirmation_status": rc.confirmation_status, "rank": rc.rank}
                   for rc in p.top_root_causes]
            # Hard rule 5: Not-Tested must never read as certain as Confirmed --
            # confirmation_status is carried on every finding (categorical, no %).
            return ({"root_causes": rcs}, {"root_causes": rcs}) if rcs else ({}, {})

        if key == "areas_to_monitor":
            cats = p.top_sub_threshold_categories
            return {"categories": cats}, {"categories": [c for c, _ in cats]}

        if key == "priority_actions":
            confirm = [{"next_actions": list(a.next_actions), "priority": a.priority}
                       for a in p.confirm_actions]
            solve = [{"next_actions": list(a.next_actions), "priority": a.priority}
                     for a in p.solve_actions]
            slots = {"confirm_actions": confirm, "solve_actions": solve}
            # intervention IDs stay in the OWNER facts; the shared view strips them.
            facts = {"confirm_actions": confirm, "solve_actions": solve,
                     "intervention_ids": [a.intervention_id for a in
                                          (*p.confirm_actions, *p.solve_actions)
                                          if a.intervention_id is not None]}
            if not confirm and not solve:
                return {}, {}
            return slots, facts

        if key == "acknowledgement":
            return {"framing": p.session_state_framing if hasattr(p, "session_state_framing") else None}, {}
        if key == "support_recommendation":
            return {}, {"wellbeing_first": True}
        if key == "hedge":
            return {}, {"provisional": True}

        return {}, {}
