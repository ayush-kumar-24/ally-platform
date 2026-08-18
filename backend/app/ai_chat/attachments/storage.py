"""Attachment blob storage -- S3 when configured, Postgres BYTEA otherwise.

Which backend holds a given file is recorded on the row itself: a non-null
`file_uploads.storage_path` means the bytes are an S3 object under that key,
NULL means they are inline in `file_uploads.content`. That is deliberate --
pointing at a bucket later never orphans what was uploaded before it, because
existing rows keep resolving from Postgres while new ones go to S3, with no
backfill required and no flag day.

S3 is used only when a bucket is configured AND boto3 imports; anything else
(local dev, CI, a missing credential) transparently falls back to inline
bytes, so the feature never depends on cloud access to be testable. A put
that fails at runtime also falls back rather than failing the upload -- an
attachment that stores is strictly better than one that errors, and the
caller records where it actually landed.
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings
from app.core.logger import logger


class ObjectStorageError(Exception):
    """Any failure talking to the object store. Callers fall back to inline bytes."""


class ObjectStorage(Protocol):
    def put(self, key: str, content: bytes, *, content_type: str) -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def delete(self, key: str) -> None: ...


class S3ObjectStorage:
    """Thin boto3 wrapper. One client per process (boto3 clients are thread-safe
    and connection-pooled; building one per request is pure latency)."""

    def __init__(self, *, bucket: str, region: str | None = None,
                 endpoint_url: str | None = None, client=None):
        if not bucket:
            raise ObjectStorageError("s3: bucket is not configured")
        self.bucket = bucket
        self._client = client or self._build_client(region, endpoint_url)

    @staticmethod
    def _build_client(region: str | None, endpoint_url: str | None):
        try:
            import boto3
        except ImportError as exc:  # dependency not installed -- caller falls back
            raise ObjectStorageError("s3: boto3 is not installed") from exc
        # Credentials come from the standard chain (ECS task role in
        # production, env/profile locally) -- never read from settings, so
        # nothing secret has to live in this repo's config.
        return boto3.client("s3", region_name=region or None,
                            endpoint_url=endpoint_url or None)

    def put(self, key: str, content: bytes, *, content_type: str) -> None:
        try:
            self._client.put_object(Bucket=self.bucket, Key=key, Body=content,
                                    ContentType=content_type)
        except Exception as exc:  # noqa: BLE001 -- boto raises many shapes
            raise ObjectStorageError(f"s3: put failed for {key!r}: {exc}") from exc

    def get(self, key: str) -> bytes | None:
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except Exception as exc:  # noqa: BLE001
            # A missing object is not fatal: the chat lists the file by name
            # and carries on, same as an unreadable format.
            logger.warning("attachments: S3 get failed",
                           extra={"stage": "s3_get", "key": key, "error": str(exc)})
            return None

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            raise ObjectStorageError(f"s3: delete failed for {key!r}: {exc}") from exc


def build_object_storage() -> ObjectStorage | None:
    """The configured store, or None to mean 'keep bytes in Postgres'.

    Returns None rather than raising when S3 isn't set up: no bucket is the
    normal, supported state for local dev and CI.
    """
    bucket = getattr(settings, "ATTACHMENT_S3_BUCKET", "") or ""
    if not bucket.strip():
        return None
    try:
        return S3ObjectStorage(
            bucket=bucket.strip(),
            region=getattr(settings, "ATTACHMENT_S3_REGION", "") or None,
            endpoint_url=getattr(settings, "ATTACHMENT_S3_ENDPOINT_URL", "") or None,
        )
    except ObjectStorageError as exc:
        # Misconfiguration must not take attachments down -- log loudly and
        # keep storing inline.
        logger.error("attachments: S3 configured but unusable; storing inline",
                     extra={"stage": "s3_init", "error": str(exc)})
        return None


def object_key(founder_id: int, attachment_id: str, extension: str) -> str:
    """Founder-scoped, collision-free, and prefixed so a bucket lifecycle rule
    can target attachments without touching anything else in it."""
    suffix = f".{extension}" if extension else ""
    return f"attachments/{founder_id}/{attachment_id}{suffix}"
