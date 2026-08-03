"""Start the API for local development.

Exists because `uvicorn --app-dir` only extends sys.path -- it does not change the
working directory, and pydantic-settings resolves `.env` relative to the CWD. Started
from anywhere else the app dies on missing DATABASE_URL/SECRET_KEY even though the
file is right there.

This chdir's to the backend root first, so the launcher can live anywhere.

    python scripts/run_dev.py [--port 8001] [--reload]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--reload", action="store_true")
    # Binds 0.0.0.0 by default so both 127.0.0.1 and ::1 reach it. Node resolves
    # "localhost" to ::1 first, so an IPv4-only bind shows up as a 502 from the
    # Vite proxy even though curl to 127.0.0.1 works fine.
    args = parser.parse_args()

    os.chdir(BACKEND_ROOT)                 # so .env is found
    sys.path.insert(0, str(BACKEND_ROOT))

    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
