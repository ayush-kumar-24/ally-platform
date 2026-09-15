from sqlalchemy import create_engine, event, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from app.core.config import settings
from app.core.logger import logger

# Supabase's pooler allows 15 client connections in session mode, shared by
# every process that talks to it -- and this app can run as more than one
# process (a multi-instance deploy, a local backend plus a hosted one, a
# migration running alongside the API). 5+10 was exactly 15 on its own, so one
# busy process could take every slot and leave nothing for anything else, at
# which point the pooler answers new connections with "(EMAXCONNSESSION) max
# clients reached" and endpoints 500 intermittently depending on who got there
# first -- which is exactly what happened in development with just two
# processes running.
#
# DB_POOL_SIZE/DB_POOL_MAX_OVERFLOW (app/core/config.py) default to a per-
# process cap of 5, sized for up to 2 instances with headroom. pool_recycle
# keeps connections from going stale behind the pooler, which closes idle ones.
# Supabase's pooler runs two modes on two ports, and which one DATABASE_URL
# points at decides whether this app can breathe.
#
#   5432  SESSION mode -- a client holds a real backend connection for its whole
#         session. The whole project gets FIFTEEN of them, shared by every
#         process. This app alone asks for pool_size + max_overflow, so two
#         instances (an API and a script; a local backend and a deployed one)
#         exceed the cap between them. Past that, new connections are refused
#         with EMAXCONNSESSION and requests BLOCK waiting for one that is not
#         coming -- which is felt as "the page takes minutes to load", not as an
#         error, because SQLAlchemy waits patiently by default.
#
#   6543  TRANSACTION mode -- a connection is borrowed per transaction and
#         handed straight back, so thousands of clients share a few backends.
#         This is the mode this workload wants. Verified compatible: RLS here
#         uses set_config(..., is_local=true), which is transaction-scoped and
#         survives pooling exactly as it should.
#
# Pointing at 5432 is not a preference this app can honour: three of ten
# end-to-end runs died mid-request with "server closed the connection
# unexpectedly", once 582 seconds in, mid-COMMIT. So a Supabase POOLER url on
# 5432 is moved to 6543 here, at engine construction, and the move is logged.
#
# Narrow on purpose. It fires only for a host under `.pooler.supabase.com`,
# where both ports are the same endpoint in two modes and the swap is a mode
# change and nothing else. A direct connection (`db.<ref>.supabase.co:5432`),
# an RDS endpoint, a local postgres, anything else on 5432 -- untouched, because
# there 5432 is the only port there is and rewriting it would point the app at
# nothing. DB_SESSION_POOLER_OK=true turns it off for someone who means it.
#
# MIGRATIONS ARE DELIBERATELY NOT REWRITTEN. alembic/env.py reads
# settings.DATABASE_URL directly and keeps whatever .env says, which is what
# Supabase asks for: session mode for DDL. This function is imported by the
# runtime engine only.

#: `aws-1-eu-west-2.pooler.supabase.com` -- both modes, two ports.
_POOLER_HOST_SUFFIX = ".pooler.supabase.com"
_SESSION_POOLER_PORT = 5432
_TRANSACTION_POOLER_PORT = 6543


def runtime_database_url(url: str, allow_session_pooler: bool = False) -> tuple[str, str]:
    """(url to run the app on, note for the log -- empty when unchanged)."""
    if allow_session_pooler:
        return url, ""
    try:
        host = make_url(url).host or ""
    except Exception:                                            # noqa: BLE001
        return url, ""  # unparseable is the caller's problem, not this one's
    if not host.endswith(_POOLER_HOST_SUFFIX):
        return url, ""
    marker = f":{_SESSION_POOLER_PORT}/"
    if marker not in url:
        return url, ""
    moved = url.replace(marker, f":{_TRANSACTION_POOLER_PORT}/", 1)
    return moved, (
        f"DATABASE_URL names the Supabase SESSION pooler ({host}:"
        f"{_SESSION_POOLER_PORT}), which gives the whole project 15 connections "
        f"and drops them mid-request under load. Running on the TRANSACTION "
        f"pooler (:{_TRANSACTION_POOLER_PORT}) instead. Change the port in "
        f"backend/.env to make this permanent, or set "
        f"DB_SESSION_POOLER_OK=true to keep session mode."
    )


_url, _note = runtime_database_url(
    settings.DATABASE_URL, settings.DB_SESSION_POOLER_OK)

#: The URL the app's own engine actually runs on, which is NOT always
#: settings.DATABASE_URL. Anything reasoning about the live connection -- the
#: pool-exhaustion check at boot, say -- must read this one, or it describes a
#: connection nobody is using. Migrations keep settings.DATABASE_URL.
DATABASE_URL_IN_USE = _url

if _note:
    logger.warning("database_url_moved_to_transaction_pooler", extra={"detail": _note})

# psycopg3 prepares statements by default and a transaction-mode pooler cannot
# keep them across the connections it hands out, so preparation is DISABLED for
# that port. Detected from the URL rather than configured, because a port and a
# flag that must agree, set in two places, will eventually disagree.
#
# THE VALUE IS None, NOT 0. This read `prepare_threshold=0` and 0 is not "off",
# it is "prepare every statement on its FIRST execution" -- the most aggressive
# setting there is, the exact opposite of what the line above it claimed. From
# psycopg's own docs:
#
#     If it is set to 0, every query is prepared the first time it is executed.
#     If it is set to None, prepared statements are disabled on the connection.
#
# So moving to 6543 with 0 was moving onto a transaction pooler with preparation
# turned up to maximum, and a live diagnosis died on
#
#     psycopg.errors.InvalidSqlStatementName: prepared statement "_pg3_312"
#     does not exist
#
# mid-session: the statement was prepared on one pooled backend and executed on
# another that had never seen it. Measured both ways against a real Postgres --
# threshold 0 leaves _pg3_0, _pg3_1 in pg_prepared_statements after three
# executions; None leaves none.
_connect_args: dict = {}
if f":{_TRANSACTION_POOLER_PORT}/" in _url:
    _connect_args["prepare_threshold"] = None

engine = create_engine(
    _url,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_MAX_OVERFLOW,
    pool_recycle=1800,
    # FAIL, DO NOT HANG. The default is 30 seconds of silent waiting per
    # checkout; with six parallel dashboard calls that is six blocked requests
    # and a spinner for half a minute with nothing in the logs. Ten seconds is
    # long enough to ride out a burst and short enough that starvation shows up
    # as an error somebody can act on.
    pool_timeout=10,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


_FOUNDER_UUID_KEY = "current_founder_uuid"
_ADMIN_KEY = "current_admin"


@event.listens_for(Session, "after_begin")
def _apply_rls_context(session, transaction, connection):
    founder_uuid = session.info.get(_FOUNDER_UUID_KEY)

    if founder_uuid:
        connection.execute(
            text(
                "SELECT set_config("
                "'app.current_founder_uuid', "
                ":founder_uuid, "
                "true)"
            ),
            {"founder_uuid": str(founder_uuid)},
        )

    if session.info.get(_ADMIN_KEY):
        connection.execute(
            text("SELECT set_config('app.current_admin', 'true', true)")
        )


def set_founder_rls_context(db: Session, founder_uuid: str) -> None:
    founder_uuid = str(founder_uuid)
    db.info[_FOUNDER_UUID_KEY] = founder_uuid

    if db.in_transaction():
        db.execute(
            text(
                "SELECT set_config("
                "'app.current_founder_uuid', "
                ":founder_uuid, "
                "true)"
            ),
            {"founder_uuid": founder_uuid},
        )


def set_admin_rls_context(db: Session) -> None:
    """Mark this session as a system/admin actor for RLS.

    The founder-isolation policies (migration d91c6e4b72aa) read
    `founder_id = public.get_founder_id() OR app.current_admin`, and
    get_founder_id() resolves from `app.current_founder_uuid`. A session with
    NEITHER set therefore sees zero rows on every founder-scoped table --
    sessions, answers, founders, founder_reports, detected_root_causes, all of
    them -- rather than failing loudly. That is the correct default for a stray
    connection and exactly wrong for a trusted server-initiated job, which has no
    founder identity to carry and legitimately works across founders.

    Used by the report-reconciliation sweep, which must find completed sessions
    belonging to ANY founder before it can know whose they are. Do not reach for
    this on a request path: a request has a founder, and
    set_founder_rls_context is the least-privilege way to say so.

    Set inside the transaction with `is_local = true`, same as the founder
    context, so it dies with the transaction and can never leak to whoever gets
    this pooled connection next.
    """
    db.info[_ADMIN_KEY] = True

    if db.in_transaction():
        db.execute(text("SELECT set_config('app.current_admin', 'true', true)"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()