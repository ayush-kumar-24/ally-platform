"""Admin Panel: RBAC enforcement, user management, audit trail."""

from datetime import datetime, timedelta, timezone
from itertools import count

import pytest

from app.admin.errors import AdminFounderNotFoundError, AdminForbiddenError
from app.admin.panel_audit import AuditRecorder, InMemoryPanelAuditRepository
from app.admin.panel_service import AdminPanelService
from app.admin.rbac import Capability, PanelRole, capabilities_for, has_capability
from app.admin.users_models import (
    ConsentStatus,
    SortField,
    UserFilters,
    UserStatus,
    UserSummary,
)
from app.admin.users_repository import InMemoryAdminUserRepository
from app.credits import CreditOperation, InMemoryCreditRepository, build_credit_service

T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


class Admin:
    def __init__(self, role: PanelRole, admin_id=99, email="a@goxl.in"):
        self.role, self.admin_id, self.email = role, admin_id, email


SUPER = Admin(PanelRole.SUPER_ADMIN)
ADMIN = Admin(PanelRole.ADMIN)
SUPPORT = Admin(PanelRole.SUPPORT)


def user(fid, name="U", email="u@x.com", status=UserStatus.ACTIVE, plan="free",
         credits=100, diag=False, consent=ConsentStatus.GRANTED, days_ago=0):
    return UserSummary(
        founder_id=fid, full_name=name, email=email, phone=f"999000{fid:04d}",
        business_name=f"Biz {fid}", status=status, plan_type=plan,
        credits_balance=credits, diagnosis_completed=diag, consent_status=consent,
        created_at=T0 - timedelta(days=days_ago), last_active_at=T0)


def build(users=None, balances=None):
    repo = InMemoryAdminUserRepository(users or [user(1)])
    credits = build_credit_service(
        InMemoryCreditRepository(balances or {1: 100}), clock=lambda: T0)
    audit_repo = InMemoryPanelAuditRepository()
    c = count(1)
    recorder = AuditRecorder(audit_repo, clock=lambda: T0, id_factory=lambda: f"e-{next(c)}")
    return AdminPanelService(repo, credits=credits, audit=recorder,
                             clock=lambda: T0), repo, audit_repo


# --- RBAC matrix ------------------------------------------------------------


def test_only_super_admin_holds_privileged_capabilities():
    for cap in (Capability.TRANSFER_CREDITS, Capability.MODIFY_SUBSCRIPTION,
                Capability.SUSPEND_USER, Capability.DELETE_USER,
                Capability.CHANGE_USER_ROLE, Capability.SYSTEM_SETTINGS):
        assert has_capability(PanelRole.SUPER_ADMIN, cap)
        assert not has_capability(PanelRole.ADMIN, cap)
        assert not has_capability(PanelRole.SUPPORT, cap)


def test_admin_capabilities():
    for cap in (Capability.VIEW_USERS, Capability.EDIT_USER_PROFILE,
                Capability.VIEW_REPORTS, Capability.RESET_DIAGNOSIS,
                Capability.RESET_CONVERSATIONS):
        assert has_capability(PanelRole.ADMIN, cap)


def test_support_can_view_but_not_modify():
    assert has_capability(PanelRole.SUPPORT, Capability.VIEW_USERS)
    assert has_capability(PanelRole.SUPPORT, Capability.VIEW_CHATS)
    assert not has_capability(PanelRole.SUPPORT, Capability.TRANSFER_CREDITS)
    assert not has_capability(PanelRole.SUPPORT, Capability.EDIT_USER_PROFILE)


def test_unknown_role_has_nothing():
    assert not has_capability(None, Capability.VIEW_USERS)
    assert capabilities_for(None) == []


# --- credits are Super-Admin-only ------------------------------------------


@pytest.mark.parametrize("admin", [ADMIN, SUPPORT])
def test_non_super_admin_cannot_touch_credits(admin):
    s, _, _ = build()
    with pytest.raises(AdminForbiddenError):
        s.adjust_credits(admin, 1, operation=CreditOperation.ADD, amount=10, reason="x")


def test_super_admin_can_adjust_credits_and_it_is_audited():
    s, _, audit = build()
    tx = s.adjust_credits(SUPER, 1, operation=CreditOperation.ADD, amount=50,
                          reason="goodwill", ip="203.0.113.9")
    assert tx.balance_after == 150
    events, _ = audit.list()
    assert events[0].action == "credits.add"
    assert events[0].target_user_id == 1
    assert events[0].ip_address == "203.0.113.9"
    assert "100" in events[0].old_value and "150" in events[0].new_value


def test_refused_credit_change_makes_no_audit_entry():
    s, _, audit = build()
    with pytest.raises(AdminForbiddenError):
        s.adjust_credits(SUPPORT, 1, operation=CreditOperation.ADD, amount=10, reason="x")
    assert audit.list()[1] == 0


# --- user mutations are authorized per field --------------------------------

def test_admin_may_edit_profile_but_not_status():
    s, _, _ = build()
    assert s.update_user(ADMIN, 1, {"full_name": "New Name"}).full_name == "New Name"
    with pytest.raises(AdminForbiddenError):
        s.update_user(ADMIN, 1, {"status": UserStatus.SUSPENDED})


def test_support_may_not_edit_at_all():
    s, _, _ = build()
    with pytest.raises(AdminForbiddenError):
        s.update_user(SUPPORT, 1, {"full_name": "Nope"})


def test_unknown_field_refused():
    s, _, _ = build()
    with pytest.raises(Exception):
        s.update_user(SUPER, 1, {"credits_balance": 99999})   # not settable via PATCH


def test_update_records_old_and_new():
    s, _, audit = build()
    s.update_user(ADMIN, 1, {"full_name": "Renamed"}, ip="10.0.0.1")
    e = audit.list()[0][0]
    assert "U" in e.old_value and "Renamed" in e.new_value and e.ip_address == "10.0.0.1"


def test_suspend_requires_super_admin():
    s, _, _ = build()
    with pytest.raises(AdminForbiddenError):
        s.set_status(ADMIN, 1, UserStatus.SUSPENDED)
    assert s.set_status(SUPER, 1, UserStatus.SUSPENDED).status is UserStatus.SUSPENDED


def test_delete_is_soft_and_super_only():
    s, _, audit = build()
    with pytest.raises(AdminForbiddenError):
        s.delete_user(ADMIN, 1)
    assert s.delete_user(SUPER, 1, reason="fraud").status is UserStatus.BANNED
    assert audit.list()[0][0].action == "user.delete"


def test_resets_allowed_for_admin_not_support():
    s, repo, _ = build()
    assert s.reset_diagnosis(ADMIN, 1) == 1
    assert s.reset_conversations(ADMIN, 1) == 1
    assert repo.resets_for(1) == ["diagnosis", "conversations"]
    with pytest.raises(AdminForbiddenError):
        s.reset_diagnosis(SUPPORT, 1)


def test_action_on_missing_user_404s():
    s, _, _ = build()
    with pytest.raises(AdminFounderNotFoundError):
        s.update_user(ADMIN, 4242, {"full_name": "ghost"})


# --- search / filter / sort / paginate --------------------------------------


def _many():
    return [
        user(1, "Alice", "alice@a.com", plan="pro", credits=10, days_ago=1),
        user(2, "Bob", "bob@b.com", status=UserStatus.SUSPENDED, plan="free",
             credits=20, days_ago=2),
        user(3, "Carol", "carol@c.com", plan="pro", credits=30, diag=True, days_ago=3),
        user(4, "Dave", "dave@d.com", plan="free", credits=40,
             consent=ConsentStatus.MISSING, days_ago=4),
    ]


def test_search_matches_name_email_and_id():
    s, _, _ = build(_many())
    assert [u.founder_id for u in s.list_users(SUPER, filters=UserFilters(search="Alice")).items] == [1]
    assert [u.founder_id for u in s.list_users(SUPER, filters=UserFilters(search="bob@b.com")).items] == [2]
    assert [u.founder_id for u in s.list_users(SUPER, filters=UserFilters(search="3")).items] == [3]
    assert [u.founder_id for u in s.list_users(SUPER, filters=UserFilters(search="Biz 4")).items] == [4]


def test_filters():
    s, _, _ = build(_many())
    assert s.list_users(SUPER, filters=UserFilters(status=UserStatus.SUSPENDED)).total == 1
    assert s.list_users(SUPER, filters=UserFilters(subscription="pro")).total == 2
    assert s.list_users(SUPER, filters=UserFilters(diagnosis_completed=True)).total == 1
    assert s.list_users(SUPER, filters=UserFilters(consent_status=ConsentStatus.MISSING)).total == 1


def test_sort_and_pagination():
    s, _, _ = build(_many())
    asc = s.list_users(SUPER, sort_by=SortField.CREDITS_BALANCE, descending=False)
    assert [u.credits_balance for u in asc.items] == [10, 20, 30, 40]

    p1 = s.list_users(SUPER, page=1, page_size=2, sort_by=SortField.CREDITS_BALANCE,
                      descending=False)
    p2 = s.list_users(SUPER, page=2, page_size=2, sort_by=SortField.CREDITS_BALANCE,
                      descending=False)
    assert p1.total == 4 and p1.pages == 2
    assert [u.founder_id for u in p1.items] == [1, 2]
    assert [u.founder_id for u in p2.items] == [3, 4]


def test_page_size_is_capped():
    s, _, _ = build(_many())
    assert s.list_users(SUPER, page_size=10_000).page_size == 100


def test_support_can_list_users():
    s, _, _ = build(_many())
    assert s.list_users(SUPPORT).total == 4


# --- audit ------------------------------------------------------------------


def test_audit_is_append_only_and_filterable():
    s, _, audit = build(_many())
    s.update_user(ADMIN, 1, {"full_name": "X"})
    s.set_status(SUPER, 2, UserStatus.ACTIVE)
    s.adjust_credits(SUPER, 1, operation=CreditOperation.ADD, amount=5, reason="r")
    assert not hasattr(audit, "delete") and not hasattr(audit, "update")
    events, total = s.list_audit(SUPER)
    assert total == 3
    only_user_1, n = s.list_audit(SUPER, target_user_id=1)
    assert n == 2 and all(e.target_user_id == 1 for e in only_user_1)


def test_support_cannot_read_audit():
    s, _, _ = build()
    with pytest.raises(AdminForbiddenError):
        s.list_audit(SUPPORT)


def test_subscription_change_grants_credits_through_the_ledger():
    s, _, audit = build()
    result = s.update_subscription(SUPER, 1, plan="pro", monthly_credits=200,
                                   bonus_credits=50)
    assert result["changes"]["plan"] == "pro"
    assert result["changes"]["monthly_credits"]["balance_after"] == 300
    assert result["changes"]["bonus_credits"]["balance_after"] == 350
    # the grants are real ledger rows, not a balance overwrite
    rows, total = s.credits.list_transactions(1)
    assert total == 2 and {r.type for r in rows} == {CreditOperation.ADD, CreditOperation.BONUS}


def test_subscription_change_denied_for_admin():
    s, _, _ = build()
    with pytest.raises(AdminForbiddenError):
        s.update_subscription(ADMIN, 1, plan="pro")


def test_subscription_expiry_is_persisted():
    s, repo, _ = build()
    when = T0 + timedelta(days=365)
    result = s.update_subscription(SUPER, 1, expires_at=when)
    assert result["changes"]["expires_at"]["applied"] is True
    assert repo.expiry_for(1) == when
