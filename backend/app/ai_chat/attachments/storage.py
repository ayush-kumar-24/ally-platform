"""Attachment blob storage -- S3 when configured, Postgres BYTEA otherwise.

Which backend holds a given file is recorded on the row itself: a non-null
`file_uploads.storage_path` means the bytes are an S3 object under that key,
NULL means they are inline in `file_uploads.content`. That is deliberate --
pointing at a bucket later never orphans what was uploaded before it, because
existing rows keep resolving from Postgres while new ones go to S3, with no
backfill required and no flag day.

The actual S3 client/protocol has moved to app.services.object_storage --
none of it was attachment-specific, and avatar uploads (profile/routes.py)
now share the exact same client, config keys and fail-open behaviour rather
than a second, drifting copy. Re-exported below so the existing
`from app.ai_chat.attachments.storage import ObjectStorage, ...` import sites
(sql_repository.py, core/container.py) need no change.
"""

from __future__ import annotations

from app.services.object_storage import (  # noqa: F401 -- re-exported for existing callers
    ObjectStorage,
    ObjectStorageError,
    S3ObjectStorage,
    build_object_storage,
)


def object_key(founder_id: int, attachment_id: str, extension: str) -> str:
    """Founder-scoped, collision-free, and prefixed so a bucket lifecycle rule
    can target attachments without touching anything else in it."""
    suffix = f".{extension}" if extension else ""
    return f"attachments/{founder_id}/{attachment_id}{suffix}"
