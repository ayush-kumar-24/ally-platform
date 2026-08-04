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
                contributing_factors=(
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
            )
            for sym in bundle.diagnosis.symptoms
        )

        recommendations = bundle.recommendations.recommendations
        priority_actions = tuple(
            PriorityAction(
                priority=rec.priority,
                recommendation_type=rec.recommendation_type.value,
                intervention_label=self._iv_label(bundle, rec.intervention_id),
                action=(rec.next_actions[0] if rec.next_actions else rec.rationale),
                confidence=rec.confidence,
            )
            for rec in recommendations
        )

        recommended_interventions = tuple(
            InterventionHighlight(
                intervention_id=rec.intervention_id,
                label=self._iv_label(bundle, rec.intervention_id),
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
            next_steps=self._next_steps(recommendations),
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
            names = ", ".join(c.category for c in categories if c.is_flagged)
            headline = f"{flagged} area(s) need attention: {names}."
        return BusinessHealthSnapshot(
            overall_confidence=bundle.overall_confidence_score,
            routing_state=bundle.routing_state,
            flagged_category_count=flagged,
            categories=categories,
            headline=headline,
        )

    def _executive_summary(self, bundle, top_root_causes) -> str:
        name = self._founder_name(bundle)
        flagged = sum(1 for c in bundle.diagnosis.category_risks if c.is_flagged)
        parts = [
            f"{name}, your diagnosis is complete.",
            f"We identified {len(top_root_causes)} priority root cause(s) "
            f"across {flagged} flagged area(s).",
            f"Overall diagnostic confidence is {self._pct(bundle.overall_confidence_score, of_100=True)}.",
        ]
        if bundle.diagnosis.distress_mode:
            parts.insert(
                1,
                "Before the business findings: we noticed signs this has been a "
                "hard stretch, and your wellbeing comes first.",
            )
        return " ".join(parts)

    def _next_steps(self, recommendations) -> tuple[str, ...]:
        steps: list[str] = []
        seen: set[str] = set()
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

    def _iv_label(self, bundle: ReasoningBundle, intervention_id: int) -> str:
        return bundle.intervention_labels.get(intervention_id, f"INT-{intervention_id}")

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
