"""The adaptive loop: rebuild RCCS from the session's answers, persist the trail,
and decide whether the diagnosis is finished.

This is the seam between the pure model (`rccs.py`, `completion.py`) and the
running session. It owns no arithmetic and no product rule -- it gathers the
inputs those two modules need and hands the decision back.

COST. Zero LLM calls. Every input is either a stored answer that the submit-time
advisor already classified, or a catalogue row. That is the point: the frozen
requirement is that a stopping decision must not cost a model call, and the
existing `incremental_confidence.recompute()` had already established the
deterministic post-answer path this reuses.

FAILS OPEN, like everything else on this path. Any error returns None and the
caller keeps asking questions. Ending a founder's diagnosis on a failed
computation is the one outcome that must be impossible; continuing to ask costs
them some questions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.completion import CompletionDecision, decide_completion
from app.api.v1.diagnosis.rccs import (
    RCCS_STRONG_THRESHOLD,
    RCCSState,
    events_for_answer,
)
from app.api.v1.diagnosis.rccs_store import RCCSStore
from app.core.config import settings
from app.core.logger import logger
from app.models.enums import ScoreLabel

__all__ = ["AdaptiveState", "evaluate_session"]

#: An unanswered question counts as HIGH VALUE when it probes a cause that is
#: close enough to the threshold that one answer could carry it across. Below
#: this, another answer cannot realistically change the diagnosis; at or above
#: 0.80 the cause is already strong and needs no further probing to qualify.
#:
#: 0.50 is the score a single Red answer produces, so the band is "at least one
#: Red already, not yet strong" -- the causes actually in contention.
_HIGH_VALUE_FLOOR = Decimal("0.50")


@dataclass(frozen=True)
class AdaptiveState:
    """Everything the loop concluded this turn."""

    rccs: RCCSState
    decision: CompletionDecision
    anchor_problem_ids: frozenset[int]
    pillars_sufficient: bool
    high_value_question_available: bool


def _answers(db: Session, session_id: int):
    return db.execute(
        text(
            "SELECT answer_id, question_id, score_label FROM answers "
            "WHERE session_id = :sid AND score_label IS NOT NULL "
            "ORDER BY answer_id"
        ),
        {"sid": session_id},
    ).all()


def _pillars_sufficient(db: Session, session_id: int, in_scope_pillars: set[int]) -> bool:
    """Has every in-scope pillar been probed enough to be scored at all?

    Reuses `MIN_ANSWERS_PER_PILLAR_SCORE` rather than inventing a second
    sufficiency floor. That constant already defines the point below which a
    pillar reports no score and no band -- so a diagnosis that stops beneath it
    would produce a report with blank pillars, which is the founder-visible
    failure this check exists to prevent.

    With no in-scope pillars known, this returns True rather than blocking: the
    gate has five other checks, and an unavailable pillar map must not be able to
    strand a founder in an endless diagnosis.
    """
    if not in_scope_pillars:
        return True
    try:
        rows = db.execute(
            text(
                """
                SELECT p.pillar_id, count(*) AS n
                  FROM answers a
                  JOIN questions q ON q.question_id = a.question_id
                  JOIN problems  p ON p.problem_id  = q.problem_id
                 WHERE a.session_id = :sid
                   AND a.score_label IS NOT NULL
                   AND a.score_label <> 'not_applicable'
                 GROUP BY p.pillar_id
                """
            ),
            {"sid": session_id},
        ).all()
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("Pillar sufficiency unavailable", extra={"error": str(exc)})
        return True

    counts = {r.pillar_id: r.n for r in rows}
    minimum = max(1, settings.MIN_ANSWERS_PER_PILLAR_SCORE)
    return all(counts.get(pid, 0) >= minimum for pid in in_scope_pillars)


def _high_value_question_available(
    db: Session, session_id: int, state: RCCSState
) -> bool:
    """Is there an unanswered question that could still change the diagnosis?

    Only causes in the contention band matter: already-strong causes need no
    further probing to qualify, and causes far below cannot be carried across by
    one answer. Asking whether such a question EXISTS is what stops the gate
    passing while the most informative question in the bank is still unasked.
    """
    contenders = [
        s.root_cause_id
        for s in state.all_scores()
        if _HIGH_VALUE_FLOOR <= s.rccs < RCCS_STRONG_THRESHOLD
    ]
    if not contenders:
        return False
    try:
        row = db.execute(
            text(
                """
                SELECT 1
                  FROM questions q
                 WHERE q.root_cause_id = ANY(:rcids)
                   AND NOT EXISTS (
                        SELECT 1 FROM answers a
                         WHERE a.session_id = :sid
                           AND a.question_id = q.question_id)
                 LIMIT 1
                """
            ),
            {"rcids": contenders, "sid": session_id},
        ).first()
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("High-value question probe unavailable", extra={"error": str(exc)})
        return False
    return row is not None


def evaluate_session(
    db: Session,
    session,
    founder,
    *,
    in_scope_pillars: set[int] | None = None,
    candidates_remaining: bool = True,
) -> AdaptiveState | None:
    """Recompute RCCS for the session and decide whether it is finished.

    Rebuilt from the stored answers every turn rather than carried in memory.
    That is what makes a resumed session, a replayed answer and a fresh request
    all produce the same scores -- and the dedupe key means rebuilding is
    idempotent by construction rather than by care.
    """
    try:
        rows = _answers(db, session.session_id)
        store = RCCSStore(db)
        edges = store.question_edges(tuple(r.question_id for r in rows))

        # Coverage-relative scoring needs to know how many questions the
        # catalogue holds for each cause this session touched -- primary causes
        # and siblings alike, since a sibling of one answer is the primary of
        # another. Gathered before scoring so every cause has its denominator
        # from the first event rather than acquiring one partway through.
        touched: set[int] = set()
        for edge in edges.values():
            if edge["root_cause_id"] is not None:
                touched.add(edge["root_cause_id"])
            touched.update(edge["sibling_ids"])
        askable = store.askable_question_counts(tuple(sorted(touched)))

        state = RCCSState(askable=askable)
        for seq, row in enumerate(rows):
            edge = edges.get(row.question_id)
            if edge is None:
                continue
            try:
                label = ScoreLabel(row.score_label)
            except ValueError:
                continue
            state.apply_all(
                events_for_answer(
                    answer_id=row.answer_id,
                    question_id=row.question_id,
                    score_label=label,
                    primary_root_cause_id=edge["root_cause_id"],
                    sibling_root_cause_ids=edge["sibling_ids"],
                    pillar_id=edge["pillar_id"],
                    sequence=seq,
                )
            )

        store.record(session.session_id, state.events)

        anchors = store.anchor_problem_ids(session.session_id)
        problem_of = store.problem_of_root_causes(state.tracked_root_cause_ids())
        pillars_ok = _pillars_sufficient(db, session.session_id, in_scope_pillars or set())
        high_value = _high_value_question_available(db, session.session_id, state)

        stage = getattr(founder, "stage", None)
        decision = decide_completion(
            state=state,
            anchor_problem_ids=anchors,
            problem_of_root_cause=problem_of,
            pillars_sufficient=pillars_ok,
            high_value_question_available=high_value,
            candidates_remaining=candidates_remaining,
            answered=len(rows),
            # The SAFETY CEILING, which is deliberately NOT `question_budget()`.
            # That number is the confidence score's coverage denominator and
            # keeps its exact meaning untouched; this one is the runaway guard.
            # `decide_completion` consults it LAST, so it can only ever catch a
            # session that neither finished nor ran out of questions.
            safety_ceiling=settings.safety_ceiling(
                getattr(stage, "question_budget", None)
            ),
        )

        logger.info(
            "Adaptive loop evaluated",
            extra={
                "session_id": session.session_id,
                "answered": len(rows),
                "tracked_causes": len(state.tracked_root_cause_ids()),
                "strong_causes": len(state.strong_scores()),
                "complete": decision.complete,
                "reason": str(decision.reason),
            },
        )
        return AdaptiveState(
            rccs=state,
            decision=decision,
            anchor_problem_ids=anchors,
            pillars_sufficient=pillars_ok,
            high_value_question_available=high_value,
        )
    except Exception as exc:                                   # noqa: BLE001
        logger.warning(
            "Adaptive loop failed; diagnosis continues",
            extra={"session_id": getattr(session, "session_id", None), "error": str(exc)},
        )
        return None
