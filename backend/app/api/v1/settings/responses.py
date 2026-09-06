"""Response models for the settings-preferences endpoints (Phase 11).

Strongly-typed Pydantic boundary models with `from_domain` mappers -- the domain
dataclasses never touch the wire."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SecurityPrefsResponse(BaseModel):
    login_notifications: bool

    @classmethod
    def from_domain(cls, s) -> "SecurityPrefsResponse":
        return cls(login_notifications=s.login_notifications)


class SettingsPreferencesResponse(BaseModel):
    founder_id: int
    security: SecurityPrefsResponse
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, snapshot) -> "SettingsPreferencesResponse":
        return cls(
            founder_id=snapshot.founder_id,
            security=SecurityPrefsResponse.from_domain(snapshot.security),
            created_at=snapshot.created_at, updated_at=snapshot.updated_at,
        )
