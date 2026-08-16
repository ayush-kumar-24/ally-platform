"""Auth for inbound webhooks. Not founder auth, not admin auth -- a shared secret,
because the caller is Supabase (or an external scheduler), not a signed-in user.

Timing-safe comparison and fail-closed-on-unconfigured are the two things that
matter here: a `==` compare leaks the secret's length/prefix one request at a time,
and treating an unset SUPABASE_WEBHOOK_SECRET as "no check needed" would turn a
missing env var in production into an open door.
"""

from __future__ import annotations

import hmac

from fastapi import Header

from app.core.config import settings
from app.middleware.error_handler import AppError


class WebhookUnauthorizedError(AppError):
    def __init__(self):
        super().__init__("Invalid or missing webhook secret.", status_code=401)


def verify_webhook_secret(x_webhook_secret: str | None = Header(default=None)) -> None:
    configured = settings.SUPABASE_WEBHOOK_SECRET
    if not configured or not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, configured):
        raise WebhookUnauthorizedError()
