from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.models import Founder
from app.repositories import founder_repository
from app.schemas.founder import FounderRead, FounderUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=FounderRead)
async def read_profile(founder: Founder = Depends(get_founder_record)):
    """The signed-in founder's profile."""
    return founder


@router.patch("", response_model=FounderRead)
async def update_profile(
    payload: FounderUpdate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Partially update the profile.

    `exclude_unset` is what makes this a real PATCH: only fields the client
    actually sent are written, so a client that knows about three fields cannot
    blank out the twenty it has never heard of.

    `updated_at` is left alone deliberately -- the set_updated_at trigger owns it.
    """
    changes = payload.model_dump(exclude_unset=True)
    return founder_repository.update(db, founder, changes)
