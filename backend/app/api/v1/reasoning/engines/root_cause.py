"""Root Cause Engine -- deterministic, database-driven detection.

Maps scored answers to candidate root causes using the structured relationship
`questions.root_cause_id`, assigns each candidate a confirmation status from the
double-red branching pattern, and returns a full evidence trail so every score is
explainable rather than a black box.

Deterministic by construction: same classifications + same question bank -> same
detections, in the same order. No embeddings, no semantic retrieval, no
agent_interpretations -- those arrive later through the optional RootCauseEnricher
(see interfaces.RootCauseEnricher), which can enrich or validate these detections
without changing this engine's `detect` signature.

Scope boundary: this engine produces `detection_score` / `detection_confidence`
(its own evidence-derived signals) and the confirmation status. It does NOT apply
the four-factor ranking weights or the stage/industry priors -- that is the
Confidence Model's job (next step). Keeping that split is what lets the two
engines be reasoned about, and tested, independently.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal

from app.api.v1.reasoning.interfaces import (
    ReasoningContext,
    RootCauseEnricher,
    RootCauseEngine,
)
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.schemas import (
    AnswerClassification,
    CategoryRisk,
    RootCauseDetection,
    RootCauseEvidence,
)
from app.models.diagnosis import Question
from app.models.enums import ConfirmationStatus, ScoreLabel

_QUANT = Decimal("0.0001")
_MAX_BAND_SCORE = Decimal("2")  # a Red answer; the per-answer maximum


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


class StandardRootCauseEngine(RootCauseEngine):
    """Deterministic detection over question -> root_cause mappings.

    `enricher` is the optional semantic layer (Retrieval Engine). When absent,
    detection is fully deterministic; when present, it runs after detection and
    may only add to or re-rank what deterministic mapping already found.
    """

    def __init__(
        self,
        repository: ReasoningRepository,
        enricher: RootCauseEnricher | None = None,
    ):
        self.repository = repository
        self.enricher = enricher

    def detect(
        self,
        classifications: list[AnswerClassification],
        category_risks: list[CategoryRisk],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> list[RootCauseDetection]:
        # Index the follow-up answers by their question id so an original answer
        # can find the probe it triggered (double-red confirmation).
        follow_up_by_question: dict[int, AnswerClassification] = {
            c.question_id: c for c in classifications if c.is_follow_up
        }
        flagged_categories = {c.category for c in category_risks if c.is_flagged}
        risk_by_category = {c.category: c.normalised_risk for c in category_risks}

        # Group every classification under the root cause its question maps to.
        # Classifications whose question is not in the bank are skipped -- they
        # cannot be attributed deterministically.
        grouped: dict[int, list[AnswerClassification]] = defaultdict(list)
        for c in classifications:
            question = questions.get(c.question_id)
            if question is None:
                continue
            grouped[question.root_cause_id].append(c)

        detections: list[RootCauseDetection] = []
        for root_cause_id, members in grouped.items():
            detection = self._build_detection(
                root_cause_id=root_cause_id,
                members=members,
                questions=questions,
                follow_up_by_question=follow_up_by_question,
                flagged_categories=flagged_categories,
                risk_by_category=risk_by_category,
                context=context,
            )
            if detection is not None:
                detections.append(detection)

        detections = self._order(detections)

        if self.enricher is not None:
            detections = self.enricher.enrich(detections, context)
        return detections

    # --- Detection of a single root cause ---------------------------------

    def _build_detection(
        self,
        *,
        root_cause_id: int,
        members: list[AnswerClassification],
        questions: dict[int, Question],
        follow_up_by_question: dict[int, AnswerClassification],
        flagged_categories: set[str],
        risk_by_category: dict[str, Decimal],
        context: ReasoningContext,
    ) -> RootCauseDetection | None:
        negative = [m for m in members if m.label != ScoreLabel.GREEN]
        if not negative:
            # Every probe of this root cause came back Green -- no problem signal,
            # so it is not a candidate.
            return None

        # detection_score: severity among the negative (Amber/Red) evidence only.
        # Each evidence's contribution is its additive share of this score, so the
        # contributions sum to detection_score exactly.
        max_negative = _MAX_BAND_SCORE * len(negative)
        detection_score = _q(sum((m.score for m in negative), Decimal(0)) / max_negative)

        evidence = tuple(
            RootCauseEvidence(
                question_id=m.question_id,
                answer_id=m.answer_id,
                score_label=m.label,
                score=m.score,
                contribution=_q(m.score / max_negative),
            )
            for m in sorted(negative, key=lambda m: (-m.score, m.question_id))
        )

        # detection_confidence: corroboration across ALL probes of this root
        # cause, Green included. A Green answer is evidence the cause is NOT
        # active, so it lowers confidence -- distinguishing "one isolated Red" from
        # "Red across everything we asked".
        max_all = _MAX_BAND_SCORE * len(members)
        detection_confidence = _q(sum((m.score for m in members), Decimal(0)) / max_all)

        confirmation_status = self._confirmation_status(
            members=members,
            questions=questions,
            follow_up_by_question=follow_up_by_question,
        )

        category = self._dominant_category(members, questions)
        contributing_factors = self._contributing_factors(
            negative=negative,
            members=members,
            confirmation_status=confirmation_status,
            category=category,
            flagged_categories=flagged_categories,
            context=context,
        )

        return RootCauseDetection(
            root_cause_id=root_cause_id,
            category=category,
            confirmation_status=confirmation_status,
            detection_score=detection_score,
            detection_confidence=detection_confidence,
            evidence=evidence,
            contributing_factors=contributing_factors,
            category_risk_score=risk_by_category.get(category),
        )

    # --- Confirmation (double-red pattern) --------------------------------

    def _confirmation_status(
        self,
        *,
        members: list[AnswerClassification],
        questions: dict[int, Question],
        follow_up_by_question: dict[int, AnswerClassification],
    ) -> ConfirmationStatus:
        """CONFIRMED when an original Red answer's triggered follow-up probe also
        scored Red; UNCONFIRMED when the cause was probed (Amber/Red) but no such
        double-red pair exists. NOT_TESTED is not emitted by deterministic
        detection -- every candidate here has at least one real probe; the
        never-probed case is surfaced later by the stage/category priors."""
        has_red = False
        for m in members:
            if m.is_follow_up or m.label != ScoreLabel.RED:
                continue
            has_red = True
            if m.triggered_follow_up_id is None:
                continue
            follow_up = follow_up_by_question.get(m.triggered_follow_up_id)
            if follow_up is not None and follow_up.label == ScoreLabel.RED:
                return ConfirmationStatus.CONFIRMED

        # A Red that arrived only as a follow-up (no mapped original) still counts
        # as a real Red signal for this cause.
        if not has_red:
            has_red = any(m.label == ScoreLabel.RED for m in members)

        return ConfirmationStatus.UNCONFIRMED

    # --- Explainability helpers -------------------------------------------

    def _dominant_category(
        self, members: list[AnswerClassification], questions: dict[int, Question]
    ) -> str:
        counts = Counter(
            questions[m.question_id].category
            for m in members
            if m.question_id in questions
        )
        # most_common is order-stable for ties on insertion; sort for determinism.
        return min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]

    def _contributing_factors(
        self,
        *,
        negative: list[AnswerClassification],
        members: list[AnswerClassification],
        confirmation_status: ConfirmationStatus,
        category: str,
        flagged_categories: set[str],
        context: ReasoningContext,
    ) -> tuple[str, ...]:
        factors: list[str] = ["Direct Question Mapping"]

        if confirmation_status == ConfirmationStatus.CONFIRMED:
            factors.append("Confirmed (double-red)")
        if any(m.label == ScoreLabel.RED for m in negative):
            factors.append("Direct Red Signal")

        amber_count = sum(1 for m in negative if m.label == ScoreLabel.AMBER)
        if amber_count >= context.config.branching.amber_cluster_trigger:
            factors.append("Amber Cluster")

        if any(m.is_distress_flagged for m in members):
            factors.append("Distress-Flagged Evidence")

        if category in flagged_categories:
            factors.append(f"Category Risk: {category}")

        return tuple(factors)

    # --- Ordering ---------------------------------------------------------

    def _order(self, detections: list[RootCauseDetection]) -> list[RootCauseDetection]:
        """Deterministic order: confirmed first, then stronger detection score,
        then stronger corroboration, then root_cause_id as a stable tiebreak.
        Final ranking is the Confidence Model's responsibility; this ordering only
        makes the engine's own output reproducible."""
        confirmed_rank = {
            ConfirmationStatus.CONFIRMED: 0,
            ConfirmationStatus.UNCONFIRMED: 1,
            ConfirmationStatus.NOT_TESTED: 2,
        }
        return sorted(
            detections,
            key=lambda d: (
                confirmed_rank.get(d.confirmation_status, 9),
                -d.detection_score,
                -d.detection_confidence,
                d.root_cause_id,
            ),
        )
