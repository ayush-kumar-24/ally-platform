"""Business Health Score -- weighted readiness across the six pillars.

All configuration comes from `readiness_pillars`: per-pillar weight
(pillar_weightage), score bands (score_bands) and red-flag threshold
(red_flag_threshold). Nothing is hardcoded.

How a pillar's answers become a 0-100 score is delegated to an injected
`PillarScoreStrategy` so the rule stays swappable. The default is the defined
rule (`RiskInversionPillarScoreStrategy`, PILLAR_SCORE_FROM_ANSWERS): mean answer
risk, inverted onto a health scale. A fail-closed strategy remains available for
callers that need to disable the score.

Pillar membership is a database fact, not a guess: an answer belongs to a pillar
via question.problem_id -> problems.pillar_id. This engine only maps answers to
pillars, delegates the per-pillar score, then applies the config-driven band and
red-flag rules and the given weighted-sum formula. It does not touch the
confidence model.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol, runtime_checkable

from app.api.v1.reasoning.errors import FeatureDisabledError
from app.api.v1.reasoning.interfaces import ReasoningContext
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.schemas import (
    AnswerClassification,
    BusinessHealthScore,
    PillarScore,
)
from app.models.diagnosis import Question

_QUANT = Decimal("0.01")
_ONE = Decimal("1")
_ZERO = Decimal("0")
_HUNDRED = Decimal("100")
_MAX_RISK_PER_ANSWER = Decimal("2")


def _q(value: Decimal) -> Decimal:
    return value.quantize(_QUANT, rounding=ROUND_HALF_UP)


def _int(value: Decimal) -> Decimal:
    """Round to a whole number (ROUND_HALF_UP).

    Both the pillar score and the overall score are whole 0-100 numbers: the
    formula rounds the pillar score explicitly, and the score_bands are integer
    buckets (0-35, 36-55, ...) with no room between them, so a fractional value
    would fall in a gap and match no band."""
    return value.quantize(_ONE, rounding=ROUND_HALF_UP)


def _band_for(score_bands, value: Decimal) -> str | None:
    """Return the band `level` whose [range_min, range_max] contains `value`."""
    for band in score_bands or []:
        low = Decimal(str(band.get("range_min", 0)))
        high = Decimal(str(band.get("range_max", 100)))
        if low <= value <= high:
            return band.get("level")
    return None


@runtime_checkable
class PillarScoreStrategy(Protocol):
    """Turns a pillar's answer band scores into a 0-100 health score.

    This is the business rule the readiness_pillars table does not define, so it
    is injected. Implementations receive the pillar (for its config) and the band
    scores (0/1/2) of the answers that belong to it.
    """

    def score(
        self,
        pillar,
        answer_scores: Sequence[Decimal],
        context: ReasoningContext,
    ) -> Decimal: ...


class NotImplementedPillarScoreStrategy:
    """Fail-closed strategy. Raises instead of scoring -- kept so a caller can
    explicitly disable the Business Health Score (e.g. in a context where the
    formula must not run), and used by tests that assert the fail-closed path."""

    def score(
        self,
        pillar,
        answer_scores: Sequence[Decimal],
        context: ReasoningContext,
    ) -> Decimal:
        raise FeatureDisabledError(
            "The pillar scoring formula is not defined -- no project document "
            "specifies how to convert a pillar's answers into a 0-100 score. The "
            "Business Health Score is disabled until a PillarScoreStrategy is "
            "supplied."
        )


class RiskInversionPillarScoreStrategy:
    """The defined pillar-scoring rule (PILLAR_SCORE_FROM_ANSWERS).

    Each answered question carries a risk score of 0 (Green), 1 (Amber) or 2
    (Red) -- higher is worse. A pillar's risk ratio is its mean risk over the
    questions ACTUALLY answered, normalised by the worst possible case:

        risk_ratio = sum(answer_scores) / (answered_count * 2)      # 0..1

    That is a RISK measure. The pillar score inverts it onto a 0-100 HEALTH
    scale (higher is better), so all-Red -> 0 and all-Green -> 100:

        pillar_score = round((1 - risk_ratio) * 100)

    The inversion is the load-bearing step: skip it and every founder gets an
    exactly-backwards score that still looks plausible.

    Only answered questions count toward the denominator -- a founder who never
    reached a stage is not penalised for its unseen questions. The caller passes
    only answered scores and routes a pillar with none to `null` before ever
    calling here, so `answer_scores` is always non-empty in practice.
    """

    def score(
        self,
        pillar,
        answer_scores: Sequence[Decimal],
        context: ReasoningContext,
    ) -> Decimal:
        answered = len(answer_scores)
        if answered == 0:
            # Unreachable via the scorer (empty pillars become null upstream);
            # a programmer error, not a disabled feature, so fail loudly.
            raise ValueError("Cannot score a pillar with no answered questions.")
        worst_case = Decimal(answered) * _MAX_RISK_PER_ANSWER
        risk_ratio = sum(answer_scores, _ZERO) / worst_case
        return _int((_ONE - risk_ratio) * _HUNDRED)


class BusinessHealthScorer:
    def __init__(
        self,
        repository: ReasoningRepository,
        pillar_score_strategy: PillarScoreStrategy | None = None,
    ):
        self.repository = repository
        self.pillar_score_strategy = (
            pillar_score_strategy or RiskInversionPillarScoreStrategy()
        )

    def compute(
        self,
        classifications: list[AnswerClassification],
        questions: dict[int, Question],
        context: ReasoningContext,
    ) -> BusinessHealthScore:
        pillars = self.repository.get_readiness_pillars()

        # question -> problem -> pillar (database FK mapping, not guessed).
        problem_ids = {
            questions[c.question_id].problem_id
            for c in classifications
            if c.question_id in questions
        }
        problems = self.repository.get_problems_by_ids(problem_ids)
        problem_to_pillar = {pid: prob.pillar_id for pid, prob in problems.items()}

        scores_by_pillar: dict[int, list[Decimal]] = defaultdict(list)
        for c in classifications:
            question = questions.get(c.question_id)
            if question is None:
                continue
            pillar_id = problem_to_pillar.get(question.problem_id)
            if pillar_id is None:
                continue
            scores_by_pillar[pillar_id].append(c.score)

        pillar_scores: list[PillarScore] = []
        for pillar in pillars:
            answer_scores = scores_by_pillar.get(pillar.pillar_id, [])
            if not answer_scores:
                pillar_scores.append(
                    PillarScore(
                        pillar_id=pillar.pillar_id,
                        pillar_name=pillar.pillar_name,
                        weight=pillar.pillar_weightage,
                        score=None,
                        band=None,
                        red_flag_triggered=False,
                        red_flag_note=None,
                        assessed_question_count=0,
                    )
                )
                continue

            # The per-pillar 0-100 score is the injected business rule.
            health = _int(self.pillar_score_strategy.score(pillar, answer_scores, context))
            threshold = pillar.red_flag_threshold
            flagged = threshold is not None and health <= threshold
            pillar_scores.append(
                PillarScore(
                    pillar_id=pillar.pillar_id,
                    pillar_name=pillar.pillar_name,
                    weight=pillar.pillar_weightage,
                    score=health,
                    band=_band_for(pillar.score_bands, health),
                    red_flag_triggered=flagged,
                    red_flag_note=pillar.red_flag_note if flagged else None,
                    assessed_question_count=len(answer_scores),
                )
            )

        overall, overall_band = self._overall(pillar_scores, pillars)
        red_flags = tuple(p.pillar_name for p in pillar_scores if p.red_flag_triggered)
        return BusinessHealthScore(
            overall_score=overall,
            band=overall_band,
            pillars=tuple(pillar_scores),
            red_flags=red_flags,
        )

    def _overall(self, pillar_scores, pillars) -> tuple[Decimal, str | None]:
        """Weight the assessed pillars by pillar_weightage, renormalising over the
        weight actually present so unseen pillars neither help nor hurt."""
        assessed = [p for p in pillar_scores if p.score is not None]
        total_weight = sum((p.weight for p in assessed), _ZERO)
        if total_weight <= 0:
            return _ZERO, None
        weighted = sum((p.score * p.weight for p in assessed), _ZERO)
        overall = _int(weighted / total_weight)
        bands = pillars[0].score_bands if pillars else None
        return overall, _band_for(bands, overall)
