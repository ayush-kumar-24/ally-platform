"""Settings persistence seam (Part 2).

`SettingsRepository` is the interface the service depends on. Two implementations:
  * InMemorySettingsRepository -- deterministic, thread-safe, offline (used by tests).
  * SqlAlchemySettingsRepository -- the production DB-backed store.
Swapping one for the other is a repository replacement only; the service is unchanged.
"""

from __future__ import annotations

import abc
import threading

from app.settings.schemas import (
    ReminderPreferences,
    SecurityPreferences,
    SettingsSnapshot,
)


class SettingsRepository(abc.ABC):
    @abc.abstractmethod
    def get(self, founder_id: int) -> SettingsSnapshot | None: ...

    @abc.abstractmethod
    def create(self, snapshot: SettingsSnapshot) -> SettingsSnapshot: ...

    @abc.abstractmethod
    def replace(self, snapshot: SettingsSnapshot) -> SettingsSnapshot: ...


class InMemorySettingsRepository(SettingsRepository):
    def __init__(self) -> None:
        self._rows: dict[int, SettingsSnapshot] = {}
        self._lock = threading.RLock()

    def get(self, founder_id: int) -> SettingsSnapshot | None:
        with self._lock:
            return self._rows.get(founder_id)

    def create(self, snapshot: SettingsSnapshot) -> SettingsSnapshot:
        with self._lock:
            self._rows[snapshot.founder_id] = snapshot
            return snapshot

    def replace(self, snapshot: SettingsSnapshot) -> SettingsSnapshot:
        with self._lock:
            self._rows[snapshot.founder_id] = snapshot
            return snapshot


class SqlAlchemySettingsRepository(SettingsRepository):
    """DB-backed store. Untested in the hermetic suite (no live DB); kept simple and
    mirrors the app's other repositories (commit + return the domain snapshot)."""

    def __init__(self, db):
        self.db = db

    def get(self, founder_id: int) -> SettingsSnapshot | None:
        from app.settings.models import FounderSettings
        row = self.db.get(FounderSettings, founder_id)
        return _to_snapshot(row) if row is not None else None

    def create(self, snapshot: SettingsSnapshot) -> SettingsSnapshot:
        from app.settings.models import FounderSettings
        row = FounderSettings(**_to_columns(snapshot))
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _to_snapshot(row)

    def replace(self, snapshot: SettingsSnapshot) -> SettingsSnapshot:
        from app.settings.models import FounderSettings
        row = self.db.get(FounderSettings, snapshot.founder_id)
        if row is None:
            return self.create(snapshot)
        for key, value in _to_columns(snapshot).items():
            setattr(row, key, value)
        self.db.commit()
        self.db.refresh(row)
        return _to_snapshot(row)


def _to_snapshot(row) -> SettingsSnapshot:
    return SettingsSnapshot(
        founder_id=row.founder_id,
        reminders=ReminderPreferences(
            daily_reminders=row.daily_reminders, reminder_time=row.reminder_time,
            task_reminders=row.task_reminders, meeting_reminders=row.meeting_reminders,
            goal_reminders=row.goal_reminders),
        security=SecurityPreferences(
            session_timeout_minutes=row.session_timeout_minutes,
            login_notifications=row.login_notifications),
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _to_columns(s: SettingsSnapshot) -> dict:
    return {
        "founder_id": s.founder_id,
        "created_at": s.created_at, "updated_at": s.updated_at,
        "daily_reminders": s.reminders.daily_reminders, "reminder_time": s.reminders.reminder_time,
        "task_reminders": s.reminders.task_reminders, "meeting_reminders": s.reminders.meeting_reminders,
        "goal_reminders": s.reminders.goal_reminders,
        "session_timeout_minutes": s.security.session_timeout_minutes,
        "login_notifications": s.security.login_notifications,
    }
