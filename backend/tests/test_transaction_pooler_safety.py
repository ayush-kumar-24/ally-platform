"""What the app must get right before DATABASE_URL points at port 6543.

Supabase's transaction pooler (Supavisor on :6543, and the dedicated PgBouncer
on the same port) has two properties the session-mode pooler does not:

  1. It does NOT support prepared statements. psycopg3 prepares a statement
     server-side after it has seen it `prepare_threshold` times -- 5 by
     default -- so without this every query the app runs more than a handful
     of times eventually lands on a backend connection that never prepared it
     and raises `prepared statement "_pg3_0" already exists`/`does not exist`.
     Sporadic, and it looks like anything but configuration.

  2. A backend connection carries session state to whoever gets it next, so a
     plain `SET` leaks between founders. This app's RLS context is set with
     `set_config(..., true)` -- the third argument is is_local, which scopes it
     to the transaction -- which is correct under both poolers.

Both are asserted here rather than left to a deploy going wrong.
"""

import importlib

import pytest

from app.core.config import Settings

SESSION_URL = "postgresql+psycopg://u:p@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
TRANSACTION_URL = "postgresql+psycopg://u:p@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"


def _settings(url: str) -> Settings:
    return Settings(DATABASE_URL=url, SECRET_KEY="x" * 20)


def test_transaction_pooler_is_recognised_by_port():
    assert _settings(TRANSACTION_URL).uses_transaction_pooler
    assert not _settings(SESSION_URL).uses_transaction_pooler


def test_pool_is_sized_for_the_pooler_the_url_names():
    session, transaction = _settings(SESSION_URL), _settings(TRANSACTION_URL)

    # Session mode shares a hard ceiling of 15 client connections with every
    # other process; two instances at 2+4 leave room for a migration.
    assert (session.DB_POOL_SIZE + session.DB_POOL_MAX_OVERFLOW) * 2 <= 15
    # Transaction mode is not subject to that ceiling, and should not be sized
    # as though it were.
    assert transaction.DB_POOL_SIZE > session.DB_POOL_SIZE


def test_an_explicit_pool_size_is_never_overridden():
    explicit = Settings(DATABASE_URL=TRANSACTION_URL, SECRET_KEY="x" * 20, DB_POOL_SIZE=3)
    assert explicit.DB_POOL_SIZE == 3


@pytest.mark.parametrize(
    "url,expected",
    [(TRANSACTION_URL, {"prepare_threshold": None}), (SESSION_URL, {})],
)
def test_prepared_statements_are_off_only_on_the_transaction_pooler(monkeypatch, url, expected):
    """The engine's connect_args, built from the URL at import time."""
    import app.core.config as config_module

    monkeypatch.setattr(config_module, "settings", _settings(url))

    import app.db.session as session_module

    monkeypatch.setattr(session_module, "settings", _settings(url))
    reloaded = importlib.reload(session_module)
    try:
        assert reloaded._connect_args == expected
    finally:
        # Leave the module bound to the real settings for the rest of the run.
        monkeypatch.undo()
        importlib.reload(session_module)


def test_rls_context_is_transaction_local_not_session_state():
    """`set_config(..., true)` -- the `true` is what keeps it off the pooled
    connection once the transaction ends. A plain SET here would leak one
    founder's RLS context to whoever got that backend connection next."""
    source = (importlib.import_module("app.db.session").__file__)
    with open(source) as fh:
        text = fh.read()

    assert "set_config(" in text
    assert "'app.current_founder_uuid', " in text
    assert "true)" in text
    # A session-scoped SET of the RLS context would be the bug this guards.
    assert "SET app.current_founder_uuid" not in text
