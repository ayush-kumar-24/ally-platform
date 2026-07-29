"""ReportNarrativeGenerator -- assembles the fixed template, enforcing the hard rules.

Order of sections is chosen by variant + the hard rules; the NARRATOR only fills
prose. Facts on each section are engine-owned and pass through untouched.

Numeric-score decision (made explicit, per the brief):
  * The report exposes NO raw numbers. Business health and each pillar are shown as
    their score_bands LABEL + written description (readiness_pillars.score_bands) --
    the paragraph exists precisely so a band can be shown instead of a grade. Raw
    scores stay internal (engine + dashboard). This keeps the report off the
    grade-anxiety surface the diagnosis engine was designed to avoid.
  * ALSO NOT EXPOSED: an overall "clarity score", a root-cause "confidence %", and
    the archetype fit_score -- all read as grades.

Narrator provenance: every section records which narrator produced it (template /
llm / llm_fallback_template). A silent LLM->template fallback would make report
quality vary invisibly, so `narrator_provenance` surfaces it (owner view only).
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
    exposes_numeric_scores: bool = False  # report shows bands + descriptions, not numbers
    unpopulated_sections: tuple[str, ...] = UNPOPULATED_SECTIONS
    narrator_provenance: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "variant": self.variant.value,
            "tone_persona": self.tone_persona,
            "sections": [
                {"key": s.key, "heading": s.heading, "prose": s.prose, "facts": s.facts}
                for s in self.sections
            ],
            "unpopulated_sections": list(self.unpopulated_sections),
            "narrator_provenance": self.narrator_provenance,
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
        sources: list[str] = []
        for key in order:
            slots, facts = self._slots_and_facts(key, payload, separate_identity)
            prose, source = self._narrate(key, slots, tone)
            if not prose and not facts:
                continue  # missing value -> omit the section, never guess
            if prose:
                sources.append(source)
                facts = {**facts, "_narrator": source}
            heading = _HEADINGS.get(key, key.title())
            if key == "psychological_note" and facts.get("section") == "H":
                heading = "Section H — Psychological State Note"
            sections.append(Section(key, heading, prose, facts))

        by_source: dict[str, int] = {}
        for s in sources:
            by_source[s] = by_source.get(s, 0) + 1
        provenance = {
            "narrator": type(self.narrator).__name__,
            "by_source": by_source,
            "degraded": any(s == "llm_fallback_template" for s in sources),
        }

        return ReportNarrative(
            report_id=payload.report_id, variant=variant,
            tone_persona=payload.tone_persona, sections=tuple(sections),
            narrator_provenance=provenance,
        )

    def _narrate(self, key: str, slots: dict, tone: ToneGuidance) -> tuple[str, str]:
        """Return (prose, source). Prefers a provenance-aware narrator; falls back
        to the plain protocol (recorded as 'template') for older narrators."""
        with_source = getattr(self.narrator, "narrate_with_source", None)
        if callable(with_source):
            return with_source(key, slots, tone)
        return self.narrator.narrate(key, slots, tone), "template"

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
            # Section H (Psychological State Note): a NAMED, spec-defined section
            # triggered when Founder Readiness is in the Critical Gap band (0-35).
            # Its content is that band's written description. It surfaces regardless
            # of the overall score. Identity fusion -> separation language.
            fr = next((pl for pl in p.pillars if pl.name == "Founder Readiness"), None)
            critical_gap = bool(fr and (fr.band == "Critical Gap" or fr.red_flag_triggered))
            section_h_text = fr.band_description if (fr and critical_gap) else None
            note = fr.red_flag_note if fr else None
            slots = {"section_h_text": section_h_text, "red_flag_note": note,
                     "separate_identity": separate_identity}
            facts = {
                "section": "H" if critical_gap else None,
                "trigger": ("founder_readiness_critical_gap" if critical_gap
                            else "psychology_category"),
                "psychology_flagged": p.psychology_flagged,
                "red_flag_pillars": [rp.name for rp in p.red_flag_pillars],
                "founder_readiness_band": fr.band if fr else None,
            }
            if not section_h_text and not note and not p.psychology_flagged and not p.red_flag_pillars:
                return {}, {}
            return slots, facts

        if key == "business_dna":
            # Bands + descriptions, NOT raw numbers. Founder Readiness in Critical
            # Gap is deferred to Section H (its full paragraph lives there) so the
            # report does not print the same block twice.
            pillars = [{"pillar_name": pf.name, "band": pf.band,
                        "band_description": (
                            None if (pf.name == "Founder Readiness" and pf.band == "Critical Gap")
                            else pf.band_description),
                        "red_flag_triggered": pf.red_flag_triggered,
                        "red_flag_note": pf.red_flag_note} for pf in p.pillars]
            slots = {"overall_band": p.business_health_band, "pillars": pillars}
            # Hard rule 2 in the facts: red-flag pillars are listed even when the
            # overall band is healthy.
            facts = {"overall_band": p.business_health_band, "pillars": pillars,
                     "red_flag_pillars": [rp.name for rp in p.red_flag_pillars]}
            if p.business_health_band is None and not pillars:
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
