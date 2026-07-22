"""Repository CRUD tests -- exercise the generic base against a real table.

Everything runs inside one transaction that is rolled back at the end, so the
database is left exactly as it was found (verified by the surrounding fixtures in
conftest not needed here -- we assert nothing persists).
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models import Founder
from app.repositories import BaseRepository, founder_repository


@pytest.fixture
def db():
    """A session on a connection wrapped in a transaction that is always rolled
    back -- create/update/delete run for real, then vanish."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


def _seed_auth_user(db) -> uuid.UUID:
    uid = uuid.uuid4()
    db.execute(text("insert into auth.users (id, email) values (:i, :e)"),
               {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    return uid


def _new_founder_data(uid) -> dict:
    return {"user_id": uid, "full_name": "Repo Test", "email": f"t{uid.hex[:8]}@x.com"}


def test_create_and_get(db):
    uid = _seed_auth_user(db)
    created = founder_repository.create(db, _new_founder_data(uid), commit=False)
    assert created.founder_id is not None  # PK assigned by the DB

    fetched = founder_repository.get(db, created.founder_id)
    assert fetched is not None
    assert fetched.full_name == "Repo Test"


def test_get_by_and_missing(db):
    uid = _seed_auth_user(db)
    founder_repository.create(db, _new_founder_data(uid), commit=False)

    assert founder_repository.get_by_user_id(db, uid) is not None
    assert founder_repository.get_by_user_id(db, uuid.uuid4()) is None
    assert founder_repository.get(db, 999_999_999) is None


def test_update_partial(db):
    uid = _seed_auth_user(db)
    obj = founder_repository.create(db, _new_founder_data(uid), commit=False)

    updated = founder_repository.update(db, obj, {"industry": "saas"}, commit=False)
    assert updated.industry == "saas"
    assert updated.full_name == "Repo Test"  # untouched field preserved


def test_count_and_list(db):
    uid = _seed_auth_user(db)
    obj = founder_repository.create(db, _new_founder_data(uid), commit=False)

    assert founder_repository.count(db, user_id=uid) == 1
    rows = founder_repository.list(db, user_id=uid, limit=10)
    assert [r.founder_id for r in rows] == [obj.founder_id]


def test_delete(db):
    uid = _seed_auth_user(db)
    obj = founder_repository.create(db, _new_founder_data(uid), commit=False)
    fid = obj.founder_id

    founder_repository.delete(db, obj, commit=False)
    assert founder_repository.get(db, fid) is None


def test_composite_pk_rejected():
    """The base guards against its single-PK assumption. No model in this schema
    has a composite key, so use a throwaway class to prove the guard fires."""
    from sqlalchemy.orm import Mapped, declarative_base, mapped_column

    throwaway_base = declarative_base()

    class Combo(throwaway_base):
        __tablename__ = "combo_guard_test"
        a: Mapped[int] = mapped_column(primary_key=True)
        b: Mapped[int] = mapped_column(primary_key=True)

    with pytest.raises(ValueError, match="composite primary key"):
        BaseRepository(Combo)
