"""Settings-preferences endpoints (Phase 11) -- additive, transport only.

Complements the existing `routes.py` (/settings, /account, /notifications,
/security) with the new preference sections that had no home before. Distinct paths
only -- no collision with the existing settings router. Every endpoint delegates to
SettingsService; no business logic here.

    GET   /settings/preferences   full settings (creates defaults on first access)
    PATCH /settings/reminders     partial reminder-preferences update
    PATCH /settings/security      partial app-security-preferences update
    POST  /settings/reset         reset to defaults
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_founder_record
from app.api.v1.settings.dependencies import get_settings_service
from app.api.v1.settings.preferences_schemas import RemindersUpdate, SecurityPrefsUpdate
from app.api.v1.settings.responses import (
    RemindersResponse,
    SecurityPrefsResponse,
    SettingsPreferencesResponse,
)
from app.models import Founder
from app.settings.service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/preferences", response_model=SettingsPreferencesResponse,
            summary="Get founder settings (reminders + security preferences)")
def get_preferences(
    founder: Founder = Depends(get_founder_record),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsPreferencesResponse:
    return SettingsPreferencesResponse.from_domain(service.get_settings(founder.founder_id))


@router.patch("/reminders", response_model=RemindersResponse,
              summary="Update reminder preferences (partial)")
def update_reminders(
    payload: RemindersUpdate,
    founder: Founder = Depends(get_founder_record),
    service: SettingsService = Depends(get_settings_service),
) -> RemindersResponse:
    snapshot = service.update_reminders(founder.founder_id, **payload.model_dump(exclude_unset=True))
    return RemindersResponse.from_domain(snapshot.reminders)


@router.patch("/security", response_model=SecurityPrefsResponse,
              summary="Update app-level security preferences (partial)")
def update_security(
    payload: SecurityPrefsUpdate,
    founder: Founder = Depends(get_founder_record),
    service: SettingsService = Depends(get_settings_service),
) -> SecurityPrefsResponse:
    snapshot = service.update_security(founder.founder_id, **payload.model_dump(exclude_unset=True))
    return SecurityPrefsResponse.from_domain(snapshot.security)


@router.post("/reset", response_model=SettingsPreferencesResponse,
             summary="Reset founder settings to defaults")
def reset_settings(
    founder: Founder = Depends(get_founder_record),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsPreferencesResponse:
    return SettingsPreferencesResponse.from_domain(service.reset_defaults(founder.founder_id))
