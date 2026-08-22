"""The Google OAuth dance, over plain HTTP.

Deliberately not google-auth-oauthlib: the flow is an authorization URL and two
form POSTs, httpx is already a dependency, and adding a package to the image for
sixty lines of well-documented protocol buys a rebuild and an extra thing to
keep patched. The tradeoff would be different if we needed the full library's
PKCE/device-flow surface; we do not.

Scope is calendar.events, NOT the broader `calendar` scope the discovery-booking
service account uses. events is enough to create, update and delete the events
Ally owns, and does not grant the ability to read every calendar the founder can
see or reconfigure their calendar list. Ask for the narrowest thing that works:
this is someone's personal calendar and the consent screen names what we ask for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = (
    "https://www.googleapis.com/auth/calendar.events",
    # Only to show "Connected: name@gmail.com". The founder's Ally login is
    # email-only and unrelated, so without this they cannot tell WHICH Google
    # account they connected -- and disconnecting the wrong one is a real risk.
    "openid",
    "email",
)

_TIMEOUT = 15.0


class GoogleOAuthError(RuntimeError):
    """The token endpoint refused us, or could not be reached."""


class GoogleAccessRevokedError(GoogleOAuthError):
    """The refresh token is no longer valid -- the founder must reconnect.

    Separate from the generic error because the response differs: a revoked
    grant is permanent and needs a prompt, while a 5xx or timeout is transient
    and must NOT burn the stored connection.
    """


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str          # "" when Google omits it (see exchange_code)
    expires_at: datetime
    account_email: str = ""


def is_configured() -> bool:
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID
                and settings.GOOGLE_OAUTH_CLIENT_SECRET
                and settings.GOOGLE_OAUTH_REDIRECT_URI)


def authorization_url(state: str) -> str:
    """Where to send the founder to grant access.

    `access_type=offline` + `prompt=consent` together are what actually produce
    a refresh token. offline alone returns one only on the FIRST authorisation
    for a given client/user pair -- so a founder who connects, disconnects and
    reconnects would come back with an access token that expires in an hour and
    no way to renew it. Forcing the consent screen every time costs one extra
    click and makes reconnection reliable.
    """
    from urllib.parse import urlencode

    return f"{AUTH_ENDPOINT}?" + urlencode({
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    })


def _expires_at(payload: dict) -> datetime:
    # 60s of slack: a token that expires "in 3600 seconds" should be refreshed
    # slightly early rather than mid-request against a clock that is a little
    # out of step with Google's.
    seconds = int(payload.get("expires_in", 3600))
    return datetime.now(timezone.utc) + timedelta(seconds=max(seconds - 60, 0))


def _post_token(data: dict) -> dict:
    try:
        response = httpx.post(TOKEN_ENDPOINT, data=data, timeout=_TIMEOUT)
    except httpx.HTTPError as exc:
        raise GoogleOAuthError(f"Could not reach Google: {exc}") from exc

    if response.status_code >= 400:
        body = response.json() if response.headers.get("content-type", "").startswith(
            "application/json") else {}
        error = str(body.get("error", ""))
        # invalid_grant is Google's answer for "this refresh token is dead" --
        # revoked from the account's permissions page, expired after long
        # disuse, or invalidated by a password change. It is the one case that
        # genuinely requires the founder to act.
        if error == "invalid_grant":
            raise GoogleAccessRevokedError(
                body.get("error_description") or "Access was revoked in Google.")
        raise GoogleOAuthError(
            f"Google returned {response.status_code}: {error or response.text[:200]}")
    return response.json()


def exchange_code(code: str) -> TokenBundle:
    """Trade the one-time code from the redirect for tokens."""
    payload = _post_token({
        "code": code,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    return TokenBundle(
        access_token=payload.get("access_token", ""),
        # May legitimately be absent -- see authorization_url. The caller keeps
        # any refresh token it already had rather than overwriting it with "".
        refresh_token=payload.get("refresh_token", ""),
        expires_at=_expires_at(payload),
        account_email=_account_email(payload.get("access_token", "")),
    )


def refresh(refresh_token: str) -> TokenBundle:
    """A fresh access token. Raises GoogleAccessRevokedError if the grant is gone."""
    payload = _post_token({
        "refresh_token": refresh_token,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "grant_type": "refresh_token",
    })
    return TokenBundle(
        access_token=payload.get("access_token", ""),
        # A refresh response does not resend the refresh token; the caller keeps
        # the one it used.
        refresh_token="",
        expires_at=_expires_at(payload),
    )


def _account_email(access_token: str) -> str:
    """Which Google account this is. Best-effort by design.

    Failing to read the display email must not fail the connection -- the
    calendar grant is the part that matters, and a connection labelled "Google
    Calendar" is far better than no connection at all.
    """
    if not access_token:
        return ""
    try:
        response = httpx.get(USERINFO_ENDPOINT, timeout=_TIMEOUT,
                             headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code < 400:
            return str(response.json().get("email", ""))
    except httpx.HTTPError:
        pass
    return ""


def revoke(token: str) -> None:
    """Ask Google to drop the grant on disconnect. Best-effort.

    We delete our own copy regardless: if this call fails, the founder has still
    disconnected as far as Ally is concerned, and leaving the row behind so the
    revocation could be retried would mean the UI keeps claiming a connection
    they just removed.
    """
    if not token:
        return
    try:
        httpx.post("https://oauth2.googleapis.com/revoke",
                   data={"token": token}, timeout=_TIMEOUT)
    except httpx.HTTPError:
        pass
