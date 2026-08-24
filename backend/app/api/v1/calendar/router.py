"""Calendar connection endpoints.

    GET    /calendar/status       is a calendar connected, and to which account
    POST   /calendar/connect      begin the Google consent flow
    GET    /calendar/callback     Google redirects the BROWSER here (no auth header)
    DELETE /calendar/connection   forget the connection

Connecting a calendar is deliberately its own step, unrelated to signing in:
Ally's login is email-only, so there is no Google token lying around to reuse,
and a founder can use Ally forever without ever connecting one.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.v1.calendar.schemas import (
    CalendarConnectStart,
    CalendarStatusResponse,
    DisconnectResult,
)
from app.api.deps import get_founder_record
from app.api.v1.planning.dependencies import get_current_founder_id
from app.calendar_sync import connections, crypto, google_oauth, state
from app.calendar_sync.db_models import STATUS_ACTIVE
from app.core.config import settings
from app.core.logger import logger
from app.models import Founder
from app.db.session import get_db, set_founder_rls_context

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _return_url(outcome: str, detail: str = "") -> str:
    """Back to Plan Your Day, carrying the outcome for the page to announce.

    The callback is a top-level browser navigation, so the only way to tell the
    founder what happened is the URL they land on. PUBLIC_APP_URL when set --
    behind the proxy the request's own origin is the API host, and bouncing
    someone to api.goxlally.ai/app/plan would 404 at the end of a flow that
    otherwise worked.
    """
    from urllib.parse import urlencode

    base = (settings.PUBLIC_APP_URL or "").strip().rstrip("/")
    params = {"calendar": outcome}
    if detail:
        params["detail"] = detail[:200]
    return f"{base}/app/plan?{urlencode(params)}"


@router.get("/status", response_model=CalendarStatusResponse,
            summary="Whether a calendar is connected, and to which account")
def calendar_status(founder_id: int = Depends(get_current_founder_id),
                    db: Session = Depends(get_db)) -> CalendarStatusResponse:
    row = connections.get_connection(db, founder_id)
    return CalendarStatusResponse(
        connected=row is not None and row.status == STATUS_ACTIVE,
        provider=row.provider if row else "google",
        account_email=row.account_email if row else "",
        status=row.status if row else "disconnected",
        # Surfaced so the page can say "reconnect" instead of a bare "connect"
        # when a grant was revoked from Google's side.
        needs_reconnect=row is not None and row.status != STATUS_ACTIVE,
        last_error=row.last_error if row else "",
        # Lets the UI hide the button entirely rather than offering a flow that
        # can only fail on a deploy where the OAuth client was never configured.
        available=google_oauth.is_configured() and crypto.is_available(),
    )


@router.post("/connect", response_model=CalendarConnectStart,
             summary="Start connecting a Google Calendar")
def start_connect(founder: Founder = Depends(get_founder_record)) -> CalendarConnectStart:
    """Hand back the Google consent URL for the browser to visit.

    Both preconditions are checked HERE rather than at the callback. Discovering
    a missing encryption key after the founder has already granted Google access
    is the worst possible moment: they have given real permission and we would
    have to throw it away.
    """
    if not google_oauth.is_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Calendar sync isn't set up on this deployment yet.")
    if not crypto.is_available():
        # Deliberately vague to the founder, loud in the log: the fix is an
        # env var, and naming it in an HTTP body tells them nothing useful.
        logger.error("calendar connect blocked: CALENDAR_TOKEN_KEY missing or invalid")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Calendar sync isn't set up on this deployment yet.")

    # The auth UUID rides along in the signed state because the callback needs it
    # to re-establish RLS context -- see state.issue() and the callback below.
    return CalendarConnectStart(
        authorization_url=google_oauth.authorization_url(
            state.issue(founder.founder_id, str(founder.user_id))))


@router.get("/callback", include_in_schema=False)
def oauth_callback(code: str | None = Query(default=None),
                   state_token: str | None = Query(default=None, alias="state"),
                   error: str | None = Query(default=None),
                   db: Session = Depends(get_db)) -> RedirectResponse:
    """Where Google sends the founder's browser after the consent screen.

    No authentication dependency, by necessity -- this is a redirect, not an API
    call, and carries no Authorization header. The signed `state` is what
    identifies the founder, and it is the only thing that does; see
    app/calendar_sync/state.py.

    Always redirects, never returns JSON. The founder is looking at a browser
    tab, and a raw error body at the end of an OAuth flow reads as a crash.
    """
    if error:
        # Most often access_denied -- they pressed Cancel. Not a failure worth
        # alarming them about.
        return RedirectResponse(_return_url("cancelled"), status_code=303)

    try:
        founder_id, founder_uuid = state.read(state_token)
    except state.InvalidOAuthStateError as exc:
        logger.warning("calendar oauth callback with bad state", exc_info=exc)
        return RedirectResponse(_return_url("error", "Link expired — please try again."),
                                status_code=303)

    if not code:
        return RedirectResponse(_return_url("error", "Google sent no authorization code."),
                                status_code=303)

    try:
        bundle = google_oauth.exchange_code(code)
    except google_oauth.GoogleOAuthError as exc:
        logger.warning("calendar oauth code exchange failed",
                       extra={"founder_id": founder_id}, exc_info=exc)
        return RedirectResponse(_return_url("error", "Google refused the connection."),
                                status_code=303)

    if not bundle.access_token:
        return RedirectResponse(_return_url("error", "Google returned no access token."),
                                status_code=303)

    try:
        # THE reason this endpoint could not write. Every other founder-scoped
        # write reaches the database through get_founder_record, which sets
        # `app.current_founder_uuid` -- the value the founder RLS policies check.
        # This endpoint has no auth dependency by necessity (Google redirects a
        # browser here with no Authorization header), so nothing established that
        # context and the INSERT was refused by RLS while the SELECT on /status
        # merely returned zero rows. Hence "not connected", then "could not save".
        set_founder_rls_context(db, founder_uuid)
        connections.save_connection(db, founder_id, bundle)
    except Exception as exc:
        logger.error("calendar connection could not be stored",
                     extra={"founder_id": founder_id}, exc_info=exc)
        return RedirectResponse(_return_url("error", "Could not save the connection."),
                                status_code=303)

    return RedirectResponse(_return_url("connected"), status_code=303)


@router.delete("/connection", response_model=DisconnectResult,
               summary="Disconnect the calendar")
def disconnect(founder_id: int = Depends(get_current_founder_id),
               db: Session = Depends(get_db)) -> DisconnectResult:
    """Forget the connection. Events Ally already created stay on the calendar.

    Team decision (2026-08-22). Bulk-deleting real calendar entries is
    unrecoverable, and if the disconnect was a mis-click it destroys a week
    somebody may have planned around. The message says so plainly rather than
    leaving them to wonder.
    """
    removed = connections.disconnect(db, founder_id)
    return DisconnectResult(
        disconnected=removed,
        message=("Calendar disconnected. Events Ally already added stay on your "
                 "calendar — remove them there if you'd like them gone."
                 if removed else "No calendar was connected."),
    )
