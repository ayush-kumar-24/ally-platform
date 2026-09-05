"""Privacy Center endpoints -- additive, transport only.

    GET    /privacy/export     download everything we hold (Art 15 + 20)
    GET    /privacy/summary    counts per category -- lighter than a full export
    DELETE /privacy/account    schedule account erasure (Art 17)
    POST   /privacy/withdraw   withdraw consent, pause processing (Art 7(3))
    POST   /privacy/restrict   restrict / resume processing (Art 18)
    GET    /privacy/status     current standing + request history

Every endpoint delegates to PrivacyService; no business logic here.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api.v1.privacy.dependencies import get_current_founder_id, get_privacy_service
from app.api.v1.privacy.responses import (
    DataSummaryResponse,
    ExportResponse,
    PrivacyActionResponse,
    PrivacyActionResult,
    PrivacyStateResponse,
)
from app.api.v1.privacy.schemas import ConfirmRequest, RestrictRequest
from app.privacy.errors import PrivacyError
from app.privacy.service import DELETION_GRACE_DAYS, PrivacyService

router = APIRouter(prefix="/privacy", tags=["privacy"])


class ConfirmationRequiredError(PrivacyError):
    def __init__(self, action: str):
        super().__init__(f"This {action} must be confirmed explicitly.", status_code=422)


@router.get("/export", response_model=ExportResponse,
            summary="Download your data -- everything held (access), or only what you provided (portability)")
def export_data(
    kind: Literal["access", "portability"] = Query(
        "access",
        description=("access: everything Ally holds, including its own analysis of you. "
                     "portability: only the data you provided, for taking to another service."),
    ),
    founder_id: int = Depends(get_current_founder_id),
    service: PrivacyService = Depends(get_privacy_service),
) -> ExportResponse:
    bundle, action = service.export_data(founder_id, kind=kind)
    return ExportResponse.from_domain(bundle, action)


@router.get("/summary", response_model=DataSummaryResponse,
            summary="See what data Ally holds about you, by category (no full export)")
def data_summary(
    founder_id: int = Depends(get_current_founder_id),
    service: PrivacyService = Depends(get_privacy_service),
) -> DataSummaryResponse:
    summary, action = service.data_summary(founder_id)
    return DataSummaryResponse.from_domain(summary, action)


@router.delete("/account", response_model=PrivacyActionResult,
               summary="Request erasure of your account (scheduled, with a recovery window)")
def delete_account(
    payload: ConfirmRequest,
    founder_id: int = Depends(get_current_founder_id),
    service: PrivacyService = Depends(get_privacy_service),
) -> PrivacyActionResult:
    if not payload.confirm:
        raise ConfirmationRequiredError("account deletion")
    state, action = service.request_account_deletion(founder_id)
    return PrivacyActionResult(
        state=PrivacyStateResponse.from_domain(state),
        request=PrivacyActionResponse.from_domain(action),
        message=(f"Account deletion scheduled for {state.deletion_scheduled_at:%d %b %Y}. "
                 f"You have {DELETION_GRACE_DAYS} days to change your mind -- sign in again "
                 f"before then and you can cancel it yourself."),
    )


@router.post("/account/cancel-deletion", response_model=PrivacyActionResult,
             summary="Cancel a scheduled account deletion (inside the grace window)")
def cancel_account_deletion(
    founder_id: int = Depends(get_current_founder_id),
    service: PrivacyService = Depends(get_privacy_service),
) -> PrivacyActionResult:
    """Founder-initiated undo of their own erasure request.

    Deliberately NOT behind a confirm flag, unlike DELETE /account: keeping an
    account is the safe direction, and the founder has already confirmed intent
    by answering the prompt the app shows them on the way in. The destructive
    direction is the one that needs a gate, not the recovery.
    """
    state, action = service.cancel_account_deletion(founder_id)
    return PrivacyActionResult(
        state=PrivacyStateResponse.from_domain(state),
        request=PrivacyActionResponse.from_domain(action),
        message="Your account deletion has been cancelled. Everything is exactly where you left it.",
    )


@router.post("/withdraw", response_model=PrivacyActionResult,
             summary="Withdraw consent and pause AI processing")
def withdraw_consent(
    payload: ConfirmRequest,
    founder_id: int = Depends(get_current_founder_id),
    service: PrivacyService = Depends(get_privacy_service),
) -> PrivacyActionResult:
    if not payload.confirm:
        raise ConfirmationRequiredError("consent withdrawal")
    state, action = service.withdraw_consent(founder_id)
    return PrivacyActionResult(
        state=PrivacyStateResponse.from_domain(state),
        request=PrivacyActionResponse.from_domain(action),
        message="Consent withdrawn. AI processing is paused; your account remains active.",
    )


@router.post("/restrict", response_model=PrivacyActionResult,
             summary="Restrict (or resume) processing of your data")
def restrict_processing(
    payload: RestrictRequest,
    founder_id: int = Depends(get_current_founder_id),
    service: PrivacyService = Depends(get_privacy_service),
) -> PrivacyActionResult:
    state, action = service.restrict_processing(founder_id, restricted=payload.restricted)
    return PrivacyActionResult(
        state=PrivacyStateResponse.from_domain(state),
        request=PrivacyActionResponse.from_domain(action),
        message=("Processing restricted. Ally will not generate new insights until you resume."
                 if payload.restricted else "Restriction lifted. Ally will resume processing."),
    )


@router.get("/status", response_model=dict,
            summary="Your current privacy standing and request history")
def read_status(
    founder_id: int = Depends(get_current_founder_id),
    service: PrivacyService = Depends(get_privacy_service),
) -> dict:
    state = service.get_state(founder_id)
    requests = service.list_requests(founder_id)
    return {
        "state": PrivacyStateResponse.from_domain(state).model_dump(mode="json"),
        "requests": [PrivacyActionResponse.from_domain(r).model_dump(mode="json") for r in requests],
        "total": len(requests),
    }
