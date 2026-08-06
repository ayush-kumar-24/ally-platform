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


def recompute(
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

        score = build_reasoning_service_for_scoring(db).score_only(session, founder)
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(
            "Incremental confidence failed; diagnosis continues",
            extra={"session_id": session.session_id, "error": str(exc)},
        )
        return None

    if score is None:
        return None

    session.overall_confidence_score = score

    answered = session.questions_answered_count or 0
    threshold = _report_threshold(db)

    if score >= threshold and answered >= MIN_ANSWERS_BEFORE_COMPLETION:
        session.routing_state = RoutingState.GENERATE_REPORT.value
    elif score >= _validate_threshold(db):
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


def _report_threshold(db: Session) -> Decimal:
    from app.api.v1.reasoning.deps import get_reasoning_config

    return get_reasoning_config(db).confidence.generate_report_min


def _validate_threshold(db: Session) -> Decimal:
    from app.api.v1.reasoning.deps import get_reasoning_config

    return get_reasoning_config(db).confidence.validate_min
