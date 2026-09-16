"""The app never runs itself on Supabase's session-mode pooler.

Three of ten end-to-end runs died with "server closed the connection
unexpectedly", one of them 582 seconds in, mid-COMMIT. All of them were on
DATABASE_URL port 5432 -- session mode, where the whole Supabase project shares
fifteen connections held for the life of a client session. Port 6543 borrows a
connection per transaction and hands it straight back.

Both ports are the same pooler endpoint, so for a *.pooler.supabase.com host the
swap is a mode change and nothing else. That is the only case that is rewritten:
on any other host, 5432 is the only port there is.
"""

import pytest

from app.db.session import runtime_database_url

POOLER = "postgresql+psycopg://postgres.abc:pw@aws-1-eu-west-2.pooler.supabase.com"


def test_a_session_pooler_url_is_moved_to_transaction_mode():
    url, note = runtime_database_url(f"{POOLER}:5432/postgres")
    assert url == f"{POOLER}:6543/postgres"
    assert note


def test_the_note_says_what_changed_and_how_to_make_it_permanent():
    _, note = runtime_database_url(f"{POOLER}:5432/postgres")
    assert "5432" in note and "6543" in note
    assert "backend/.env" in note
    assert "DB_SESSION_POOLER_OK" in note


def test_a_transaction_pooler_url_is_left_alone():
    url, note = runtime_database_url(f"{POOLER}:6543/postgres")
    assert url == f"{POOLER}:6543/postgres"
    assert note == ""


@pytest.mark.parametrize("url", [
    # Direct Supabase connection: 5432 is the only port it answers on.
    "postgresql+psycopg://postgres:pw@db.abcdefgh.supabase.co:5432/postgres",
    # RDS, the documented next home for this value.
    "postgresql+psycopg://ally:pw@ally.abc123.eu-west-2.rds.amazonaws.com:5432/ally",
    "postgresql+psycopg://postgres:pw@localhost:5432/ally",
    "postgresql+psycopg://postgres:pw@127.0.0.1:5432/ally",
])
def test_only_pooler_hosts_are_rewritten(url):
    """Rewriting any of these points the app at a port nothing is listening on."""
    assert runtime_database_url(url) == (url, "")


def test_a_lookalike_host_is_not_a_pooler_host():
    """Suffix match, not substring: this is not Supabase's pooler."""
    url = "postgresql+psycopg://u:p@pooler.supabase.com.attacker.example:5432/db"
    assert runtime_database_url(url) == (url, "")


def test_the_opt_out_keeps_session_mode():
    url = f"{POOLER}:5432/postgres"
    assert runtime_database_url(url, allow_session_pooler=True) == (url, "")


def test_5432_in_the_password_is_not_the_port():
    """Only `:5432/` -- the port sits immediately before the database name."""
    url = ("postgresql+psycopg://postgres.abc:p5432word@"
           "aws-1-eu-west-2.pooler.supabase.com:6543/postgres")
    assert runtime_database_url(url) == (url, "")


def test_an_unparseable_url_is_returned_untouched():
    """A bad URL is create_engine's error to raise, with its own message."""
    assert runtime_database_url("not a url at all") == ("not a url at all", "")


def test_the_engine_disables_prepared_statements_after_the_move():
    """The move is only safe because psycopg3's prepared statements are off;
    a transaction pooler cannot carry them across the connections it hands out.

    None, not 0. psycopg reads 0 as "prepare every statement on its first
    execution" -- see the pair of tests below, which measure it.
    """
    from app.db import session as mod

    if f":{mod._TRANSACTION_POOLER_PORT}/" not in mod._url:
        pytest.skip("not on the transaction pooler")
    assert "prepare_threshold" in mod._connect_args
    assert mod._connect_args["prepare_threshold"] is None


def test_zero_is_not_off_and_the_source_does_not_claim_it_is():
    """A live diagnosis died mid-session on

        psycopg.errors.InvalidSqlStatementName:
        prepared statement "_pg3_312" does not exist

    because this said 0 while its comment said "disabled". 0 is the most
    aggressive setting psycopg has. Moving to the transaction pooler with 0
    set was moving onto the one pooler that cannot survive it.
    """
    from app.core.paths import BACKEND_DIR

    source = (BACKEND_DIR / "app" / "db" / "session.py").read_text(encoding="utf-8")
    assert "prepare_threshold\"] = 0" not in source
    assert "prepare_threshold\"] = None" in source


def test_psycopg_still_reads_zero_as_prepare_immediately():
    """Pins the semantics this depends on, straight from psycopg. If a future
    release redefines 0 as "off", this test says so instead of the fix quietly
    becoming unnecessary -- or, worse, someone re-reading 0 as harmless."""
    import psycopg

    doc = psycopg.Connection.prepare_threshold.__doc__ or ""
    assert "set to 0, every query is prepared" in doc
    assert "None`, prepared statements are disabled" in doc.replace("`!", "`")


def test_migrations_still_use_database_url_as_written():
    """alembic must keep session mode for DDL: it reads settings directly and
    must never import the rewritten URL."""
    from pathlib import Path

    from app.core.paths import BACKEND_DIR

    source = (BACKEND_DIR / "alembic" / "env.py").read_text(encoding="utf-8")
    assert 'config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)' in source
    assert "runtime_database_url" not in source


# --- the boot check must describe the connection that exists ------------


def test_the_engine_exposes_the_url_it_actually_runs_on():
    from app.db import session as mod

    assert mod.DATABASE_URL_IN_USE == mod._url


def test_the_pool_warning_reads_the_url_in_use_not_the_raw_setting():
    """A live run logged, at ERROR:

        db_pool_may_exhaust_session_mode_pooler ... "the real fix -- point
        DATABASE_URL at the transaction-mode pooler on port 6543"

    one line after it had already been moved to 6543. The check was reading
    settings.DATABASE_URL, which still said 5432, so it warned about a
    session-mode hazard for a process that was not in session mode and
    prescribed the thing that had just happened. An ERROR that is wrong is
    worse than no ERROR: it is what teaches people to skip the log.
    """
    from app.core.paths import BACKEND_DIR

    source = (BACKEND_DIR / "app" / "main.py").read_text(encoding="utf-8")
    check = source.split("_SESSION_MODE_POOLER_LIMIT = 15", 1)[1].split("logger.error", 1)[0]
    assert "DATABASE_URL_IN_USE" in check
    assert "settings.DATABASE_URL" not in check


def test_a_pooler_url_on_5432_does_not_warn_because_it_is_moved():
    """The two pieces together: the move happens, so the hazard does not."""
    moved, note = runtime_database_url(f"{POOLER}:5432/postgres")
    assert note
    assert ":6543" in moved, "the boot check keys off exactly this substring"


def test_session_mode_kept_on_purpose_still_warns():
    """Opting out keeps the URL on 5432 -- and the warning is then correct."""
    kept, _ = runtime_database_url(f"{POOLER}:5432/postgres",
                                   allow_session_pooler=True)
    assert ":6543" not in kept


def test_the_two_settings_measured_against_a_real_server():
    """Not a reading of the docs -- a measurement. threshold 0 leaves named
    statements behind on the server; None leaves none. The names psycopg
    generates are `_pg3_N`, which is what the live failure was called.

    Skipped when DATABASE_URL is not a reachable Postgres.
    """
    psycopg = pytest.importorskip("psycopg")

    from sqlalchemy.engine.url import make_url

    from app.core.config import settings

    url = make_url(settings.DATABASE_URL)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("not a postgres DATABASE_URL")
    dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)

    try:
        left_behind = {}
        for value in (0, None):
            with psycopg.connect(dsn, prepare_threshold=value,
                                 connect_timeout=5) as conn:
                cur = conn.cursor()
                for _ in range(3):
                    cur.execute("select 1 where %s = 1", (1,))
                left_behind[value] = conn.execute(
                    "select count(*) from pg_prepared_statements").fetchone()[0]
    except psycopg.OperationalError as exc:
        pytest.skip(f"no reachable postgres: {exc}")

    assert left_behind[0] > 0, (
        "prepare_threshold=0 was expected to prepare statements -- if this "
        "stops being true, the fix it justifies can be revisited")
    assert left_behind[None] == 0, "None must leave nothing prepared"
