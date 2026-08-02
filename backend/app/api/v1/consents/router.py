"""Consent endpoints -- additive, transport only.

    POST /consents   record a consent (idempotent: 201 created / 200 unchanged)
    GET  /consents   current consent + full history + whether re-consent is due

Every endpoint delegates to ConsentService; no business logic here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.consents.dependencies import get_consent_service, get_current_founder_id
from app.api.v1.consents.responses import ConsentResponse, ConsentStatusResponse
from app.api.v1.consents.schemas import ConsentCreate
from app.consents.defaults import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
from app.consents.service import ConsentService

router = APIRouter(prefix="/consents", tags=["consents"])


@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED,
             summary="Record the founder's consent (Terms + Privacy, and the optional diagnosis opt-in)")
def create_consent(
    payload: ConsentCreate,
    response: Response,
    founder_id: int = Depends(get_current_founder_id),
    service: ConsentService = Depends(get_consent_service),
) -> ConsentResponse:
    """Append a consent record.

    Idempotent by design: re-posting a consent identical to the founder's current
    one returns 200 with the existing record instead of appending a duplicate, so a
    double-click or a retried request cannot pollute the ledger. A genuine *change*
    (e.g. turning the diagnosis opt-in off) is always appended and returns 201.
    """
    record, created = service.record_consent(
        founder_id,
        terms_version=payload.terms_version,
        privacy_version=payload.privacy_version,
        agree_terms=payload.agree_terms,
        agree_diagnosis=payload.agree_diagnosis,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return ConsentResponse.from_domain(record)


@router.get("", response_model=ConsentStatusResponse,
            summary="Get the founder's current consent and its full history")
def read_consents(
    founder_id: int = Depends(get_current_founder_id),
    service: ConsentService = Depends(get_consent_service),
) -> ConsentStatusResponse:
    current = service.get_current(founder_id)
    history = service.list_history(founder_id)
    return ConsentStatusResponse(
        has_consented=current is not None,
        needs_reconsent=service.needs_reconsent(founder_id),
        current_terms_version=CURRENT_TERMS_VERSION,
        current_privacy_version=CURRENT_PRIVACY_VERSION,
        current=ConsentResponse.from_domain(current) if current else None,
        history=[ConsentResponse.from_domain(r) for r in history],
        total=len(history),
    )
