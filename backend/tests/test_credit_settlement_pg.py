"""Integration: settlement through the real SQLAlchemy repository against Postgres.

Everything runs inside ONE transaction that is rolled back, so the production schema
and data are untouched. The transient DDL (adding the credit columns, creating
credit_transactions, dropping the auth.users FK so a test founder can be inserted)
is undone by the same rollback -- Postgres has transactional DDL.

Skipped automatically when no database is reachable, so the suite stays hermetic.

Scope note: because the schema lives in an uncommitted transaction, a second
*session* cannot see it. These tests therefore verify the SQL, the settlement
ordering and the ledger chain -- not multi-session `FOR UPDATE` contention, which
needs a committed schema. The lock semantics are covered logically in
tests/test_credit_settlement.py.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.credits.db_repository import SqlAlchemyCreditRepository
from app.credits.errors import InsufficientCreditsError
from app.credits.models import CreditOperation
from app.credits.service import CreditService

T0 = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
PAST = T0 - timedelta(seconds=1)

_COLUMNS = (
    ("monthly_credits", "integer not null default 0"),
    ("bonus_credits", "integer not null default 0"),
    ("credits_balance", "integer not null default 0"),
    ("credits_expires_at", "timestamptz"),
    ("credits_renewal_date", "timestamptz"),
    ("monthly_credit_allowance", "integer not null default 0"),
)

_LEDGER_DDL = """
create table credit_transactions (
    id serial primary key,
    user_id integer not null,
    admin_id integer not null,
    type varchar(20) not null,
    bucket varchar(10) not null default 'bonus',
    amount integer not null,
    balance_before integer not null,
    balance_after integer not null,
    reason text not null,
    created_at timestamptz not null default now(),
    constraint credit_transactions_type_check
        check (type in ('add','remove','set','bonus','expire','renew','consume')),
    constraint credit_transactions_bucket_check check (bucket in ('monthly','bonus')),
    constraint credit_transactions_after_non_negative check (balance_after >= 0)
)
"""


@pytest.fixture
def pg():
    """Live connection with a transient credit schema, rolled back on teardown."""
    try:
        from app.db.session import engine
        conn = engine.connect()
    except Exception as exc:                                    # pragma: no cover
        pytest.skip(f"no database available: {exc}")

    trans = conn.begin()
    try:
        conn.execute(text("select 1"))
        fk = conn.execute(text("""select conname from pg_constraint
                                   where conrelid='founders'::regclass and contype='f'
                                     and conname like '%user_id%'""")).scalar()
        if fk:
            conn.execute(text(f'alter table founders drop constraint "{fk}"'))
        for name, ddl in _COLUMNS:
            conn.execute(text(f"alter table founders add column if not exists {name} {ddl}"))
        conn.execute(text("drop table if exists credit_transactions"))
        conn.execute(text(_LEDGER_DDL))
    except Exception as exc:                                    # pragma: no cover
        trans.rollback()
        conn.close()
        pytest.skip(f"could not prepare transient schema: {exc}")

    db = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield conn, db
    db.close()
    trans.rollback()
    conn.close()


def _founder(conn, *, monthly=0, bonus=0, allowance=0, expires=None, renews=None) -> int:
    import uuid
    fid = conn.execute(text("""
        insert into founders (user_id, full_name, email, monthly_credits, bonus_credits,
                              credits_balance, credits_expires_at, credits_renewal_date,
                              monthly_credit_allowance)
        values (:u, 'PG Test', :e, :m, :b, :t, :exp, :ren, :al)
        returning founder_id"""),
        {"u": str(uuid.uuid4()), "e": f"pg-{uuid.uuid4().hex[:8]}@example.com",
         "m": monthly, "b": bonus, "t": monthly + bonus,
         "exp": expires, "ren": renews, "al": allowance}).scalar()
    return fid


def _rows(conn, fid):
    return conn.execute(text("""select type, bucket, amount, balance_before, balance_after,
                                       admin_id
                                  from credit_transactions where user_id = :f
                                 order by id"""), {"f": fid}).mappings().all()


def _stored(conn, fid):
    return conn.execute(text("""select monthly_credits, bonus_credits, credits_balance,
                                       credits_expires_at, credits_renewal_date
                                  from founders where founder_id = :f"""),
                        {"f": fid}).mappings().first()


# --- reads settle -----------------------------------------------------------


def test_read_settles_expiry_in_postgres(pg):
    conn, db = pg
    fid = _founder(conn, monthly=100, bonus=25, expires=PAST)
    repo = SqlAlchemyCreditRepository(db)

    assert repo.get_balance(fid).balance == 25
    rows = _rows(conn, fid)
    assert [r["type"] for r in rows] == ["expire"]
    assert rows[0]["bucket"] == "monthly" and rows[0]["admin_id"] == 0
    stored = _stored(conn, fid)
    assert stored["monthly_credits"] == 0 and stored["credits_balance"] == 25


def test_read_settles_renewal_in_postgres(pg):
    conn, db = pg
    fid = _founder(conn, allowance=200, renews=PAST)
    repo = SqlAlchemyCreditRepository(db)

    assert repo.get_balance(fid).balance == 200
    assert [r["type"] for r in _rows(conn, fid)] == ["renew"]
    assert _stored(conn, fid)["credits_renewal_date"] > T0


def test_read_with_nothing_due_writes_nothing(pg):
    conn, db = pg
    fid = _founder(conn, monthly=40, bonus=10,
                   expires=T0 + timedelta(days=10), renews=T0 + timedelta(days=10))
    SqlAlchemyCreditRepository(db).get_balance(fid)
    assert _rows(conn, fid) == []


# --- writes settle first ----------------------------------------------------


def test_write_settles_before_applying(pg):
    conn, db = pg
    fid = _founder(conn, monthly=100, bonus=20, expires=PAST)
    svc = CreditService(SqlAlchemyCreditRepository(db), clock=lambda: T0)

    tx = svc.adjust(fid, admin_id=7, operation=CreditOperation.ADD, amount=5, reason="r")
    assert tx.balance_before == 20 and tx.balance_after == 25
    types = [r["type"] for r in _rows(conn, fid)]
    assert types == ["expire", "add"]                  # settlement first, then the op


def test_expired_credits_cannot_be_spent_in_postgres(pg):
    conn, db = pg
    fid = _founder(conn, monthly=100, bonus=10, expires=PAST)
    svc = CreditService(SqlAlchemyCreditRepository(db), clock=lambda: T0)

    with pytest.raises(InsufficientCreditsError):
        svc.adjust(fid, admin_id=7, operation=CreditOperation.REMOVE, amount=50, reason="r")

    # Settlement shares the operation's transaction, so the rollback discards it
    # too -- no half-applied state is left behind.
    assert _rows(conn, fid) == []

    # And nothing is lost: the next read re-derives the expiry from the stored
    # dates, so the balance the user sees is still correct.
    assert SqlAlchemyCreditRepository(db).get_balance(fid).balance == 10
    assert [r["type"] for r in _rows(conn, fid)] == ["expire"]


def test_spend_order_writes_one_row_per_bucket(pg):
    conn, db = pg
    fid = _founder(conn, monthly=20, bonus=50, expires=T0 + timedelta(days=5))
    svc = CreditService(SqlAlchemyCreditRepository(db), clock=lambda: T0)

    tx = svc.adjust(fid, admin_id=7, operation=CreditOperation.REMOVE, amount=35, reason="r")
    assert tx.balance_before == 70 and tx.balance_after == 35

    rows = _rows(conn, fid)
    assert [(r["bucket"], r["amount"]) for r in rows] == [("monthly", -20), ("bonus", -15)]
    stored = _stored(conn, fid)
    assert (stored["monthly_credits"], stored["bonus_credits"]) == (0, 35)


# --- multiple missed renewals ----------------------------------------------


def test_multiple_missed_renewals_in_postgres(pg):
    conn, db = pg
    fid = _founder(conn, bonus=5, allowance=100, renews=T0 - timedelta(days=95))
    repo = SqlAlchemyCreditRepository(db)

    assert repo.get_balance(fid).balance == 105
    renewals = [r for r in _rows(conn, fid) if r["type"] == "renew"]
    assert len(renewals) >= 3
    assert _stored(conn, fid)["credits_renewal_date"] > T0


# --- idempotency ------------------------------------------------------------


def test_settlement_is_idempotent_in_postgres(pg):
    conn, db = pg
    fid = _founder(conn, monthly=100, expires=PAST)
    repo = SqlAlchemyCreditRepository(db)

    for _ in range(5):
        repo.get_balance(fid)
    assert len(_rows(conn, fid)) == 1

    _, written = repo.settle_only(fid, T0)
    assert written == 0


# --- ledger integrity -------------------------------------------------------


def test_ledger_chain_unbroken_across_settlement_and_ops(pg):
    conn, db = pg
    fid = _founder(conn, monthly=50, bonus=50, expires=PAST)
    svc = CreditService(SqlAlchemyCreditRepository(db), clock=lambda: T0)
    svc.adjust(fid, admin_id=7, operation=CreditOperation.ADD, amount=10, reason="a")
    svc.adjust(fid, admin_id=7, operation=CreditOperation.REMOVE, amount=20, reason="b")

    rows = _rows(conn, fid)
    for prev, nxt in zip(rows, rows[1:]):
        assert nxt["balance_before"] == prev["balance_after"]
    assert rows[-1]["balance_after"] == _stored(conn, fid)["credits_balance"]


def test_balance_cache_matches_buckets(pg):
    """credits_balance is a cache of monthly + bonus; it must never drift."""
    conn, db = pg
    fid = _founder(conn, monthly=30, bonus=20, expires=T0 + timedelta(days=5))
    svc = CreditService(SqlAlchemyCreditRepository(db), clock=lambda: T0)
    svc.adjust(fid, admin_id=7, operation=CreditOperation.BONUS, amount=15, reason="r")

    s = _stored(conn, fid)
    assert s["credits_balance"] == s["monthly_credits"] + s["bonus_credits"] == 65


def test_list_transactions_does_not_settle(pg):
    """Paging through history must never mutate it."""
    conn, db = pg
    fid = _founder(conn, monthly=100, expires=PAST)
    repo = SqlAlchemyCreditRepository(db)

    _, total = repo.list_transactions(fid)
    assert total == 0                                   # no expire row written by a read
    assert _stored(conn, fid)["monthly_credits"] == 100


def test_unknown_user_raises(pg):
    _, db = pg
    from app.credits.errors import UserNotFoundError
    with pytest.raises(UserNotFoundError):
        SqlAlchemyCreditRepository(db).get_balance(987654321)
