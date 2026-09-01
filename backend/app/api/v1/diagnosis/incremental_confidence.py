"""Recompute session confidence after every answer, and decide what happens next.

Confidence used to be computed once, by ReasoningService, on an ALREADY-completed
session. That made the 60/80 routing thresholds unreachable by construction: the
score arrived after the report had been generated, so `continue` and `validate`
were stored and never acted on, and a session only ended when the question bank
ran out -- 569 questions for Stage 0->1, which nobody finishes.

This runs the minimum needed to answer "how sure are we now": diagnosis
(category / stage / symptom) -> root-cause detection and ranking -> confidence.
It deliberately does NOT run retrieval enrichment, recommendations, business
health, archetype or report generation. Those produce the report and belong at the
end; running them per answer would cost thirty times what a diagnosis should.

The score is not monotonic, and that is correct. Four of its five signals can
fall:

    category signal (30%)  a weak answer dilutes the strongest category risk
    coverage        (25%)  only ever rises -- answered / question budget
    consistency     (20%)  a contradiction with an earlier answer cuts it sharply
    confirmation    (15%)  falls if top causes lose confirmation
    separation      (10%)  falls when a second cause becomes as likely as the first

Separation is the least obvious and the most useful: learning that two causes are
equally plausible LOWERS confidence, because it is genuinely less clear which one
is the problem. A founder answering well can still see the score dip.

Cost note: `classify_answers` re-classifies every answer it is given, with no
reuse. Running it over the whole history after each answer would be O(n^2) LLM
calls -- 465 for a 30-question diagnosis instead of 30. Prior answers already have
their label persisted on `answers.score_label`, so this path uses the STORED
classifier and lets the answer-time LLM classification stand. That keeps the
recompute deterministic and effectively free.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.models import DiagnosisSession, Founder, RoutingState

#: Never complete a diagnosis before this many answers, whatever the score says.
#: Early on, few signals are measured and the ones that are sit on thin evidence,
#: so a high score is more likely to be an artefact than a finding. Ending a
#: diagnosis in three questions would be indefensible to a founder regardless of
#: what the arithmetic said.
MIN_ANSWERS_BEFORE_COMPLETION = 8


async def recompute(
    db: Session,
    session: DiagnosisSession,
    founder: Founder,
) -> Decimal | None:
    """Score the session as it stands and update its routing_state in place.

    Returns the 0-100 score, or None when it could not be computed.

    Fails OPEN: any error leaves the session's existing routing_state untouched
    and the diagnosis continues. A scoring failure must never end a founder's
    diagnosis early, and must never strand them either -- the question budget
    still bounds the session even when this never succeeds.
    """
    try:
        from app.api.v1.reasoning.deps import build_reasoning_service_for_scoring

        assessment = await build_reasoning_service_for_scoring(db).assess_only(
            session, founder
        )
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(
            "Incremental confidence failed; diagnosis continues",
            extra={"session_id": session.session_id, "error": str(exc)},
        )
        return None

    if assessment is None:
        return None

    score = assessment.score
    session.overall_confidence_score = score

    answered = session.questions_answered_count or 0
    report_min, validate_min = _thresholds(db)

    if score >= report_min and answered >= MIN_ANSWERS_BEFORE_COMPLETION:
        session.routing_state = RoutingState.GENERATE_REPORT.value
    elif _healthy_enough_to_stop(db, assessment, answered, founder):
        session.routing_state = RoutingState.MONITOR.value
    elif score >= validate_min:
        session.routing_state = RoutingState.VALIDATE.value
    else:
        session.routing_state = RoutingState.CONTINUE.value

    logger.info(
        "Diagnosis confidence updated",
        extra={
            "session_id": session.session_id,
            "answered": answered,
            "confidence": float(score),
            "routing_state": session.routing_state,
        },
    )
    return score


def _healthy_enough_to_stop(
    db: Session,
    assessment,
    answered: int,
    founder: Founder,
) -> bool:
    """Has this founder been asked enough for "nothing is wrong" to be a finding?

    Two conditions, and both are necessary.

    NOTHING FLAGGED. Not "a low score" -- a low score is also what an incomplete
    diagnosis looks like. `any_category_flagged` is the only signal that
    separates a founder with no problem from one whose problem has not surfaced
    yet, which is why it travels with the score from `assess_only`.

    ENOUGH COVERAGE. Declaring a founder healthy needs MORE evidence than
    pointing at a problem, not less: a false all-clear sends someone away
    reassured, and nothing later in the product re-opens that question. So the
    bar is a high fraction of the stage's budget rather than the report
    threshold's usual floor.

    Without this route a healthy founder cannot finish at all. Their ceiling is
    45 against a report threshold of 80, and rule 4 caps them at 59 so `validate`
    is unreachable too -- so they answer every question in their budget and the
    session completes as `continue`, a state that says nothing was concluded
    while a report gets written anyway. This is the other half of
    NO_CATEGORY_ABOVE_THRESHOLD_ACTION, which already says not to force a
    diagnosis but never said when to stop asking.

    Fails CLOSED, unlike most of this module: any error keeps the diagnosis
    going. Continuing to ask costs a founder some questions; stopping early on a
    miscomputed threshold tells them their business is fine when nobody checked.
    """
    try:
        from app.api.v1.reasoning.config import monitor_eligible

        stage = getattr(founder, "stage", None)
        return monitor_eligible(
            any_category_flagged=assessment.any_category_flagged,
            answered=answered,
            budget=settings.question_budget(getattr(stage, "question_budget", None)),
            min_coverage=_monitor_min_coverage(db),
            min_answers=MIN_ANSWERS_BEFORE_COMPLETION,
        )
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(
            "Monitor-route eligibility could not be resolved; diagnosis continues",
            extra={"error": str(exc)},
        )
        return False


def _monitor_min_coverage(db: Session) -> Decimal:
    """Fraction of the stage budget required before an all-clear may be called.

    Externalised like every other threshold in this pipeline, with a safe
    in-code fallback so an unseeded database does not crash the route -- the
    `_optional` convention from the reasoning config.
    """
    from app.api.v1.reasoning.config import DEFAULT_MONITOR_MIN_COVERAGE, RuleCode
    from app.api.v1.reasoning.repository import ReasoningRepository

    values = ReasoningRepository(db).get_active_rule_values()
    return values.get(RuleCode.MONITOR_MIN_COVERAGE.value, DEFAULT_MONITOR_MIN_COVERAGE)


def _thresholds(db: Session) -> tuple[Decimal, Decimal]:
    """(generate_report_min, validate_min) from the live scoring_rules -- the same
    rows routing_state_for() uses, so the loop and the report layer can never
    disagree about what 80 means."""
    from app.api.v1.reasoning.config import build_reasoning_config
    from app.api.v1.reasoning.deps import build_confidence_strategy
    from app.api.v1.reasoning.repository import ReasoningRepository

    rule_values = ReasoningRepository(db).get_active_rule_values()
    cfg = build_reasoning_config(
        rule_values, confidence_strategy=build_confidence_strategy(rule_values)
    )
    return cfg.confidence.generate_report_min, cfg.confidence.validate_min
