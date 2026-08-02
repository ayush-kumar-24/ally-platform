"""Settlement wired into the repository: reads, writes, spend order, concurrency.

These run against InMemoryCreditRepository, which shares `expiry.settle` and
`buckets.plan_movements` with the SQLAlchemy implementation -- so the rules proved
here are the rules the database path executes. The Postgres-specific piece (the
`FOR UPDATE` lock) is covered by tests/test_credit_settlement_pg.py.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.credits import (
    CreditOperation,
    InsufficientCreditsError,
    InMemoryCreditRepository,
    build_credit_service,
)
from app.credits.buckets import plan_movements
from app.credits.expiry import CreditBucket, CreditState

T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
PAST = T0 - timedelta(seconds=1)
UID = 1


def repo(state: CreditState):
    return InMemoryCreditRepository({UID: state})


def svc(state: CreditState, now=T0):
    r = repo(state)
    return build_credit_service(r, clock=lambda: now), r


def adjust(s, op, amount, reason="test"):
    return s.adjust(UID, admin_id=9, operation=op, amount=amount, reason=reason)


# ── unit: bucket policy ─────────────────────────────────────────────────────


def test_grants_land_in_bonus():
    """Admin grants must not evaporate at the next renewal."""
    state = CreditState(monthly=10, bonus=5)
    after, moves = plan_movements(state, CreditOperation.ADD, 50)
    assert after.bonus == 55 and after.monthly == 10
    assert moves == [(CreditBucket.BONUS, 50)]


def test_bonus_operation_also_lands_in_bonus():
    after, moves = plan_movements(CreditState(bonus=5), CreditOperation.BONUS, 20)
    assert after.bonus == 25 and moves == [(CreditBucket.BONUS, 20)]


def test_deduction_drains_monthly_first():
    after, moves = plan_movements(CreditState(monthly=30, bonus=100),
                                  CreditOperation.REMOVE, 20)
    assert (after.monthly, after.bonus) == (10, 100)
    assert moves == [(CreditBucket.MONTHLY, -20)]


def test_deduction_spanning_buckets_yields_two_movements():
    """One row cannot honestly claim both buckets, so there are two."""
    after, moves = plan_movements(CreditState(monthly=20, bonus=50),
                                  CreditOperation.REMOVE, 35)
    assert (after.monthly, after.bonus) == (0, 35)
    assert moves == [(CreditBucket.MONTHLY, -20), (CreditBucket.BONUS, -15)]


def test_set_up_adds_to_bonus_set_down_uses_spend_order():
    up, moves_up = plan_movements(CreditState(monthly=10, bonus=10), CreditOperation.SET, 50)
    assert up.total == 50 and moves_up == [(CreditBucket.BONUS, 30)]

    down, moves_down = plan_movements(CreditState(monthly=10, bonus=10),
                                      CreditOperation.SET, 5)
    assert down.total == 5
    assert moves_down == [(CreditBucket.MONTHLY, -10), (CreditBucket.BONUS, -5)]


def test_set_to_current_total_is_a_no_op():
    state = CreditState(monthly=10, bonus=10)
    after, moves = plan_movements(state, CreditOperation.SET, 20)
    assert after == state and moves == []


def test_deduction_beyond_total_is_refused():
    with pytest.raises(ValueError, match="insufficient"):
        plan_movements(CreditState(monthly=5, bonus=5), CreditOperation.REMOVE, 11)


# ── requirement 1: reads settle ─────────────────────────────────────────────


def test_reading_balance_settles_expiry():
    """A read must not report credits that have already expired."""
    r = repo(CreditState(monthly=100, bonus=25, expires_at=PAST))
    assert r.get_balance(UID).balance == 25          # not 125
    rows, _ = r.list_transactions(UID)
    assert [x.type for x in rows] == [CreditOperation.EXPIRE]


def test_reading_balance_settles_renewal():
    r = repo(CreditState(monthly=0, bonus=0, monthly_allowance=200, renewal_date=PAST))
    assert r.get_balance(UID).balance == 200
    assert r.get_state(UID).renewal_date > T0


def test_read_when_nothing_due_writes_no_rows():
    r = repo(CreditState(monthly=50, bonus=10,
                         expires_at=T0 + timedelta(days=10),
                         renewal_date=T0 + timedelta(days=10)))
    r.get_balance(UID)
    assert r.list_transactions(UID)[1] == 0


# ── requirement 2 & 5: writes settle; expired credits are unspendable ───────


def test_write_settles_before_applying():
    s, r = svc(CreditState(monthly=100, bonus=20, expires_at=PAST))
    tx = adjust(s, CreditOperation.ADD, 5)
    # Settlement ran first, so the operation started from 20, not 120.
    assert tx.balance_before == 20 and tx.balance_after == 25


def test_expired_monthly_credits_cannot_be_spent():
    """The core guarantee: 100 expired monthly + 10 bonus cannot fund a 50 spend."""
    s, _ = svc(CreditState(monthly=100, bonus=10, expires_at=PAST))
    with pytest.raises(InsufficientCreditsError):
        adjust(s, CreditOperation.REMOVE, 50)


def test_unexpired_monthly_credits_can_be_spent():
    s, _ = svc(CreditState(monthly=100, bonus=10, expires_at=T0 + timedelta(days=5)))
    assert adjust(s, CreditOperation.REMOVE, 50).balance_after == 60


def test_failed_spend_rolls_settlement_back_with_the_operation():
    """Settlement shares the operation's transaction, so a rejected spend discards
    it too. Nothing is lost: settlement is a pure function of stored state and
    time, so the very next access re-derives it -- as asserted below."""
    s, r = svc(CreditState(monthly=100, bonus=10, expires_at=PAST))
    with pytest.raises(InsufficientCreditsError):
        adjust(s, CreditOperation.REMOVE, 50)
    assert r.list_transactions(UID)[1] == 0            # rolled back with the operation

    # Re-derived on the next read, and the balance is still correct.
    assert r.get_balance(UID).balance == 10
    rows, total = r.list_transactions(UID)
    assert total == 1 and rows[0].type is CreditOperation.EXPIRE


# ── requirement 6: spend order through the service ─────────────────────────


def test_spend_order_monthly_then_bonus_end_to_end():
    s, r = svc(CreditState(monthly=20, bonus=50, expires_at=T0 + timedelta(days=5)))
    tx = adjust(s, CreditOperation.REMOVE, 35)
    assert tx.balance_before == 70 and tx.balance_after == 35
    state = r.get_state(UID)
    assert (state.monthly, state.bonus) == (0, 35)
    rows, _ = r.list_transactions(UID)
    assert [x.amount for x in rows] == [-15, -20]     # newest first: bonus then monthly


# ── requirement 7: multiple missed renewals ────────────────────────────────


def test_multiple_missed_renewals_are_all_settled():
    r = repo(CreditState(monthly=0, bonus=5, monthly_allowance=100,
                         renewal_date=T0 - timedelta(days=95)))
    assert r.get_balance(UID).balance == 105          # 100 granted + 5 bonus
    rows, _ = r.list_transactions(UID)
    renewals = [x for x in rows if x.type is CreditOperation.RENEW]
    assert len(renewals) >= 3                          # one per elapsed period
    assert r.get_state(UID).renewal_date > T0


def test_missed_periods_do_not_accumulate_allowance():
    """Three missed months grant 100, not 300 -- that is what 'expires' means."""
    r = repo(CreditState(monthly=0, bonus=0, monthly_allowance=100,
                         renewal_date=T0 - timedelta(days=95)))
    assert r.get_balance(UID).balance == 100


# ── requirement 4: idempotency ─────────────────────────────────────────────


def test_repeated_settlement_writes_nothing_extra():
    r = repo(CreditState(monthly=100, bonus=0, expires_at=PAST))
    r.get_balance(UID)
    after_first = r.list_transactions(UID)[1]
    for _ in range(5):
        r.get_balance(UID)
    assert r.list_transactions(UID)[1] == after_first


def test_settle_only_reports_rows_written():
    r = repo(CreditState(monthly=100, bonus=0, expires_at=PAST))
    _, first = r.settle_only(UID, T0)
    _, second = r.settle_only(UID, T0)
    assert first == 1 and second == 0


# ── requirement 8: ledger compatibility ────────────────────────────────────


def test_ledger_chain_is_unbroken_across_settlement_and_operations():
    """balance_before of every row equals balance_after of the previous one, even
    when settlement rows are interleaved with admin operations."""
    s, r = svc(CreditState(monthly=50, bonus=50, expires_at=PAST, monthly_allowance=0))
    adjust(s, CreditOperation.ADD, 10)
    adjust(s, CreditOperation.REMOVE, 20)
    rows, _ = r.list_transactions(UID, limit=100)
    chron = list(reversed(rows))
    for prev, nxt in zip(chron, chron[1:]):
        assert nxt.balance_before == prev.balance_after
    assert chron[-1].balance_after == r.get_balance(UID).balance


def test_settlement_rows_are_attributed_to_the_system_not_an_admin():
    s, r = svc(CreditState(monthly=100, bonus=0, expires_at=PAST))
    adjust(s, CreditOperation.ADD, 1)
    rows, _ = r.list_transactions(UID)
    expire = next(x for x in rows if x.type is CreditOperation.EXPIRE)
    admin_row = next(x for x in rows if x.type is CreditOperation.ADD)
    assert expire.admin_id == 0 and admin_row.admin_id == 9


def test_legacy_int_balances_are_treated_as_bonus():
    """Existing balances were granted with no expiry; they must not vanish."""
    r = InMemoryCreditRepository({UID: 250})
    state = r.get_state(UID)
    assert (state.monthly, state.bonus) == (0, 250)
    assert r.get_balance(UID).balance == 250


# ── requirement 11: concurrent settlement ──────────────────────────────────


def test_concurrent_reads_settle_expiry_exactly_once():
    """40 threads reading a balance with expiry due must produce ONE expire row."""
    r = repo(CreditState(monthly=100, bonus=10, expires_at=PAST))

    with ThreadPoolExecutor(max_workers=8) as pool:
        balances = list(pool.map(lambda _: r.get_balance(UID).balance, range(40)))

    assert set(balances) == {10}
    rows, total = r.list_transactions(UID, limit=100)
    assert total == 1 and rows[0].type is CreditOperation.EXPIRE


def test_concurrent_writes_settle_once_and_do_not_lose_updates():
    s, r = svc(CreditState(monthly=100, bonus=0, expires_at=PAST))

    def add(_):
        return adjust(s, CreditOperation.ADD, 1, reason="concurrent")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(add, range(30)))

    assert r.get_balance(UID).balance == 30           # expired 100 gone, 30 added
    rows, total = r.list_transactions(UID, limit=100)
    assert len([x for x in rows if x.type is CreditOperation.EXPIRE]) == 1
    assert total == 31                                 # 1 expire + 30 adds


def test_concurrent_spends_never_go_negative_after_expiry():
    """Balance is 20 bonus once the expired monthly is settled; only 4 spends of 5
    can succeed no matter how many threads race."""
    r = repo(CreditState(monthly=999, bonus=20, expires_at=PAST))
    s = build_credit_service(r, clock=lambda: T0)
    ok, refused = [], []

    def take(_):
        try:
            ok.append(adjust(s, CreditOperation.REMOVE, 5, reason="race"))
        except InsufficientCreditsError:
            refused.append(1)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(take, range(20)))

    assert len(ok) == 4 and len(refused) == 16
    assert r.get_balance(UID).balance == 0


def test_concurrent_renewals_grant_one_period_only():
    r = repo(CreditState(monthly=0, bonus=0, monthly_allowance=50, renewal_date=PAST))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: r.get_balance(UID), range(25)))

    assert r.get_balance(UID).balance == 50
    rows, _ = r.list_transactions(UID, limit=100)
    assert len([x for x in rows if x.type is CreditOperation.RENEW]) == 1
