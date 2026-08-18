"""ReasoningService -- end-to-end orchestrator for the Tier-1 reasoning pipeline.

Runs, for one COMPLETED session, exactly once:

    Diagnosis -> Category Scoring -> Stage Detection -> Symptom Detection
    -> Root Cause -> Confidence -> Retrieval Enrichment -> Recommendation
    -> Report Generation -> Persist

Guarantees:
  * Exactly once: an active founder_report is the idempotency signal; a re-trigger
    is a no-op. A row-lock on the session during persist serialises concurrent
    completions, and the persist re-checks the guard under the lock.
  * Single transaction: all reads and writes run in one transaction; the writes
    commit together at the end, and any failure rolls everything back.
  * No engine logic here: this only sequences the engines, times/logs each stage,
    assembles the report bundle, and persists. Engines are untouched.

Persistence covers detected_root_causes, the session confidence/routing/distress
fields, and one founder_reports row carrying both the founder report (in
`insights`) and the internal consultant report (in `business_dna`).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.ally.memory.schemas import MemoryType
from app.api.v1.reasoning.config import ReasoningConfig
from app.api.v1.reasoning.engines.archetype import ArchetypeEngine
from app.api.v1.reasoning.engines.business_health import BusinessHealthScorer
from app.api.v1.reasoning.engines.founder_dna_extras import (
    origin_and_vision,
    resolve_behavioural_dimensions,
    resolve_phase2_dimensions,
)
from app.api.v1.reasoning.engines.psychological_state import (
    PsychologicalStateEngine,
    PsychologicalStateSignalScorer,
)
from app.api.v1.reasoning.engines.diagnosis import DeterministicDiagnosisEngine
from app.api.v1.reasoning.engines.distress_language import build_distress_assessment
from app.api.v1.reasoning.errors import (
    FeatureDisabledError,
    ReasoningError,
    ReasoningPersistenceError,
    SessionNotAnalyzableError,
)
from app.api.v1.reasoning.interfaces import (
    ConfidenceModel,
    ReasoningContext,
    RecommendationEngine,
    RootCauseEngine,
)
from app.api.v1.reasoning.reporting import (
    BusinessProfile,
    DictReportRenderer,
    FounderProfile,
    MarkdownReportRenderer,
    ReasoningBundle,
    ReportGenerator,
)
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.schemas import (
    ReasoningResult,
    RecommendationType,
    ScoredRootCause,
)
from app.core.logger import logger
from app.models import (
    DetectedRootCause,
    FounderReport,
    InternalIntelligenceReport,
    ReportType,
    SessionStatus,
)
from app.models.diagnosis import Founder


# Routing state for a session that leaves the diagnostic loop for wellbeing
# support (CONFIDENCE_HARD_RULES rule 1). Distinct from the confidence-driven
# states so the app can divert to a support flow instead of asking more questions.
DISTRESS_SUPPORT_ROUTE = "distress_support"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


class ReasoningService:
    def __init__(
        self,
        db: Session,
        repository: ReasoningRepository,
        config: ReasoningConfig,
        diagnosis_engine: DeterministicDiagnosisEngine,
        root_cause_engine: RootCauseEngine,
        confidence_model: ConfidenceModel,
        recommendation_engine: RecommendationEngine,
        report_generator: ReportGenerator | None = None,
        retrieval_enabled: bool = False,
        consistency_detector=None,
        distress_detector=None,
        memory=None,
        archetype_engine=None,
    ):
        self.db = db
        self.repository = repository
        self.config = config
        self.diagnosis_engine = diagnosis_engine
        self.root_cause_engine = root_cause_engine
        self.confidence_model = confidence_model
        self.recommendation_engine = recommendation_engine
        self.report_generator = report_generator or ReportGenerator()
        self.retrieval_enabled = retrieval_enabled
        # Founder memory (M6), optional -- when supplied, a completed diagnosis is
        # also recorded as a memory item so the chat section's memory_summary block
        # carries it, not just the (session-only) AllyContext.diagnosis. None =>
        # diagnosis stays visible to chat only via AllyContext, same as before.
        self.memory = memory
        # Answer-consistency detector (input (c) of the confidence score). None =>
        # unmeasured => excluded + renormalised by the confidence strategy.
        self.consistency_detector = consistency_detector
        # Distress language detector (#11). None => deterministic proxy. When set,
        # it REPLACES the proxy and fails CLOSED (error -> high distress).
        self.distress_detector = distress_detector
        self.business_health_scorer = BusinessHealthScorer(repository)
        self.psychological_state_engine = PsychologicalStateEngine(
            repository,
            PsychologicalStateSignalScorer(repository),
            config.distress.high_distress_score,
        )
        # Injectable so the LLM assigner can be swapped in without touching this
        # orchestrator; both satisfy assign(texts) -> ArchetypeMatch | None.
        self.archetype_engine = archetype_engine or ArchetypeEngine(repository)

    async def analyze_session(
        self, founder: Founder, session_id: int, *, force: bool = False
    ) -> ReasoningResult | None:
        """Run the full pipeline once for a completed session and persist results.

        Returns the ReasoningResult, or None when the session was already analysed
        (idempotent no-op). Any failure rolls the whole transaction back.
        """
        session = self._load_analyzable_session(founder, session_id)

        if not force and self.repository.get_active_report(session_id) is not None:
            logger.info(
                "reasoning already completed; skipping",
                extra={"session_id": session_id, "stage": "idempotency_guard"},
            )
            return None

        pipeline_start = time.perf_counter()
        try:
            result = await self._run_pipeline(session, founder, force=force)
        except ReasoningError:
            self.db.rollback()
            raise
        except Exception as exc:  # any engine/report failure -> roll everything back
            self.db.rollback()
            logger.error(
                "reasoning pipeline failed; rolled back",
                extra={"session_id": session_id, "stage": "pipeline"},
                exc_info=exc,
            )
            raise
        logger.info(
            "reasoning pipeline complete",
            extra={
                "session_id": session_id,
                "stage": "pipeline",
                "duration_ms": _elapsed_ms(pipeline_start),
                "skipped": result is None,
            },
        )
        return result

    # --- Pipeline ---------------------------------------------------------

    async def score_only(self, session, founder: Founder) -> Decimal | None:
        """Confidence for a session AS IT STANDS, without producing a report.

        The minimum needed to answer "how sure are we now": diagnosis (category /
        stage / symptom) -> root-cause detection and ranking -> confidence. It
        deliberately stops there. Retrieval enrichment, recommendations, business
        health, archetype and report generation all belong to a finished
        diagnosis; running them after every answer would cost thirty times what a
        diagnosis should and produce a report nobody asked for yet.

        Writes nothing. The caller decides what to do with the number -- keeping
        this read-only means it cannot half-update a session if it throws.

        Returns None when the session has no answers yet.
        """
        context = self._build_context(session, founder)
        answers = self.repository.get_answers_for_session(session.session_id)
        if not answers:
            return None
        questions = self.repository.get_questions_by_ids(a.question_id for a in answers)

        diagnosis = await self.diagnosis_engine.diagnose(answers, questions, context)
        detections = self.root_cause_engine.detect(
            list(diagnosis.classifications), list(diagnosis.category_risks),
            questions, context,
        )
        scored = self.confidence_model.score_and_rank(detections, context)
        # Consistency is left unmeasured here: the detector is an LLM call over
        # the whole answer history, which after every answer is the same O(n^2)
        # problem that rules out re-classification. The confidence strategy
        # already excludes an unavailable signal and renormalises the rest, so
        # omitting it shifts weight to the measured signals rather than scoring
        # a zero it never earned. The full pipeline measures it once at the end.
        inputs = self.confidence_model.build_confidence_inputs(
            diagnosis=diagnosis,
            scored=scored,
            questions_answered=len(answers),
            context=context,
            consistency=None,
        )
        return self.confidence_model.overall_confidence(inputs, context)

    async def _run_pipeline(
        self, session, founder: Founder, *, force: bool = False
    ) -> ReasoningResult | None:
        session_id = session.session_id
        context = self._build_context(session, founder)

        start = time.perf_counter()
        answers = self.repository.get_answers_for_session(session_id)
        if not answers:
            raise SessionNotAnalyzableError("Session has no answers to analyse.")
        questions = self.repository.get_questions_by_ids(a.question_id for a in answers)
        self._log_stage("load_inputs", session_id, start, answers=len(answers))

        # --- Diagnosis (category scoring + stage + symptom detection) ---
        start = time.perf_counter()
        diagnosis = await self.diagnosis_engine.diagnose(answers, questions, context)
        self._log_stage(
            "diagnosis", session_id, start,
            classifications=len(diagnosis.classifications),
            flagged=sum(1 for c in diagnosis.category_risks if c.is_flagged),
            stage_id=diagnosis.stage_detection.stage_id,
            symptoms=len(diagnosis.symptoms),
            distress=diagnosis.distress_mode,
        )
        if diagnosis.stage_detection.stage_id is not None:
            context = replace(context, stage_id=diagnosis.stage_detection.stage_id)

        # --- Psychological state: compute the session distress score ---
        # Sets sessions.session_distress_score (previously never computed -> 0),
        # which the Confidence model reads for its reliability modifier and the
        # High-Distress override. Deterministic proxy until the LLM signal
        # detector is wired; see PsychologicalStateEngine.
        start = time.perf_counter()
        if self.distress_detector is not None:
            # Real LLM language detection over the founder's words. FAILS CLOSED:
            # a detector error maps to high distress + override (never a clean
            # "no signals"), so the session routes to wellbeing support.
            catalog = self.repository.get_distress_signals_catalog()
            det_result = await self.distress_detector.detect([a.answer_text for a in answers])
            distress = build_distress_assessment(
                det_result, catalog,
                scorer=self.psychological_state_engine.scorer,
                high_distress_score=self.config.distress.high_distress_score,
                empathy_lookup=self.repository.get_empathy_protocol,
            )
            self._log_stage(
                "distress_detection", session_id, start,
                detector_status=det_result.status,
                signals_present=len(det_result.present_ids),
                session_distress_score=str(distress.session_distress_score),
                high_distress=distress.is_high_distress,
            )
        else:
            distress = self.psychological_state_engine.assess_from_diagnosis(
                list(diagnosis.classifications), questions
            )
            self._log_stage(
                "psychological_state", session_id, start,
                session_distress_score=str(distress.session_distress_score),
                high_distress=distress.is_high_distress,
            )
        session.session_distress_score = distress.session_distress_score

        # --- Root Cause (+ retrieval enrichment inside the engine) ---
        start = time.perf_counter()
        detections = self.root_cause_engine.detect(
            list(diagnosis.classifications), list(diagnosis.category_risks),
            questions, context,
        )
        self._log_stage(
            "root_cause", session_id, start,
            detections=len(detections), retrieval_enabled=self.retrieval_enabled,
        )

        # --- Confidence ---
        start = time.perf_counter()
        scored = self.confidence_model.score_and_rank(detections, context)
        # Answer consistency (input (c)). Runs only when a detector is wired; a
        # detector failure returns an UNAVAILABLE result, which the confidence
        # strategy excludes and renormalises around (never a false 1.0).
        consistency = None
        if self.consistency_detector is not None:
            consistency = await self.consistency_detector.assess(answers, questions)
            self._log_stage(
                "answer_consistency", session_id, start,
                available=consistency.available,
                score=(str(consistency.score) if consistency.score is not None else None),
                contradictions=len(consistency.contradictions),
            )
        confidence_inputs = self.confidence_model.build_confidence_inputs(
            diagnosis=diagnosis,
            scored=scored,
            questions_answered=len(answers),
            context=context,
            consistency=consistency,
        )
        overall_confidence = self.confidence_model.overall_confidence(
            confidence_inputs, context
        )
        routing_state = self.config.confidence.routing_state_for(overall_confidence)
        # Distress overrides routing entirely: wellbeing before diagnostic
        # completeness. The session leaves the confidence loop for a support path
        # rather than being told to keep answering questions.
        if confidence_inputs.distress_override or distress.distress_override:
            routing_state = DISTRESS_SUPPORT_ROUTE
        self._log_stage(
            "confidence", session_id, start,
            scored=len(scored), overall_confidence=str(overall_confidence),
            routing_state=routing_state,
        )

        # --- Recommendation ---
        start = time.perf_counter()
        top = [s for s in scored if s.is_top_finding]
        semantic_evidence = {d.root_cause_id: d.semantic_evidence for d in detections}
        recommendations = self.recommendation_engine.recommend(
            top, context, semantic_evidence=semantic_evidence
        )
        self._log_stage(
            "recommendation", session_id, start,
            recommendations=len(recommendations.recommendations),
        )

        # --- Business Health Score (readiness pillars; independent of confidence) ---
        # Fail-closed: if the pillar scoring formula is not configured, omit the
        # score from the report rather than failing the whole pipeline.
        start = time.perf_counter()
        try:
            business_health = self.business_health_scorer.compute(
                list(diagnosis.classifications), questions, context
            )
            self._log_stage(
                "business_health", session_id, start,
                overall=str(business_health.overall_score),
                red_flags=len(business_health.red_flags),
            )
        except FeatureDisabledError as exc:
            business_health = None
            logger.info(
                "business health score disabled; omitting from report",
                extra={"session_id": session_id, "stage": "business_health",
                       "reason": str(exc)},
            )

        # --- Founder archetype / pattern (deterministic lexical match; LLM seam) ---
        start = time.perf_counter()
        archetype = self.archetype_engine.assign([a.answer_text for a in answers])
        self._log_stage(
            "archetype", session_id, start,
            archetype=(archetype.name if archetype is not None else None),
            fit=(str(archetype.score) if archetype is not None else None),
        )

        # --- Report generation ---
        start = time.perf_counter()
        founder_report, internal_report = self._generate_reports(
            session, founder, context, diagnosis, detections, scored,
            recommendations, overall_confidence, routing_state, business_health,
        )
        self._log_stage("report_generation", session_id, start)

        # --- Persist (single committed transaction) ---
        return self._persist(
            session=session,
            founder=founder,
            scored=scored,
            overall_confidence=overall_confidence,
            routing_state=routing_state,
            distress_mode=diagnosis.distress_mode or distress.is_high_distress,
            recommendations=recommendations,
            founder_report=founder_report,
            internal_report=internal_report,
            archetype=archetype,
            business_health=business_health,
            distress_assessment=distress,
            force=force,
        )

    # --- Report assembly (delegates to the report module) -----------------

    def _generate_reports(
        self, session, founder, context, diagnosis, detections, scored,
        recommendations, overall_confidence, routing_state, business_health,
    ):
        rc_map = self.repository.get_root_causes_by_ids(s.root_cause_id for s in scored)
        iv_map = self.repository.get_interventions_by_ids(
            r.intervention_id for r in recommendations.recommendations
        )
        industry_name = None
        if context.industry_id is not None:
            industry = self.repository.get_industry(context.industry_id)
            industry_name = industry.industry_name if industry is not None else None

        bundle = ReasoningBundle(
            diagnosis=diagnosis,
            detections=tuple(detections),
            scored_root_causes=tuple(scored),
            recommendations=recommendations,
            overall_confidence_score=overall_confidence,
            routing_state=routing_state,
            founder_profile=FounderProfile(founder.founder_id, founder.full_name),
            business_profile=BusinessProfile(industry=industry_name),
            session_id=session.session_id,
            root_cause_labels={rid: rc.root_cause_name for rid, rc in rc_map.items()},
            intervention_labels={iid: iv.intervention_code for iid, iv in iv_map.items()},
            business_health=business_health,
        )
        return (
            self.report_generator.founder_report(bundle),
            self.report_generator.internal_report(bundle),
        )

    def _record_diagnosis_memory(self, founder: Founder, session, founder_report) -> None:
        """Record the completed diagnosis as founder memory (best-effort). Runs
        AFTER the report transaction has committed, on its own failure path: a
        memory-write error must never undo or fail an already-persisted diagnosis.
        Upserts by the fixed key `diagnosis_summary`, so a later diagnosis replaces
        the memory item rather than accumulating one per session."""
        if self.memory is None:
            return
        try:
            self.memory.store(
                founder.founder_id,
                MemoryType.STRATEGIC,
                founder_report.executive_summary,
                importance=90,
                key="diagnosis_summary",
                session_id=session.session_id,
                actor="system",
            )
        except Exception as exc:  # noqa: BLE001 -- best-effort, never fail the caller
            logger.warning(
                "reasoning: failed to record diagnosis summary as founder memory",
                extra={"session_id": session.session_id, "stage": "persist", "error": str(exc)},
            )

    # --- Persistence ------------------------------------------------------

    def _persist(
        self,
        *,
        session,
        founder: Founder,
        scored: list[ScoredRootCause],
        overall_confidence: Decimal,
        routing_state: str,
        distress_mode: bool,
        recommendations,
        founder_report,
        internal_report,
        archetype=None,
        business_health=None,
        distress_assessment=None,
        force: bool = False,
    ) -> ReasoningResult | None:
        start = time.perf_counter()
        renderer = DictReportRenderer()
        try:
            # Lock the session and re-check the guard: exactly-once under races.
            # A forced reprocess intentionally overwrites, so it skips the guard.
            self.repository.get_session_for_update(session.session_id)
            if not force and self.repository.get_active_report(session.session_id) is not None:
                self.db.rollback()
                logger.info(
                    "reasoning completed concurrently; skipping persist",
                    extra={"session_id": session.session_id, "stage": "persist"},
                )
                return None

            rows = [self._to_detection_row(session, founder, s) for s in scored]
            self.repository.replace_detected_root_causes(session.session_id, rows)

            session.overall_confidence_score = overall_confidence
            session.routing_state = routing_state
            session.distress_mode_triggered = distress_mode
            session.session_state = self._session_state(session, distress_mode)
            session.last_activity_at = _utcnow()

            self.repository.deactivate_existing_reports(session.session_id)

            # Founder DNA jsonb -- archetype (always, when assigned) plus
            # whichever of the newer dimensions actually resolved to real data.
            # The 6 phase-2 dimensions (Purpose & Mission, Core Values, Mindset
            # & Excellence, Energy Patterns, Decision Style, Focus/Attention)
            # come from the founder_dna_answers a founder gives BEFORE this
            # diagnosis even starts (see app/api/v1/founder_dna/) -- they are
            # simply absent here if that phase hasn't produced anything for a
            # given dimension yet, never guessed.
            founder_dna_dict: dict = {}
            if archetype is not None:
                founder_dna_dict["archetype"] = archetype.as_founder_dna()
            founder_dna_dict.update(origin_and_vision(founder))
            try:
                codes = self._root_cause_codes(scored)
                founder_dna_dict.update(resolve_behavioural_dimensions(self.repository, codes))
            except Exception:  # noqa: BLE001 -- optional enrichment, never blocks the report
                logger.warning(
                    "founder DNA behavioural-dimension lookup failed; leaving those keys absent",
                    extra={"session_id": session.session_id},
                )
            try:
                phase2 = resolve_phase2_dimensions(self.db, founder.founder_id)
                # Asked answers beat the onboarding fields for origin/vision:
                # a considered reply to a situational question is better
                # material than a signup-form box. Popped rather than merged
                # so they land as strings under their real keys -- the report
                # payload reads those two as text, not lists.
                asked_origin = phase2.pop("_origin_text", None)
                asked_vision = phase2.pop("_vision_text", None)
                if asked_origin:
                    founder_dna_dict["origin"] = asked_origin
                if asked_vision:
                    founder_dna_dict["vision"] = asked_vision
                founder_dna_dict.update(phase2)
            except Exception:  # noqa: BLE001 -- optional enrichment, never blocks the report
                logger.warning(
                    "founder DNA phase-2 dimension lookup failed; leaving those keys absent",
                    extra={"session_id": session.session_id},
                )

            report = FounderReport(
                founder_id=founder.founder_id,
                session_id=session.session_id,
                report_type=ReportType.FULL_DIAGNOSIS.value,
                summary=founder_report.executive_summary,
                top_root_cause_ids=[s.root_cause_id for s in scored if s.is_top_finding],
                recommended_intervention_ids=list(recommendations.intervention_ids),
                confirm_actions=self._action_dicts(recommendations, RecommendationType.CONFIRM),
                solve_actions=self._action_dicts(recommendations, RecommendationType.SOLVE),
                distress_acknowledged_first=distress_mode,
                session_state_at_generation=session.session_state,
                # Founder report -> insights (its founder-facing slot).
                insights=renderer.render_founder(founder_report),
                # Founder pattern/archetype + newer dimensions -> founder_dna.
                founder_dna=(founder_dna_dict or None),
                # Business health (readiness pillars) -> business_dna (structured,
                # queryable for the Business-DNA report + dashboard display).
                business_dna=self._business_dna(business_health),
            )
            self.repository.add_report(report)  # flush populates report_id

            # Internal consultant report -> its dedicated table, linked to the
            # founder report via report_id.
            self.repository.replace_internal_report(
                session.session_id,
                self._build_internal_report_row(
                    session, founder, report.report_id, internal_report,
                    distress_assessment, scored,
                ),
            )

            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "database error persisting reasoning result; rolled back",
                extra={"session_id": session.session_id, "stage": "persist"},
                exc_info=exc,
            )
            raise ReasoningPersistenceError()

        self.db.refresh(session)
        self._record_diagnosis_memory(founder, session, founder_report)
        self._log_stage(
            "persist", session.session_id, start,
            detected_root_causes=len(scored), report_id=report.report_id,
        )
        return ReasoningResult(
            session_id=session.session_id,
            founder_id=founder.founder_id,
            detected_root_causes=tuple(scored),
            overall_confidence_score=overall_confidence,
            routing_state=routing_state,
            distress_mode=distress_mode,
            recommendations=recommendations,
            report_id=report.report_id,
        )

    # --- Helpers ----------------------------------------------------------

    def _load_analyzable_session(self, founder: Founder, session_id: int):
        session = self.repository.get_session(session_id)
        if session is None or session.founder_id != founder.founder_id:
            raise SessionNotAnalyzableError("No analysable session was found.")
        if session.status != SessionStatus.COMPLETED:
            raise SessionNotAnalyzableError(
                f"Session {session_id} is '{session.status}', not 'completed'."
            )
        return session

    def _build_context(self, session, founder: Founder) -> ReasoningContext:
        return ReasoningContext(
            session=session,
            founder=founder,
            config=self.config,
            stage_id=session.founder_stage_id or founder.stage_id,
            industry_id=session.founder_industry_id or founder.industry_mapped_id,
        )

    def _to_detection_row(
        self, session, founder: Founder, scored: ScoredRootCause
    ) -> DetectedRootCause:
        return DetectedRootCause(
            session_id=session.session_id,
            founder_id=founder.founder_id,
            root_cause_id=scored.root_cause_id,
            category_risk_score=scored.category_risk_score,
            confirmation_status=scored.confirmation_status.value,
            confirmation_multiplier=scored.confirmation_multiplier,
            stage_probability=scored.stage_probability,
            industry_probability=scored.industry_probability,
            final_weighted_score=scored.final_weighted_score,
            rank=scored.rank,
            is_top_finding=scored.is_top_finding,
        )

    def _root_cause_codes(self, scored: Sequence[ScoredRootCause]) -> list[str]:
        """Root-cause CODEs (not ids) for a scored set -- the shared key used to
        resolve interventions, blind_spots, and behaviour_patterns alike."""
        if not scored:
            return []
        root_causes = self.repository.get_root_causes_by_ids(
            s.root_cause_id for s in scored
        )
        return [rc.root_cause_code for rc in root_causes.values() if rc.root_cause_code]

    def _build_internal_report_row(
        self, session, founder: Founder, report_id: int, internal_report,
        distress_assessment=None, scored: Sequence[ScoredRootCause] = (),
    ) -> InternalIntelligenceReport:
        """Map the internal report onto internal_intelligence_reports.

        `psychological_state` reuses the session-state vocabulary (which the
        table's CHECK enforces). `internal_notes` carries the rendered consultant
        report. `distress_signals` captures the distress-flagged symptoms.

        `blind_spot_ids` and `behaviour_pattern_ids` used to be left empty
        unconditionally -- not because blind_spots/behaviour_patterns had no
        data (20 and 27 real seeded rows respectively), but because nothing
        ever queried them. Both tables link to root causes by CODE
        ("RC-019"), the same convention `recommendation.py` already resolves
        interventions through, so this reuses that exact resolve-then-match
        shape rather than inventing a new one. Best-effort: a lookup failure
        here must not fail the whole report.
        """
        blind_spot_ids: list[int] = []
        behaviour_pattern_ids: list[int] = []
        try:
            codes = self._root_cause_codes(scored)
            if codes:
                blind_spot_ids = self.repository.get_blind_spot_ids_by_root_cause_codes(codes)
                behaviour_pattern_ids = (
                    self.repository.get_behaviour_pattern_ids_by_root_cause_codes(codes)
                )
        except Exception:  # noqa: BLE001 -- optional enrichment, never blocks the report
            logger.warning(
                "blind spot / behaviour pattern lookup failed; leaving empty",
                extra={"session_id": session.session_id},
            )
        distress_signals = [
            {
                "category": s.category,
                "symptoms": list(s.symptoms),
                "severity": str(s.severity),
            }
            for s in internal_report.symptoms
            if s.is_distress
        ]
        # Record the empathy protocol to apply (prompt_library, category='distress')
        # for the detected acute state -- service-role only, never shown to the founder.
        if distress_assessment is not None and distress_assessment.empathy_protocol_code:
            distress_signals.insert(0, {
                "empathy_protocol": distress_assessment.empathy_protocol_code,
                "guidance": distress_assessment.empathy_protocol_text,
                "distress_red_count": distress_assessment.distress_red_count,
                # "error" => distress detector failed and we failed CLOSED; this
                # session's high-distress state was assumed, not measured.
                "detector_status": distress_assessment.detector_status,
            })
        return InternalIntelligenceReport(
            founder_id=founder.founder_id,
            session_id=session.session_id,
            report_id=report_id,
            psychological_state=session.session_state,
            distress_signals=distress_signals,
            internal_notes=MarkdownReportRenderer().render_internal(internal_report),
            blind_spot_ids=blind_spot_ids,
            behaviour_pattern_ids=behaviour_pattern_ids,
        )

    def _business_dna(self, business_health) -> dict | None:
        """Serialise the Business Health score to structured JSON for
        founder_reports.business_dna -- the queryable Business-DNA snapshot the
        report aggregation and the dashboard display layer read."""
        if business_health is None:
            return None
        return {
            "overall_score": int(business_health.overall_score),
            "band": business_health.band,
            "red_flags": list(business_health.red_flags),
            "pillars": [
                {
                    "pillar_id": p.pillar_id,
                    "pillar_name": p.pillar_name,
                    "weight": float(p.weight),
                    "score": (int(p.score) if p.score is not None else None),
                    "band": p.band,
                    "red_flag_triggered": p.red_flag_triggered,
                    "red_flag_note": p.red_flag_note,
                    "assessed_question_count": p.assessed_question_count,
                }
                for p in business_health.pillars
            ],
        }

    def _action_dicts(self, recommendations, rec_type: RecommendationType) -> list[dict]:
        return [
            {
                "intervention_id": rec.intervention_id,
                "priority": rec.priority,
                "next_actions": list(rec.next_actions),
                "rationale": rec.rationale,
            }
            for rec in recommendations.recommendations
            if rec.recommendation_type == rec_type
        ]

    def _session_state(self, session, distress_mode: bool) -> str:
        # Reflect distress in the session state without recomputing anything: the
        # diagnosis engine already decided distress_mode.
        if distress_mode:
            return "high_distress"
        return session.session_state or "stable"

    def _log_stage(self, stage: str, session_id: int, start: float, **extra) -> None:
        logger.info(
            f"reasoning stage: {stage}",
            extra={
                "session_id": session_id,
                "stage": stage,
                "duration_ms": _elapsed_ms(start),
                **extra,
            },
        )
