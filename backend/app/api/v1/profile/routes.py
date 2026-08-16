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

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder
from app.repositories import founder_context_repository, founder_repository
from app.schemas.founder import AvatarUploadResponse, FounderRead, FounderUpdate
from app.schemas.founder_context import FounderContextRead, FounderContextUpdate
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


_AVATAR_CONTENT_TYPES = {
    "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/webp": "webp",
}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5MB, matches the frontend's own check


class InvalidAvatarError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


@router.post("/avatar", response_model=AvatarUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Replace the founder's profile photo.

    Live-confirmed gap: the camera button on the profile page had no
    onClick at all, and there was no backend support for it whatsoever --
    no upload endpoint, no storage, no column. This is the first real
    version: local disk storage, served back via the /uploads static mount
    (see main.py). A real deployment wants this on a cloud bucket instead
    -- files here do not survive a redeploy onto a fresh container -- but
    that is a storage-backend swap scoped to this one function, not a
    reason to leave the feature fake in the meantime.

    One file per founder (named by founder_id, extension only): a new
    upload overwrites the old one rather than accumulating orphaned files
    with nothing to ever clean them up.
    """
    content_type = (file.content_type or "").lower()
    ext = _AVATAR_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise InvalidAvatarError(
            f"Unsupported image type {content_type!r} -- use PNG, JPEG or WEBP."
        )

    content = await file.read()
    if len(content) > _MAX_AVATAR_BYTES:
        raise InvalidAvatarError("That image is too large -- please pick one under 5MB.")
    if not content:
        raise InvalidAvatarError("That file is empty.")

    upload_dir = Path(__file__).resolve().parents[4] / "uploads" / "avatars"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Wipe any previous avatar for this founder under a DIFFERENT extension
    # first -- otherwise switching from a .png to a .jpg would leave the old
    # .png sitting on disk forever, unreferenced but never deleted.
    for old in upload_dir.glob(f"{founder.founder_id}.*"):
        old.unlink(missing_ok=True)

    # jti-free, cache-busting filename: a browser (or CDN in front of this
    # later) must not keep serving yesterday's photo from cache under the
    # same URL just because the founder_id is unchanged.
    filename = f"{founder.founder_id}.{uuid.uuid4().hex[:8]}.{ext}"
    (upload_dir / filename).write_bytes(content)

    avatar_url = f"{str(request.base_url).rstrip('/')}/uploads/avatars/{filename}"
    founder_repository.update(db, founder, {"avatar_url": avatar_url})
    return AvatarUploadResponse(avatar_url=avatar_url)


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


# --- founder context / "memory" ---------------------------------------------

@router.get("/context", response_model=FounderContextRead)
async def read_context(
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """The founder's background context. Returns an empty object if none set yet."""
    ctx = founder_context_repository.get_by_founder(db, founder.founder_id)
    return ctx if ctx is not None else FounderContextRead()


@router.put("/context", response_model=FounderContextRead)
async def upsert_context(
    payload: FounderContextUpdate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Create or update the founder's background context (one row per founder)."""
    return founder_context_repository.upsert(
        db, founder.founder_id, payload.model_dump(exclude_unset=True)
    )


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
