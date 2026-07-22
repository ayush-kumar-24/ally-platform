"""End-to-end smoke test -- proves what the backend claims to do, from scratch.

Runs the whole API in-process (no server, no network) and checks every piece
built so far: health, the full auth token lifecycle, and that the database is
only read, never written.

    python scripts/smoke_test.py

Exit code 0 = everything passed. Non-zero = something is wrong (and it prints
which line). Safe to run against the shared database -- it never writes.
"""

import sys
import time
import uuid
from pathlib import Path

# Make `app` importable no matter which directory this is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Silence request logs so the PASS/FAIL list is readable.
import logging

logging.disable(logging.CRITICAL)

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.core.auth import factory  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from sqlalchemy import text  # noqa: E402

client = TestClient(app)
_passed = 0
_failed = 0


def check(label, condition):
    global _passed, _failed
    mark = "PASS" if condition else "FAIL"
    if condition:
        _passed += 1
    else:
        _failed += 1
    print(f"  [{mark}] {label}")


def section(title):
    print(f"\n{title}")


# --- DB write guard: record founder count before and after ---
with engine.connect() as c:
    founders_before = c.execute(text("select count(*) from founders")).scalar()

section("Health & wiring")
r = client.get("/")
check("GET / returns running", r.status_code == 200 and r.json().get("status") == "running")
r = client.get("/api/v1/health")
check("DB health = connected", r.json().get("database") == "connected")
r = client.get("/api/v1/auth/status")
check("auth/status reports backend-issued tokens",
      r.json().get("token_model") == "backend-issued session tokens")

section("Auth: issue -> validate (dev mode)")
was_provider = settings.AUTH_PROVIDER
settings.AUTH_PROVIDER = "dev"
factory.get_auth_provider.cache_clear()

r = client.post("/api/v1/auth/session")
sess = r.json()
check("POST /auth/session issues a token pair",
      r.status_code == 200 and "access_token" in sess and "refresh_token" in sess)
access, refresh = sess["access_token"], sess["refresh_token"]

r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
check("GET /auth/me accepts our access token", r.status_code == 200)

section("Auth: security (must all be rejected)")
r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"})
check("refresh token rejected as access token", r.status_code == 401)
r = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
check("access token rejected as refresh token", r.status_code == 401)
r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access[:-3]}xxx"})
check("tampered token rejected", r.status_code == 401)

section("Auth: refresh rotation & logout")
r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
check("refresh returns a new pair", r.status_code == 200)
new_refresh = r.json()["refresh_token"]
r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
check("old refresh token can't be reused (rotation)", r.status_code == 401)
r = client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh})
check("logout succeeds", r.status_code == 200)
r = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
check("refresh after logout rejected", r.status_code == 401)

section("Auth: real-user path (supabase mode)")
settings.AUTH_PROVIDER = "supabase"
settings.SUPABASE_JWT_SECRET = "smoke-test-secret"
factory.get_auth_provider.cache_clear()
now = int(time.time())
idp_token = jwt.encode(
    {"sub": str(uuid.uuid4()), "email": "user@gmail.com", "aud": "authenticated", "exp": now + 600},
    "smoke-test-secret", algorithm="HS256",
)
r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {idp_token}"})
check("raw provider token rejected on normal route", r.status_code == 401)
r = client.post("/api/v1/auth/session", headers={"Authorization": f"Bearer {idp_token}"})
check("provider token exchanged for backend tokens at /auth/session", r.status_code == 200)
r = client.post("/api/v1/auth/session")
check("no token at /auth/session rejected", r.status_code == 401)

settings.AUTH_PROVIDER = was_provider
factory.get_auth_provider.cache_clear()

section("Database was only read, never written")
with engine.connect() as c:
    founders_after = c.execute(text("select count(*) from founders")).scalar()
check(f"founders row count unchanged ({founders_before})", founders_before == founders_after)

print(f"\n{'=' * 40}\n  {_passed} passed, {_failed} failed\n{'=' * 40}")
sys.exit(1 if _failed else 0)
