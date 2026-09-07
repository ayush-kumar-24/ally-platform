from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from app.core.config import settings

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
# psycopg3 prepares statements by default and a transaction-mode pooler cannot
# keep them across borrowed connections, so prepare_threshold=0 is set for that
# port. Detected from the URL rather than configured, because a port and a flag
# that must agree, set in two places, will eventually disagree.
_TRANSACTION_POOLER_PORT = 6543
_connect_args: dict = {}
if f":{_TRANSACTION_POOLER_PORT}/" in settings.DATABASE_URL:
    _connect_args["prepare_threshold"] = 0

engine = create_engine(
    settings.DATABASE_URL,
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