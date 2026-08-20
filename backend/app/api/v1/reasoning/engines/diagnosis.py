"""Deterministic Diagnosis Engine facade.

Composes category scoring, stage detection and symptom detection into the single
`DiagnosisResult` the reasoning pipeline consumes:

    Category Scoring -> Stage Detection -> Symptom Detection -> (Root Cause ...)

It owns no business logic of its own -- it sequences the three deterministic
components and bundles their outputs. Downstream engines (Root Cause, Confidence,
Retrieval, Recommendation) are untouched; this only produces their inputs.
"""

from __future__ import annotations

from app.api.v1.reasoning.engines.diagnostic import StandardDiagnosticEngine
from app.api.v1.reasoning.engines.stage_detection import StageDetector
from app.api.v1.reasoning.engines.symptom_detection import SymptomDetector
from app.api.v1.reasoning.interfaces import ReasoningContext
from app.api.v1.reasoning.schemas import DiagnosisResult
from app.models.diagnosis import Answer, Question


class DeterministicDiagnosisEngine:
    def __init__(
        self,
        category_engine: StandardDiagnosticEngine,
        stage_detector: StageDetector,
        symptom_detector: SymptomDetector,
    ):
        self.category_engine = category_engine
        self.stage_detector = stage_detector
        self.symptom_detector = symptom_detector

    async def diagnose(
        self,
        answers: list[Answer],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> DiagnosisResult:
        # 1. Category scoring (classification is read from stored scores).
        classifications = await self.category_engine.classify_answers(
            answers, questions, context
        )
        classified_ids = {c.answer_id for c in classifications}
        unscored = tuple(
            a.answer_id for a in answers if a.answer_id not in classified_ids
        )

        category_risks = self.category_engine.compute_category_risks(
            classifications, questions, context
        )
        follow_ups = self.category_engine.follow_up_triggers(
            classifications, questions, context
        )
        distress_signal_ids = self.category_engine.distress_signal_answers(
            classifications, questions, context
        )
        distress_count = len(distress_signal_ids)
        distress_mode = distress_count >= context.config.distress.distress_questions_trigger

        # 2. Stage detection.
        stage_detection = self.stage_detector.detect(classifications, questions, context)

        # 3. Symptom detection.
        symptoms = self.symptom_detector.detect(
            classifications, questions, category_risks, context
        )

        return DiagnosisResult(
            classifications=tuple(classifications),
            category_risks=tuple(category_risks),
            follow_up_triggers=tuple(follow_ups),
            stage_detection=stage_detection,
            symptoms=tuple(symptoms),
            distress_mode=distress_mode,
            distress_signal_count=distress_count,
            unscored_answer_ids=unscored,
            distress_signal_answer_ids=tuple(distress_signal_ids),
        )
