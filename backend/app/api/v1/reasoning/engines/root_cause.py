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
        # The full rows too: the ranking-facing intensity needs raw_score and
        # max_score, which the normalised map has already divided away.
        risk_rows = {c.category: c for c in category_risks}

        # Group every classification under the root cause its question maps to.
        # Classifications whose question is not in the bank are skipped -- they
        # cannot be attributed deterministically.
        grouped: dict[int, list[AnswerClassification]] = defaultdict(list)
        for c in classifications:
            question = questions.get(c.question_id)
            if question is None:
                continue
            # NOT_APPLICABLE never becomes evidence: it is not a signal that
            # this cause is present OR absent, so it must not open a detection
            # and must not sit in `members` diluting detection_confidence.
            if not c.label.is_scored:
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
                risk_rows=risk_rows,
                context=context,
            )
            if detection is not None:
                detections.append(detection)

        detections = self._order(detections)
        detections = self._focus(detections, context)

        if self.enricher is not None:
            detections = self.enricher.enrich(detections, context)
        return detections

    def _focus(
        self, detections: list[RootCauseDetection], context: ReasoningContext
    ) -> list[RootCauseDetection]:
        """Drop weakly-corroborated candidates and cap the count, so a focused set
        reaches ranking instead of a long tail of single-signal causes.

        A CONFIRMED cause (a real double-red) is never dropped by the confidence
        floor -- confirmation is the strongest signal we have. Limits come from
        config (scoring_rules, with safe provisional defaults); 0 disables a limit.
        """
        floor = context.config.branching.root_cause_min_detection_confidence
        cap = context.config.branching.root_cause_max_candidates

        if floor > 0:
            detections = [
                d
                for d in detections
                if d.detection_confidence >= floor
                or d.confirmation_status == ConfirmationStatus.CONFIRMED
            ]
        if cap and len(detections) > cap:
            # detections are already in priority order (_order); keep the strongest.
            detections = detections[:cap]
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
        risk_rows: dict[str, object],
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
                # Everything the deterministic engine produces is direct by
                # construction: it only ever sees an answer given to a question
                # that questions.root_cause_id maps to this cause. Inferred and
                # volunteered evidence have no producer yet -- the fields exist
                # so those paths have somewhere to put their findings instead of
                # being dropped, which is what happens today.
                directness="direct",
                dimension=self._dimension_of(m.question_id, questions),
                volunteered=False,
            )
            for m in sorted(negative, key=lambda m: (-m.score, m.question_id))
        )

        # Breadth, recorded but NOT yet used for ranking. detection_score above
        # is a mean and divides this out; see the note on RootCauseDetection.
        # Distinct dimensions rather than raw count, so one subject probed six
        # times does not read as six independent signals.
        dimensions = {
            d for d in (self._dimension_of(m.question_id, questions)
                        for m in negative)
            if d
        }
        independent_signal_count = len(dimensions)
        evidence_mass = _q(sum((m.score for m in negative), Decimal(0)))

        # detection_confidence: how sure we are the cause is actually PRESENT.
        #
        # Two factors, because they answer different questions and the previous
        # formula answered only the first:
        #
        #   intensity     -- how bad the answers were, across ALL probes of this
        #                    cause, Green included. A Green is evidence the cause
        #                    is NOT active, so it pulls intensity down and
        #                    distinguishes "one isolated Red" from "Red across
        #                    everything we asked".
        #   corroboration -- how much we actually asked. One probe cannot
        #                    corroborate itself.
        #
        # Without the second factor a single Red answer produced
        # detection_confidence = 2.0 / (2 * 1) = 1.0 -- maximum confidence from
        # one sentence. Measured in QA: 6 of 8 root causes rested on a single
        # answer and 6 carried confidence 1.0000, in all three personas.
        #
        # Corroboration is n / (n + 1): 0.50 at one probe, 0.67 at two, 0.75 at
        # three, approaching 1 thereafter. Deliberately gentle -- it caps a
        # lone answer at half confidence without punishing a cause the interview
        # only had budget to probe twice, and it never reaches 1.0, because no
        # finite number of probes makes a diagnosis certain.
        max_all = _MAX_BAND_SCORE * len(members)
        intensity = sum((m.score for m in members), Decimal(0)) / max_all
        probes = Decimal(len(members))
        corroboration = probes / (probes + Decimal(1))
        detection_confidence = _q(intensity * corroboration)

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
            ranking_category_risk=self._ranking_category_risk(negative, questions, risk_rows),
            independent_signal_count=independent_signal_count,
            evidence_mass=evidence_mass,
        )

    #: Smoothing prior for the ranking-facing category intensity, in questions.
    #: The founder-facing mean divides by the questions actually asked, so one
    #: question answered Red scores 1.0 -- the maximum the scale allows, from a
    #: single answer. Adding k pseudo-questions to the denominator means a
    #: category has to be probed more than once to reach a high intensity, which
    #: removes the "asking again lowers the score" artifact without touching the
    #: founder-facing number. k = 2 is the smallest value that stops a single
    #: answer dominating; it is deliberately not tuned to a persona.
    _RANKING_RISK_PRIOR = Decimal("2")

    def _ranking_category_risk(
        self,
        negative: list[AnswerClassification],
        questions: dict[int, "Question"],
        risk_rows: dict[str, object],
    ) -> Decimal | None:
        """Evidence-weighted category intensity for THIS cause, 0..1.

        Two departures from `category_risk_score`, both deliberate:

        1. Smoothed intensity. raw / (red_band * (asked + k)) instead of
           raw / (red_band * asked). A category asked once and answered Red
           reads 0.33 rather than 1.00, so depth of investigation no longer
           deflates a category and a single answer no longer maxes it out.

        2. Averaged across the categories this cause actually spans, weighted by
           its own evidence in each. `_dominant_category` picks one label and
           the ranker borrowed that category's risk whole -- for a cause whose
           evidence sits in six categories, five were thrown away.

        Returns None when no category carrying this cause's evidence has a risk
        row, so the ranker can record the factor as unavailable instead of
        scoring it zero.
        """
        weighted = Decimal(0)
        total = Decimal(0)
        for m in negative:
            question = questions.get(m.question_id)
            category = getattr(question, "category", None) if question else None
            row = risk_rows.get(category) if category else None
            if row is None:
                continue
            asked = (Decimal(row.max_score) / _MAX_BAND_SCORE
                     if _MAX_BAND_SCORE else Decimal(0))
            denominator = _MAX_BAND_SCORE * (asked + self._RANKING_RISK_PRIOR)
            if denominator <= 0:
                continue
            intensity = Decimal(row.raw_score) / denominator
            weighted += m.score * intensity
            total += m.score
        if total <= 0:
            return None
        return _q(min(Decimal(1), max(Decimal(0), weighted / total)))

    @staticmethod
    def _dimension_of(question_id: int, questions) -> str | None:
        """The diagnostic dimension a question belongs to -- its category.

        Deliberately the same field `_dominant_category` uses, so "how many
        dimensions" and "which category" cannot disagree about what a dimension
        is.
        """
        question = questions.get(question_id)
        return getattr(question, "category", None) if question is not None else None

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
