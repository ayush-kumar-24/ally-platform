"""Profile endpoints.

The whole profile is one `founders` row. This exposes it both as a whole
(`/profile`) and as the four onboarding/profile sections, so the frontend can
save one step at a time:

    /profile/founder    founder DNA (Q9-13) + name
    /profile/business   what you're building (Q1-6)
    /profile/goals      90-day goal + 1-year vision (Q7-8)

Each section has GET (read that slice) and PATCH (partial update). The founder
row itself is created at login (see auth /session provisioning), so there is no
create here -- these only read and update. Name and email come from the
Google/LinkedIn login, so there is no separate company-details step.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder
from app.repositories import founder_repository
from app.schemas.founder import FounderRead, FounderUpdate
from app.schemas.progress import ProgressResponse, ValidationResponse
from app.schemas.sections import (
    BusinessInfoRead,
    BusinessInfoUpdate,
    FounderInfoRead,
    FounderInfoUpdate,
    GoalsRead,
    GoalsUpdate,
)
from app.services.profile_progress import compute_progress, validate_profile

router = APIRouter(prefix="/profile", tags=["profile"])


class UnknownStageError(AppError):
    def __init__(self, stage: str):
        super().__init__(f"Unknown stage {stage!r}", status_code=422)


# --- whole profile ----------------------------------------------------------

@router.get("", response_model=FounderRead)
async def read_profile(founder: Founder = Depends(get_founder_record)):
    """The signed-in founder's full profile."""
    return founder


@router.patch("", response_model=FounderRead)
async def update_profile(
    payload: FounderUpdate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Partially update the profile. Only the fields sent are written."""
    return founder_repository.update(db, founder, payload.model_dump(exclude_unset=True))


# --- progress + validation --------------------------------------------------

@router.get("/progress", response_model=ProgressResponse)
async def read_progress(founder: Founder = Depends(get_founder_record)):
    """How complete the profile is -- per-field, per-section, and overall %."""
    return compute_progress(founder)


@router.get("/validate", response_model=ValidationResponse)
async def validate(founder: Founder = Depends(get_founder_record)):
    """Whether the profile has every required field; lists what's still missing."""
    return validate_profile(founder)


# --- Founder information (Q9-13 + name) -------------------------------------

@router.get("/founder", response_model=FounderInfoRead)
async def read_founder_info(founder: Founder = Depends(get_founder_record)):
    return founder


@router.patch("/founder", response_model=FounderInfoRead)
async def update_founder_info(
    payload: FounderInfoUpdate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    return founder_repository.update(db, founder, payload.model_dump(exclude_unset=True))


# --- Business information (Q1-6) --------------------------------------------

@router.get("/business", response_model=BusinessInfoRead)
async def read_business_info(founder: Founder = Depends(get_founder_record)):
    return founder


@router.patch("/business", response_model=BusinessInfoRead)
async def update_business_info(
    payload: BusinessInfoUpdate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)

    # `stage` comes in as a name/label -- resolve it to the stage_id column.
    if "stage" in changes:
        stage = changes.pop("stage")
        if stage is not None:
            stage_id = founder_repository.resolve_stage_id(db, stage)
            if stage_id is None:
                raise UnknownStageError(stage)
            changes["stage_id"] = stage_id

    return founder_repository.update(db, founder, changes)


# --- Goals (Q7-8) -----------------------------------------------------------

@router.get("/goals", response_model=GoalsRead)
async def read_goals(founder: Founder = Depends(get_founder_record)):
    return founder


@router.patch("/goals", response_model=GoalsRead)
async def update_goals(
    payload: GoalsUpdate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    return founder_repository.update(db, founder, payload.model_dump(exclude_unset=True))
