from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

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
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_MAX_OVERFLOW,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()