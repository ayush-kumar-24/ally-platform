"""Recording a resolved dimension must not clobber a concurrent one.

`founders.founder_dna_resolved_dimensions` is a JSONB array and
FounderDnaRepository.mark_dimension_resolved updates it by read-modify-write:
the whole list is read into Python, appended to, and assigned back. Nothing
serialised that. Two overlapping answers -- a double-click, or a client retry
that overlapped the original request -- each read the list BEFORE either had
committed, so the second commit wrote its own one-element addition over the
first's and one dimension's resolution vanished.

That is not a cosmetic loss. `select_next_question` skips a dimension only when
it is in this list, so a dropped entry makes the phase re-ask a dimension the
advisor had already closed, spending one of the two follow-up slots that
MAX_FOUNDER_DNA_QUESTIONS leaves (see its comment in core/config.py) on a
question that did not need asking. The diagnosis module already took a row lock
for the same class of bug; this phase never did.

These pin the lock, and specifically the REFRESH under it -- a lock without
re-reading would serialise the writes and still append to the stale list.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.founder_dna.service import (
    FounderDnaPersistenceError,
    FounderDnaService,
)


class _Db:
    """Records the order of the calls the service makes, and lets a test stand
    in for "a concurrent transaction committed while we were blocked on the
    lock" by mutating the founder inside refresh()."""

    def __init__(self, *, on_refresh=None, refresh_raises=False):
        self.calls: list[str] = []
        self._on_refresh = on_refresh
        self._refresh_raises = refresh_raises

    def refresh(self, obj):
        self.calls.append("refresh")
        if self._refresh_raises:
            raise SQLAlchemyError("connection lost")
        if self._on_refresh is not None:
            self._on_refresh(obj)

    def rollback(self):
        self.calls.append("rollback")


class _Repo:
    """Only what _record_resolution and _maybe_resolve touch. Real
    mark_dimension_resolved semantics, copied so the append-vs-clobber
    behaviour under test is the production one."""

    def __init__(self, db, *, lock_raises=False, per_dimension=None, history=()):
        self.db = db
        self._lock_raises = lock_raises
        self._per_dimension = per_dimension or {}
        self._history = list(history)

    def lock_founder_for_update(self, founder_id):
        self.db.calls.append("lock")
        if self._lock_raises:
            raise SQLAlchemyError("deadlock detected")

    def mark_dimension_resolved(self, founder, dimension_code):
        self.db.calls.append(f"mark:{dimension_code}")
        current = list(founder.founder_dna_resolved_dimensions or [])
        if dimension_code not in current:
            current.append(dimension_code)
            founder.founder_dna_resolved_dimensions = current

    def get_resolved_dimensions(self, founder):
        return set(founder.founder_dna_resolved_dimensions or [])

    def answers_per_dimension(self, founder_id, stage_group):
        return dict(self._per_dimension)

    def recent_qa_for_dimension(self, founder_id, dimension_code, stage_group):
        return list(self._history)


class _Engine:
    def __init__(self, exhausted=False):
        self._exhausted = exhausted

    def dimension_pool_exhausted(self, founder, dimension_code, stage_group):
        return self._exhausted


class _Advisor:
    """Stands in for DimensionResolutionAdvisor."""

    def __init__(self, resolved: bool):
        self._resolved = resolved

    async def judge(self, *, dimension_code, qa_history):
        return SimpleNamespace(resolved=self._resolved)


def _founder(resolved):
    return SimpleNamespace(founder_id=7, founder_dna_resolved_dimensions=list(resolved))


def _service(db, repo, *, engine=None, advisor=None):
    service = FounderDnaService.__new__(FounderDnaService)
    service.db = db
    service.repository = repo
    service.engine = engine or _Engine()
    service.advisor = advisor
    return service


# --- the lock itself ---------------------------------------------------------

def test_the_row_is_locked_and_re_read_before_the_append():
    """Order is the whole point: locking after reading protects nothing."""
    db = _Db()
    service = _service(db, _Repo(db))
    service._record_resolution(_founder(["origin"]), "core_values")

    assert db.calls == ["lock", "refresh", "mark:core_values"]


def test_a_concurrent_resolution_is_not_erased():
    """THE REGRESSION. This request loaded ["origin"] before the advisor call;
    while it was blocked on the lock another request committed "vision". Without
    the refresh the append is built on the stale list and "vision" is lost."""
    db = _Db(on_refresh=lambda f: setattr(
        f, "founder_dna_resolved_dimensions", ["origin", "vision"]))
    service = _service(db, _Repo(db))

    founder = _founder(["origin"])  # stale: does not know about "vision"
    service._record_resolution(founder, "core_values")

    assert founder.founder_dna_resolved_dimensions == ["origin", "vision", "core_values"]


def test_a_dimension_a_concurrent_request_already_recorded_is_not_duplicated():
    db = _Db(on_refresh=lambda f: setattr(
        f, "founder_dna_resolved_dimensions", ["origin", "core_values"]))
    service = _service(db, _Repo(db))

    founder = _founder(["origin"])
    service._record_resolution(founder, "core_values")

    assert founder.founder_dna_resolved_dimensions == ["origin", "core_values"]


# --- both call sites are covered ---------------------------------------------

def test_the_pool_exhausted_path_takes_the_lock():
    """The deterministic stop (advisor off or no questions left) writes to the
    same array and needs the same protection."""
    db = _Db()
    repo = _Repo(db, per_dimension={"origin": 2})
    service = _service(db, repo, engine=_Engine(exhausted=True))

    asyncio.run(service._maybe_resolve(_founder([]), "origin", "Stage 0"))

    assert db.calls == ["lock", "refresh", "mark:origin"]


def test_the_advisor_path_takes_the_lock():
    db = _Db()
    repo = _Repo(db, per_dimension={"origin": 2}, history=[("q", "a")])
    service = _service(db, repo, engine=_Engine(), advisor=_Advisor(resolved=True))

    asyncio.run(service._maybe_resolve(_founder([]), "origin", "Stage 0"))

    assert db.calls == ["lock", "refresh", "mark:origin"]


def test_an_unresolved_verdict_touches_nothing():
    """No write, so no lock -- the point of taking it late is that the common
    path never holds a transaction open across the advisor call."""
    db = _Db()
    repo = _Repo(db, per_dimension={"origin": 2}, history=[("q", "a")])
    service = _service(db, repo, engine=_Engine(), advisor=_Advisor(resolved=False))

    asyncio.run(service._maybe_resolve(_founder([]), "origin", "Stage 0"))

    assert db.calls == []


# --- database failures ---------------------------------------------------------

def test_a_failed_lock_rolls_back_and_raises():
    """A lost write is not a lost judgement: the commit that follows would fail
    anyway, so this surfaces rather than silently dropping the resolution."""
    db = _Db()
    service = _service(db, _Repo(db, lock_raises=True))

    with pytest.raises(FounderDnaPersistenceError):
        service._record_resolution(_founder([]), "origin")

    assert db.calls == ["lock", "rollback"]
    assert "mark:origin" not in db.calls


def test_a_failed_refresh_rolls_back_and_raises():
    db = _Db(refresh_raises=True)
    service = _service(db, _Repo(db))

    with pytest.raises(FounderDnaPersistenceError):
        service._record_resolution(_founder([]), "origin")

    assert db.calls == ["lock", "refresh", "rollback"]
