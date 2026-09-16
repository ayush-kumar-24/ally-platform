"""One-off: test the Supabase password with no URL-encoding involved.

Reads the password from $env:PGPASSWORD (or PGPASSWORD on bash) so it never
touches a URL string, and connects with explicit keyword args. This isolates
"wrong password" from "password has characters that break URL parsing" --
the two most common causes of a connection string that looks fine but still
gets rejected after a Supabase password reset.

Usage (PowerShell):
    $env:PGPASSWORD = "<paste the exact password from Supabase here>"
    python scripts/_conn_probe.py
"""
import os
import sys

import psycopg

pw = os.environ.get("PGPASSWORD")
if not pw:
    print("Set $env:PGPASSWORD first (see docstring).")
    sys.exit(1)

try:
    conn = psycopg.connect(
        host="aws-1-ap-south-1.pooler.supabase.com",
        port=5432,
        dbname="postgres",
        user="postgres.wxggmjvyzuerjbhhtcab",
        password=pw,
        connect_timeout=10,
    )
    cur = conn.cursor()
    cur.execute("select current_user, now()")
    print("CONNECTED:", cur.fetchone())
    conn.close()
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
