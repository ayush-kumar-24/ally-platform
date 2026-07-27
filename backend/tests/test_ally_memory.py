"""Unit tests for the Ally Founder Memory Layer (Phase 5, Milestone 6).

Fully offline: an in-memory repository + an injected fake clock (so timestamps and
expiration are deterministic). No database, no LLM, no retrieval.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.api.v1.ally.memory import (
    InMemoryMemoryRepository,
    InvalidMemoryError,
    MemoryEventType,
    MemorySearchRequest,
    MemoryStatus,
    MemoryType,
    Retention,
    build_memory_service,
)

T0 = datetime(2026, 7, 27, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, now):
        self._now = now

    def now(self):
        return self._now

    def advance(self, delta):
        self._now += delta


def make():
    clock = FakeClock(T0)
    return build_memory_service(InMemoryMemoryRepository(), clock=clock), clock


def req(founder_id=1, **kw):
    return MemorySearchRequest(founder_id=founder_id, **kw)


# --- Store ------------------------------------------------------------------


def test_store_creates_permanent_preference():
    svc, _ = make()
    item = svc.store(1, MemoryType.PREFERENCE, "prefers concise answers", importance=80, tags=("tone",))
    assert item is not None
    assert item.metadata.retention == Retention.PERMANENT
    assert item.metadata.expires_at is None
    assert item.metadata.status == MemoryStatus.ACTIVE
    assert item.metadata.audit.created_at == T0
    assert item.metadata.audit.created_by == "system"
    assert item.metadata.audit.access_count == 0


def test_store_gate_skips_unimportant():
    svc, _ = make()
    assert svc.store(1, MemoryType.WORKING, "meh", importance=0) is None
    assert svc.search(req()).is_empty


def test_invalid_memory_raises():
    svc, _ = make()
    with pytest.raises(InvalidMemoryError):
        svc.store(1, MemoryType.WORKING, "   ", importance=50)     # empty content
    with pytest.raises(InvalidMemoryError):
        svc.store(1, MemoryType.WORKING, "ok", importance=150)     # bad importance


# --- Retrieve ---------------------------------------------------------------


def test_retrieve_touches_audit_but_not_ranking():
    svc, clock = make()
    item = svc.store(1, MemoryType.STRATEGIC, "raise Series A", importance=70)
    clock.advance(timedelta(minutes=5))
    got = svc.retrieve(item.memory_id)
    assert got.metadata.audit.access_count == 1
    assert got.metadata.audit.accessed_at == T0 + timedelta(minutes=5)
    assert svc.retrieve(item.memory_id).metadata.audit.access_count == 2


def test_retrieve_missing_returns_none():
    svc, _ = make()
    assert svc.retrieve("mem:doesnotexist") is None


def test_retrieve_without_touch_leaves_audit():
    svc, _ = make()
    item = svc.store(1, MemoryType.STRATEGIC, "goal", importance=60)
    assert svc.retrieve(item.memory_id, touch=False).metadata.audit.access_count == 0


# --- Update / Archive -------------------------------------------------------


def test_update_changes_content_keeps_creation_history():
    svc, clock = make()
    item = svc.store(1, MemoryType.STRATEGIC, "old goal", importance=60)
    clock.advance(timedelta(hours=1))
    updated = svc.update(item.memory_id, content="new goal", importance=75, actor="ceo")
    assert updated.content == "new goal" and updated.metadata.importance == 75
    assert updated.metadata.audit.created_at == T0                    # unchanged
    assert updated.metadata.audit.updated_at == T0 + timedelta(hours=1)
    assert updated.metadata.audit.updated_by == "ceo"


def test_archive_sets_status_and_audit_and_hides_from_search():
    svc, clock = make()
    item = svc.store(1, MemoryType.STRATEGIC, "shelved goal", importance=60)
    clock.advance(timedelta(days=1))
    archived = svc.archive(item.memory_id, actor="admin")
    assert archived.metadata.status == MemoryStatus.ARCHIVED
    assert archived.metadata.audit.archived_at == T0 + timedelta(days=1)
    assert svc.search(req()).is_empty                                # excluded by default
    assert not svc.search(req(include_archived=True)).is_empty


# --- Expiration -------------------------------------------------------------


def test_expiration_excludes_after_ttl():
    svc, clock = make()
    svc.store(1, MemoryType.WORKING, "temp note", importance=50)     # TEMPORARY, 7d ttl
    assert not svc.search(req()).is_empty                            # present at T0
    clock.advance(timedelta(days=8))
    assert svc.search(req()).is_empty                                # expired -> hidden
    assert not svc.search(req(include_expired=True)).is_empty        # still retrievable if asked


# --- Duplicate prevention ---------------------------------------------------


def test_duplicate_store_updates_not_duplicates():
    svc, clock = make()
    a = svc.store(1, MemoryType.STRATEGIC, "Raise Series A", importance=80)
    clock.advance(timedelta(hours=2))
    b = svc.store(1, MemoryType.STRATEGIC, "Raise Series A", importance=85, actor="ceo")
    assert a.memory_id == b.memory_id
    assert len(svc.repository.list_for_founder(1)) == 1
    assert b.metadata.importance == 85
    assert b.metadata.audit.created_at == T0                          # creation preserved
    assert b.metadata.audit.updated_at == T0 + timedelta(hours=2)


# --- Search + filtering -----------------------------------------------------


def test_search_filters():
    svc, _ = make()
    svc.store(1, MemoryType.PREFERENCE, "likes bullet points", importance=90, tags=("tone", "ui"))
    svc.store(1, MemoryType.STRATEGIC, "expand to EU", importance=70, tags=("growth",))
    svc.store(2, MemoryType.STRATEGIC, "other founder", importance=95)   # different founder
    assert {i.content for i in svc.search(req(memory_type=MemoryType.PREFERENCE)).items} == {"likes bullet points"}
    assert {i.content for i in svc.search(req(tags=("growth",))).items} == {"expand to EU"}
    assert {i.content for i in svc.search(req(min_importance=80)).items} == {"likes bullet points"}
    assert {i.content for i in svc.search(req(keyword="EU")).items} == {"expand to EU"}
    assert svc.search(req(founder_id=999)).is_empty                      # empty repo for founder


def test_search_date_range():
    svc, _ = make()
    svc.store(1, MemoryType.STRATEGIC, "goal", importance=60)
    assert not svc.search(req(date_from=T0, date_to=T0)).is_empty
    assert svc.search(req(date_from=T0 + timedelta(days=1))).is_empty


def test_deterministic_ordering():
    svc, clock = make()
    svc.store(1, MemoryType.STRATEGIC, "low", importance=40)
    clock.advance(timedelta(minutes=1))
    svc.store(1, MemoryType.STRATEGIC, "high", importance=90)
    clock.advance(timedelta(minutes=1))
    svc.store(1, MemoryType.STRATEGIC, "mid", importance=40)          # ties 'low' on importance
    result = svc.search(req())
    order = [i.content for i in result.items]
    assert order[0] == "high"                                        # importance desc
    assert order[1] == "mid" and order[2] == "low"                   # tie -> most recent first
    assert svc.search(req()).items == result.items                   # repeatable


# --- Session isolation ------------------------------------------------------


def test_session_isolation():
    svc, _ = make()
    a = svc.store(1, MemoryType.SESSION, "same note", importance=50, session_id=1)
    b = svc.store(1, MemoryType.SESSION, "same note", importance=50, session_id=2)
    assert a.memory_id != b.memory_id                                # isolated by session
    s1 = svc.search(req(memory_type=MemoryType.SESSION, session_id=1))
    assert {i.metadata.session_id for i in s1.items} == {1}


# --- Memory events (timeline) -----------------------------------------------


def types(events):
    return [e.event_type for e in events]


def test_created_event_on_store():
    svc, _ = make()
    item = svc.store(1, MemoryType.STRATEGIC, "goal", importance=60, actor="ceo")
    tl = svc.timeline(item.memory_id)
    assert types(tl) == [MemoryEventType.CREATED]
    assert tl[0].actor == "ceo" and tl[0].timestamp == T0
    assert tl[0].memory_id == item.memory_id and tl[0].founder_id == 1


def test_update_and_access_and_archive_events_form_a_timeline():
    svc, clock = make()
    item = svc.store(1, MemoryType.STRATEGIC, "goal", importance=60)
    clock.advance(timedelta(minutes=1))
    svc.retrieve(item.memory_id)
    clock.advance(timedelta(minutes=1))
    svc.update(item.memory_id, importance=80)
    clock.advance(timedelta(minutes=1))
    svc.archive(item.memory_id)
    assert types(svc.timeline(item.memory_id)) == [
        MemoryEventType.CREATED, MemoryEventType.ACCESSED,
        MemoryEventType.UPDATED, MemoryEventType.ARCHIVED,
    ]


def test_duplicate_store_emits_updated_event():
    svc, _ = make()
    item = svc.store(1, MemoryType.STRATEGIC, "Raise Series A", importance=80)
    svc.store(1, MemoryType.STRATEGIC, "Raise Series A", importance=85)
    assert types(svc.timeline(item.memory_id)) == [MemoryEventType.CREATED, MemoryEventType.UPDATED]


def test_sweep_expired_emits_expired_event_and_is_idempotent():
    svc, clock = make()
    item = svc.store(1, MemoryType.WORKING, "temp", importance=50)      # TEMPORARY
    assert svc.sweep_expired(1) == ()                                   # not yet expired
    clock.advance(timedelta(days=8))
    swept = svc.sweep_expired(1)
    assert [i.memory_id for i in swept] == [item.memory_id]
    assert MemoryEventType.EXPIRED in types(svc.timeline(item.memory_id))
    assert svc.sweep_expired(1) == ()                                   # idempotent


def test_founder_timeline_spans_multiple_memories():
    svc, clock = make()
    svc.store(1, MemoryType.STRATEGIC, "a", importance=60)
    clock.advance(timedelta(minutes=1))
    svc.store(1, MemoryType.PREFERENCE, "b", importance=60)
    svc.store(2, MemoryType.STRATEGIC, "other", importance=60)          # different founder
    tl = svc.founder_timeline(1)
    assert len(tl) == 2 and all(e.founder_id == 1 for e in tl)


# --- Correlation IDs (request tracing) --------------------------------------


def test_events_carry_correlation_id():
    svc, _ = make()
    cid = "req-abc-123"
    item = svc.store(1, MemoryType.STRATEGIC, "raise funding", importance=70, correlation_id=cid)
    svc.retrieve(item.memory_id, correlation_id=cid)
    tl = svc.timeline(item.memory_id)
    assert [e.correlation_id for e in tl] == [cid, cid]


def test_correlation_id_defaults_none_and_does_not_affect_state():
    svc, _ = make()
    item = svc.store(1, MemoryType.STRATEGIC, "goal", importance=70)   # no correlation_id
    assert svc.timeline(item.memory_id)[0].correlation_id is None
    # Same stored state whether or not a correlation id is supplied (observational).
    plain = svc.store(2, MemoryType.STRATEGIC, "goal", importance=70)
    traced = svc.store(3, MemoryType.STRATEGIC, "goal", importance=70, correlation_id="req-x")
    assert plain.content == traced.content and plain.metadata.retention == traced.metadata.retention


def test_correlation_id_groups_one_interaction_across_events():
    svc, clock = make()
    cid = "interaction-42"
    a = svc.store(1, MemoryType.STRATEGIC, "goal a", importance=70, correlation_id=cid)
    clock.advance(timedelta(minutes=1))
    b = svc.store(1, MemoryType.PREFERENCE, "pref b", importance=70, correlation_id=cid)
    clock.advance(timedelta(minutes=1))
    svc.store(1, MemoryType.WORKING, "later note", importance=50, correlation_id="other-req")
    one_interaction = [e for e in svc.founder_timeline(1) if e.correlation_id == cid]
    assert {e.memory_id for e in one_interaction} == {a.memory_id, b.memory_id}


# --- Summarize --------------------------------------------------------------


def test_summarize_aggregates_deterministically():
    svc, _ = make()
    svc.store(1, MemoryType.STRATEGIC, "goal A", importance=80)
    svc.store(1, MemoryType.PREFERENCE, "pref A", importance=90)
    svc.store(1, MemoryType.WORKING, "challenge A", importance=50)
    s = svc.summarize(1)
    assert s.total == 3 and s.active == 3 and s.archived == 0
    assert s.counts_by_type["strategic"] == 1
    assert s.strategic_goals == ("goal A",)
    assert s.preferences == ("pref A",)
    assert s.recurring_challenges == ("challenge A",)
