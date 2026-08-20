"""Founder Goals persistence seam.

`FounderGoalRepository` is the interface the service depends on. Two
implementations: InMemoryFounderGoalRepository (deterministic, thread-safe,
used by tests) and SqlAlchemyFounderGoalRepository (db_repository.py,
production). Swapping one for the other is a repository replacement only;
the service is unchanged. Mirrors app/planning/repository.py's shape.
"""

from __future__ import annotations

import abc
import threading

from app.founder_goals.models import FounderGoal


class FounderGoalRepository(abc.ABC):
    @abc.abstractmethod
    def add(self, goal: FounderGoal) -> FounderGoal: ...

    @abc.abstractmethod
    def get(self, goal_id: str) -> FounderGoal | None: ...

    @abc.abstractmethod
    def replace(self, goal: FounderGoal) -> FounderGoal: ...

    @abc.abstractmethod
    def list_for_founder(self, founder_id: int) -> tuple[FounderGoal, ...]: ...

    @abc.abstractmethod
    def delete(self, goal_id: str) -> None: ...


class InMemoryFounderGoalRepository(FounderGoalRepository):
    def __init__(self) -> None:
        self._rows: dict[str, FounderGoal] = {}
        self._lock = threading.RLock()

    def add(self, goal: FounderGoal) -> FounderGoal:
        with self._lock:
            self._rows[goal.goal_id] = goal
        return goal

    def get(self, goal_id: str) -> FounderGoal | None:
        with self._lock:
            return self._rows.get(goal_id)

    def replace(self, goal: FounderGoal) -> FounderGoal:
        with self._lock:
            self._rows[goal.goal_id] = goal
        return goal

    def list_for_founder(self, founder_id: int) -> tuple[FounderGoal, ...]:
        with self._lock:
            items = [g for g in self._rows.values() if g.founder_id == founder_id]
        # Newest first -- matches the frontend's own ordering (new goals prepended).
        items.sort(key=lambda g: (g.created_at, g.goal_id), reverse=True)
        return tuple(items)

    def delete(self, goal_id: str) -> None:
        with self._lock:
            self._rows.pop(goal_id, None)
