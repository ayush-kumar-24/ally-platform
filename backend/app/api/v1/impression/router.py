"""The founder's first impression.

One endpoint. It is a GET because callers only ever want "the impression"; that
it is produced on first ask is an implementation detail, not a verb the client
should have to know about.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.api.v1.impression.schemas import FirstImpressionEnvelope
from app.api.v1.impression.service import get_or_create
from app.db.session import get_db
from app.models import Founder

router = APIRouter(prefix="/impression", tags=["impression"])


@router.get("", response_model=FirstImpressionEnvelope)
async def read_first_impression(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """The read Ally formed of this founder after onboarding.

    Generated and stored on the first request, then returned unchanged. Returns
    `available: false` when onboarding has not produced enough to read yet --
    the caller shows an empty state rather than a fabricated impression.
    """
    return await get_or_create(db, founder)
