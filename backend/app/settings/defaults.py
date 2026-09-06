"""Sensible defaults for a founder's settings (Part 3)."""

from __future__ import annotations

from datetime import datetime

from app.settings.schemas import SecurityPreferences, SettingsSnapshot


def default_security() -> SecurityPreferences:
    return SecurityPreferences(
        login_notifications=True,
    )


def default_settings(founder_id: int, now: datetime) -> SettingsSnapshot:
    return SettingsSnapshot(
        founder_id=founder_id, security=default_security(),
        created_at=now, updated_at=now,
    )
