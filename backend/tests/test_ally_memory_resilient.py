"""Resilient memory wrapper: a DB failure DEGRADES (logged), it never fails a chat."""

import logging
from types import SimpleNamespace

from app.api.v1.ally.memory.resilient import (
    ResilientMemoryEventRepository, ResilientMemoryRepository,
)


class _Boom:
    """Inner repo whose every operation raises, simulating a DB outage."""
    def save(self, item): raise RuntimeError("db down")
    def get(self, memory_id): raise RuntimeError("db down")
    def list_for_founder(self, founder_id): raise RuntimeError("db down")
    def delete(self, memory_id): raise RuntimeError("db down")
    def append(self, event): raise RuntimeError("db down")
    def list_for_memory(self, memory_id): raise RuntimeError("db down")


class _FakeDB:
    def __init__(self): self.rolled_back = False
    def rollback(self): self.rolled_back = True


def test_write_degrades_and_is_visible(caplog):
    db = _FakeDB()
    repo = ResilientMemoryRepository(_Boom(), db)
    item = SimpleNamespace(founder_id=7, memory_id="mem:x")
    with caplog.at_level(logging.WARNING, logger="ally.memory"):
        out = repo.save(item)                 # must NOT raise -> chat continues
    assert out is item                        # degraded: returned, not persisted
    assert db.rolled_back is True             # session not left poisoned
    assert any("DEGRADED" in r.message for r in caplog.records)  # logged, not swallowed


def test_reads_degrade_to_empty():
    repo = ResilientMemoryRepository(_Boom(), _FakeDB())
    assert repo.list_for_founder(7) == ()
    assert repo.get("mem:x") is None
    assert repo.delete("mem:x") is False


def test_event_append_degrades():
    db = _FakeDB()
    repo = ResilientMemoryEventRepository(_Boom(), db)
    ev = SimpleNamespace(founder_id=7)
    assert repo.append(ev) is ev              # no raise
    assert db.rolled_back is True
    assert repo.list_for_founder(7) == ()
