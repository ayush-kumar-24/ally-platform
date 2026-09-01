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
from app.api.v1.diagnosis.stage_scope import resolve_scope
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
    NoClassifiableAnswersError,
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
    SessionAssessment,
)
from app.core.config import settings
from app.core.logger import logger
from app.models import (
    DetectedRootCause,
    FounderReport,
    InternalIntelligenceReport,
    ReportType,
    RoutingState,
    SessionStatus,
)
from app.models.diagnosis import Founder


# Routing state for a session that leaves the diagnostic loop for wellbeing
# support (CONFIDENCE_HARD_RULES rule 1). Distinct from the confidence-driven
# states so the app can divert to a support flow instead of asking more questions.
#
# Now an alias for the enum member rather than a second definition of the string.
# It predates RoutingState carrying this value, and two spellings of one state is
# how the DB CHECK and the enum drifted apart in the first place.
DISTRESS_SUPPORT_ROUTE = RoutingState.DISTRESS_SUPPORT.value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def category_risk_map(category_risks: Sequence) -> dict[str, str]:
    """`sessions.category_risk_scores` -- {category: normalised_risk}, 0..1.

    The shape `ReportPayload` reads: `any_category_flagged` compares each value
    against CAT_RISK_THRESHOLD and `top_sub_threshold_categories` ranks them.

    str(), not float(). These are Decimals, the payload's `_to_float` parses
    either, and a threshold comparison is exactly where binary-float drift on a
    boundary value would silently flip which report variant a founder gets.
    """
    return {c.category: str(c.normalised_risk) for c in category_risks}


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
        action_plan_balancer=None,
    ):
        self.db = db
        self.repository = repository
        self.config = config
        self.diagnosis_engine = diagnosis_engine
        self.root_cause_engine = root_cause_engine
        self.confidence_model = confidence_model
        self.recommendation_engine = recommendation_engine
        #: Fills the empty half of the free report's 3+3 plan, or None (off) to
        #: ship whatever the intervention library produced. See
        #: engines/action_plan_llm.py.
        self.action_plan_balancer = action_plan_balancer
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

    def _monitor_eligible(self, confidence_inputs, context, answered: int) -> bool:
        """Whether this finished session is an all-clear rather than an unfinished one.

        Delegates the condition to `config.monitor_eligible`, the same function
        the in-loop scorer uses, so the decision that ended the session and the
        decision recorded on the report cannot disagree.

        Never raises: a report is worth far more than a perfectly labelled
        routing state, and the fallback is the pre-existing behaviour.
        """
        from app.api.v1.reasoning.config import (
            DEFAULT_MONITOR_MIN_COVERAGE,
            RuleCode,
            monitor_eligible,
        )

        try:
            budget = settings.question_budget(
                self.repository.get_question_budget(context.stage_id)
            )
            values = self.repository.get_active_rule_values()
            return monitor_eligible(
                any_category_flagged=confidence_inputs.any_category_flagged,
                answered=answered,
                budget=budget,
                min_coverage=values.get(
                    RuleCode.MONITOR_MIN_COVERAGE.value, DEFAULT_MONITOR_MIN_COVERAGE
                ),
                min_answers=int(
                    values.get(RuleCode.CONFIDENCE_MIN_QUESTIONS_FLOOR.value, 0)
                ),
            )
        except Exception as exc:                              # noqa: BLE001
            logger.warning(
                "Monitor eligibility could not be resolved; leaving routing as scored",
                extra={"session_id": context.session.session_id, "error": str(exc)},
            )
            return False

    async def assess_only(self, session, founder: Founder) -> SessionAssessment | None:
        """Confidence for a session AS IT STANDS, plus whether anything is wrong.

        The minimum needed to answer "how sure are we now": diagnosis (category /
        stage / symptom) -> root-cause detection and ranking -> confidence. It
        deliberately stops there. Retrieval enrichment, recommendations, business
        health, archetype and report generation all belong to a finished
        diagnosis; running them after every answer would cost thirty times what a
        diagnosis should and produce a report nobody asked for yet.

        Writes nothing. The caller decides what to do with the number -- keeping
        this read-only means it cannot half-update a session if it throws.

        Returns None when the session has no answers yet.

        The score alone cannot drive routing. Three of its five signals measure
        pathology, so "we found nothing" and "we have not looked hard enough"
        both come back as a low number, and rule 4 caps an unflagged session at
        59 on top of that. `any_category_flagged` is what separates them, so it
        travels with the score rather than being re-derived by the caller.
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
        score = self.confidence_model.overall_confidence(inputs, context)
        if score is None:
            return None
        return SessionAssessment(
            score=score,
            any_category_flagged=inputs.any_category_flagged,
            questions_answered=len(answers),
        )

    async def score_only(self, session, founder: Founder) -> Decimal | None:
        """Just the confidence number, for callers that do not route on it."""
        assessment = await self.assess_only(session, founder)
        return assessment.score if assessment is not None else None

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
            # How many answers were DROPPED from the evidence set. The all-or-
            # nothing case is caught loudly just below, but a partial drop --
            # one answer in thirty whose advisor call failed at submit time --
            # has been silent, and it is silent in exactly the configuration
            # production runs: ANSWER_CLASSIFIER=stored skips an unscored answer
            # rather than classifying it, so the founder's report is built from
            # 29 answers with nothing saying so. Measured non-zero on 2 of 5 test
            # sessions.
            unscored_skipped=len(diagnosis.unscored_answer_ids),
        )
        # Zero classifications from a non-empty answer set means every answer was
        # skipped as unscored, and everything downstream -- root causes,
        # confidence, recommendations, the report itself -- would be derived from
        # nothing. classify_answers skips bad rows individually on purpose, which
        # is right for one and wrong for all of them; this is where "all of them"
        # is caught. See NoClassifiableAnswersError for how configuration alone
        # reaches this state, and why failing beats persisting an empty report.
        if not diagnosis.classifications:
            logger.error(
                "no answer in this session could be classified; refusing to "
                "generate an empty report",
                extra={
                    "session_id": session_id,
                    "stage": "diagnosis",
                    "answers": len(answers),
                    # Both flags are logged because the pair is the usual cause and
                    # neither is meaningful alone -- this line should be enough to
                    # diagnose it without reading the deploy config.
                    "answer_classifier": settings.ANSWER_CLASSIFIER,
                    "adaptive_questions": settings.ADAPTIVE_QUESTIONS,
                },
            )
            raise NoClassifiableAnswersError(
                f"Session {session_id} has {len(answers)} answers but none could "
                "be classified, so there is no evidence to reason from."
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
        # A clean session that was asked enough ends on `monitor`, not `continue`.
        # routing_state_for reads the score alone, and a healthy founder's score
        # is low for the opposite of the usual reason -- nothing was found, rather
        # than nothing has been found YET. Without this the in-loop decision that
        # completed the session is silently relabelled here, moments later, by
        # this pipeline recomputing from the same low number.
        if self._monitor_eligible(confidence_inputs, context, len(answers)):
            routing_state = RoutingState.MONITOR.value
        # Distress overrides routing entirely: wellbeing before diagnostic
        # completeness. The session leaves the confidence loop for a support path
        # rather than being told to keep answering questions. Last because it
        # outranks every other outcome, monitor included -- a founder in distress
        # is not "all clear" however clean their business answers were.
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
        scope = resolve_scope(context.founder)
        if scope is not None and not scope.emits_business_health:
            # An ideation founder is diagnosed on two pillars. Scoring them would
            # renormalise 45% of the model up to 100 and present it as a verdict
            # on a business that does not exist yet -- see StageScope.
            # emits_business_health. Their report is the Founder DNA Snapshot and
            # the Idea Validation read; `business_dna` stays null, which the
            # report and dashboard already handle.
            business_health = None
            logger.info(
                "business health omitted for this stage",
                extra={"session_id": session_id, "stage": "business_health",
                       "stage_scope": scope.label},
            )
        else:
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

        # --- Distress: which input actually decided it ---------------------
        # sessions.distress_mode_triggered is an OR of two independent
        # mechanisms, and a live session came out True while BOTH looked False
        # from the persisted data: no answer qualified as a distress signal
        # (score_labels on disk), and the language detector logged
        # high_distress=False with a score inside the "Open and Engaged" band.
        # A founder was told "burnout, identity crisis, fear of failure or
        # isolation appear to be active blockers" on the strength of that.
        #
        # There is no way to tell which side fired from what is stored, so log
        # both inputs, the threshold they were judged against, and the answer
        # ids the counting side actually used -- those can be read back off
        # `answers` to see whether the engine classified them differently from
        # what is on the row. INFO, not debug: this needs to be present in an
        # ordinary run, which is the only place the disagreement has shown up.
        # Corroboration rule. This used to be a bare OR, so the language
        # detector alone could declare high distress -- and did: a live session
        # resolved True with signal_count 0 on the counting side, purely on
        # tone, and the founder was told burnout and isolation were active
        # blockers. Candour reads like distress to a language model; a founder
        # willing to say "it stings" scores higher than one who says nothing.
        #
        # An ACUTE (State D) signal still fires alone and unconditionally --
        # that is the crisis protocol and must never wait for a second opinion.
        # What now needs corroboration is the *cumulative* path: tone-only
        # distress requires the counting side (answers actually classified as
        # distress signals) to agree before it overrides the whole session.
        acute_present = distress.distress_red_count > 0
        cumulative_only = distress.is_high_distress and not acute_present
        distress_mode = (
            diagnosis.distress_mode
            or acute_present
            or (cumulative_only and diagnosis.distress_signal_count > 0)
        )
        logger.info(
            "distress decision",
            extra={
                "session_id": session_id,
                "resolved": distress_mode,
                "by_counting": diagnosis.distress_mode,
                "signal_count": diagnosis.distress_signal_count,
                "signal_answer_ids": list(diagnosis.distress_signal_answer_ids),
                "trigger": str(self.config.distress.distress_questions_trigger),
                "by_language": distress.is_high_distress,
                "acute_present": acute_present,
                "cumulative_only": cumulative_only,
                "distress_red_count": distress.distress_red_count,
                "language_score": str(distress.session_distress_score),
                "language_status": getattr(distress, "detector_status", None),
                "high_distress_threshold": str(self.config.distress.high_distress_score),
            },
        )

        # --- Persist (single committed transaction) ---
        return self._persist(
            session=session,
            founder=founder,
            scored=scored,
            category_risks=diagnosis.category_risks,
            overall_confidence=overall_confidence,
            routing_state=routing_state,
            distress_mode=distress_mode,
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
            # capability_domain ("Quality Management"), not intervention_code
            # ("INT-052"): this map is what the founder-facing report prints as
            # the name of a recommendation, and a catalogue key is not a name.
            # Falls back to the code only if a row has no domain set.
            intervention_labels={
                iid: (getattr(iv, "capability_domain", None) or iv.intervention_code)
                for iid, iv in iv_map.items()
            },
            business_health=business_health,
            # The founder's own words, so findings can be shown with the evidence
            # that produced them instead of generic catalogue text. Built here
            # rather than in the bundle because ReasoningBundle deliberately does
            # no DB access.
            answer_evidence=self._answer_evidence(session.session_id),
        )
        return (
            self.report_generator.founder_report(bundle),
            self.report_generator.internal_report(bundle),
        )

    def _warm_report_narrative(self, report) -> None:
        """Generate the report narrative now, while the founder is already waiting.

        GET /reports/{id} generates this lazily on first read -- 7 sequential
        LLM calls, measured at 26.5s live -- and caches it forever after. That
        cost landed on the founder's FIRST view of their own report: the browser
        aborted the request and the page showed "Couldn't load your DNA" at the
        single moment that matters most. Every later view was fast, so the
        failure only ever hit people seeing their report for the first time.

        This method runs inside the post-diagnosis reasoning pass, which is
        already a background task the founder waits through behind the Thinking
        screen, so the same work costs them nothing extra here.

        Best-effort by design: a narrator failure must not fail the diagnosis or
        lose the report that was just committed. If this does not succeed the
        lazy path still works exactly as before -- this makes the cold read
        unlikely, it does not replace it.
        """
        try:
            from app.api.v1.reports.routes import _build_narrative

            _build_narrative(self.db, report)
        except Exception as exc:  # noqa: BLE001 -- never fail a diagnosis for this
            logger.warning(
                "Could not pre-generate the report narrative; "
                "it will be generated on first read instead",
                extra={"report_id": getattr(report, "report_id", None)},
                exc_info=exc,
            )

    def _answer_evidence(self, session_id: int) -> dict[int, tuple[str, str]]:
        """question_id -> (question text, the founder's answer) for this session.

        Answers are trimmed to a readable length: this is quoted back in the
        report as supporting evidence, not reproduced in full.
        """
        try:
            answers = self.repository.get_answers_for_session(session_id)
            questions = self.repository.get_questions_by_ids(
                {a.question_id for a in answers}
            )
        except Exception as exc:  # evidence is additive -- never fail a report for it
            logger.warning(
                "Could not load answer evidence for the report",
                extra={"session_id": session_id}, exc_info=exc,
            )
            return {}

        out: dict[int, tuple[str, str]] = {}
        for a in answers:
            q = questions.get(a.question_id)
            text = (a.answer_text or "").strip()
            if not q or not text:
                continue
            if len(text) > 320:
                text = text[:319].rstrip() + "…"
            out[a.question_id] = (q.question_text, text)
        return out

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
        category_risks: Sequence = (),
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
            # Category risk, persisted for the report layer. This column had
            # readers and no writer: `ReportPayload.any_category_flagged` and
            # `top_sub_threshold_categories` both read it, and `select_variant`
            # gates NO_CLEAR_DIAGNOSIS on `payload.category_risk_scores and not
            # payload.any_category_flagged`. An empty dict is falsy, so with
            # nothing ever written the variant was unreachable and every clean
            # session fell through to LOW_CONFIDENCE -- the "areas to monitor"
            # section, its copy and its template all existed and could never be
            # selected.
            #
            session.category_risk_scores = category_risk_map(category_risks)
            session.last_activity_at = _utcnow()

            superseded = self.repository.deactivate_existing_reports(session.session_id)

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

            confirm_dicts = self._action_dicts(recommendations, RecommendationType.CONFIRM)
            solve_dicts = self._action_dicts(recommendations, RecommendationType.SOLVE)
            confirm_dicts, solve_dicts = self._balanced_action_plan(
                confirm_dicts, solve_dicts, founder_report, scored,
            )

            report = FounderReport(
                founder_id=founder.founder_id,
                session_id=session.session_id,
                report_type=ReportType.FULL_DIAGNOSIS.value,
                title=self._report_title(founder_report),
                summary=founder_report.executive_summary,
                top_root_cause_ids=[s.root_cause_id for s in scored if s.is_top_finding],
                recommended_intervention_ids=list(recommendations.intervention_ids),
                confirm_actions=confirm_dicts,
                solve_actions=solve_dicts,
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

            # Carry any live share links onto the report that just replaced the
            # one they pointed at. Without this a regeneration silently broke
            # every link the founder had already sent out -- see
            # ReasoningRepository.repoint_shares.
            moved = self.repository.repoint_shares(superseded, report.report_id)
            if moved:
                logger.info(
                    "moved active share links onto the regenerated report",
                    extra={
                        "session_id": session.session_id,
                        "report_id": report.report_id,
                        "shares_moved": moved,
                    },
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
        self._warm_report_narrative(report)
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

    def _report_title(self, founder_report) -> str:
        """A name for the report row.

        founder_reports.title was never written -- the column existed, the
        dashboard's recent-reports query selected it, and the report page read
        meta?.title, so every report card rendered with a blank title and the
        page fell back to the generic "Your diagnosis report". Named after the
        lead root cause, which is the one thing that distinguishes one of a
        founder's reports from another at a glance; the label only, never an
        intervention id or a score.
        """
        causes = getattr(founder_report, "top_root_causes", ()) or ()
        lead = str(getattr(causes[0], "label", "") or "").strip() if causes else ""
        when = datetime.now(timezone.utc).strftime("%b %Y")
        return f"{lead} · {when}" if lead else f"Clarity report · {when}"

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

    def _balanced_action_plan(self, confirm: list[dict], solve: list[dict],
                              founder_report, scored) -> tuple[list[dict], list[dict]]:
        """Both halves of the doc's 3+3 plan, filled.

        StandardRecommendationEngine types every recommendation from its lead
        supporting cause, so a report diagnosing ONE cause gets all CONFIRM or
        all SOLVE and never both -- see engines/action_plan_llm.py. That leaves
        the founder reading half a plan with nothing on the page saying so.

        No balancer wired (the default) returns the two lists untouched, which
        is exactly today's behaviour. Never raises: a report with a lopsided
        plan is worth far more than no report.
        """
        if self.action_plan_balancer is None:
            return confirm, solve

        def _lines(items: list[dict]) -> list[str]:
            return [str(a) for item in items for a in (item.get("next_actions") or [])]

        try:
            top = next((s for s in scored if getattr(s, "is_top_finding", False)), None)
            new_confirm, new_solve = self.action_plan_balancer.balance(
                _lines(confirm),
                _lines(solve),
                root_cause=getattr(top, "root_cause_name", None),
                stage_name=getattr(founder_report, "stage_name", None),
                evidence=getattr(founder_report, "key_symptoms", ()) or (),
            )
        except Exception:  # noqa: BLE001 -- cosmetic completion, never blocks the report
            logger.warning("Action-plan balancing raised; keeping the library's plan",
                           exc_info=True)
            return confirm, solve

        return (
            self._plan_side(confirm, new_confirm),
            self._plan_side(solve, new_solve),
        )

    @staticmethod
    def _plan_side(original: list[dict], lines: list[str]) -> list[dict]:
        """Rebuild one half, keeping the curated entries' provenance.

        Lines the library supplied stay attached to the intervention they came
        from -- intervention_id and rationale intact -- so nothing generated can
        be mistaken for reviewed content later. Only genuinely new lines land in
        a separate entry with intervention_id None, which is what marks them as
        authored rather than curated.
        """
        if not lines:
            return original
        curated = {a for item in original for a in (item.get("next_actions") or [])}
        added = [line for line in lines if line not in curated]
        if not added:
            return original
        return original + [{
            "intervention_id": None,
            "priority": (max((i.get("priority") or 0) for i in original) + 1) if original else 1,
            "next_actions": added,
            "rationale": "Written to complete the 3+3 plan; no curated "
                         "intervention covered this half.",
        }]

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
