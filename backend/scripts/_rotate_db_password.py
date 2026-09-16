"""One-off: verify a freshly-reset Supabase password, then write it into
.env's DATABASE_URL with correct URL-encoding -- without ever printing the
password to the terminal or putting it in a shell history as a URL.

Usage (PowerShell):
    $env:NEW_DB_PASSWORD = "<paste the new password Supabase just showed you>"
    python scripts/_rotate_db_password.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg

HOST = "aws-1-ap-south-1.pooler.supabase.com"
PORT = 5432
DBNAME = "postgres"
USER = "postgres.wxggmjvyzuerjbhhtcab"
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def main() -> int:
    pw = os.environ.get("NEW_DB_PASSWORD")
    if not pw:
        print("Set $env:NEW_DB_PASSWORD first (see docstring).")
        return 1

    print(f"Testing new password against {HOST} ...")
    try:
        conn = psycopg.connect(
            host=HOST, port=PORT, dbname=DBNAME, user=USER,
            password=pw, connect_timeout=10,
        )
        conn.execute("select 1")
        conn.close()
        print("Connected successfully with the new password.")
    except Exception as e:
        print(f"Still failing: {type(e).__name__}: {e}")
        print("Not touching .env -- fix the password with Supabase first.")
        return 1

    if not ENV_PATH.exists():
        print(f".env not found at {ENV_PATH}; nothing to update.")
        return 1

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    new_url = (
        f"postgresql+psycopg://{USER}:{quote(pw, safe='')}@{HOST}:{PORT}/{DBNAME}"
    )
    found = False
    for i, line in enumerate(lines):
        if line.startswith("DATABASE_URL="):
            lines[i] = f'DATABASE_URL="{new_url}"\n'
            found = True
            break

    if not found:
        print("No DATABASE_URL= line found in .env; nothing changed.")
        return 1

    ENV_PATH.write_text("".join(lines), encoding="utf-8")
    print(".env updated with the new, correctly-encoded DATABASE_URL.")
    print("Re-extract $env:E2E_DB from it and retry your command.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
