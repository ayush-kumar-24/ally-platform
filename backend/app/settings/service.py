"""SettingsService (Part 5).

Repository-driven, deterministic (injected clock). Creates defaults on first access,
loads settings, applies partial section updates (only the fields sent change), and
resets to defaults. All business logic lives here -- the API only maps HTTP to these
calls. Fails closed on invalid values via the validators.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable

from app.settings.defaults import default_settings
from app.settings.repository import SettingsRepository
from app.settings.schemas import ReminderPreferences, SecurityPreferences, SettingsSnapshot
from app.settings.validators import validate_reminder_time, validate_session_timeout


class SettingsService:
    def __init__(self, repository: SettingsRepository, *, now: Callable[[], datetime] | None = None):
        self.repository = repository
        self._now = now or (lambda: datetime.now(timezone.utc))

    # --- load / create-default -------------------------------------------

    def get_settings(self, founder_id: int) -> SettingsSnapshot:
        """Load a founder's settings, creating the defaults row on first access."""
        existing = self.repository.get(founder_id)
        if existing is not None:
            return existing
        return self.repository.create(default_settings(founder_id, self._now()))

    # --- partial section updates -----------------------------------------

    def update_reminders(
        self, founder_id: int, *, daily_reminders: bool | None = None,
        reminder_time: str | None = None, task_reminders: bool | None = None,
        meeting_reminders: bool | None = None, goal_reminders: bool | None = None,
    ) -> SettingsSnapshot:
        if reminder_time is not None:
            validate_reminder_time(reminder_time)
        current = self.get_settings(founder_id)
        r = current.reminders
        new_reminders = ReminderPreferences(
            daily_reminders=r.daily_reminders if daily_reminders is None else daily_reminders,
            reminder_time=r.reminder_time if reminder_time is None else reminder_time,
            task_reminders=r.task_reminders if task_reminders is None else task_reminders,
            meeting_reminders=r.meeting_reminders if meeting_reminders is None else meeting_reminders,
            goal_reminders=r.goal_reminders if goal_reminders is None else goal_reminders,
        )
        return self._save(replace(current, reminders=new_reminders, updated_at=self._now()))

    def update_security(
        self, founder_id: int, *, session_timeout_minutes: int | None = None,
        login_notifications: bool | None = None,
    ) -> SettingsSnapshot:
        if session_timeout_minutes is not None:
            validate_session_timeout(session_timeout_minutes)
        current = self.get_settings(founder_id)
        s = current.security
        new_security = SecurityPreferences(
            session_timeout_minutes=(s.session_timeout_minutes if session_timeout_minutes is None
                                     else session_timeout_minutes),
            login_notifications=(s.login_notifications if login_notifications is None
                                 else login_notifications),
        )
        return self._save(replace(current, security=new_security, updated_at=self._now()))

    # --- reset -----------------------------------------------------------

    def reset_defaults(self, founder_id: int) -> SettingsSnapshot:
        defaults = default_settings(founder_id, self._now())
        if self.repository.get(founder_id) is None:
            return self.repository.create(defaults)
        return self.repository.replace(defaults)

    # --- internals -------------------------------------------------------

    def _save(self, snapshot: SettingsSnapshot) -> SettingsSnapshot:
        return self.repository.replace(snapshot)


def build_settings_service(
    repository: SettingsRepository | None = None,
    *,
    now: Callable[[], datetime] | None = None,
) -> SettingsService:
    from app.settings.repository import InMemorySettingsRepository
    return SettingsService(repository or InMemorySettingsRepository(), now=now)
