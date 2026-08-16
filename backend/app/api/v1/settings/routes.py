"""Settings & notifications endpoints.

    GET  /settings                consolidated view (account + notifications + security)
    GET  /settings/account        account settings
    PATCH /settings/account       update account settings (preferred_language)
    GET  /settings/notifications  notification preferences
    PATCH /settings/notifications partial update (merges, doesn't replace)
    GET  /settings/security       security overview
    GET  /settings/privacy        list the founder's privacy / data-rights requests
    POST /settings/privacy        submit a new privacy request (queued for admin review)

Note on scope: **profile settings** live on `/profile` (name + the 13 fields), so
they are not duplicated here. **Password management** does not exist *here*:
founders do have a password, but Supabase owns it end to end, and a reset runs
through the same emailed-OTP flow as first sign-in rather than any endpoint of
ours. Credentials and 2FA stay with the identity provider, surfaced read-only
under /settings/security.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_founder_record
from app.core.auth import AuthUser, get_current_founder
from app.db.session import get_db
from app.models import Founder
from app.repositories import founder_repository, privacy_request_repository
from app.schemas.privacy import (
    PrivacyRequestCreate,
    PrivacyRequestListResponse,
    PrivacyRequestRead,
)
from app.schemas.settings import (
    AccountSettingsRead,
    AccountSettingsUpdate,
    NotificationPreferencesRead,
    NotificationPreferencesUpdate,
    SecurityRead,
    SettingsOverview,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _security(auth_user: AuthUser) -> SecurityRead:
    return SecurityRead(auth_provider=auth_user.provider)


def _notifications(founder: Founder) -> dict:
    return founder.notification_preferences or {}


# --- overview ---------------------------------------------------------------

@router.get("", response_model=SettingsOverview)
async def read_settings(
    founder: Founder = Depends(get_founder_record),
    auth_user: AuthUser = Depends(get_current_founder),
):
    return SettingsOverview(
        account=AccountSettingsRead.model_validate(founder),
        notifications=NotificationPreferencesRead.model_validate(_notifications(founder)),
        security=_security(auth_user),
    )


# --- account ----------------------------------------------------------------

@router.get("/account", response_model=AccountSettingsRead)
async def read_account(founder: Founder = Depends(get_founder_record)):
    return founder


@router.patch("/account", response_model=AccountSettingsRead)
async def update_account(
    payload: AccountSettingsUpdate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    return founder_repository.update(db, founder, payload.model_dump(exclude_unset=True))


# --- notification preferences ----------------------------------------------

@router.get("/notifications", response_model=NotificationPreferencesRead)
async def read_notifications(founder: Founder = Depends(get_founder_record)):
    return _notifications(founder)


@router.patch("/notifications", response_model=NotificationPreferencesRead)
async def update_notifications(
    payload: NotificationPreferencesUpdate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Merge the sent toggles into the stored preferences (never wipe the others)."""
    merged = dict(_notifications(founder))
    merged.update(payload.model_dump(exclude_unset=True))
    founder_repository.update(db, founder, {"notification_preferences": merged})
    return merged


# --- security ---------------------------------------------------------------

@router.get("/security", response_model=SecurityRead)
async def read_security(auth_user: AuthUser = Depends(get_current_founder)):
    """Social login only -- no password. Credentials are provider-managed."""
    return _security(auth_user)


# --- privacy center (data rights) ------------------------------------------

@router.post("/privacy", response_model=PrivacyRequestRead, status_code=status.HTTP_201_CREATED)
async def submit_privacy_request(
    payload: PrivacyRequestCreate,
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Queue a data-rights request for admin review.

    Allowed types (enforced by DB constraint): view_data, download_data,
    correct_data, withdraw_consent, restrict_processing, portability.
    The row is created with status='pending' and routed to admins for fulfilment.
    """
    return privacy_request_repository.submit(
        db,
        founder_id=founder.founder_id,
        request_type=payload.request_type,
        request_details=payload.request_details,
    )


@router.get("/privacy", response_model=PrivacyRequestListResponse)
async def list_privacy_requests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    founder: Founder = Depends(get_founder_record),
    db: Session = Depends(get_db),
):
    """Return all privacy/data-rights requests submitted by the signed-in founder."""
    items = privacy_request_repository.list_for_founder(
        db, founder.founder_id, limit=limit, offset=offset
    )
    total = privacy_request_repository.count_for_founder(db, founder.founder_id)
    return PrivacyRequestListResponse(items=items, total=total)
