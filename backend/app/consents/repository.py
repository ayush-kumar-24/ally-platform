"""Consent persistence seam.

`ConsentRepository` is the interface the service depends on. Two implementations:
  * InMemoryConsentRepository -- deterministic, thread-safe, offline (used by tests).
  * SqlAlchemyConsentRepository (db_repository.py) -- the production DB-backed store.
Swapping one for the other is a repository replacement only; the service is unchanged.

The interface is deliberately append-only: `add` and reads. There is no `update` and
no `delete`, so no caller -- present or future -- can quietly rewrite consent history.
"""

from __future__ import annotations

import abc
import threading

from app.consents.models import ConsentRecord


class ConsentRepository(abc.ABC):
    @abc.abstractmethod
    def add(self, record: ConsentRecord) -> ConsentRecord:
        """Append one immutable consent record."""

    @abc.abstractmethod
    def latest(self, founder_id: int) -> ConsentRecord | None:
        """The founder's most recent record, or None if they never consented."""

    @abc.abstractmethod
    def list_for_founder(self, founder_id: int) -> list[ConsentRecord]:
        """Full history, newest first."""


class InMemoryConsentRepository(ConsentRepository):
    def __init__(self) -> None:
        self._rows: list[ConsentRecord] = []
        self._lock = threading.RLock()

    def add(self, record: ConsentRecord) -> ConsentRecord:
        with self._lock:
            self._rows.append(record)
            return record

    def latest(self, founder_id: int) -> ConsentRecord | None:
        with self._lock:
            found = [r for r in self._rows if r.founder_id == founder_id]
            return found[-1] if found else None

    def list_for_founder(self, founder_id: int) -> list[ConsentRecord]:
        with self._lock:
            return [r for r in reversed(self._rows) if r.founder_id == founder_id]
