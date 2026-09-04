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
    AccountSuspendedError,
    AuthError,
    AuthUser,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_auth_provider,
    get_current_founder,
    get_session_store,
    get_upstream_identity,
    identity_from_claims,
    is_account_active,
    record_last_active,
)
from app.core.config import settings
from app.db.session import get_db
from app.middleware.rate_limit import ip_rate_limit
from app.schemas.auth import (
    AuthStatus,
    IdentityOut,
    LogoutRequest,
    RefreshRequest,
    SessionResponse,
    TokenPair,
)
from app.services.provisioning import ensure_founder_with_status

router = APIRouter(prefix="/auth", tags=["auth"])

# Scoped to /api/v1/auth, not "/" -- the cookie only needs to ride on calls
# this router actually reads it from (refresh/resume/logout). A wider scope
# would mean the browser attaches it to every single API request for no
# benefit, the opposite of least-privilege for a long-lived credential.
_COOKIE_PATH = "/api/v1/auth"

# Named module-level dependency objects, not inline Depends(ip_rate_limit(...))
# calls -- FastAPI's dependency_overrides keys by the exact callable object
# passed to Depends(), and a factory call produces a fresh closure every
# time. Naming these lets a test override them (same pattern as chat_gate /
# message_rate_limit) if a suite ever needs to exceed these limits within a
# single run.
session_rate_limit = ip_rate_limit(key="auth-session", limit=20, window_seconds=60)
refresh_rate_limit = ip_rate_limit(key="auth-refresh", limit=30, window_seconds=60)
resume_rate_limit = ip_rate_limit(key="auth-resume", limit=30, window_seconds=60)


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


@router.post(
    "/session",
    response_model=SessionResponse,
    dependencies=[Depends(session_rate_limit)],
)
async def start_session(
    request: Request,
    response: Response,
    identity: AuthUser = Depends(get_upstream_identity),
    db: Session = Depends(get_db),
):
    """Exchange a verified Google/LinkedIn (Supabase) token for backend tokens.

    On a real first login this also creates the founder row (provisioning); on
    later logins it just finds it. Send the Supabase access token as the bearer
    token. In dev mode, send any id as the bearer token (or none for the default
    dev founder) -- dev identities are not provisioned.
    """
    ip = request.client.host if request.client else "0.0.0.0"
    founder, created = ensure_founder_with_status(identity, db, ip_address=ip)

    pair, refresh_token = _token_pair(identity)
    _set_refresh_cookie(response, refresh_token)
    return SessionResponse(
        **pair.model_dump(),
        # The founder ROW's email, not the upstream identity's. In dev mode the
        # identity carries a synthesised "<uuid>@ally.local" address, so echoing
        # it reported a fake email for a founder whose real one was sitting in
        # the row this call had just loaded. The frontend happened to survive
        # that by re-fetching /profile; anything trusting this response did not.
        founder=IdentityOut(
            id=identity.id,
            email=(founder.email if founder is not None else None) or identity.email,
            provider=identity.provider,
        ),
        # Whether this call CREATED the row -- not whether one exists. The old
        # `founder is not None` reported true for every returning login, and for
        # dev identities that provisioning explicitly never touches.
        provisioned=created,
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    dependencies=[Depends(refresh_rate_limit)],
)
async def refresh_session(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    """Trade a valid, non-revoked refresh token for a fresh token pair.

    The old refresh token is revoked as part of this call (rotation), so a
    refresh token works exactly once. Also refuses a suspended/banned founder
    here, not just on their next API call -- a suspended founder should not be
    able to mint a fresh access token at all, even one that would immediately
    403 on first use.
    """
    token = _incoming_refresh_token(request, payload)
    claims = decode_token(token, REFRESH)

    store = get_session_store(db)
    if store.is_revoked(claims["jti"]):
        raise AuthError("Refresh token has been revoked")
    if not is_account_active(db, claims["sub"]):
        raise AccountSuspendedError()
    record_last_active(db, claims["sub"])

    store.revoke(claims["jti"], expires_at=_claim_expiry(claims))
    pair, new_refresh_token = _token_pair(identity_from_claims(claims))
    _set_refresh_cookie(response, new_refresh_token)
    return pair


@router.post(
    "/resume",
    response_model=SessionResponse,
    dependencies=[Depends(resume_rate_limit)],
)
async def resume_session(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    """Restore a session on app reload from a stored refresh token.

    Like /session, but the starting point is our refresh token rather than a
    fresh Google/LinkedIn login -- so a returning user who still holds a valid
    refresh token is brought back in without bouncing through the provider. The
    refresh token is rotated (the old one is revoked), and the caller gets a new
    pair plus their identity, ready to rehydrate the UI.

    Differs from /refresh, which only swaps tokens and returns no identity.
    """
    token = _incoming_refresh_token(request, payload)
    claims = decode_token(token, REFRESH)

    store = get_session_store(db)
    if store.is_revoked(claims["jti"]):
        raise AuthError("Session has ended; please log in again")
    if not is_account_active(db, claims["sub"]):
        raise AccountSuspendedError()
    record_last_active(db, claims["sub"])

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
