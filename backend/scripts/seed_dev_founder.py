"""Seed sample founders so local integration can actually run.

Why this is needed
------------------
Every protected endpoint resolves the caller through `get_founder_record`, which
requires a row in `founders` whose `user_id` matches the authenticated identity.
An empty database therefore 404s every request, which looks like a broken backend
but is really just missing seed data.

`founders.user_id` is a FK to `auth.users`, so the auth row has to exist first.

Why NOT the dev identity
------------------------
It is tempting to seed the fixed dev user (dev@ally.local), because dev-mode auth
resolves to it when no bearer token is sent. Don't. Two tests assert that identity
is never provisioned -- `test_dev_identity_not_provisioned` and
`test_session_issues_access_and_refresh` -- and they hit the real database, so
seeding it turns them red. That guarantee is worth more than the convenience.

Instead, act as a seeded founder by minting a session token:

    curl -X POST http://localhost:8001/api/v1/auth/session \\
         -H "Authorization: Bearer <that founder's user_id>"

then send the returned access_token as a normal bearer token. That is the flow the
auth layer documents, and it exercises the real token path rather than a shortcut.

Safety
------
* Idempotent -- re-running changes nothing (ON CONFLICT DO NOTHING).
* Refuses to run unless AUTH_PROVIDER=dev, so it cannot seed fake auth identities
  into an environment wired to real Supabase auth.
* Only ever INSERTs; it never updates or deletes existing rows.

Usage:
    python -m scripts.seed_dev_founder            # sample founders
    python -m scripts.seed_dev_founder --print-ids  # + their user_ids for tokens
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

SAMPLES = [
    ("Priya Nair", "priya@northstar.in", "NorthStar Labs", "starter", "9820011001"),
    ("Rahul Menon", "rahul@fernway.co", "Fernway", "pro", "9820011002"),
    ("Aisha Khan", "aisha@tildehq.com", "Tilde", "free", "9820011003"),
]


def _insert_auth_user(conn, user_id: str, email: str) -> None:
    """Minimal auth.users row. `id` is the only NOT NULL column without a default."""
    conn.execute(text("""
        insert into auth.users (id, email)
        values (:id, :email)
        on conflict (id) do nothing
    """), {"id": user_id, "email": email})


def _insert_founder(conn, user_id: str, *, name: str, email: str,
                    business: str | None = None, plan: str = "free",
                    phone: str | None = None, created_at=None) -> int | None:
    existing = conn.execute(
        text("select founder_id from founders where user_id = :uid"),
        {"uid": user_id}).scalar()
    if existing:
        return existing

    # Only columns guaranteed to exist pre-migration are written here, so the seed
    # works whether or not the pending admin/plan migrations have been applied.
    cols = {"user_id": user_id, "full_name": name, "email": email,
            "created_at": created_at or datetime.now(timezone.utc)}
    optional = {"business_name": business, "plan_type": plan, "phone": phone}
    present = {c["name"] for c in _columns(conn, "founders")}
    for key, value in optional.items():
        if key in present and value is not None:
            cols[key] = value

    names = ", ".join(cols)
    binds = ", ".join(f":{k}" for k in cols)
    return conn.execute(
        text(f"insert into founders ({names}) values ({binds}) returning founder_id"),
        cols).scalar()


def _columns(conn, table: str):
    from sqlalchemy import inspect
    return inspect(conn.engine).get_columns(table)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-ids", action="store_true",
                        help="print each founder's user_id, for minting session tokens")
    args = parser.parse_args()

    if settings.AUTH_PROVIDER.strip().lower() != "dev":
        print(f"refusing to seed: AUTH_PROVIDER is {settings.AUTH_PROVIDER!r}, not 'dev'.")
        return 1

    created = []
    with engine.begin() as conn:               # one transaction; all or nothing
        for i, (name, email, business, plan, phone) in enumerate(SAMPLES, start=1):
            # uuid5 keeps ids stable across runs, so re-seeding is a no-op rather
            # than piling up duplicate founders with fresh random ids.
            uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ally-sample-{email}"))
            _insert_auth_user(conn, uid, email)
            sid = _insert_founder(
                conn, uid, name=name, email=email, business=business, plan=plan,
                phone=phone,
                created_at=datetime.now(timezone.utc) - timedelta(days=i * 3))
            created.append((sid, email, plan, uid))

    print("seeded:")
    for fid, email, plan, uid in created:
        print(f"  founder_id={fid:<6} {email:<28} {plan}")
        if args.print_ids:
            print(f"      user_id: {uid}")

    print("\nTo act as one of these founders, mint a session token:")
    print("  curl -X POST http://localhost:8001/api/v1/auth/session \\")
    print('       -H "Authorization: Bearer <user_id>"')
    print("\nThe fixed dev identity is deliberately NOT seeded -- see the module docstring.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
