"""POST /profile/avatar -- live-confirmed gap: the camera button had no
onClick at all, and there was no backend support whatsoever (no endpoint, no
storage, no column). This is the first real version.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal

BASE = "/api/v1/profile"

# 1x1 red pixel PNG, valid image bytes.
_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415408d763f8cfc0c00000030001c9dbf9d80000000049"
    "454e44ae426082"
)

_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads" / "avatars"


@pytest.fixture
def auth_headers(client):
    """A throwaway founder + Authorization header, provisioned through the
    real dev-auth session flow. The bare `client` fixture's default dev
    identity has no founders row in this database (removed by unrelated
    account-deletion testing) -- every profile-scoped call 404s under it,
    which is not a route bug, just a missing seed. Cleaned up in reverse-FK
    order, including any avatar file the test itself wrote."""
    db = SessionLocal()
    uid = uuid4()
    email = f"avatar-test+{uid.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid), "e": email})
    db.commit()
    fid = db.execute(text(
        "insert into founders (user_id,full_name,email) values (:u,:n,:e) returning founder_id"
    ), {"u": str(uid), "n": "Avatar Test", "e": email}).scalar()
    db.commit()
    db.close()

    session = client.post("/api/v1/auth/session", headers={"Authorization": f"Bearer {uid}"})
    access = session.json()["access_token"]
    yield {"Authorization": f"Bearer {access}"}

    for f in _UPLOAD_DIR.glob(f"{fid}.*"):
        f.unlink(missing_ok=True)
    cleanup = SessionLocal()
    cleanup.execute(text("delete from founders where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from auth.users where id=:u"), {"u": str(uid)})
    cleanup.commit()
    cleanup.close()


def test_upload_persists_and_serves(client, auth_headers):
    r = client.post(BASE + "/avatar", files={"file": ("test.png", _PNG_BYTES, "image/png")}, headers=auth_headers)
    assert r.status_code == 201
    url = r.json()["avatar_url"]
    assert url.startswith("http")
    assert "/uploads/avatars/" in url

    profile = client.get(BASE, headers=auth_headers).json()
    assert profile["avatar_url"] == url

    # The file really exists where the URL claims it does, not just in the DB.
    filename = url.rsplit("/", 1)[-1]
    assert (_UPLOAD_DIR / filename).exists()


def test_reupload_removes_the_old_file(client, auth_headers):
    first = client.post(BASE + "/avatar", files={"file": ("a.png", _PNG_BYTES, "image/png")}, headers=auth_headers)
    first_name = first.json()["avatar_url"].rsplit("/", 1)[-1]
    assert (_UPLOAD_DIR / first_name).exists()

    second = client.post(BASE + "/avatar", files={"file": ("b.png", _PNG_BYTES, "image/png")}, headers=auth_headers)
    second_name = second.json()["avatar_url"].rsplit("/", 1)[-1]

    assert second_name != first_name
    assert not (_UPLOAD_DIR / first_name).exists()  # old one cleaned up
    assert (_UPLOAD_DIR / second_name).exists()


def test_rejects_unsupported_content_type(client, auth_headers):
    r = client.post(BASE + "/avatar", files={"file": ("x.gif", b"GIF89a", "image/gif")}, headers=auth_headers)
    assert r.status_code == 422


def test_rejects_empty_file(client, auth_headers):
    r = client.post(BASE + "/avatar", files={"file": ("x.png", b"", "image/png")}, headers=auth_headers)
    assert r.status_code == 422


def test_rejects_oversized_file(client, auth_headers):
    huge = b"\x00" * (5 * 1024 * 1024 + 1)
    r = client.post(BASE + "/avatar", files={"file": ("x.png", huge, "image/png")}, headers=auth_headers)
    assert r.status_code == 422
