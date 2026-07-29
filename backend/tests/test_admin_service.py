"""Domain tests for the Admin module (Phase 12). In-memory repos, deterministic."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import count

import pytest

from app.admin import (
    AdminForbiddenError,
    AdminFounderNotFoundError,
    AdminRegistry,
    AdminRole,
    AdminService,
    AdminUser,
    ConversationSummary,
    FeedbackSummary,
    FounderStatus,
    FounderSummary,
    InMemoryAdminRepository,
    InMemoryAnnouncementRepository,
    InMemoryAuditRepository,
    InvalidAnnouncementError,
    InvalidSearchError,
    UsageMetrics,
)

T0 = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)


def _ids():
    c = count(1)
    return lambda: f"id-{next(c)}"


def _founders():
    return [
        FounderSummary(1, "Asha Rao", "asha@x.com", FounderStatus.ACTIVE, "pro", T0, 3),
        FounderSummary(2, "Bo Li", "bo@y.com", FounderStatus.ACTIVE, "free", T0 - timedelta(days=10), 1),
        FounderSummary(3, "Cara Diaz", "cara@z.com", FounderStatus.SUSPENDED, "starter", T0 - timedelta(days=40), 0),
    ]


def _conversations():
    stamps = [T0, T0 - timedelta(days=2), T0 - timedelta(days=10), T0 - timedelta(days=40)]
    return [ConversationSummary(f"c{i}", 1, "chat", "active", 2, ts, ts) for i, ts in enumerate(stamps)]


def build(role=AdminRole.ADMIN):
    repo = InMemoryAdminRepository(
        founders=_founders(), conversations=_conversations(),
        feedback=[FeedbackSummary("fb1", "s1", 1, "accepted", T0)],
        usage=UsageMetrics(messages_sent=120, attachments_uploaded=8, suggestions_generated=15))
    service = AdminService(
        admin_repository=repo, announcement_repository=InMemoryAnnouncementRepository(),
        audit_repository=InMemoryAuditRepository(), clock=lambda: T0, id_factory=_ids())
    return service, AdminUser(99, "ops@goxl.in", role), repo


# --- founders ---------------------------------------------------------------


def test_list_founders():
    service, admin, _ = build()
    assert [f.founder_id for f in service.list_founders(admin)] == [1, 2, 3]


def test_search_founders_by_name_and_email():
    service, admin, _ = build()
    assert [f.founder_id for f in service.search_founders(admin, "asha")] == [1]
    assert [f.founder_id for f in service.search_founders(admin, "y.com")] == [2]


def test_search_empty_query_rejected():
    service, admin, _ = build()
    with pytest.raises(InvalidSearchError):
        service.search_founders(admin, "   ")


def test_get_founder_and_not_found():
    service, admin, _ = build()
    assert service.get_founder(admin, 1).full_name == "Asha Rao"
    with pytest.raises(AdminFounderNotFoundError):
        service.get_founder(admin, 999)


# --- suspend / restore + audit ---------------------------------------------


def test_suspend_and_restore_records_audit():
    service, admin, _ = build()
    assert service.suspend_founder(admin, 1, reason="ToS").status == FounderStatus.SUSPENDED
    assert service.restore_founder(admin, 1).status == FounderStatus.ACTIVE
    events = service.list_audit(admin)
    assert [e.action for e in events] == ["restore_founder", "suspend_founder"]   # newest first
    assert events[1].result == "success" and events[1].reason == "ToS"


def test_suspend_requires_operator_role():
    service, admin, _ = build(role=AdminRole.READ_ONLY)
    with pytest.raises(AdminForbiddenError):
        service.suspend_founder(admin, 1)


def test_suspend_missing_founder_audits_failure():
    service, admin, _ = build()
    with pytest.raises(AdminFounderNotFoundError):
        service.suspend_founder(admin, 999)
    assert service.list_audit(admin)[0].result == "failure"


# --- dashboard --------------------------------------------------------------


def test_dashboard_metrics():
    service, admin, _ = build()
    s = service.dashboard(admin)
    assert s.total_founders == 3 and s.active_founders == 2 and s.suspended_founders == 1
    assert s.new_founders == 1                       # only founder 1 created within 7 days
    assert s.total_conversations == 4
    assert (s.daily_activity, s.weekly_activity, s.monthly_activity) == (1, 2, 3)
    assert s.usage.messages_sent == 120 and s.usage.suggestions_generated == 15
    assert s.generated_at == T0


# --- announcements ----------------------------------------------------------


def test_publish_and_list_announcements():
    service, admin, _ = build()
    a = service.publish_announcement(admin, title="Maintenance", body="Sunday 2am UTC")
    assert a.created_by == 99 and a.active is True
    assert [x.announcement_id for x in service.list_announcements(admin)] == [a.announcement_id]


def test_publish_requires_operator():
    service, admin, _ = build(role=AdminRole.READ_ONLY)
    with pytest.raises(AdminForbiddenError):
        service.publish_announcement(admin, title="x", body="y")


def test_publish_invalid_rejected():
    service, admin, _ = build()
    with pytest.raises(InvalidAnnouncementError):
        service.publish_announcement(admin, title="   ", body="y")


# --- permissions / audit append-only ----------------------------------------


def test_read_only_can_read():
    service, admin, _ = build(role=AdminRole.READ_ONLY)
    assert len(service.list_founders(admin)) == 3
    assert service.dashboard(admin).total_founders == 3


def test_audit_is_append_only_newest_first():
    service, admin, _ = build()
    service.suspend_founder(admin, 1)
    service.suspend_founder(admin, 2)
    events = service.list_audit(admin)
    assert len(events) == 2 and events[0].resource == "founder:2"


# --- concurrency / determinism / registry ----------------------------------


def test_concurrent_reads():
    service, admin, _ = build()

    def read(_):
        return service.dashboard(admin).total_founders == 3 and len(service.list_founders(admin)) == 3

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(read, range(40)))


def test_deterministic_execution():
    def run():
        service, admin, _ = build()
        service.suspend_founder(admin, 1, reason="r")
        a = service.publish_announcement(admin, title="T", body="B")
        return a, service.list_audit(admin)
    assert run() == run()


def test_registry_parsing_and_resolution():
    reg = AdminRegistry(env={"GOXL_ADMIN_USERS": "a@x.com:admin, b@x.com:operator, junk, c@x.com:bogus"})
    assert reg.resolve("A@X.com") == AdminRole.ADMIN
    assert reg.resolve("b@x.com") == AdminRole.OPERATOR
    assert reg.resolve("c@x.com") is None and reg.resolve("nobody@x.com") is None
