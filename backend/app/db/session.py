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
# DB_POOL_SIZE/DB_POOL_MAX_OVERFLOW (app/core/config.py) size themselves from
# which pooler DATABASE_URL names, because the two modes have completely
# different budgets -- see the comment there. What made the size start to
# matter is that routes taking a Session are now `def` rather than `async def`
# (see the note above SessionLocal below): they run in the threadpool and
# really do run concurrently, so the pool is what bounds concurrency instead
# of the event loop accidentally doing it. pool_recycle keeps connections from
# going stale behind the pooler, which closes idle ones.
# Transaction mode does NOT support prepared statements -- Supabase's own
# connecting-to-postgres guide says so outright, and the dedicated PgBouncer
# pooler on the same port is the same story. psycopg3 does not know that: it
# prepares a statement server-side once it has seen it `prepare_threshold`
# times (default 5), so on a transaction pooler every query the app runs more
# than a handful of times eventually raises `prepared statement "_pg3_0"
# already exists` (or `does not exist`) when it lands on a backend connection
# that is not the one it was prepared on. The failure is sporadic and depends
# on which pooled connection a request happens to get, which makes it look
# like anything except a configuration problem.
#
# `prepare_threshold=None` turns server-side prepares off entirely. It costs
# the parse-plan reuse a repeated query would get, which is why it is tied to
# the pooler mode rather than set unconditionally: session mode supports
# prepared statements and keeps them.
_connect_args = {}
if settings.uses_transaction_pooler and "+psycopg" in settings.DATABASE_URL:
    _connect_args["prepare_threshold"] = None

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=1800,
    connect_args=_connect_args,
)

# This Session is SYNCHRONOUS, and that decides how routes must be declared:
# a FastAPI route that takes one is `def`, never `async def`. An `async def`
# route runs ON the event loop, so each of its queries blocks every other
# request in the process for the duration of a network round trip to the
# database; a `def` route runs in the threadpool and blocks only itself. This
# is enforced by tests/test_routes_do_not_block_the_event_loop.py, which has
# the full story -- it was found through the founder dashboard, whose six
# parallel requests were executing strictly one after another.
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