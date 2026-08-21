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
    "supporting_evidence": "What this is based on",
    "recommended_roadmap": "How to sequence this",
    "why_steps": "Why these steps",
    "acknowledgement": "Before we begin",
    "support_recommendation": "A first step for you",
    "hedge": "A note on certainty",
    "discovery_cta": "Your next move with Ally",
}

#: The free tier's "3+3 action plan" -- three lines to confirm/isolate, three
#: to solve (Stage-Adaptive doc s6). A ceiling, not a quota: fewer is honest,
#: more is the paid tier's "multiple problems ranked by priority".
_ACTION_LINES_PER_SIDE = 3

# Frontend sections with NO backend source -- surfaced empty, never fabricated.
#
# Only "expected_impact" is genuinely sourceless: it covers the two frontend
# boxes (Expected Business / Founder Impact) and nothing in `interventions` or
# the reasoning output estimates an impact, so anything written there would be
# invented. It stays declared-and-absent rather than guessed.
#
# The other three were listed here for the same reason but did NOT need to be:
# the material was already on the payload and simply never assembled into
# sections. supporting_evidence is the founder's own symptom probes plus the
# root causes' confirmation status; recommended_roadmap is the confirm-then-
# solve ordering the engine already produces; why_steps is ActionItem.rationale,
# which was carried all the way onto the payload and then dropped. A founder was
# getting a root cause and three actions with no evidence trail, no sequencing,
# and no statement of why those three.
UNPOPULATED_SECTIONS = ("expected_impact",)


#: Fact keys that must never reach a founder-facing report.
#:
#: `facts` doubles as the narrator's input slots AND as label/value pairs the
#: report UI renders. That meant internal routing keys were printed to the
#: founder verbatim -- a real report showed "Section: H" and
#: "Trigger: founder_readiness_critical_gap" next to the most personal section
#: in the document. Those describe how the report was assembled, not anything
#: about the founder's business.
#:
#: A denylist rather than an allowlist on purpose: an unrecognised NEW fact is
#: far more likely to be real founder content than a new internal key, so the
#: default has to be "show it". Internal keys are few and known.
_INTERNAL_FACT_KEYS = frozenset({
    "section",        # spec slot letter ("H")
    "trigger",        # routing reason code ("founder_readiness_critical_gap")
    "_narrator",      # which narrator produced the prose
    "psychology_flagged",   # internal boolean; rendered as a bare "Yes"
    "separate_identity",    # narrator tone switch, not a finding
})


def _founder_facts(facts: dict) -> dict:
    """Drop internal routing keys and empty values from founder-facing facts.

    Empty values go too: a label with None behind it renders as a heading with
    nothing under it, which reads as a broken report rather than an absent fact.
    """
    return {
        k: v for k, v in (facts or {}).items()
        if k not in _INTERNAL_FACT_KEYS and v not in (None, "", [], {})
    }


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
            "exposes_numeric_scores": self.exposes_numeric_scores,
            "unpopulated_sections": list(self.unpopulated_sections),
            "narrator_provenance": self.narrator_provenance,
        }

    @classmethod
    def from_dict(cls, report_id: int, data: dict) -> "ReportNarrative":
        """Reconstruct from `as_dict()`'s output -- the read side of the
        report-narrative cache (see narrative_snapshot on founder_reports).
        Round-trips every field `_build_narrative`'s callers actually read."""
        return cls(
            report_id=report_id,
            variant=ReportVariant(data["variant"]),
            tone_persona=data.get("tone_persona"),
            sections=tuple(
                Section(key=s["key"], heading=s["heading"], prose=s["prose"], facts=s.get("facts") or {})
                for s in data.get("sections", [])
            ),
            exposes_numeric_scores=data.get("exposes_numeric_scores", False),
            unpopulated_sections=tuple(data.get("unpopulated_sections", UNPOPULATED_SECTIONS)),
            narrator_provenance=data.get("narrator_provenance") or {},
        )


class ReportNarrativeGenerator:
    def __init__(self, narrator: SectionNarrator | None = None):
        self.narrator = narrator or TemplateNarrator()

    def generate(
        self,
        payload: ReportPayload,
        *,
        session_framing: str | None = None,
        distress_protocol: str | None = None,
        separate_identity: bool | None = None,
    ) -> ReportNarrative:
        tone = ToneGuidance(
            persona=payload.tone_persona,
            session_framing=session_framing,
            distress_protocol=distress_protocol,
        )
        # Identity-fusion separation language is driven by the payload's chronic-state
        # derivation unless a caller overrides it explicitly.
        sep_identity = payload.separate_identity if separate_identity is None else separate_identity
        variant = select_variant(payload)
        order = self._section_order(payload, variant)

        # Sequential on purpose. Narrating these concurrently was tried and
        # reverted: measured on a real 30-answer session, the whole
        # report_generation stage is 0.4s of a 203s pipeline, so overlapping it
        # bought nothing and cost a ThreadPoolExecutor. The 161s is in answer
        # classification -- see DiagnosticEngine.classify_answers.
        sections: list[Section] = []
        sources: list[str] = []
        for key in order:
            slots, facts = self._slots_and_facts(key, payload, sep_identity)
            if key == "business_dna" and variant is ReportVariant.DISTRESS:
                slots = {**slots, "brief": True}  # de-prioritise business under distress
            prose, source = self._narrate(key, slots, tone)
            if not prose and not facts:
                continue  # missing value -> omit the section, never guess
            if prose:
                sources.append(source)
                facts = {**facts, "_narrator": source}
            heading = _HEADINGS.get(key, key.title())
            if key == "psychological_note" and facts.get("section") == "H":
                # Was "Section H — Psychological State Note". "Section H" is the
                # internal spec's name for this slot, not something that means
                # anything to the founder reading it; it made the most personal
                # part of the report read like a clause reference.
                heading = "Before the business — how you're doing"
            sections.append(Section(key, heading, prose, _founder_facts(facts)))

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
        # Section H is Founder-Readiness-specific (see _slots_and_facts below) --
        # a red flag on an UNRELATED pillar (e.g. Financial Runway) must not
        # trigger it. Business DNA already surfaces those pillars' own bands and
        # notes. Gating on "any red_flag_pillars" here handed the LLM narrator an
        # empty-content section for a non-psychology red flag, and it fabricated
        # a claim to fill it -- so this must match the Founder-Readiness check
        # _slots_and_facts actually uses, not any red flag.
        show_psych = p.psychology_flagged or self._founder_readiness_flagged(p)

        if variant is ReportVariant.DISTRESS:
            # Acknowledgement FIRST; a support recommendation BEFORE any business.
            # NO discovery CTA -- no sales/discovery content reaches a distressed founder.
            head = ["acknowledgement", "support_recommendation"]
            body = ["founder_dna", "business_dna", "problem_path", "priority_actions"]
            if show_psych:
                body.insert(0, "psychological_note")
            return head + body

        # supporting_evidence sits directly after the root cause it supports, and
        # the roadmap/why pair directly after the actions they sequence and
        # justify. Each is dropped by _slots_and_facts when its source is empty,
        # so ordering them unconditionally here costs nothing.
        #
        # DISTRESS deliberately gets none of them (see above): that variant
        # de-prioritises business content entirely, and handing a founder in
        # distress a sequenced execution plan is the same mistake as handing
        # them a sales CTA.
        if variant is ReportVariant.NO_CLEAR_DIAGNOSIS:
            order = ["founder_summary", "founder_dna", "business_dna",
                     "areas_to_monitor", "priority_actions",
                     "recommended_roadmap", "why_steps"]
        elif variant is ReportVariant.LOW_CONFIDENCE:
            order = ["hedge", "founder_summary", "founder_dna", "business_dna",
                     "problem_path", "supporting_evidence", "priority_actions",
                     "recommended_roadmap", "why_steps"]
        else:  # STANDARD
            order = ["founder_summary", "founder_dna", "business_dna",
                     "problem_path", "supporting_evidence", "priority_actions",
                     "recommended_roadmap", "why_steps"]

        # Hard rule 1: Founder Psychology leads the narrative when flagged --
        # place the psychological note before Business DNA + Root cause.
        if show_psych:
            insert_at = 2 if p.psychology_flagged else order.index("business_dna") + 1
            order.insert(insert_at, "psychological_note")

        # Discovery CTA is the last section on every NON-distress variant (it is how
        # GoXL converts, and the frontend renders it last).
        order.append("discovery_cta")
        return order

    @staticmethod
    def _founder_readiness_state(p: ReportPayload):
        """The Founder Readiness pillar and whether it is in the Critical Gap
        state (band or explicit red flag) -- the single source of truth for
        Section H, so ordering and content agree on the same trigger."""
        fr = next((pl for pl in p.pillars if pl.name == "Founder Readiness"), None)
        critical_gap = bool(fr and (fr.band == "Critical Gap" or fr.red_flag_triggered))
        return fr, critical_gap

    def _founder_readiness_flagged(self, p: ReportPayload) -> bool:
        _, critical_gap = self._founder_readiness_state(p)
        return critical_gap

    # --- slots + facts per section ---------------------------------------
    def _slots_and_facts(self, key: str, p: ReportPayload, separate_identity: bool):
        if key == "founder_summary":
            return {"founder_name": p.founder_name}, {}

        if key == "founder_dna":
            # Open set of dimensions -- archetype plus whichever of the newer
            # ones (origin, vision, strengths/blind spots, stress response,
            # communication preference, and now the 6 phase-2 dimensions) the
            # payload actually resolved. A dimension with no source data
            # simply isn't a key here; the frontend's card grid renders
            # however many keys exist (see FounderDNA.jsx's generic
            # factList() rendering), so nothing here needs to special-case a
            # still-unanswered phase-2 dimension -- it appears automatically
            # once the founder answers questions for it.
            if not any((
                p.archetype, p.founder_origin, p.founder_vision,
                p.strengths_blind_spots, p.stress_response, p.communication_preference,
                p.phase2_dimensions,
            )):
                return {}, {}

            slots: dict = {}
            facts: dict = {}
            if p.archetype:
                a = p.archetype
                slots["archetype"] = {
                    "name": a.name, "core_motivation": a.core_motivation,
                    "is_confident": a.is_confident,
                }
                # facts: NO fit_score (a grade) in the founder-facing report.
                facts["archetype"] = {
                    "name": a.name, "code": a.code,
                    "core_motivation": a.core_motivation, "is_confident": a.is_confident,
                    "tentative": not a.is_confident,
                }
            if p.founder_origin:
                slots["origin"] = facts["origin"] = p.founder_origin
            if p.founder_vision:
                slots["vision"] = facts["vision"] = p.founder_vision
            if p.strengths_blind_spots:
                slots["strengths_blind_spots"] = facts["strengths_blind_spots"] = list(p.strengths_blind_spots)
            if p.stress_response:
                slots["stress_response"] = facts["stress_response"] = list(p.stress_response)
            if p.communication_preference:
                slots["communication_preference"] = facts["communication_preference"] = list(p.communication_preference)
            for dimension_code, answers in p.phase2_dimensions.items():
                slots[dimension_code] = facts[dimension_code] = list(answers)
            return slots, facts

        if key == "psychological_note":
            # Section H (Psychological State Note): a NAMED, spec-defined section
            # triggered when Founder Readiness is in the Critical Gap band (0-35).
            # Its content is that band's written description. It surfaces regardless
            # of the overall score. Identity fusion -> separation language.
            fr, critical_gap = self._founder_readiness_state(p)
            section_h_text = fr.band_description if (fr and critical_gap) else None
            note = fr.red_flag_note if fr else None
            slots = {"section_h_text": section_h_text, "red_flag_note": note,
                     "separate_identity": separate_identity,
                     "psychology_flagged": p.psychology_flagged}
            facts = {
                "section": "H" if critical_gap else None,
                "trigger": ("founder_readiness_critical_gap" if critical_gap
                            else "psychology_category"),
                "psychology_flagged": p.psychology_flagged,
                "red_flag_pillars": [rp.name for rp in p.red_flag_pillars],
                "founder_readiness_band": fr.band if fr else None,
            }
            # Belt-and-suspenders: skip if there is truly no content to narrate --
            # matches the Founder-Readiness-only trigger in _section_order, not
            # any red flag, so an unrelated pillar's flag never renders this
            # section with empty slots (which is what caused the LLM to fabricate
            # a claim to fill it).
            if not section_h_text and not note and not p.psychology_flagged and not critical_gap:
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
            # `slots` is narrator input; `facts` is rendered to the founder. They
            # must not be the same list. `red_flag_note` is the SCORING RULE for
            # a pillar -- operator text, written for whoever tunes the engine --
            # and shipping it in `facts` put this on a founder's Business DNA
            # page verbatim:
            #
            #   "A score below 35% in this pillar triggers Section H
            #    (Psychological State Note) in the Founder Clarity Report
            #    regardless of all other scores."
            #
            # The frontend cannot save us here: services/reports.js flattens
            # every fact key it does not explicitly know to be internal, so any
            # new key added above is founder-visible by default. Strip it at the
            # source instead, and leave `slots` intact -- the narrator may
            # legitimately use the note as guidance for prose it then writes in
            # the founder's own language.
            founder_facing = [
                {k: v for k, v in pillar.items() if k != "red_flag_note"}
                for pillar in pillars
            ]
            # Hard rule 2 in the facts: red-flag pillars are listed even when the
            # overall band is healthy.
            facts = {"overall_band": p.business_health_band, "pillars": founder_facing,
                     "red_flag_pillars": [rp.name for rp in p.red_flag_pillars]}
            if p.business_health_band is None and not pillars:
                return {}, {}
            return slots, facts

        if key == "problem_path":
            rcs = [{"name": rc.name, "category": rc.category,
                    "confirmation_status": rc.confirmation_status, "rank": rc.rank}
                   for rc in p.top_root_causes]
            # The founder's own words, plus the probe answers the
            # contradiction is drawn from. Both go into slots as well as
            # facts: this is the one section where the narrator is SUPPOSED to
            # quote the founder back to themselves, so withholding the text
            # from the LLM would leave it asserting a root cause with nothing
            # to weigh it against. Absent on pre-Current-Problem reports, in
            # which case the narrator falls back to root-causes-only prose.
            probes = [{"question": q, "answer": a} for q, a in p.symptom_probes]
            extra = {}
            if p.stated_symptom:
                extra["stated_symptom"] = p.stated_symptom
            if probes:
                extra["symptom_probes"] = probes
            if not rcs and not extra:
                return {}, {}
            # Hard rule 5: Not-Tested must never read as certain as Confirmed --
            # confirmation_status is carried on every finding (categorical, no %).
            return {"root_causes": rcs, **extra}, {"root_causes": rcs, **extra}

        if key == "areas_to_monitor":
            # Names ONLY -- never the raw category-risk score. The score is an
            # internal 0..1 number, and handing it to the LLM in slots let it
            # surface as "(scoring 0.2 and 0.18)" in prose, which is exactly the
            # raw-number leak the bands-not-numbers report rule exists to prevent.
            names = [c for c, _ in p.top_sub_threshold_categories]
            return {"categories": names}, {"categories": names}

        if key == "priority_actions":
            # The doc's free tier is "a 3+3 action plan (3 lines to
            # confirm/isolate the problem further, 3 lines to solve it)" --
            # three LINES per side, not three interventions. next_actions is a
            # list per intervention, so the cap has to be applied to the
            # flattened lines; capping the interventions instead let a single
            # intervention carrying five steps render a five-line "3 lines of
            # action". Ordering is already priority-sorted upstream, so the
            # first three are the three that matter most.
            def _capped(items):
                lines, out = 0, []
                for a in items:
                    if lines >= _ACTION_LINES_PER_SIDE:
                        break
                    take = list(a.next_actions)[: _ACTION_LINES_PER_SIDE - lines]
                    if not take:
                        continue
                    lines += len(take)
                    out.append({"next_actions": take, "priority": a.priority})
                return out

            confirm = _capped(p.confirm_actions)
            solve = _capped(p.solve_actions)
            slots = {"confirm_actions": confirm, "solve_actions": solve}
            # intervention IDs stay in the OWNER facts; the shared view strips them.
            facts = {"confirm_actions": confirm, "solve_actions": solve,
                     "intervention_ids": [a.intervention_id for a in
                                          (*p.confirm_actions, *p.solve_actions)
                                          if a.intervention_id is not None]}
            if not confirm and not solve:
                return {}, {}
            return slots, facts

        if key == "supporting_evidence":
            # The evidence trail for the root cause, in the founder's OWN words.
            # symptom_probes are (question, answer) pairs they gave before the
            # diagnosis ran, so quoting them back is not an assertion about them
            # -- it is showing the working. Confirmation status travels with each
            # root cause so an unconfirmed one cannot read as settled.
            probes = [{"question": q, "answer": a} for q, a in p.symptom_probes]
            causes = [{"name": rc.name, "rank": rc.rank,
                       "confirmation_status": rc.confirmation_status}
                      for rc in p.top_root_causes if rc.name]
            if not probes and not causes:
                return {}, {}
            slots = {"stated_symptom": p.stated_symptom, "probes": probes,
                     "root_causes": causes}
            facts = {"probes": probes, "root_causes": causes}
            return slots, facts

        if key == "recommended_roadmap":
            # Sequencing, not new advice: confirm/isolate before solve is the
            # order the engine already produces, and it is the one thing the
            # action list did not say out loud. Uncapped, unlike priority_actions
            # -- that section is the free tier's "3+3" summary; this one is the
            # full ordered set, and truncating a roadmap to three lines would
            # make the sequence it exists to show incomplete.
            def _steps(items):
                return [{"priority": a.priority, "next_actions": list(a.next_actions)}
                        for a in items if a.next_actions]

            confirm, solve = _steps(p.confirm_actions), _steps(p.solve_actions)
            if not confirm and not solve:
                return {}, {}
            slots = {"confirm_steps": confirm, "solve_steps": solve}
            return slots, {"confirm_steps": confirm, "solve_steps": solve}

        if key == "why_steps":
            # ActionItem.rationale reached the payload and was then dropped, so a
            # founder got three actions and no reason for any of them.
            #
            # It goes in SLOTS ONLY, never facts. Some rationales are engine
            # bookkeeping -- "Confirm recommendation addressing 1 ranked root
            # cause(s); lead cause ranked #1 (unconfirmed) in section
            # 'Competitive Awareness'. Supported by 10 semantic evidence
            # item(s)." -- and facts render verbatim, which is exactly how
            # red_flag_note ended up on a founder's screen. Passing it as a slot
            # hands it to the narrator to say in the founder's language instead,
            # under the same never-invent contract as every other section.
            rationales = [a.rationale for a in (*p.confirm_actions, *p.solve_actions)
                          if a.rationale]
            if not rationales:
                return {}, {}
            causes = [rc.name for rc in p.top_root_causes if rc.name]
            return {"rationales": rationales, "root_causes": causes}, {}

        if key == "acknowledgement":
            return {}, {"wellbeing_first": True}
        if key == "support_recommendation":
            return {}, {"wellbeing_first": True}
        if key == "hedge":
            return {}, {"provisional": True}
        if key == "discovery_cta":
            return {"cta": True}, {"cta": True}

        return {}, {}
