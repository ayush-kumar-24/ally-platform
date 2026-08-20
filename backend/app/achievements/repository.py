"""Achievements persistence seam.

`AchievementRepository` is the interface the service depends on: CRUD plus
`total_messages`, the one read that reaches outside this module's own table
(into `conversations`) to compute the real engagement signal. Two
implementations: InMemoryAchievementRepository (deterministic, thread-safe,
tests -- `total_messages` is fed in directly rather than simulated) and
SqlAlchemyAchievementRepository (db_repository.py, production).
"""

from __future__ import annotations

import abc
import threading

from app.achievements.models import Achievement


class AchievementRepository(abc.ABC):
    @abc.abstractmethod
    def add(self, achievement: Achievement) -> Achievement: ...

    @abc.abstractmethod
    def get(self, achievement_id: str) -> Achievement | None: ...

    @abc.abstractmethod
    def replace(self, achievement: Achievement) -> Achievement: ...

    @abc.abstractmethod
    def list_for_founder(self, founder_id: int) -> tuple[Achievement, ...]: ...

    @abc.abstractmethod
    def delete(self, achievement_id: str) -> None: ...

    @abc.abstractmethod
    def total_messages(self, founder_id: int) -> int:
        """Sum of conversations.message_count for this founder -- the real
        'how much have they talked to Ally' signal."""


class InMemoryAchievementRepository(AchievementRepository):
    """`preset_message_count` lets a test declare the founder's engagement
    directly, since there is no in-memory conversations table to sum."""

    def __init__(self, preset_message_count: dict[int, int] | None = None) -> None:
        self._rows: dict[str, Achievement] = {}
        self._message_counts: dict[int, int] = dict(preset_message_count or {})
        self._lock = threading.RLock()

    def add(self, achievement: Achievement) -> Achievement:
        with self._lock:
            self._rows[achievement.achievement_id] = achievement
        return achievement

    def get(self, achievement_id: str) -> Achievement | None:
        with self._lock:
            return self._rows.get(achievement_id)

    def replace(self, achievement: Achievement) -> Achievement:
        with self._lock:
            self._rows[achievement.achievement_id] = achievement
        return achievement

    def list_for_founder(self, founder_id: int) -> tuple[Achievement, ...]:
        with self._lock:
            items = [a for a in self._rows.values() if a.founder_id == founder_id]
        items.sort(key=lambda a: (a.created_at, a.achievement_id), reverse=True)
        return tuple(items)

    def delete(self, achievement_id: str) -> None:
        with self._lock:
            self._rows.pop(achievement_id, None)

    def total_messages(self, founder_id: int) -> int:
        with self._lock:
            return self._message_counts.get(founder_id, 0)

    def set_message_count(self, founder_id: int, count: int) -> None:
        """Test helper -- not part of the abstract interface."""
        with self._lock:
            self._message_counts[founder_id] = count
