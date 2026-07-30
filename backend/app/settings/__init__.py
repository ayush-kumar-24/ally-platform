"""Founder Settings module (Phase 11) -- database-backed, repository-driven.

Extends the existing social-login settings surface additively. It owns ONLY the
settings that had no home before:
  * reminder preferences (daily/task/meeting/goal reminders + reminder time)
  * app-level security preferences (session timeout, login notifications)

Deliberately NOT duplicated here (they keep their existing homes):
  * profile          -> /profile (name + fields)
  * account           -> founders table (email/phone/country/company)
  * notifications     -> founders.notification_preferences (JSONB) + /settings/notifications
  * password / 2FA    -> owned by the identity provider (Google/LinkedIn via Supabase),
                          surfaced read-only under /settings/security

The service is deterministic and repository-driven, so it is testable fully offline
(in-memory repo) while production uses the SQLAlchemy repo + `founder_settings` table.
"""

from app.settings.defaults import (
    DEFAULT_REMINDER_TIME,
    DEFAULT_SESSION_TIMEOUT_MINUTES,
    default_settings,
)
from app.settings.errors import InvalidSettingError, SettingsError, SettingsNotFoundError
from app.settings.repository import (
    InMemorySettingsRepository,
    SettingsRepository,
    SqlAlchemySettingsRepository,
)
from app.settings.schemas import (
    ReminderPreferences,
    SecurityPreferences,
    SettingsSnapshot,
)
from app.settings.service import SettingsService, build_settings_service

__all__ = [
    "SettingsSnapshot",
    "ReminderPreferences",
    "SecurityPreferences",
    "SettingsRepository",
    "InMemorySettingsRepository",
    "SqlAlchemySettingsRepository",
    "SettingsService",
    "build_settings_service",
    "default_settings",
    "DEFAULT_REMINDER_TIME",
    "DEFAULT_SESSION_TIMEOUT_MINUTES",
    "SettingsError",
    "InvalidSettingError",
    "SettingsNotFoundError",
]
