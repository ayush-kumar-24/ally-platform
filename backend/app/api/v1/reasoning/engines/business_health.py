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

from app.api.v1.diagnosis.stage_scope import resolve_scope
from app.api.v1.reasoning.errors import FeatureDisabledError
from app.api.v1.reasoning.interfaces import ReasoningContext
from app.api.v1.reasoning.repository import ReasoningRepository
from app.api.v1.reasoning.schemas import (
    AnswerClassification,
    BusinessHealthScore,
    PillarScore,
)
from app.core.config import settings
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


#: How far the band floors are lowered, so that a founder who answers amber to
#: everything reads as Developing rather than Needs Attention.
#:
#: The scoring formula is (1 - sum/(count*2)) * 100 with green 0, amber 1, red
#: 2, so all-amber lands on exactly 50 -- and the catalogue's bands put 50 in
#: "Needs Attention". Amber means a real practice with a real gap, which is the
#: ordinary state of a working business, so the effect was that a fairly graded
#: session still read as a warning from end to end.
#:
#: Measured, not chosen. A keyed ideation run graded 5 red / 7 amber / 1 green
#: -- a spread with genuine variation in it -- and produced Market Clarity 42
#: ("Needs Attention"), Strategic Clarity 17, and an overall of 34: one point
#: under the Critical Gap line. The grading was right. The bands sat above
#: where honest grading lands.
#:
#: Applied here rather than by editing readiness_pillars.score_bands, because
#: those rows are content the team edits directly and carry the written band
#: descriptions with them. This moves only where the boundaries fall, leaves
#: the prose alone, and keeps the change in one reviewable place.
_BAND_FLOOR_SHIFT = Decimal("15")

#: The bottom band's wording is written for a business that has tried and is
#: failing. At ideation nothing is built yet, and readiness_pillars says so
#: itself -- "Revenue Maturity is not expected at this stage. The score here
#: measures intent." Telling a founder four months into an idea that she has a
#: "Critical Gap" describes being early as being broken.
_EARLY_STAGE_ORDERS = frozenset({1, 2})
_EARLY_BOTTOM_BAND = "Not started yet"
_BOTTOM_BAND = "Critical Gap"


def _flag_agrees_with_band(band: str | None) -> bool:
    """Whether a red flag may fire on a pillar showing `band`.

    readiness_pillars.red_flag_threshold is a fixed number per pillar; the band
    is decided separately by `_band_for`, which lowers the floors by
    _BAND_FLOOR_SHIFT and renames the bottom band at early stages. The two were
    never reconciled, so the same score got two verdicts on one page:

      * a live ideation report called all four pillars "Not started yet" or
        "Needs Attention" and then listed all four under RED FLAG PILLARS;
      * a live growth-stage report flagged three pillars reading "Needs
        Attention" -- the threshold is 40 and that band starts at 36.

    A red flag is the report's strongest claim: this one is WRONG. It cannot
    sit beside a band that says otherwise. So the flag is allowed only where
    the page already says the pillar is at the bottom -- which is also the
    honest reading at ideation, where a pillar with nothing in it is the stage
    rather than a fault.

    The threshold still decides WHETHER to flag within that band; this decides
    only where flagging is permitted at all. A pillar with no band (under the
    evidence floor) is never flagged, which is what already happened.
    """
    return band in (_BOTTOM_BAND, _EARLY_BOTTOM_BAND)


def _stage_order(context) -> int | None:
    """The founder's stage ORDER, not their stage id.

    Read from the loaded stage row when it is there; `stage_id` is the
    fallback, and only because the two coincide in the seeded catalogue -- an
    id is not an ordering and must not be treated as one if the rows are ever
    renumbered.
    """
    stage = getattr(getattr(context, "founder", None), "stage", None)
    order = getattr(stage, "stage_order", None)
    if order is not None:
        return int(order)
    sid = getattr(context, "stage_id", None)
    return int(sid) if sid is not None else None


def _band_for(score_bands, value: Decimal, stage_order: int | None = None) -> str | None:
    """Return the band `level` for `value`, with the middle floors shifted down.

    The BOTTOM band keeps its floor at 0 -- there is nothing beneath it to
    shift into -- and the TOP band keeps its own floor, so "Strong" is exactly
    as hard to reach as it was. Only the boundaries in between move, and
    ceilings follow from the floors so the bands still tile 0-100 with no gap
    for a value to fall through.
    """
    bands = list(score_bands or [])
    if not bands:
        return None
    ordered = sorted(bands, key=lambda b: Decimal(str(b.get("range_min", 0))))
    last = len(ordered) - 1

    floors: list[Decimal] = []
    for i, band in enumerate(ordered):
        low = Decimal(str(band.get("range_min", 0)))
        if i == 0:
            floors.append(Decimal("0"))
        elif i == last:
            floors.append(low)
        else:
            floors.append(max(Decimal("0"), low - _BAND_FLOOR_SHIFT))

    level = None
    for i, band in enumerate(ordered):
        ceiling = (Decimal(str(band.get("range_max", 100))) if i == last
                   else floors[i + 1] - 1)
        if floors[i] <= value <= ceiling:
            level = band.get("level")
            break
    if level is None:
        level = ordered[last].get("level")

    if (level == _BOTTOM_BAND and stage_order is not None
            and stage_order in _EARLY_STAGE_ORDERS):
        return _EARLY_BOTTOM_BAND
    return level


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
    reached a stage is not penalised for its unseen questions. The caller routes
    a pillar with too few answers to `null` before ever calling here (see
    Settings.MIN_ANSWERS_PER_PILLAR_SCORE), so `answer_scores` always holds at
    least that many in practice.
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
        stage_order = _stage_order(context)

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
            # NOT_APPLICABLE is excluded from BOTH the numerator and the
            # denominator, which is the whole reason it exists as a band rather
            # than being folded into Amber: "this does not apply to my business"
            # must not drag the pillar down, and it must not dilute it either.
            #
            # Two things went wrong without this guard. c.score is None for the
            # unscored band, so `sum(answer_scores)` in
            # RiskInversionPillarScoreStrategy raised on the None; and even had
            # it not, `len(answer_scores)` counted the answer, inflating
            # `answered_count * 2` and quietly pulling the pillar's risk ratio
            # down as though an inapplicable question were a Green one.
            #
            # Unreachable until migration d4a91c7e2b83 widened
            # answers.score_label from varchar(10), since 'not_applicable' is
            # fourteen characters and no row could carry it. The equivalent
            # filter has always been present in diagnostic.py's category-risk
            # loop (`if question is not None and c.label.is_scored`); this one
            # was never updated alongside it.
            if not c.label.is_scored:
                continue
            scores_by_pillar[pillar_id].append(c.score)

        # Which of each pillar's Part 2 dimensions this founder's STAGE covers.
        # Attached to every pillar, scored or not, so the report can qualify a
        # pillar name that stands for only part of the pillar. None when the
        # stage is unknown, which yields no coverage claim rather than a wrong
        # one -- same fail-open convention as the scope filters themselves.
        scope = resolve_scope(getattr(context, "founder", None)) if context else None

        pillar_scores: list[PillarScore] = []
        minimum = max(1, settings.MIN_ANSWERS_PER_PILLAR_SCORE)
        for pillar in pillars:
            covered, total = (
                scope.coverage_of(pillar.pillar_id) if scope is not None else ((), 0)
            )
            answer_scores = scores_by_pillar.get(pillar.pillar_id, [])
            # Too little evidence is reported as no evidence. A pillar answered
            # once or twice can only land on a handful of values, and the founder
            # is shown a BAND -- so a "Critical Gap" off one amber answer is
            # indistinguishable from one off eight. Showing nothing is honest;
            # showing a band the sample cannot support is not. See
            # Settings.MIN_ANSWERS_PER_PILLAR_SCORE.
            #
            # assessed_question_count still carries the real count, so a caller
            # can tell "never asked" (0) from "asked, below the floor" (1-2).
            if len(answer_scores) < minimum:
                pillar_scores.append(
                    PillarScore(
                        pillar_id=pillar.pillar_id,
                        pillar_name=pillar.pillar_name,
                        weight=pillar.pillar_weightage,
                        score=None,
                        band=None,
                        red_flag_triggered=False,
                        red_flag_note=None,
                        assessed_question_count=len(answer_scores),
                        dimensions_in_scope=covered,
                        dimensions_total=total,
                    )
                )
                continue

            # The per-pillar 0-100 score is the injected business rule.
            health = _int(self.pillar_score_strategy.score(pillar, answer_scores, context))
            band = _band_for(pillar.score_bands, health, stage_order)
            threshold = pillar.red_flag_threshold
            flagged = (threshold is not None and health <= threshold
                       and _flag_agrees_with_band(band))
            pillar_scores.append(
                PillarScore(
                    pillar_id=pillar.pillar_id,
                    pillar_name=pillar.pillar_name,
                    weight=pillar.pillar_weightage,
                    score=health,
                    band=band,
                    red_flag_triggered=flagged,
                    red_flag_note=pillar.red_flag_note if flagged else None,
                    assessed_question_count=len(answer_scores),
                    dimensions_in_scope=covered,
                    dimensions_total=total,
                )
            )

        overall, overall_band = self._overall(pillar_scores, pillars, stage_order)
        red_flags = tuple(p.pillar_name for p in pillar_scores if p.red_flag_triggered)
        return BusinessHealthScore(
            overall_score=overall,
            band=overall_band,
            pillars=tuple(pillar_scores),
            red_flags=red_flags,
        )

    def _overall(self, pillar_scores, pillars,
                 stage_order: int | None = None) -> tuple[Decimal, str | None]:
        """Weight the assessed pillars by pillar_weightage, renormalising over the
        weight actually present so unseen pillars neither help nor hurt."""
        assessed = [p for p in pillar_scores if p.score is not None]
        total_weight = sum((p.weight for p in assessed), _ZERO)
        if total_weight <= 0:
            return _ZERO, None
        weighted = sum((p.score * p.weight for p in assessed), _ZERO)
        overall = _int(weighted / total_weight)
        bands = pillars[0].score_bands if pillars else None
        return overall, _band_for(bands, overall, stage_order)
