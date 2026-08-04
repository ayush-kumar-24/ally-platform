"""Founder feedback endpoints."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.feedback.schemas import FeedbackCreate, FeedbackList, FeedbackRead
from app.api.v1.feedback.service import list_for_founder, submit
from app.db.session import get_db
from app.models import Founder

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackCreate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Record a 1-5 rating, with optional words.

    Submitting the same prompt twice updates the first answer rather than
    creating a duplicate, so a founder can change their mind.
    """
    return submit(db, founder.founder_id, payload)


@router.get("", response_model=FeedbackList)
async def read_feedback(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Everything this founder has already told us.

    The UI uses it to avoid asking the same question twice -- a founder who has
    rated a report should not be prompted again each time they open it.
    """
    return FeedbackList(items=list_for_founder(db, founder.founder_id))
