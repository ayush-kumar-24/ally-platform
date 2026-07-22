"""Quick database connectivity check.

Reads DATABASE_URL from .env via settings -- never hardcode the connection
string here. This file is committed; .env is not.

    python test_connection.py
"""

import sys

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine


def main() -> int:
    # Host only -- never print the URL itself, it contains the password.
    host = settings.DATABASE_URL.split("@")[-1].split("/")[0]
    print(f"Connecting to {host} ...", flush=True)

    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
            tables = conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            ).scalar()
    except Exception as exc:
        print("FAILED:", repr(exc), flush=True)
        return 1

    print(f"SUCCESS -- {version.split(',')[0]}", flush=True)
    print(f"public tables: {tables}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
