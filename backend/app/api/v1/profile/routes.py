"""Profile endpoints.

The whole profile is one `founders` row. This exposes it both as a whole
(`/profile`) and as the four onboarding/profile sections, so the frontend can
save one step at a time:

    /profile/founder    founder DNA (Q9-13) + name
    /profile/business   what you're building (Q1-6)
    /profile/goals      90-day goal + 1-year vision (Q7-8)

Each section has GET (read that slice) and PATCH (partial update). The founder
row itself is created at login (see auth /session provisioning), so there is no
create here -- these only read and update. Email comes from the login itself, so
there is no separate company-details step.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.logger import logger
from app.db.session import get_db
from app.middleware.error_handler import AppError
from app.models import Founder
from app.repositories import founder_context_repository, founder_repository
from app.schemas.founder import AvatarUploadResponse, FounderRead, FounderUpdate
from app.services.object_storage import ObjectStorageError, build_object_storage
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


def avatar_object_key(founder_id: int, filename: str) -> str:
    """Nested under attachments/ on purpose: the ECS task role's IAM policy
    for chat attachments is scoped to that exact prefix (see
    app/ai_chat/attachments/storage.py), so avatars ride the same grant --
    turning S3 on for avatars needs no new IAM permission, no new env var,
    nothing beyond what attachments already required."""
    return f"attachments/avatars/{founder_id}/{filename}"


@router.post("/avatar", response_model=AvatarUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Replace the founder's profile photo.

    Live-confirmed gap (original version): the camera button on the profile
    page had no onClick at all, and there was no backend support for it
    whatsoever -- no upload endpoint, no storage, no column. First real
    version stored to local disk only, which its own docstring already
    flagged: "files here do not survive a redeploy onto a fresh container."

    S3-first now, using the exact same storage layer, bucket and key prefix
    already proven for chat attachments (app.services.object_storage) --
    genuinely the same problem, so it reuses the same fix rather than a
    second one. Falls back to local disk when no bucket is configured (local
    dev, CI) or if the S3 put itself fails at runtime, same fail-open
    contract as attachments: an avatar that saves beats an upload that
    errors. avatar_storage_path records which backend actually holds THIS
    photo, so a switch to S3 never orphans avatars uploaded before it.

    One photo per founder: a new upload overwrites/deletes the old one
    (whichever backend it was on) rather than accumulating orphans forever.
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

    # jti-free, cache-busting filename: a browser (or CDN in front of this
    # later) must not keep serving yesterday's photo from cache under the
    # same URL just because the founder_id is unchanged.
    # Full uuid4 (32 hex), not the first 8. Access control for this photo IS the
    # unguessability of its URL -- the serving route is public and no longer
    # consults the database at all -- so the random component is the whole
    # security boundary. 8 hex characters is ~4 billion, brute-forceable against
    # an enumerable founder_id; 32 is not. Older 8-char names keep working: the
    # route serves whatever key it is given.
    filename = f"{founder.founder_id}.{uuid.uuid4().hex}.{ext}"

    old_storage_path = founder.avatar_storage_path
    storage = build_object_storage()
    stored_to_s3 = False
    new_storage_path = None

    if storage is not None:
        key = avatar_object_key(founder.founder_id, filename)
        try:
            storage.put(key, content, content_type=content_type)
            new_storage_path = key
            stored_to_s3 = True
        except ObjectStorageError as exc:
            logger.error("profile: S3 avatar put failed; storing on local disk instead",
                        extra={"stage": "s3_put", "founder_id": founder.founder_id, "error": str(exc)})

    if stored_to_s3:
        # /profile is mounted under the /api/v1 prefix (see app/api/v1/router.py)
        # -- this route is not, so the URL handed back must include it explicitly
        # or the browser's <img> request 404s against the bare /profile/... path.
        avatar_url = f"{str(request.base_url).rstrip('/')}/api/v1/profile/avatar/{founder.founder_id}/{filename}"
        # Old avatar was also on S3 -- clean it up now that the new one is
        # confirmed stored. Best-effort: a leftover object is wasted space,
        # not a broken photo, so this must never fail the upload.
        if old_storage_path:
            try:
                storage.delete(old_storage_path)
            except ObjectStorageError as exc:
                logger.warning("profile: could not delete old S3 avatar (leaked, not fatal)",
                               extra={"founder_id": founder.founder_id, "error": str(exc)})
    else:
        upload_dir = Path(__file__).resolve().parents[4] / "uploads" / "avatars"
        upload_dir.mkdir(parents=True, exist_ok=True)
        # Wipe any previous LOCAL avatar for this founder first -- otherwise
        # switching extensions (.png -> .jpg) would leave the old file
        # sitting on disk forever, unreferenced but never deleted.
        for old in upload_dir.glob(f"{founder.founder_id}.*"):
            old.unlink(missing_ok=True)
        (upload_dir / filename).write_bytes(content)
        avatar_url = f"{str(request.base_url).rstrip('/')}/uploads/avatars/{filename}"
        new_storage_path = None
        # Old avatar was on S3 but this upload fell back to disk (bucket
        # unreachable this one time) -- still worth trying to clean up.
        if old_storage_path and storage is not None:
            try:
                storage.delete(old_storage_path)
            except ObjectStorageError:
                pass

    founder_repository.update(
        db, founder, {"avatar_url": avatar_url, "avatar_storage_path": new_storage_path}
    )
    return AvatarUploadResponse(avatar_url=avatar_url)


@router.get("/avatar/{founder_id}/{filename}", include_in_schema=False)
async def serve_avatar(founder_id: int, filename: str):
    """Proxies an S3-stored avatar back to the browser.

    Deliberately unauthenticated, matching the security model the local-disk
    /uploads static mount already used: an <img src> tag sends no
    Authorization header, so this can't require one either. Safety comes from
    the same place it already did for local files -- founder_id plus an
    unguessable random filename component (a full uuid4) -- rather than from a
    bearer token.
    """
    # NO database read here, deliberately.
    #
    # This route used to look the founder up to confirm the requested filename
    # matched their current avatar_storage_path. That check could never succeed
    # in production: `founders` is under row-level security, the runtime connects
    # as the non-superuser `ally_app`, and an <img> request carries no bearer
    # token -- so no RLS context is ever established and the lookup returned
    # None for every founder. The route then 404'd before it so much as reached
    # S3, which is why the upload appeared to work and the image never did.
    # Confirmed live: CURRENT_USER=ally_app, founder invisible without context.
    #
    # Establishing an RLS context here is not the answer either: there is no
    # authenticated founder to establish it *for*. The lookup itself has to go.
    #
    # What that check bought us -- "an old URL stops working the moment a new
    # photo replaces it" -- is preserved by the upload deleting the previous S3
    # object, so a stale key resolves to nothing. That deletion is best-effort,
    # so a stale URL can outlive its replacement if the delete failed; the
    # widened random filename component (see upload_avatar) is what keeps that
    # acceptable, since the URL is unguessable rather than merely stale.
    key = avatar_object_key(founder_id, filename)

    storage = build_object_storage()
    if storage is None:
        # Row says S3, but this process has no bucket configured -- config
        # drift (e.g. ATTACHMENT_S3_BUCKET removed) rather than a missing photo.
        logger.error("avatar 404: row points at S3 but no bucket is configured",
                     extra={"stage": "avatar_serve", "reason": "storage_unconfigured",
                            "founder_id": founder_id, "stored_key": key})
        raise HTTPException(status_code=404, detail="Avatar not found")

    content = storage.get(key)
    if content is None:
        # The row and the bucket agree, but the object is not readable. Either
        # the PUT never landed, or the task role can PutObject and not
        # GetObject -- an asymmetric IAM policy looks exactly like a missing
        # photo from here, and is invisible without this line.
        logger.error("avatar 404: object missing or unreadable in S3",
                     extra={"stage": "avatar_serve", "reason": "object_unreadable",
                            "founder_id": founder_id, "stored_key": key})
        raise HTTPException(status_code=404, detail="Avatar not found")

    ext = filename.rsplit(".", 1)[-1].lower()
    content_type = {v: k for k, v in _AVATAR_CONTENT_TYPES.items()}.get(ext, "application/octet-stream")
    # Immutable: the filename's random component changes on every upload, so
    # this exact URL can never point at a different photo later.
    return Response(content=content, media_type=content_type,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})


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
