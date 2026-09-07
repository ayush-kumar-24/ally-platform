"""Admin-side reads over `payments`.

The table was written from the day checkout shipped and read by nothing: the
dashboard summed `subscriptions` for revenue, and the user detail page showed a
plan or "No subscription record". A declined card and a founder who never tried
to pay produced the same screen.

So the cases worth pinning here are the ones that used to be invisible: failed
rows, pending rows, and a payment whose founder or subscription row is absent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.admin.payments_repository import (
    STATUSES,
    AdminPaymentsRepository,
    PaymentsUnavailableError,
)
from app.admin.rbac import PanelRole
from app.api.v1.admin.panel_dependencies import PanelAdmin, get_panel_admin
from app.db.session import get_db
from app.main import app

BASE = "/api/v1/admin"

T0 = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)

#: Every column the real table has. Most tests hand this to the repository
#: directly rather than going through `_available()`, which needs a live bind;
#: the tests that care about inspection stub `sqlalchemy.inspect` instead.
ALL_COLUMNS = {
    "payment_id", "founder_id", "subscription_id", "amount_inr", "currency",
    "status", "payment_gateway", "gateway_payment_id", "gateway_order_id",
    "invoice_url", "invoice_number", "failure_reason", "paid_at", "refunded_at",
    "created_at", "coupon_id", "list_amount_inr", "discount_inr",
}


class _Result:
    def __init__(self, rows, scalar):
        self._rows, self._scalar = rows, scalar

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeDb:
    """Records every query so a test can assert on the SQL shape and the bound
    parameters, not just the values that come back."""

    def __init__(self, rows=None, scalar=0):
        self.rows = rows or []
        self.scalar_value = scalar
        self.calls: list[tuple[str, dict]] = []

    def execute(self, clause, params=None):
        self.calls.append((str(clause), params or {}))
        return _Result(self.rows, self.scalar_value)

    def rollback(self):
        pass

    def get_bind(self):
        return "bind"


def _repo(db, *, columns=ALL_COLUMNS):
    repo = AdminPaymentsRepository(db)
    repo._cols = set(columns)
    return repo


def _payment_row(**over):
    row = {
        "payment_id": 7, "founder_id": 42, "amount_inr": Decimal("4999"),
        "currency": "INR", "status": "failed", "payment_gateway": "razorpay",
        "gateway_order_id": "order_ABC123", "gateway_payment_id": None,
        "created_at": T0, "paid_at": None, "refunded_at": None,
        "invoice_url": None, "invoice_number": None,
        "failure_reason": "card declined", "coupon_id": None,
        "list_amount_inr": None, "discount_inr": None, "subscription_id": None,
        "email": "f@x.com", "full_name": "Founder", "plan_type": None,
        "coupon_code": None,
    }
    row.update(over)
    return row


def _raises(_bind):
    raise RuntimeError("relation \"payments\" does not exist")


class _Inspector:
    def __init__(self, columns):
        self.columns = columns

    def get_columns(self, _table):
        return [{"name": c} for c in self.columns]


def _sql_for(db, marker):
    return next(sql for sql, _ in db.calls if marker in sql)


# --- the rows that used to be invisible -------------------------------------


def test_a_failed_payment_is_returned_with_its_reason():
    db = FakeDb(rows=[_payment_row()], scalar=1)
    res = _repo(db).search()

    assert res["total"] == 1
    row = res["items"][0]
    assert row["status"] == "failed"
    assert row["failure_reason"] == "card declined"
    assert row["gateway_payment_id"] is None      # never captured, so never set
    assert row["paid_at"] is None


def test_joins_are_left_so_a_payment_without_a_founder_or_plan_still_appears():
    """An INNER join would hide exactly the rows this page exists for: a failed
    payment has no subscription, and a founder erased under a DSAR has no
    founders row."""
    db = FakeDb(rows=[_payment_row(email=None, full_name=None)], scalar=1)
    res = _repo(db).search()

    sql = _sql_for(db, "gateway_order_id")
    assert "left join founders" in sql
    assert "left join subscriptions" in sql
    assert "left join coupons" in sql

    row = res["items"][0]
    assert row["founder_id"] == 42
    assert row["email"] is None


def test_ordering_never_relies_on_the_nullable_created_at_alone():
    """`payments.created_at` is nullable, so it cannot be the only sort key --
    a NULL would float to wherever the database felt like putting it."""
    db = FakeDb(rows=[], scalar=0)
    _repo(db).search()
    sql = _sql_for(db, "order by")
    assert "order by p.created_at desc nulls last, p.payment_id desc" in sql


# --- search -----------------------------------------------------------------


def test_a_gateway_id_is_matched_exactly_not_as_a_substring():
    """`order_ABC123` gets pasted whole off a Razorpay dashboard or a founder's
    screenshot; matching it with LIKE would return other orders that happen to
    share a prefix."""
    db = FakeDb(rows=[], scalar=0)
    _repo(db).search(search="order_ABC123")

    sql, params = next(c for c in db.calls if "gateway_order_id = :q_exact" in c[0])
    assert "p.gateway_payment_id = :q_exact" in sql
    assert params["q_exact"] == "order_ABC123"
    assert params["q"] == "%order_ABC123%"       # name/email still fuzzy


def test_search_is_bound_never_interpolated():
    db = FakeDb(rows=[], scalar=0)
    _repo(db).search(search="o'brien; drop table payments")
    for sql, _ in db.calls:
        assert "o'brien" not in sql


def test_an_unknown_status_is_rejected_rather_than_silently_matching_nothing():
    db = FakeDb(rows=[], scalar=0)
    with pytest.raises(ValueError):
        _repo(db).search(status="captured")      # Razorpay's word, not ours


def test_every_known_status_is_accepted():
    for status in STATUSES:
        db = FakeDb(rows=[], scalar=0)
        _repo(db).search(status=status)
        _, params = next(c for c in db.calls if "p.status = :status" in c[0])
        assert params["status"] == status


def test_founder_filter_scopes_to_one_person():
    db = FakeDb(rows=[_payment_row()], scalar=1)
    _repo(db).for_founder(42)
    _, params = next(c for c in db.calls if "p.founder_id = :fid" in c[0])
    assert params["fid"] == 42


# --- shaping ----------------------------------------------------------------


def test_amounts_come_back_as_whole_rupees_not_decimal():
    """The column is `numeric`, which arrives as Decimal -- not JSON
    serialisable, and not the UI's job to coerce."""
    db = FakeDb(rows=[_payment_row(amount_inr=Decimal("4999.00"))], scalar=1)
    row = _repo(db).search()["items"][0]
    assert row["amount_inr"] == 4999
    assert isinstance(row["amount_inr"], int)


def test_a_discounted_payment_carries_what_it_would_have_cost():
    db = FakeDb(rows=[_payment_row(status="success",
                                   amount_inr=Decimal("3999"),
                                   list_amount_inr=Decimal("4999"),
                                   discount_inr=Decimal("1000"),
                                   coupon_code="LAUNCH20",
                                   paid_at=T0)], scalar=1)
    row = _repo(db).search()["items"][0]
    assert (row["amount_inr"], row["list_amount_inr"], row["discount_inr"]) == (3999, 4999, 1000)
    assert row["coupon_code"] == "LAUNCH20"
    assert row["paid_at"] == T0.isoformat()


def test_an_undiscounted_payment_leaves_the_coupon_fields_empty():
    """NULL rather than a copy of the amount, so "was this discounted?" is
    answered by the field being set at all."""
    row = _repo(FakeDb(rows=[_payment_row()], scalar=1)).search()["items"][0]
    assert row["list_amount_inr"] is None
    assert row["discount_inr"] is None
    assert row["coupon_code"] is None


# --- summary ----------------------------------------------------------------


def test_summary_reports_every_status_even_the_ones_with_no_rows():
    """"0 failed" has to render as a zero. A status simply missing from the
    response reads as "not measured", which is a different claim."""
    db = FakeDb(rows=[{"status": "success", "count": 3, "amount_inr": Decimal("14997")}],
                scalar=0)
    summary = _repo(db).summary()

    assert set(summary["by_status"]) >= set(STATUSES)
    assert summary["by_status"]["success"] == {"count": 3, "amount_inr": 14997}
    assert summary["by_status"]["failed"] == {"count": 0, "amount_inr": 0}
    assert summary["captured_inr"] == 14997
    assert summary["total_payments"] == 3


def test_summary_keeps_a_status_nobody_wrote_this_code_for():
    db = FakeDb(rows=[{"status": "disputed", "count": 1, "amount_inr": Decimal("4999")}],
                scalar=0)
    summary = _repo(db).summary()
    assert summary["by_status"]["disputed"]["count"] == 1


def test_captured_counts_only_successful_payments():
    db = FakeDb(rows=[{"status": "failed", "count": 9, "amount_inr": Decimal("44991")}],
                scalar=0)
    summary = _repo(db).summary()
    assert summary["captured_inr"] == 0, "failed attempts are not revenue"
    assert summary["by_status"]["failed"]["count"] == 9


def test_discounts_are_summed_over_successful_payments_only():
    db = FakeDb(rows=[], scalar=1000)
    _repo(db).summary()
    sql = _sql_for(db, "sum(p.discount_inr)")
    assert "p.status = 'success'" in sql


# --- a table that is not there ----------------------------------------------


def test_an_unreadable_payments_table_raises_rather_than_reporting_zero(monkeypatch):
    """The distinction the whole module turns on: "no payments recorded" and
    "cannot read payments" send an admin to completely different places, and
    the second must never render as the first."""
    monkeypatch.setattr("sqlalchemy.inspect", _raises)
    repo = AdminPaymentsRepository(FakeDb())
    with pytest.raises(PaymentsUnavailableError):
        repo.search()
    with pytest.raises(PaymentsUnavailableError):
        repo.summary()


def test_columns_from_a_pending_migration_read_as_empty_not_as_a_failed_query():
    """Naming an absent column fails the whole statement, so the SELECT is built
    from what the database actually has."""
    lean = ALL_COLUMNS - {"discount_inr", "list_amount_inr", "coupon_id", "invoice_url"}
    db = FakeDb(rows=[_payment_row()], scalar=1)
    row = _repo(db, columns=lean).search()["items"][0]

    sql = _sql_for(db, "gateway_order_id")
    assert "null as discount_inr" in sql
    assert "null as coupon_code" in sql
    assert "left join coupons" not in sql
    assert row["discount_inr"] is None


# --- over HTTP ---------------------------------------------------------------
#
# The tests above prove the SQL; these prove the two things that only exist at
# the boundary: who is allowed to look ("did my payment go through?" is a
# support question, and this page is read-only, so answering it grants
# nothing), and that a table this environment does not have comes back as a 503
# with a sentence rather than a stack trace.

@pytest.fixture
def http(monkeypatch):
    db = FakeDb(rows=[_payment_row()], scalar=1)
    monkeypatch.setattr("sqlalchemy.inspect", lambda _bind: _Inspector(ALL_COLUMNS))

    current = {"role": PanelRole.SUPER_ADMIN}
    app.dependency_overrides[get_panel_admin] = lambda: PanelAdmin(
        admin_id=99, email="admin@goxl.in", role=current["role"])
    app.dependency_overrides[get_db] = lambda: db
    yield SimpleNamespace(client=TestClient(app), current=current, db=db)
    for dep in (get_panel_admin, get_db):
        app.dependency_overrides.pop(dep, None)


def test_support_can_list_payments(http):
    http.current["role"] = PanelRole.SUPPORT
    res = http.client.get(f"{BASE}/payments")
    assert res.status_code == 200
    assert res.json()["items"][0]["status"] == "failed"


def test_admin_can_read_one_founders_history(http):
    http.current["role"] = PanelRole.ADMIN
    res = http.client.get(f"{BASE}/users/42/payments")
    assert res.status_code == 200
    body = res.json()
    assert body["founder_id"] == 42 and body["total"] == 1


def test_an_unknown_status_is_a_422_not_an_empty_page(http):
    res = http.client.get(f"{BASE}/payments", params={"status": "captured"})
    assert res.status_code == 422


def test_a_missing_table_is_a_503_with_a_sentence(http, monkeypatch):
    monkeypatch.setattr("sqlalchemy.inspect", _raises)
    res = http.client.get(f"{BASE}/payments")
    assert res.status_code == 503
    assert "payments" in res.text.lower()


def test_the_summary_endpoint_answers_for_every_status(http):
    http.db.rows = [{"status": "success", "count": 2, "amount_inr": Decimal("9998")}]
    res = http.client.get(f"{BASE}/payments/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["captured_inr"] == 9998
    assert body["by_status"]["failed"]["count"] == 0
