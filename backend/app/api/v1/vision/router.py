"""Vision API router -- transport only. Every endpoint resolves the
authenticated founder and delegates to VisionService; validation lives in
the service. Domain errors propagate to the global handler.

Gated on Feature.VISION (Rs 999) at the router, not per endpoint -- see
require_vision. Goals, the cheaper tiers' equivalent, stays ungated in
app/api/v1/founder_goals/router.py.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status

from app.core.logger import logger
from app.middleware.error_handler import AppError
from app.services.object_storage import ObjectStorageError, build_object_storage

from app.api.v1.vision.dependencies import (
    get_current_founder_id,
    get_vision_service,
    require_vision,
)
from app.api.v1.vision.responses import VisionResponse, VisionSummaryResponse, VisionTerritoryResponse
from app.api.v1.vision.schemas import VisionSummaryUpdate, VisionTerritoryUpdate
from app.vision.service import VisionService

router = APIRouter(prefix="/vision", tags=["vision"],
                   dependencies=[Depends(require_vision)])

#: The image route lives on its own router because it must NOT inherit the plan
#: gate above. It is unauthenticated by necessity (an <img src> sends no
#: Authorization header), so a router-level dependency would 401 every vision
#: picture -- including for the Rs 999 founders the gate exists to serve.
#: Mounted separately in app/api/v1/router.py; both carry the /vision prefix.
public_router = APIRouter(prefix="/vision", tags=["vision"])

#: Same three formats the avatar upload accepts. GIF is left out on purpose: an
#: animated vision board is a different feature with different storage costs,
#: and silently keeping only the first frame would be worse than refusing it.
_IMAGE_CONTENT_TYPES = {
    "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/webp": "webp",
}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB, same ceiling as avatars


class InvalidVisionImageError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


def vision_object_key(founder_id: int, filename: str) -> str:
    """Under the same `attachments/` prefix chat attachments and avatars already
    use, so turning S3 on here needs no new bucket, env var or IAM grant."""
    return f"attachments/vision/{founder_id}/{filename}"


def _local_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "uploads" / "vision"


def _delete_previous(storage_path: str | None, storage) -> None:
    """Best-effort cleanup of the picture being replaced.

    One image per territory, so the old one has no reader the moment the new
    row is written. A failure here leaks a file; it must never fail the upload
    the founder is waiting on, which is why it is swallowed rather than raised.
    """
    if not storage_path:
        return
    try:
        if storage_path.startswith("s3:") and storage is not None:
            storage.delete(storage_path[3:])
        elif storage_path.startswith("local:"):
            (_local_dir() / storage_path[6:]).unlink(missing_ok=True)
    except (ObjectStorageError, OSError) as exc:
        logger.warning("vision: could not delete replaced image (leaked, not fatal)",
                       extra={"stage": "vision_image_cleanup", "path": storage_path, "error": str(exc)})


@router.get("", response_model=VisionResponse, summary="Get my vision")
def get_vision(
    founder_id: int = Depends(get_current_founder_id),
    service: VisionService = Depends(get_vision_service),
) -> VisionResponse:
    return VisionResponse.from_domain(service.get_territories(founder_id), service.get_summary(founder_id))


@router.put("/territories/{territory_key}", response_model=VisionTerritoryResponse, summary="Save one vision territory")
def upsert_territory(
    territory_key: str,
    payload: VisionTerritoryUpdate,
    founder_id: int = Depends(get_current_founder_id),
    service: VisionService = Depends(get_vision_service),
) -> VisionTerritoryResponse:
    t = service.upsert_territory(
        founder_id, territory_key, statement=payload.statement, tag1=payload.tag1, tag2=payload.tag2)
    return VisionTerritoryResponse.from_domain(territory_key, t)


@router.put("/summary", response_model=VisionSummaryResponse, summary="Save my vision summary")
def upsert_summary(
    payload: VisionSummaryUpdate,
    founder_id: int = Depends(get_current_founder_id),
    service: VisionService = Depends(get_vision_service),
) -> VisionSummaryResponse:
    fields = payload.model_dump(exclude_unset=True)
    s = service.upsert_summary(founder_id, **fields)
    return VisionSummaryResponse.from_domain(s)


@router.post(
    "/territories/{territory_key}/image",
    response_model=VisionTerritoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a picture to one vision territory",
)
async def upload_territory_image(
    territory_key: str,
    request: Request,
    file: UploadFile = File(...),
    founder_id: int = Depends(get_current_founder_id),
    service: VisionService = Depends(get_vision_service),
) -> VisionTerritoryResponse:
    """Put a picture on a vision the founder has already written.

    S3 first, local disk when no bucket is configured or the put fails at
    runtime -- the same fail-open contract as avatars and chat attachments,
    reusing the same storage layer rather than a third copy of it. An image
    that saves beats an upload that errors.

    404 when the territory has no statement yet: the picture belongs to a
    vision, and creating an empty one to hold it would put a blank card on the
    founder's page.
    """
    content_type = (file.content_type or "").lower()
    ext = _IMAGE_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise InvalidVisionImageError(
            f"Unsupported image type {content_type!r} -- use PNG, JPEG or WEBP."
        )

    content = await file.read()
    if not content:
        raise InvalidVisionImageError("That file is empty.")
    if len(content) > _MAX_IMAGE_BYTES:
        raise InvalidVisionImageError("That image is too large -- please pick one under 5MB.")

    # Full uuid4, as for avatars: the serving route is public and does not read
    # the database, so the unguessability of this name IS the access control.
    filename = f"{founder_id}.{territory_key}.{uuid.uuid4().hex}.{ext}"
    previous = service.get_territory_storage_path(founder_id, territory_key)

    storage = build_object_storage()
    stored_to_s3 = False
    if storage is not None:
        try:
            storage.put(vision_object_key(founder_id, filename), content, content_type=content_type)
            stored_to_s3 = True
        except ObjectStorageError as exc:
            logger.error("vision: S3 put failed; storing on local disk instead",
                         extra={"stage": "vision_image_upload", "error": str(exc)})

    base = str(request.base_url).rstrip("/")
    if stored_to_s3:
        image_url = f"{base}/api/v1/vision/image/{founder_id}/{filename}"
        storage_path = f"s3:{vision_object_key(founder_id, filename)}"
    else:
        directory = _local_dir()
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_bytes(content)
        image_url = f"{base}/uploads/vision/{filename}"
        storage_path = f"local:{filename}"

    updated = service.set_territory_image(
        founder_id, territory_key, image_url=image_url, storage_path=storage_path)
    if updated is None:
        # Nothing to attach it to. Clean up the bytes just written rather than
        # leaving an orphan behind a 404.
        _delete_previous(storage_path, storage)
        raise HTTPException(
            status_code=404,
            detail="Write this vision before adding a picture to it.",
        )

    _delete_previous(previous, storage)
    return VisionTerritoryResponse.from_domain(territory_key, updated)


@router.delete(
    "/territories/{territory_key}/image",
    response_model=VisionTerritoryResponse,
    summary="Remove a vision territory's picture",
)
def delete_territory_image(
    territory_key: str,
    founder_id: int = Depends(get_current_founder_id),
    service: VisionService = Depends(get_vision_service),
) -> VisionTerritoryResponse:
    """The statement stays; only the picture goes."""
    previous = service.get_territory_storage_path(founder_id, territory_key)
    updated = service.set_territory_image(founder_id, territory_key, image_url=None, storage_path=None)
    if updated is None:
        raise HTTPException(status_code=404, detail="No such vision.")
    _delete_previous(previous, build_object_storage())
    return VisionTerritoryResponse.from_domain(territory_key, updated)


@public_router.get("/image/{founder_id}/{filename}", include_in_schema=False)
def serve_vision_image(founder_id: int, filename: str):
    """Proxies an S3-stored vision image back to the browser.

    Unauthenticated by necessity, exactly as for avatars: an <img src> sends no
    Authorization header. Safety is the unguessable uuid4 in the filename, not
    a token. No database read either -- `vision_territories` is under row-level
    security and an image request establishes no RLS context, so a lookup here
    would return nothing for every founder and 404 every picture. Avatars shipped
    that bug once; this route starts without it.
    """
    storage = build_object_storage()
    if storage is None:
        logger.error("vision image 404: no bucket configured",
                     extra={"stage": "vision_image_serve", "founder_id": founder_id})
        raise HTTPException(status_code=404, detail="Image not found")

    content = storage.get(vision_object_key(founder_id, filename))
    if content is None:
        logger.error("vision image 404: object missing or unreadable in S3",
                     extra={"stage": "vision_image_serve", "founder_id": founder_id,
                            "filename": filename})
        raise HTTPException(status_code=404, detail="Image not found")

    ext = filename.rsplit(".", 1)[-1].lower()
    media_type = {v: k for k, v in _IMAGE_CONTENT_TYPES.items()}.get(ext, "application/octet-stream")
    # Immutable: the random component changes on every upload, so this exact
    # URL can never point at a different picture later.
    return Response(content=content, media_type=media_type,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})
