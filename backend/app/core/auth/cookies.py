"""How the refresh token travels: an httpOnly cookie, not a JSON field.

The refresh token is the long-lived credential -- 30 days by default, enough to
mint access tokens for that whole window. Held in localStorage it is readable by
any script that reaches the page; held in an httpOnly cookie it is invisible to
JavaScript entirely. XSS can still ride the current session, but it cannot walk
off with a month of it.

The cookie is scoped to /api/v1/auth, so it is attached to the four endpoints
that actually need it (session, refresh, resume, logout) and to no other API
call.
"""

from fastapi import Request, Response

from app.core.config import settings

COOKIE_NAME = "ally_refresh"
COOKIE_PATH = "/api/v1/auth"


def _cookie_attrs() -> dict:
    """Attributes shared by set and delete.

    They must match exactly: a delete_cookie whose path or flags differ from the
    set_cookie is a different cookie to the browser, and the original one stays
    put -- a logout that doesn't log you out.
    """
    return {
        "path": COOKIE_PATH,
        "httponly": True,
        # Secure makes the cookie undeliverable over plain http, which is what
        # local development runs on -- so it is on everywhere else.
        "secure": settings.ENVIRONMENT != "development",
        # The SPA and this API are served from the same site (/api/v1 is a
        # rewrite, not a separate origin), so Lax is sufficient and keeps the
        # cookie off cross-site requests.
        "samesite": "lax",
    }


def set_refresh_cookie(response: Response, token: str) -> None:
    """Hand the browser a rotated refresh token."""
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        **_cookie_attrs(),
    )


def clear_refresh_cookie(response: Response) -> None:
    """Drop the cookie. Pair every revocation with this."""
    response.delete_cookie(COOKIE_NAME, **_cookie_attrs())


def read_refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(COOKIE_NAME)
