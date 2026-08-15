"""POST /frontend-errors -- the sink for uncaught frontend errors.

Public-tolerant on purpose: an error can happen before login (the landing
page, a broken auth handshake), and those are exactly the reports most worth
seeing, not the ones to 401 away. `optional_founder_id` resolves the caller's
identity when a valid token is present and returns None otherwise -- this
route never rejects a report for lacking one.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth.tokens import ACCESS, decode_token, identity_from_claims
from app.core.logger import logger
from app.db.session import get_db
from app.repositories import founder_repository

router = APIRouter(prefix="/frontend-errors", tags=["frontend-errors"])

# auto_error=False: a missing/invalid token here is not a rejection, it just
# means the report is attributed to no one. A dedicated (not shared) instance
# so a change to the main auth bearer scheme's error behaviour can never
# accidentally start 401ing this endpoint.
_bearer = HTTPBearer(auto_error=False, description="Bearer token (optional)")


class FrontendErrorReport(BaseModel):
    # Every field is length-capped: this is a telemetry sink, not a general
    # upload endpoint, and a cap bounds both storage and what a single bad
    # actor (or a genuinely huge stack trace) can push through it.
    message: str = Field(..., max_length=2000)
    stack: str | None = Field(None, max_length=4000)
    component_stack: str | None = Field(None, max_length=4000)
    url: str = Field(..., max_length=500)
    user_agent: str | None = Field(None, max_length=300)
    # 'error_boundary' (React render error) | 'window_error' | 'unhandled_rejection'
    source: str = Field("unknown", max_length=50)
    event_id: str | None = Field(None, max_length=100)


def optional_founder_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> int | None:
    if credentials is None:
        return None
    try:
        claims = decode_token(credentials.credentials, ACCESS)
        auth_user = identity_from_claims(claims)
        user_uuid = UUID(str(auth_user.id))
    except Exception:  # noqa: BLE001 -- any failure here means "unknown caller", not an error
        return None
    founder = founder_repository.get_by_user_id(db, user_uuid)
    return founder.founder_id if founder else None


@router.post("", status_code=status.HTTP_202_ACCEPTED, summary="Report an uncaught frontend error")
def report_frontend_error(
    payload: FrontendErrorReport,
    request: Request,
    founder_id: int | None = Depends(optional_founder_id),
) -> dict:
    logger.error(
        "frontend error reported",
        extra={
            "fe_source": payload.source,
            "fe_message": payload.message,
            "fe_stack": payload.stack,
            "fe_component_stack": payload.component_stack,
            "fe_url": payload.url,
            "fe_user_agent": payload.user_agent,
            "fe_event_id": payload.event_id,
            "founder_id": founder_id,
            "request_id": getattr(request.state, "request_id", None),
        },
    )
    # 202: accepted for logging, not "processed" in any stronger sense -- this
    # is fire-and-forget telemetry, there is nothing here for the caller to
    # wait on or retry against.
    return {"received": True}
