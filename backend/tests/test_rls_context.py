from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api import deps as api_deps
from app.db.session import _apply_rls_context, set_founder_rls_context
from app.services import provisioning


FOUNDER_UUID = "11111111-1111-4111-8111-111111111111"


def test_after_begin_applies_transaction_local_founder_context():
    session = MagicMock()
    session.info = {"current_founder_uuid": FOUNDER_UUID}
    connection = MagicMock()

    _apply_rls_context(session, None, connection)

    connection.execute.assert_called_once()
    statement, params = connection.execute.call_args.args
    sql = str(statement)

    assert "app.current_founder_uuid" in sql
    assert "true" in sql.lower()
    assert params == {"founder_uuid": FOUNDER_UUID}


def test_set_founder_context_applies_immediately_inside_active_transaction():
    db = MagicMock()
    db.info = {}
    db.in_transaction.return_value = True

    set_founder_rls_context(db, FOUNDER_UUID)

    assert db.info["current_founder_uuid"] == FOUNDER_UUID
    db.execute.assert_called_once()

    statement, params = db.execute.call_args.args
    assert "app.current_founder_uuid" in str(statement)
    assert "true" in str(statement).lower()
    assert params == {"founder_uuid": FOUNDER_UUID}


def test_provisioning_sets_context_before_founder_lookup(monkeypatch):
    events = []
    existing = object()
    db = MagicMock()

    identity = SimpleNamespace(
        id=FOUNDER_UUID,
        email="founder@example.com",
        provider="supabase",
    )

    monkeypatch.setattr(
        provisioning,
        "set_founder_rls_context",
        lambda db, founder_uuid: events.append(("context", founder_uuid)),
    )

    monkeypatch.setattr(
        provisioning.founder_repository,
        "get_by_user_id",
        lambda db, user_uuid: events.append(("lookup", str(user_uuid))) or existing,
    )

    result = provisioning.ensure_founder(identity, db)

    assert result is existing
    assert events == [
        ("context", FOUNDER_UUID),
        ("lookup", FOUNDER_UUID),
    ]


def test_api_dependency_sets_context_before_founder_lookup(monkeypatch):
    events = []
    founder = object()
    db = MagicMock()

    auth_user = SimpleNamespace(id=FOUNDER_UUID)

    monkeypatch.setattr(
        api_deps,
        "set_founder_rls_context",
        lambda db, founder_uuid: events.append(("context", founder_uuid)),
    )

    monkeypatch.setattr(
        api_deps.founder_repository,
        "get_by_user_id",
        lambda db, user_uuid: events.append(("lookup", str(user_uuid))) or founder,
    )

    result = api_deps.get_founder_record(auth_user=auth_user, db=db)

    assert result is founder
    assert events == [
        ("context", FOUNDER_UUID),
        ("lookup", FOUNDER_UUID),
    ]