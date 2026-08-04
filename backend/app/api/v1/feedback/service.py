"""Reading and writing founder feedback."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.feedback.schemas import FeedbackCreate, FeedbackRead
from app.middleware.error_handler import AppError
from app.models.schema import FounderFeedback, FounderReports, Sessions


class UnknownFeedbackTargetError(AppError):
    """The session or report being rated is not this founder's, or isn't there."""

    def __init__(self, what: str):
        super().__init__(f"No such {what} for this founder", status_code=422)

# Prompted feedback is asked once per thing. Unprompted feedback from the
# dashboard is not deduplicated -- a founder who wants to tell us something
# twice is not a bug.
PROMPTED_TYPES = {"diagnosis_rating", "report_rating"}


def _to_read(row: FounderFeedback) -> FeedbackRead:
    return FeedbackRead(
        feedback_id=row.feedback_id,
        feedback_type=row.feedback_type,
        rating=row.rating,
        comment=row.outcome_text,
        session_id=row.session_id,
        report_id=row.report_id,
        collected_at=row.collected_at,
    )


def _existing(db: Session, founder_id: int, payload: FeedbackCreate) -> FounderFeedback | None:
    """The founder's earlier answer to this exact prompt, if any."""
    if payload.feedback_type not in PROMPTED_TYPES:
        return None
    stmt = select(FounderFeedback).where(
        FounderFeedback.founder_id == founder_id,
        FounderFeedback.feedback_type == payload.feedback_type,
    )
    if payload.report_id is not None:
        stmt = stmt.where(FounderFeedback.report_id == payload.report_id)
    if payload.session_id is not None:
        stmt = stmt.where(FounderFeedback.session_id == payload.session_id)
    return db.execute(stmt).scalars().first()


def _assert_target_is_theirs(db: Session, founder_id: int, payload: FeedbackCreate) -> None:
    """The session/report must exist AND belong to the caller.

    Without this, the only check is the foreign key, which asks whether the row
    exists -- not whose it is. A founder could file feedback against another
    founder's report, and an id that simply doesn't exist would surface as a
    500 from the FK violation rather than a clear rejection.
    """
    if payload.session_id is not None:
        owned = db.execute(
            select(Sessions.session_id).where(
                Sessions.session_id == payload.session_id,
                Sessions.founder_id == founder_id,
            )
        ).scalar_one_or_none()
        if owned is None:
            raise UnknownFeedbackTargetError("diagnosis session")

    if payload.report_id is not None:
        owned = db.execute(
            select(FounderReports.report_id).where(
                FounderReports.report_id == payload.report_id,
                FounderReports.founder_id == founder_id,
            )
        ).scalar_one_or_none()
        if owned is None:
            raise UnknownFeedbackTargetError("report")


def submit(db: Session, founder_id: int, payload: FeedbackCreate) -> FeedbackRead:
    """Record feedback.

    Re-answering a prompt updates the earlier answer rather than stacking a
    second row: a founder who reopens a report and changes their mind has one
    opinion about it, not two.
    """
    _assert_target_is_theirs(db, founder_id, payload)

    row = _existing(db, founder_id, payload)
    if row is None:
        row = FounderFeedback(
            founder_id=founder_id,
            feedback_type=payload.feedback_type,
            session_id=payload.session_id,
            report_id=payload.report_id,
        )
        db.add(row)

    row.rating = payload.rating
    row.outcome_text = (payload.comment or "").strip() or None

    db.commit()
    db.refresh(row)
    return _to_read(row)


def list_for_founder(db: Session, founder_id: int) -> list[FeedbackRead]:
    """Newest first, so the client can answer 'have I already been asked?'."""
    rows = db.execute(
        select(FounderFeedback)
        .where(FounderFeedback.founder_id == founder_id)
        .order_by(FounderFeedback.collected_at.desc())
    ).scalars().all()
    return [_to_read(r) for r in rows]
