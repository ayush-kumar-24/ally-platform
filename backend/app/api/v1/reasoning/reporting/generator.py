"""Report generation -- assembles typed report DTOs from a ReasoningBundle.

Presentation only: every value is read from the pipeline DTOs; nothing is scored,
ranked or re-derived here. Narrative strings are formatting over existing data,
not new business logic. Deterministic: same bundle -> same report.

Rendering to markdown / dict / PDF lives in renderers.py -- this module produces
the structured DTOs those renderers consume.
"""

from __future__ import annotations

from decimal import Decimal

from app.api.v1.reasoning.reporting.schemas import (
    BusinessHealthSnapshot,
    CategorySnapshot,
    ConfidenceBreakdown,
    FounderReport,
    FounderStageSection,
    HealthBand,
    InternalReport,
    InterventionHighlight,
    PriorityAction,
    ReasoningBundle,
    RootCauseHighlight,
    SymptomHighlight,
)
from app.api.v1.reasoning.schemas import RootCauseDetection
from app.services.retrieval.evidence import RetrievalEvidence

_ZERO = Decimal("0")


class ReportGenerator:
    """Produces the Founder and Internal reports from a ReasoningBundle."""

    # --- Founder report ---------------------------------------------------

    def founder_report(self, bundle: ReasoningBundle) -> FounderReport:
        detection_by_rc = {d.root_cause_id: d for d in bundle.detections}
        top_scored = sorted(
            (s for s in bundle.scored_root_causes if s.is_top_finding),
            key=lambda s: s.rank,
        )

        top_root_causes = tuple(
            RootCauseHighlight(
                root_cause_id=s.root_cause_id,
                label=self._rc_label(bundle, s.root_cause_id),
                category=self._category_of(detection_by_rc.get(s.root_cause_id)),
                rank=s.rank,
                confirmation_status=s.confirmation_status.value,
                confidence=s.final_weighted_score,
                contributing_factors=self._readable_factors(
                    detection_by_rc[s.root_cause_id].contributing_factors
                    if s.root_cause_id in detection_by_rc
                    else ()
                ),
            )
            for s in top_scored
        )

        key_symptoms = tuple(
            SymptomHighlight(
                category=sym.category,
                symptoms=sym.symptoms,
                severity=sym.severity,
                is_distress=sym.is_distress,
                # The founder's own answers behind this finding. Empty when the
                # caller supplied no evidence map, which keeps this additive.
                evidence=self._evidence_for(bundle, sym.evidence_question_ids),
            )
            for sym in bundle.diagnosis.symptoms
        )

        recommendations = bundle.recommendations.recommendations
        priority_actions = tuple(
            PriorityAction(
                priority=rec.priority,
                recommendation_type=rec.recommendation_type.value,
                intervention_label=self._iv_label(bundle, rec),
                action=(rec.next_actions[0] if rec.next_actions else rec.rationale),
                confidence=rec.confidence,
            )
            for rec in recommendations
        )

        recommended_interventions = tuple(
            InterventionHighlight(
                intervention_id=rec.intervention_id,
                label=self._iv_label(bundle, rec),
                section=rec.section,
                recommendation_type=rec.recommendation_type.value,
                next_actions=rec.next_actions,
                supporting_root_causes=rec.supporting_root_causes,
            )
            for rec in recommendations
        )

        return FounderReport(
            generated_for=self._founder_name(bundle),
            distress_acknowledged=bundle.diagnosis.distress_mode,
            executive_summary=self._executive_summary(bundle, top_root_causes),
            founder_stage=self._founder_stage(bundle),
            business_health=self._business_health(bundle),
            top_root_causes=top_root_causes,
            key_symptoms=key_symptoms,
            priority_actions=priority_actions,
            recommended_interventions=recommended_interventions,
            next_steps=self._next_steps(
                recommendations,
                already_shown=tuple(a.action for a in priority_actions),
            ),
            business_health_score=bundle.business_health,
        )

    def _founder_stage(self, bundle: ReasoningBundle) -> FounderStageSection:
        stage = bundle.diagnosis.stage_detection
        if stage.stage_id is None:
            narrative = "Your current stage could not be determined from the session."
        else:
            narrative = (
                f"You are operating at the {stage.stage_name or f'stage {stage.stage_id}'} "
                f"stage (detection confidence {self._pct(stage.confidence)})."
            )
        return FounderStageSection(
            stage_id=stage.stage_id,
            stage_name=stage.stage_name,
            confidence=stage.confidence,
            narrative=narrative,
        )

    def _business_health(self, bundle: ReasoningBundle) -> BusinessHealthSnapshot:
        categories = tuple(
            CategorySnapshot(
                category=c.category,
                risk=c.normalised_risk,
                band=self._band(c.is_flagged, c.normalised_risk),
                is_flagged=c.is_flagged,
            )
            for c in bundle.diagnosis.category_risks
        )
        flagged = sum(1 for c in categories if c.is_flagged)
        if flagged == 0:
            headline = "No category crossed the risk threshold in this session."
        else:
            # Ranked by risk, and only the worst few are named. This used to
            # list EVERY flagged category alphabetically -- "10 area(s) need
            # attention: Business Model Design, Business Planning, Competitive
            # Awareness, ..." -- which tells a founder their whole business is
            # on fire and gives them no way to tell where to start. Naming ten
            # problems ranks none of them.
            worst = sorted(
                (c for c in categories if c.is_flagged),
                key=lambda c: c.risk, reverse=True,
            )
            lead = ", ".join(c.category.lower() for c in worst[:3])
            rest = flagged - min(3, len(worst))
            headline = (
                f"The areas under most strain are {lead}"
                + (f", with {rest} other area(s) also flagged." if rest > 0 else ".")
            )
        return BusinessHealthSnapshot(
            overall_confidence=bundle.overall_confidence_score,
            routing_state=bundle.routing_state,
            flagged_category_count=flagged,
            categories=categories,
            headline=headline,
        )

    def _executive_summary(self, bundle, top_root_causes) -> str:
        """What Ally understood, in the founder's terms.

        This used to be a status receipt -- "your diagnosis is complete. We
        identified 3 priority root cause(s) across 10 flagged area(s)." Counting
        findings is not the same as saying what they are, and a founder reading
        their own report learned nothing from it: every number in that sentence
        described the process rather than their business. It now leads with the
        finding itself, names the runner-up, and keeps the confidence figure last
        as a qualifier rather than the headline.
        """
        name = self._founder_name(bundle)
        parts: list[str] = []

        if bundle.diagnosis.distress_mode:
            # Stays first, before any finding: wellbeing precedes analysis.
            parts.append(
                f"{name}, before anything else -- we noticed signs this has been "
                "a hard stretch, and that matters more than any of what follows."
            )
        else:
            parts.append(f"{name}, here is what we understood.")

        if top_root_causes:
            primary = top_root_causes[0]
            parts.append(
                f"The main thing holding you back looks like {primary.label.lower()}"
                f", showing up most clearly in {primary.category.lower()}."
            )
            if len(top_root_causes) > 1:
                others = ", ".join(rc.label.lower() for rc in top_root_causes[1:3])
                parts.append(f"Underneath it we also found {others}.")
        else:
            # Honest rather than silent: no confirmed cause is a real outcome,
            # not an error, and pretending otherwise would invent a finding.
            parts.append(
                "Nothing rose to the level of a confirmed root cause from this "
                "session -- there is signal here, but not yet enough to name one "
                "cause with confidence."
            )

        parts.append(
            "Confidence in this read is "
            f"{self._pct(bundle.overall_confidence_score, of_100=True)}."
        )
        return " ".join(parts)

    def _next_steps(self, recommendations, already_shown: tuple[str, ...] = ()) -> tuple[str, ...]:
        """Everything to do next, minus what priority_actions already said.

        priority_actions takes each recommendation's FIRST next_action, and this
        used to re-emit every action including those -- so the same three
        sentences appeared twice in one report, once as "your priorities" and
        again as "next steps". A founder reading it twice does not read it twice
        as carefully; they conclude the report is padded.
        """
        steps: list[str] = []
        seen: set[str] = set(already_shown)
        for rec in recommendations:
            for action in rec.next_actions:
                if action not in seen:
                    seen.add(action)
                    steps.append(action)
        return tuple(steps)

    # --- Internal report --------------------------------------------------

    def internal_report(self, bundle: ReasoningBundle) -> InternalReport:
        diagnosis = bundle.diagnosis
        return InternalReport(
            session_id=bundle.session_id,
            confidence_breakdown=ConfidenceBreakdown(
                overall_confidence=bundle.overall_confidence_score,
                routing_state=bundle.routing_state,
                top_finding_count=sum(1 for s in bundle.scored_root_causes if s.is_top_finding),
                distress_mode=diagnosis.distress_mode,
                distress_signal_count=diagnosis.distress_signal_count,
            ),
            scoring_audit=tuple(bundle.scored_root_causes),
            category_risk_analysis=diagnosis.category_risks,
            stage_detection=diagnosis.stage_detection,
            recommendation_rationale=bundle.recommendations.recommendations,
            retrieval_evidence=self._aggregate_retrieval_evidence(bundle),
            llm_reasoning=tuple(
                c.llm_classification
                for c in diagnosis.classifications
                if c.llm_classification is not None
            ),
            diagnostic_trace=tuple(bundle.detections),
            follow_up_triggers=diagnosis.follow_up_triggers,
            symptoms=diagnosis.symptoms,
        )

    def _aggregate_retrieval_evidence(
        self, bundle: ReasoningBundle
    ) -> tuple[RetrievalEvidence, ...]:
        """Dedup retrieval hits across detections and recommendations by
        (source, source_id), preserving first occurrence. No re-querying."""
        seen: set[tuple[str, int]] = set()
        collected: list[RetrievalEvidence] = []
        sources: list[RetrievalEvidence] = []
        for detection in bundle.detections:
            sources.extend(detection.semantic_evidence)
        for rec in bundle.recommendations.recommendations:
            sources.extend(rec.supporting_retrieval_evidence)
        for ev in sources:
            key = (ev.source.value, ev.source_id)
            if key not in seen:
                seen.add(key)
                collected.append(ev)
        return tuple(collected)

    # --- Helpers ----------------------------------------------------------

    def _rc_label(self, bundle: ReasoningBundle, root_cause_id: int) -> str:
        return bundle.root_cause_labels.get(root_cause_id, f"RC-{root_cause_id}")

    def _iv_label(self, bundle: ReasoningBundle, rec) -> str:
        """A label a founder can read, never an internal code.

        Two things were leaking into founder-facing reports here:

        1. `intervention_id=0` is the deliberate marker for an LLM-generated
           recommendation with no curated library row behind it
           (recommendation_llm.py). The old fallback turned that marker into the
           literal string "INT-0" and printed it as the recommendation's name.
        2. Even on the success path the label was `intervention_code` -- "INT-052"
           -- which is a catalogue key, not a name.

        Neither means anything to the founder reading their own report. Prefer
        the human-readable `capability_domain` the interventions table already
        carries ("Quality Management"), and for a generated recommendation name
        it after the root cause it addresses, which is the only thing that
        actually describes it.
        """
        label = bundle.intervention_labels.get(rec.intervention_id)
        if label:
            return label
        causes = getattr(rec, "supporting_root_causes", ()) or ()
        if causes:
            return self._rc_label(bundle, causes[0])
        return "Recommended focus"

    def _readable_factors(self, factors: tuple[str, ...]) -> tuple[str, ...]:
        """Translate scoring internals into why-we-think-this, for the founder.

        `contributing_factors` is the engine's own audit trail and stays as-is in
        the internal consultant report, where those terms are meaningful. In the
        FOUNDER report it was printed verbatim -- "Direct Question Mapping",
        "Semantic Support (11)", "Category Risk: Idea & Validation" -- which
        tells a founder nothing about why a conclusion was reached and reads like
        debug output that escaped into a document about their business.

        Unrecognised factors are dropped rather than passed through: a new
        internal term appearing in a founder's report is the failure mode this
        exists to prevent, and losing one line of provenance is the cheaper
        mistake.
        """
        out: list[str] = []
        for f in factors:
            if f.startswith("Category Risk:"):
                area = f.split(":", 1)[1].strip()
                text = f"Several of your answers in {area.lower()} pointed the same way"
            elif f == "Direct Question Mapping":
                text = "Your answers matched this pattern directly"
            elif f == "Direct Red Signal":
                text = "At least one answer was a strong signal on its own"
            elif f.startswith("Semantic Support"):
                text = "Similar cases in our knowledge base support this read"
            else:
                continue
            if text not in out:
                out.append(text)
        return tuple(out)

    def _evidence_for(
        self, bundle: ReasoningBundle, question_ids: tuple[int, ...]
    ) -> tuple[tuple[str, str], ...]:
        """The founder's own (question, answer) pairs behind a finding.

        Capped at three: the point is to let them recognise the finding as
        theirs, not to replay the transcript. Silently yields nothing for ids the
        caller did not supply, so a missing map degrades to the previous
        behaviour rather than failing the report.
        """
        out: list[tuple[str, str]] = []
        for qid in question_ids:
            pair = bundle.answer_evidence.get(qid)
            if pair:
                out.append(pair)
            if len(out) == 3:
                break
        return tuple(out)

    def _founder_name(self, bundle: ReasoningBundle) -> str:
        profile = bundle.founder_profile
        return profile.full_name or f"Founder {profile.founder_id}"

    def _category_of(self, detection: RootCauseDetection | None) -> str:
        return detection.category if detection is not None else "Uncategorised"

    def _band(self, is_flagged: bool, risk: Decimal) -> HealthBand:
        if is_flagged:
            return HealthBand.AT_RISK
        if risk > _ZERO:
            return HealthBand.WATCH
        return HealthBand.HEALTHY

    def _pct(self, value: Decimal, of_100: bool = False) -> str:
        if of_100:
            # Was `f"{value}/100"` -- the raw Decimal, unrounded, so a report read
            # "confidence is 0.0000/100" instead of "0/100". The percent branch
            # below already rounds; this one didn't.
            return f"{value.quantize(Decimal('1'))}/100"
        return f"{(value * 100).quantize(Decimal('1'))}%"
