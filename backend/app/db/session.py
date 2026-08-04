from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# Supabase's pooler allows 15 client connections in session mode. pool_size=5 +
# max_overflow=10 was exactly 15, so one busy API process could take every slot
# and leave nothing for anything else -- a second backend, an alembic run, a
# script -- at which point the pooler answers new connections with
# "(EMAXCONNSESSION) max clients reached" and endpoints 500 intermittently
# depending on who got there first.
#
# 3 + 5 caps this process at 8, leaving genuine headroom. pool_recycle keeps
# connections from going stale behind the pooler, which closes idle ones.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=5,
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