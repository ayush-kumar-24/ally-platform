"""Object blob storage -- S3 when configured, a local fallback otherwise.

Originally lived under app/ai_chat/attachments/storage.py, written for chat
attachments only. Pulled out here unchanged (aside from generalised
docstrings) so avatar uploads (app/api/v1/profile/routes.py) can reuse the
exact same S3 client, config keys and fail-open behaviour rather than a
second, drifting copy of the same logic -- it was never attachment-specific
to begin with, only its call site was.

S3 is used only when a bucket is configured AND boto3 imports; anything else
(local dev, CI, a missing credential) transparently falls back, so a feature
built on this never depends on cloud access to be testable. A put that fails
at runtime falls back too rather than failing the caller's operation outright
-- callers decide what "falls back" means for them (inline bytes for
attachments, local disk for avatars), this module only ever reports whether
the S3 side succeeded.
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings
from app.core.logger import logger


class ObjectStorageError(Exception):
    """Any failure talking to the object store. Callers decide the fallback."""


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
            # A missing object is not fatal: callers list-by-name or 404
            # gracefully rather than this raising into a 500.
            logger.warning("object_storage: S3 get failed",
                           extra={"stage": "s3_get", "key": key, "error": str(exc)})
            return None

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            raise ObjectStorageError(f"s3: delete failed for {key!r}: {exc}") from exc

    def ping(self) -> None:
        """Cheap reachability + auth probe for the Health page -- confirms the
        bucket is there and the configured credentials can see it, without
        reading, writing or listing any actual object."""
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception as exc:  # noqa: BLE001 -- boto raises many shapes
            raise ObjectStorageError(f"s3: head_bucket failed for {self.bucket!r}: {exc}") from exc


def build_object_storage() -> ObjectStorage | None:
    """The configured store, or None to mean 'no S3, use the local fallback'.

    Shared by attachments and avatars -- same bucket (ATTACHMENT_S3_BUCKET),
    both nested under the attachments/ prefix (see object_key() /
    avatar_object_key() at each call site), so no new IAM grant or env var is
    needed to turn S3 on for avatars once it is already on for attachments.

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
        # Misconfiguration must not take the feature down -- log loudly and
        # let the caller fall back.
        logger.error("object_storage: S3 configured but unusable; falling back",
                     extra={"stage": "s3_init", "error": str(exc)})
        return None
