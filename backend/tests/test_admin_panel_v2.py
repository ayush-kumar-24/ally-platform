"""Bulk credits, timeline merging, conversation viewer, report regeneration."""

from datetime import datetime, timedelta, timezone
from itertools import count

import pytest

from app.admin.conversations import (
    ConversationMessage,
    ConversationView,
    InMemoryConversationReadRepository,
)
from app.admin.errors import AdminForbiddenError
from app.admin.insights import (
    InMemoryInsightsRepository,
    Metric,
    TimelineEvent,
    build_insights_service,
    merge_timeline,
)
from app.admin.panel_audit import AuditRecorder, InMemoryPanelAuditRepository
from app.admin.panel_service import AdminPanelService
from app.admin.rbac import PanelRole
from app.admin.users_models import ConsentStatus, UserFilters, UserStatus, UserSummary
from app.admin.users_repository import InMemoryAdminUserRepository
from app.credits import CreditOperation, InMemoryCreditRepository, build_credit_service

T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


class Admin:
    def __init__(self, role, admin_id=99, email="a@goxl.in"):
        self.role, self.admin_id, self.email = role, admin_id, email


SUPER = Admin(PanelRole.SUPER_ADMIN)
ADMIN = Admin(PanelRole.ADMIN)
SUPPORT = Admin(PanelRole.SUPPORT)


def _u(fid, plan="free", credits=100):
    return UserSummary(founder_id=fid, full_name=f"U{fid}", email=f"u{fid}@x.com",
                       phone=None, business_name=None, status=UserStatus.ACTIVE,
                       plan_type=plan, credits_balance=credits, diagnosis_completed=False,
                       consent_status=ConsentStatus.GRANTED, created_at=T0)


def build(users=None, balances=None, conversations=None, regenerator=None):
    users = users or [_u(1, "pro"), _u(2, "pro"), _u(3, "free")]
    repo = InMemoryAdminUserRepository(users)
    balances = balances or {u.founder_id: u.credits_balance for u in users}
    credits = build_credit_service(InMemoryCreditRepository(balances), clock=lambda: T0)
    audit_repo = InMemoryPanelAuditRepository()
    c = count(1)
    return AdminPanelService(
        repo, credits=credits,
        audit=AuditRecorder(audit_repo, clock=lambda: T0, id_factory=lambda: f"e-{next(c)}"),
        clock=lambda: T0,
        conversations=conversations,
        report_regenerator=regenerator), repo, audit_repo


# --- bulk credits -----------------------------------------------------------


def test_bulk_by_explicit_ids():
    s, _, _ = build()
    res = s.bulk_adjust_credits(SUPER, operation=CreditOperation.ADD, amount=50,
                                reason="promo", founder_ids=[1, 3])
    assert res["succeeded"] == 2 and res["failure_count"] == 0
    assert s.credits.get_balance(1).balance == 150
    assert s.credits.get_balance(2).balance == 100      # untouched
    assert s.credits.get_balance(3).balance == 150


def test_bulk_by_cohort_filter():
    s, _, _ = build()
    res = s.bulk_adjust_credits(SUPER, operation=CreditOperation.ADD, amount=100,
                                reason="all pro", filters=UserFilters(subscription="pro"))
    assert res["targeted"] == 2 and res["succeeded"] == 2
    assert s.credits.get_balance(1).balance == 200
    assert s.credits.get_balance(3).balance == 100      # free plan untouched


def test_bulk_requires_exactly_one_target_spec():
    s, _, _ = build()
    with pytest.raises(Exception):
        s.bulk_adjust_credits(SUPER, operation=CreditOperation.ADD, amount=5,
                              reason="r", founder_ids=[1], filters=UserFilters())
    with pytest.raises(Exception):
        s.bulk_adjust_credits(SUPER, operation=CreditOperation.ADD, amount=5, reason="r")


def test_bulk_dry_run_writes_nothing():
    s, _, audit = build()
    res = s.bulk_adjust_credits(SUPER, operation=CreditOperation.ADD, amount=100,
                                reason="preview", filters=UserFilters(subscription="pro"),
                                dry_run=True)
    assert res["dry_run"] is True and res["matched"] == 2
    assert s.credits.get_balance(1).balance == 100      # unchanged
    assert audit.list()[1] == 0                          # no audit row for a preview


def test_bulk_partial_failure_is_reported_not_aborted():
    """One user short of credits must not roll back everyone else's adjustment."""
    s, _, _ = build(balances={1: 100, 2: 5, 3: 100})
    res = s.bulk_adjust_credits(SUPER, operation=CreditOperation.REMOVE, amount=50,
                                reason="clawback", founder_ids=[1, 2, 3])
    assert res["succeeded"] == 2 and res["failure_count"] == 1
    assert res["failed"][0]["founder_id"] == 2
    assert s.credits.get_balance(1).balance == 50
    assert s.credits.get_balance(2).balance == 5        # untouched by its own failure
    assert s.credits.get_balance(3).balance == 50


def test_bulk_dedupes_ids():
    s, _, _ = build()
    res = s.bulk_adjust_credits(SUPER, operation=CreditOperation.ADD, amount=10,
                                reason="r", founder_ids=[1, 1, 1])
    assert res["targeted"] == 1 and s.credits.get_balance(1).balance == 110


def test_bulk_is_audited_with_counts():
    s, _, audit = build()
    s.bulk_adjust_credits(SUPER, operation=CreditOperation.ADD, amount=10,
                          reason="r", founder_ids=[1, 2])
    e = audit.list()[0][0]
    assert e.action == "credits.bulk_add" and "targeted" in (e.new_value or "")


@pytest.mark.parametrize("admin", [ADMIN, SUPPORT])
def test_bulk_forbidden_for_non_super(admin):
    s, _, _ = build()
    with pytest.raises(AdminForbiddenError):
        s.bulk_adjust_credits(admin, operation=CreditOperation.ADD, amount=10,
                              reason="r", founder_ids=[1])


# --- timeline ---------------------------------------------------------------


def test_merge_timeline_sorts_newest_first():
    events = [
        TimelineEvent(at=T0 - timedelta(days=2), kind="account", title="created"),
        TimelineEvent(at=T0, kind="credits", title="granted"),
        TimelineEvent(at=T0 - timedelta(days=1), kind="report", title="report"),
    ]
    assert [e.title for e in merge_timeline(events)] == ["granted", "report", "created"]


def test_merge_timeline_handles_naive_and_aware_mix():
    """Schema columns differ (timestamp vs timestamptz); sorting must not raise."""
    events = [
        TimelineEvent(at=datetime(2026, 8, 1, 12, 0), kind="a", title="naive"),
        TimelineEvent(at=T0, kind="b", title="aware"),
    ]
    assert [e.title for e in merge_timeline(events)] == ["aware", "naive"]


def test_merge_timeline_drops_undated_and_applies_limit():
    events = [TimelineEvent(at=None, kind="x", title="undated")]
    events += [TimelineEvent(at=T0 - timedelta(hours=i), kind="c", title=f"e{i}")
               for i in range(10)]
    merged = merge_timeline(events, limit=3)
    assert len(merged) == 3 and all(e.title != "undated" for e in merged)


def test_timeline_service_returns_events():
    repo = InMemoryInsightsRepository(events={
        1: [TimelineEvent(at=T0, kind="account", title="created")]})
    assert len(build_insights_service(repo).user_timeline(1)) == 1


# --- metrics ----------------------------------------------------------------


def test_unavailable_metric_reports_none_not_zero():
    """A metric that cannot be measured must not render as a confident 0."""
    repo = InMemoryInsightsRepository(metrics=[
        Metric(key="revenue", label="Revenue", value=None,
               unavailable_reason="source table unavailable"),
        Metric(key="total_users", label="Total users", value=42),
    ])
    cards = build_insights_service(repo).dashboard_metrics()
    by_key = {m.key: m for m in cards}
    assert by_key["revenue"].available is False
    assert by_key["revenue"].value is None
    assert by_key["total_users"].available is True and by_key["total_users"].value == 42


# --- conversation viewer ----------------------------------------------------


def _conv(cid="c-1", fid=1):
    return ConversationView(
        conversation_id=cid, founder_id=fid, title="Growth", created_at=T0,
        message_count=2,
        messages=[ConversationMessage(message_id="m1", role="user", content="hi",
                                      created_at=T0),
                  ConversationMessage(message_id="m2", role="assistant", content="hello",
                                      created_at=T0)])


def test_support_can_view_conversations():
    convs = InMemoryConversationReadRepository([_conv()])
    s, _, _ = build(conversations=convs)
    items, total = s.list_conversations(SUPPORT, 1)
    assert total == 1 and items[0].conversation_id == "c-1"
    view = s.view_conversation(SUPPORT, "c-1")
    assert [m.role for m in view.messages] == ["user", "assistant"]


def test_conversation_viewer_has_no_write_path():
    """Support may view but never edit -- the mutation simply does not exist."""
    s, _, _ = build(conversations=InMemoryConversationReadRepository([_conv()]))
    for forbidden in ("edit_conversation", "update_conversation", "delete_conversation",
                      "redact_message"):
        assert not hasattr(s, forbidden)
    assert not hasattr(s.conversations, "save") and not hasattr(s.conversations, "delete")


def test_admin_role_lacks_view_chats():
    """Per the requested matrix, VIEW_CHATS is a Support capability."""
    s, _, _ = build(conversations=InMemoryConversationReadRepository([_conv()]))
    with pytest.raises(AdminForbiddenError):
        s.list_conversations(ADMIN, 1)


# --- report regeneration ----------------------------------------------------


def test_regenerate_report_runs_and_audits():
    calls = []
    s, _, audit = build(regenerator=lambda fid: calls.append(fid) or {"report_id": "r-9"})
    res = s.regenerate_report(ADMIN, 1, reason="model changed")
    assert calls == [1] and res["result"]["report_id"] == "r-9"
    assert audit.list()[0][0].action == "report.regenerate"


def test_regenerate_report_unconfigured_is_explicit():
    s, _, _ = build(regenerator=None)
    with pytest.raises(Exception):
        s.regenerate_report(ADMIN, 1)


def test_regenerate_forbidden_for_support():
    s, _, _ = build(regenerator=lambda fid: {})
    with pytest.raises(AdminForbiddenError):
        s.regenerate_report(SUPPORT, 1)
