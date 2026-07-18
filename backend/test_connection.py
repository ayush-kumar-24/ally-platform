import sys
import psycopg

print("Starting connection test...", flush=True)

try:
    conn = psycopg.connect(
        "postgresql://postgres.wxggmjvyzuerjbhhtcab:founder-alley2026@aws-1-ap-south-1.pooler.supabase.com:5432/postgres",
        connect_timeout=10
    )
    print("SUCCESS — connected!", flush=True)
    conn.close()
except BaseException as e:
    print("REAL ERROR:", flush=True)
    print(repr(e), flush=True)
    sys.exit(1)

print("Script finished normally.", flush=True)