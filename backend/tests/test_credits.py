"""Credit ledger tests: arithmetic, guards, ledger integrity, concurrency."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from app.credits import (
    CreditOperation,
    InsufficientCreditsError,
    InvalidCreditAmountError,
    InMemoryCreditRepository,
    MissingReasonError,
    UserNotFoundError,
    build_credit_service,
)

T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
UID = 1


def svc(balance=100):
    repo = InMemoryCreditRepository({UID: balance})
    return build_credit_service(repo, clock=lambda: T0), repo


def adjust(s, op, amount, reason="test"):
    return s.adjust(UID, admin_id=9, operation=op, amount=amount, reason=reason)


# --- arithmetic -------------------------------------------------------------


def test_add():
    s, _ = svc(100)
    tx = adjust(s, CreditOperation.ADD, 50)
    assert (tx.balance_before, tx.amount, tx.balance_after) == (100, 50, 150)


def test_remove():
    s, _ = svc(100)
    tx = adjust(s, CreditOperation.REMOVE, 30)
    assert (tx.balance_before, tx.amount, tx.balance_after) == (100, -30, 70)


def test_set_up_and_down():
    s, _ = svc(100)
    assert adjust(s, CreditOperation.SET, 250).balance_after == 250
    assert adjust(s, CreditOperation.SET, 10).balance_after == 10


def test_set_to_zero_allowed():
    s, _ = svc(100)
    tx = adjust(s, CreditOperation.SET, 0)
    assert tx.balance_after == 0 and tx.amount == -100


def test_bonus_is_additive_but_tagged():
    s, _ = svc(100)
    tx = adjust(s, CreditOperation.BONUS, 25)
    assert tx.balance_after == 125 and tx.type is CreditOperation.BONUS


# --- guards -----------------------------------------------------------------


def test_no_negative_balance():
    s, _ = svc(50)
    with pytest.raises(InsufficientCreditsError):
        adjust(s, CreditOperation.REMOVE, 51)


def test_failed_removal_leaves_no_trace():
    """A rejected operation must not append a ledger row or move the balance."""
    s, _ = svc(50)
    with pytest.raises(InsufficientCreditsError):
        adjust(s, CreditOperation.REMOVE, 999)
    assert s.get_balance(UID).balance == 50
    assert s.list_transactions(UID)[1] == 0


def test_set_negative_rejected():
    s, _ = svc(50)
    with pytest.raises(InvalidCreditAmountError):
        adjust(s, CreditOperation.SET, -1)


def test_negative_amount_rejected():
    s, _ = svc()
    with pytest.raises(InvalidCreditAmountError):
        adjust(s, CreditOperation.ADD, -10)


def test_zero_add_rejected_but_zero_set_allowed():
    s, _ = svc()
    with pytest.raises(InvalidCreditAmountError):
        adjust(s, CreditOperation.ADD, 0)
    assert adjust(s, CreditOperation.SET, 0).balance_after == 0


def test_reason_required():
    s, _ = svc()
    with pytest.raises(MissingReasonError):
        adjust(s, CreditOperation.ADD, 5, reason="   ")


def test_amount_ceiling():
    s, _ = svc()
    with pytest.raises(InvalidCreditAmountError):
        adjust(s, CreditOperation.ADD, 1_000_001)


def test_unknown_user():
    s, _ = svc()
    with pytest.raises(UserNotFoundError):
        s.adjust(999, admin_id=1, operation=CreditOperation.ADD, amount=5, reason="x")


# --- ledger integrity -------------------------------------------------------


def test_ledger_is_append_only_and_chains():
    s, _ = svc(0)
    adjust(s, CreditOperation.ADD, 100)
    adjust(s, CreditOperation.REMOVE, 40)
    adjust(s, CreditOperation.BONUS, 10)
    rows, total = s.list_transactions(UID)
    assert total == 3
    chron = list(reversed(rows))                       # oldest first
    assert [r.balance_after for r in chron] == [100, 60, 70]
    # every row's before == previous row's after
    for prev, nxt in zip(chron, chron[1:]):
        assert nxt.balance_before == prev.balance_after


def test_balance_matches_last_row():
    s, _ = svc(0)
    adjust(s, CreditOperation.ADD, 75)
    rows, _ = s.list_transactions(UID)
    assert s.get_balance(UID).balance == rows[0].balance_after


def test_pagination():
    s, _ = svc(0)
    for i in range(1, 6):
        adjust(s, CreditOperation.ADD, i)
    page1, total = s.list_transactions(UID, limit=2, offset=0)
    page2, _ = s.list_transactions(UID, limit=2, offset=2)
    assert total == 5 and len(page1) == 2 and len(page2) == 2
    assert {t.id for t in page1}.isdisjoint({t.id for t in page2})


# --- concurrency ------------------------------------------------------------


def test_concurrent_adds_do_not_lose_updates():
    """40 parallel +1s must land exactly 40 credits — no lost updates."""
    s, _ = svc(0)

    def add(_):
        return adjust(s, CreditOperation.ADD, 1, reason="concurrent")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(add, range(40)))

    assert s.get_balance(UID).balance == 40
    rows, total = s.list_transactions(UID, limit=100)
    assert total == 40
    # The ledger must form one unbroken chain even under interleaving.
    chron = list(reversed(rows))
    assert [r.balance_after for r in chron] == list(range(1, 41))


def test_concurrent_removals_never_go_negative():
    """20 threads racing to remove 10 from a balance of 50: at most 5 succeed."""
    s, _ = svc(50)
    ok, refused = [], []

    def remove(_):
        try:
            ok.append(adjust(s, CreditOperation.REMOVE, 10, reason="race"))
        except InsufficientCreditsError:
            refused.append(1)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(remove, range(20)))

    assert len(ok) == 5 and len(refused) == 15
    assert s.get_balance(UID).balance == 0
