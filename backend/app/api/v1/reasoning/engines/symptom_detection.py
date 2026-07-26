"""Symptom detection -- deterministic, from the existing tables.

Non-Green answers point at problems through questions.problem_id; each problem
carries a catalogue of symptoms (problems.symptoms). This engine groups the
negative answers by problem, attaches the catalogue symptoms, and computes a
normalised severity from the answer scores. Distress is surfaced per problem
(distress-tagged question or distress-flagged answer) and category flags come
from the already-computed category risks.

Everything is derived from stored data -- no inference, no model calls.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from app.api.v1.reasoning.interfaces import ReasoningContext
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.schemas import (
    AnswerClassification,
    CategoryRisk,
    SymptomDetection,
)
from app.models.diagnosis import Question
from app.models.enums import ScoreLabel

_QUANT = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


class SymptomDetector:
    def __init__(self, repository: ReasoningRepository):
        self.repository = repository

    def detect(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        category_risks: list[CategoryRisk],
        context: ReasoningContext,
    ) -> list[SymptomDetection]:
        red_band = context.config.question_scores.red

        by_problem: dict[int, list[AnswerClassification]] = defaultdict(list)
        for c in classifications:
            if c.label == ScoreLabel.GREEN:
                continue
            question = questions.get(c.question_id)
            if question is not None:
                by_problem[question.problem_id].append(c)

        if not by_problem:
            return []

        problems = self.repository.get_problems_by_ids(by_problem.keys())

        detections: list[SymptomDetection] = []
        for problem_id, members in by_problem.items():
            problem = problems.get(problem_id)
            if problem is None:
                continue

            max_score = red_band * len(members)
            raw = sum((m.score for m in members), _ZERO)
            severity = _q(min(_ONE, max(_ZERO, raw / max_score))) if max_score > 0 else _ZERO

            is_distress = any(
                m.is_distress_flagged
                or (
                    m.question_id in questions
                    and questions[m.question_id].is_distress_tagged
                )
                for m in members
            )

            detections.append(
                SymptomDetection(
                    problem_id=problem_id,
                    category=problem.category,
                    symptoms=tuple(str(s) for s in (problem.symptoms or [])),
                    severity=severity,
                    evidence_question_ids=tuple(sorted(m.question_id for m in members)),
                    is_distress=is_distress,
                )
            )

        detections.sort(key=lambda d: (-d.severity, d.problem_id))
        return detections
