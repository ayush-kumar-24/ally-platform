"""The one place this backend uses Supabase's service role key.

Sign-ups are switched off at the project level and the frontend's sign-in call
passes `shouldCreateUser: false`, so an address with no `auth.users` row can
never receive a login code. Creating that row is therefore the whole of what
"granting access" means, and it needs an admin credential the anon key does not
have.

SCOPE, DELIBERATELY NARROW
The service role key bypasses RLS on every table in the project. This module
exists so that fact is contained in one reviewable file: it makes exactly one
kind of request (create a user), against exactly one endpoint, and returns a
uuid. It does not hold a client, expose a generic request helper, or get
imported anywhere except the waitlist approval path. Anything that wants a
second use of this key should have to add it here, in the open.

WHY email_confirm=true
The founder never sees a Supabase-sent confirmation link -- our own approval
email is what tells them they are in, and they sign in with an OTP we ask
Supabase to mail at that point. An unconfirmed user would be refused that OTP,
so confirming here is what makes the approval email true.

NO PASSWORD IS SET
None is chosen for them, and none is transported. The founder's first sign-in
is the emailed code, and `verifyOtpAndSetPassword` in the frontend is where a
password of their choosing gets stored. This backend still handles no
credentials, which is the property worth keeping.
"""

from __future__ import annotations

from uuid import UUID

import httpx

from app.core.config import settings
from app.core.logger import logger
from app.middleware.error_handler import AppError

_TIMEOUT_SECONDS = 10


class IdentityProviderError(AppError):
    """The identity could not be created, so access was NOT granted.

    A 502, not a 500: the failure is upstream at Supabase, and the caller's own
    request was fine. Surfacing that difference matters to whoever is looking
    at the panel -- "try again in a minute" and "this registration is broken"
    are different instructions.
    """

    def __init__(self, message: str):
        super().__init__(message, status_code=502)


class IdentityProviderNotConfigured(AppError):
    def __init__(self) -> None:
        super().__init__(
            "SUPABASE_SERVICE_ROLE_KEY is not set, so approving cannot create the "
            "founder's login. Nothing was changed.",
            status_code=503,
        )


def is_configured() -> bool:
    """Whether approval can actually grant access. Read by the panel so it can
    say so up front rather than failing at the click."""
    return bool(settings.SUPABASE_SERVICE_ROLE_KEY and settings.SUPABASE_URL)


def create_auth_user(email: str, *, full_name: str | None = None) -> UUID:
    """Create the Supabase identity for `email` and return its uuid.

    Raises IdentityProviderNotConfigured when there is no key, and
    IdentityProviderError on any upstream failure. Never returns on failure --
    the caller must not be able to mistake a failed grant for a successful one.
    """
    if not is_configured():
        raise IdentityProviderNotConfigured()

    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users"
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    payload: dict = {"email": email, "email_confirm": True}
    if full_name:
        # Read by provisioning's _display_name at first login, so the founder
        # row starts with their real name instead of the local part of their
        # address.
        payload["user_metadata"] = {"full_name": full_name}

    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        logger.warning("Supabase admin create_user failed", extra={"error": str(exc)})
        raise IdentityProviderError(
            "Could not reach the identity provider. Nothing was changed -- try again."
        ) from exc

    if response.status_code in (200, 201):
        user_id = (response.json() or {}).get("id")
        if not user_id:
            raise IdentityProviderError("Identity provider returned no user id.")
        return UUID(str(user_id))

    # An address that already has an identity is not an error worth failing on:
    # it means someone created them by hand, or a previous approval got as far
    # as this call and lost the response. Recover the existing id so the
    # registration ends up correctly marked rather than permanently stuck.
    if response.status_code == 422:
        existing = _find_by_email(email)
        if existing is not None:
            logger.info("Supabase identity already existed", extra={"path": email})
            return existing

    # The body can carry the key in an echoed request under some error shapes,
    # so only the status code is logged.
    logger.warning(
        "Supabase admin create_user rejected",
        extra={"path": f"status={response.status_code}"},
    )
    raise IdentityProviderError(
        f"The identity provider refused the request ({response.status_code}). "
        "Nothing was changed."
    )


def _find_by_email(email: str) -> UUID | None:
    """The uuid of an existing identity, or None. Best-effort: used only to
    recover from a 422, so a failure here re-raises as the original refusal."""
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users"
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    try:
        response = httpx.get(
            url,
            params={"page": 1, "per_page": 200},
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        for user in (response.json() or {}).get("users", []):
            if (user.get("email") or "").lower() == email.lower():
                return UUID(str(user["id"]))
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("Supabase admin lookup failed", extra={"error": str(exc)})
    return None
