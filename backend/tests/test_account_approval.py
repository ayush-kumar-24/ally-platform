"""The approval gate: who may use the product, and who is told they may.

Two properties are worth protecting here, and neither existed before.

The first is that `founders.status` means something. The column, the admin
endpoint that sets it and the audit trail behind it all shipped together, but
nothing outside the admin panel ever read the value -- so "suspend" and "ban"
wrote a string and the founder carried on with full access. Every test below
that asserts a refusal is asserting that the column is now load-bearing.

The second is that 'pending' is distinguishable from the rest. A founder
waiting for approval and a founder who has been banned are both refused, but
they are not the same situation, and the first one needs to be told something
useful rather than shown a wall.
"""

from __future__ import annotations

import pytest

from app.api.deps import (
    AccountNotActiveError,
    AccountPendingApprovalError,
    assert_account_usable,
)


class FakeFounder:
    """Only the attribute the gate reads. A real Founder row carries 60 columns
    the gate has no business knowing about."""

    def __init__(self, status):
        self.status = status


# --- who gets in ------------------------------------------------------------


def test_active_founders_are_let_through():
    assert_account_usable(FakeFounder("active")) is None


@pytest.mark.parametrize("status", [None, ""])
def test_a_missing_status_reads_as_active(status):
    """The column is nullable in some environments and absent in others (see
    users_db_repository's optional-column handling). Failing closed on absence
    would lock out every founder the moment this deploys somewhere the column
    was never backfilled -- an outage caused entirely by the safety check."""
    assert_account_usable(FakeFounder(status)) is None


def test_a_founder_row_without_the_attribute_at_all_is_let_through():
    """Same reasoning, one step further: a stub or an older mapped model that
    has no `status` at all must not take the product down."""
    class NoStatus:
        pass

    assert_account_usable(NoStatus()) is None


# --- who does not -----------------------------------------------------------


def test_pending_founders_are_refused_and_told_why():
    with pytest.raises(AccountPendingApprovalError) as exc:
        assert_account_usable(FakeFounder("pending"))
    # 403, not 401: the token is valid and refreshing it changes nothing, so the
    # frontend must not treat this as a session problem and try to recover.
    assert exc.value.status_code == 403
    assert "approval" in exc.value.message.lower()


@pytest.mark.parametrize("status", ["suspended", "banned", "inactive"])
def test_inactive_founders_are_refused(status):
    with pytest.raises(AccountNotActiveError) as exc:
        assert_account_usable(FakeFounder(status))
    assert exc.value.status_code == 403


@pytest.mark.parametrize("status", ["suspended", "banned", "inactive"])
def test_the_refusal_does_not_name_which_state_it_is(status):
    """A banned account learning it is banned rather than merely inactive gains
    nothing legitimate, and tells someone probing exactly where they stand. The
    admin panel and the audit log carry the real reason."""
    with pytest.raises(AccountNotActiveError) as exc:
        assert_account_usable(FakeFounder(status))
    assert status not in exc.value.message.lower()


def test_an_unrecognised_status_is_refused_rather_than_admitted():
    """Fail closed on a value nobody planned for. A status the CHECK constraint
    somehow permitted but this code has never heard of must not be a way in."""
    with pytest.raises(AccountNotActiveError):
        assert_account_usable(FakeFounder("some_future_state"))


# --- the two errors are distinguishable by a client -------------------------


def test_pending_and_not_active_are_different_error_types():
    """The frontend routes on these: one goes to a waiting screen that explains
    an email is coming, the other to a support message. Collapsing them into one
    error would make the common case -- a new signup waiting -- indistinguishable
    from being thrown out."""
    assert AccountPendingApprovalError is not AccountNotActiveError
    assert (AccountPendingApprovalError().__class__.__name__
            != AccountNotActiveError().__class__.__name__)
