"""Authentication endpoints.

Flow (email as the login id; an emailed OTP on first use, a password after):

    1. Frontend signs the founder in with Supabase -- either by verifying a
       6-digit code mailed to their address (first login, or a forgotten
       password, after which they choose a password) or with that password on
       every later visit. Either way it ends up holding a Supabase access token.
    2. Frontend calls POST /auth/session with that token. The backend verifies it
       once, then issues its OWN access + refresh tokens.
    3. Every later request carries our access token.
    4. POST /auth/refresh trades a refresh token for a new access token.
    5. POST /auth/logout revokes a refresh token.

Nothing below step 1 knows or cares which of those two doors was used: the token
is verified by signature, so OTP, password and (were it re-enabled) OAuth are
indistinguishable here. Passwords are Supabase's to store and check -- this
backend never sees, hashes or transports one.

Why the backend issues its own tokens: the rest of the API never depends on the
provider's token format, so moving to AWS Cognito later changes only step 1.

Refresh-token delivery: an HttpOnly cookie (ally_refresh_token), not the JSON
body. It used to be returned in the body alongside the access token, which
meant a browser client's only place to keep it was localStorage -- readable
by any script on the page. /session and /resume now set the cookie directly;
/refresh, /resume and /logout read it from there first (a body field is
still accepted as a fallback for a non-cookie-capable caller, but nothing in
this codebase's own frontend should ever populate it -- see REFRESH_COOKIE_*
in core/config.py for the cookie attributes and why each is set the way it is).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.auth import (
    ACCESS,
    REFRESH,
    AuthError,
    AuthUser,
    clear_refresh_cookie,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_auth_provider,
    get_current_founder,
    get_session_store,
    get_upstream_identity,
    identity_from_claims,
    read_refresh_cookie,
    set_refresh_cookie,
)
from app.core.config import settings
from app.db.session import get_db
from app.schemas.auth import (
    AuthStatus,
    IdentityOut,
    LogoutRequest,
    RefreshRequest,
    SessionResponse,
    TokenPair,
)
from app.services.provisioning import ensure_founder

router = APIRouter(prefix="/auth", tags=["auth"])

# Scoped to /api/v1/auth, not "/" -- the cookie only needs to ride on calls
# this router actually reads it from (refresh/resume/logout). A wider scope
# would mean the browser attaches it to every single API request for no
# benefit, the opposite of least-privilege for a long-lived credential.
_COOKIE_PATH = "/api/v1/auth"


def _claim_expiry(claims: dict) -> datetime | None:
    """The token's own `exp` claim as a datetime, for SqlSessionStore's pruning --
    a revoked row is useless once the token it revokes would have expired anyway."""
    exp = claims.get("exp")
    return datetime.fromtimestamp(exp, tz=timezone.utc) if exp is not None else None


def _token_pair(identity: AuthUser) -> tuple[TokenPair, str]:
    """Returns the response body (refresh_token always None in it -- see
    TokenPair's own docstring) and the raw refresh token separately, so the
    caller can set the cookie without the value ever touching the body."""
    access, _ = create_access_token(identity)
    refresh, _ = create_refresh_token(identity)
    pair = TokenPair(
        access_token=access,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return pair, refresh


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        domain=settings.REFRESH_COOKIE_DOMAIN or None,
        path=_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        domain=settings.REFRESH_COOKIE_DOMAIN or None,
        path=_COOKIE_PATH,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        secure=settings.REFRESH_COOKIE_SECURE,
    )


def _incoming_refresh_token(request: Request, payload) -> str:
    """Cookie first, body second. A browser client that's correctly wired
    never sends the body field at all; the fallback exists for a caller
    that genuinely cannot use a cookie jar, not as a way to route around
    the cookie for a client that could."""
    token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if token:
        return token
    if payload is not None and payload.refresh_token:
        return payload.refresh_token
    raise AuthError("No refresh token provided")


@router.post("/session", response_model=SessionResponse)
async def start_session(
    request: Request,
    response: Response,
    identity: AuthUser = Depends(get_upstream_identity),
    db: Session = Depends(get_db),
):
    """Exchange a verified Supabase token for backend tokens.

    On a real first login this also creates the founder row (provisioning); on
    later logins it just finds it. Send the Supabase access token as the bearer
    token. In dev mode, send any id as the bearer token (or none for the default
    dev founder) -- dev identities are not provisioned.
    """
    ip = request.client.host if request.client else "0.0.0.0"
    founder = ensure_founder(identity, db, ip_address=ip)

    pair, refresh_token = _token_pair(identity)
    _set_refresh_cookie(response, refresh_token)
    return SessionResponse(
        **pair.model_dump(),
        founder=IdentityOut(id=identity.id, email=identity.email, provider=identity.provider),
        provisioned=founder is not None,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh_session(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    """Trade a valid, non-revoked refresh token for a fresh token pair.

    Reads the token from the httpOnly cookie, or from the body for callers that
    don't have one. The old refresh token is revoked as part of this call
    (rotation), so a refresh token works exactly once -- which is also why the
    cookie is re-set here with the new one.
    """
    token = _incoming_refresh_token(request, payload)
    claims = decode_token(token, REFRESH)

    store = get_session_store(db)
    if store.is_revoked(claims["jti"]):
        raise AuthError("Refresh token has been revoked")

    store.revoke(claims["jti"], expires_at=_claim_expiry(claims))
    pair, new_refresh_token = _token_pair(identity_from_claims(claims))
    _set_refresh_cookie(response, new_refresh_token)
    return pair


@router.post("/resume", response_model=SessionResponse)
async def resume_session(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    """Restore a session on app reload from a stored refresh token.

    Like /session, but the starting point is our refresh token rather than a
    fresh Supabase login -- so a returning user who still holds a valid refresh
    token is brought back in without retyping their password. The
    refresh token is rotated (the old one is revoked), and the caller gets a new
    pair plus their identity, ready to rehydrate the UI.

    Differs from /refresh, which only swaps tokens and returns no identity.
    """
    token = _incoming_refresh_token(request, payload)
    claims = decode_token(token, REFRESH)

    store = get_session_store(db)
    if store.is_revoked(claims["jti"]):
        raise AuthError("Session has ended; please log in again")

    store.revoke(claims["jti"], expires_at=_claim_expiry(claims))
    identity = identity_from_claims(claims)
    pair, new_refresh_token = _token_pair(identity)
    _set_refresh_cookie(response, new_refresh_token)
    return SessionResponse(
        **pair.model_dump(),
        founder=IdentityOut(id=identity.id, email=identity.email, provider=identity.provider),
        provisioned=False,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    payload: LogoutRequest | None = None,
    db: Session = Depends(get_db),
):
    """Revoke a refresh token. The client should also discard its access token.

    Access tokens are short-lived and not individually tracked, so they remain
    valid until they expire -- keep their lifetime short. Revoking the refresh
    token is what actually ends the session.

    Always succeeds: the cookie is cleared first, and a token that is missing or
    no longer decodes has nothing left to revoke. Answering 401 here would leave
    the browser holding the very cookie it asked us to get rid of -- a logout
    that doesn't log you out, with no way for the client to recover.
    """
    token = _incoming_refresh_token(request, payload)
    claims = decode_token(token, REFRESH)
    get_session_store(db).revoke(claims["jti"], expires_at=_claim_expiry(claims))
    _clear_refresh_cookie(response)
    return {"detail": "logged out"}


@router.get("/me", response_model=IdentityOut)
async def read_current_founder(founder: AuthUser = Depends(get_current_founder)):
    """Who am I, according to the access token I sent."""
    return IdentityOut(id=founder.id, email=founder.email, provider=founder.provider)


@router.get("/status", response_model=AuthStatus)
async def read_auth_status():
    """Non-protected: how auth is configured. Works before you have any token."""
    return AuthStatus(
        provider=get_auth_provider().name,
        token_model="backend-issued session tokens",
        access_token_ttl_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token_ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        provisioning_enabled=settings.ENABLE_FOUNDER_PROVISIONING,
    )
