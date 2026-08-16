"""GET /plans/me -> diagnosis_usage. Live-confirmed gap: the profile page's
"AI Business Diagnosis" usage meter was hardcoded to "1 / 1" for every founder
regardless of whether they had ever actually started one -- a founder who had
never run a diagnosis saw the same "fully used" state as one who genuinely had.
_diagnosis_usage (plans/router.py) reuses the exact count/limit
_check_diagnosis_allowance (diagnosis/service.py) already enforces, so the
two can never disagree.

The limit is a LIFETIME cap on COMPLETED diagnoses, not a monthly one on
started sessions -- changed after a live account was found stuck showing
"2 / 1" from two duplicate in-progress sessions a race condition had created,
neither of which the founder had ever finished. Counting starts (any status,
any month) made that number technically accurate but operationally useless:
it could go over the cap while the founder had never received a single
report. Counting completions, lifetime, is what "you get one free diagnosis"
actually promises.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal

BASE = "/api/v1/plans/me"


@pytest.fixture
def founder(client):
    """(founder_id, user_id, access_token) for a throwaway founder, provisioned
    through the real dev-auth session flow so the token is genuinely valid.
    Cleaned up in reverse-FK order."""
    db = SessionLocal()
    uid = uuid4()
    email = f"plans-diag-usage+{uid.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid), "e": email})
    db.commit()
    fid = db.execute(text(
        "insert into founders (user_id,full_name,email,plan_type) values (:u,:n,:e,'free') "
        "returning founder_id"
    ), {"u": str(uid), "n": "Plans Diag Usage Test", "e": email}).scalar()
    db.commit()
    db.close()

    session = client.post("/api/v1/auth/session", headers={"Authorization": f"Bearer {uid}"})
    access = session.json()["access_token"]
    yield fid, uid, access

    cleanup = SessionLocal()
    for t in ("sessions", "founders"):
        cleanup.execute(text(f"delete from {t} where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from auth.users where id=:u"), {"u": str(uid)})
    cleanup.commit()
    cleanup.close()


def test_no_sessions_reports_zero_used(client, founder):
    _fid, _uid, access = founder
    r = client.get(BASE, headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert r.json()["diagnosis_usage"] == {"used": 0, "limit": 1}


def test_an_abandoned_session_does_not_count(client, founder):
    """Only a completed diagnosis has reached a report. An abandoned one must
    not spend the founder's one lifetime slot -- they never got anything for it."""
    fid, _uid, access = founder
    db = SessionLocal()
    db.execute(text(
        "insert into sessions (founder_id, status, started_at) "
        "values (:f, 'abandoned', now())"
    ), {"f": fid})
    db.commit()
    db.close()

    r = client.get(BASE, headers={"Authorization": f"Bearer {access}"})
    assert r.json()["diagnosis_usage"] == {"used": 0, "limit": 1}


def test_an_in_progress_session_does_not_count(client, founder):
    """A session being resumed right now is not "used" until it completes --
    otherwise the act of resuming would itself look like exhausting the cap."""
    fid, _uid, access = founder
    db = SessionLocal()
    db.execute(text(
        "insert into sessions (founder_id, status, started_at) "
        "values (:f, 'in_progress', now())"
    ), {"f": fid})
    db.commit()
    db.close()

    r = client.get(BASE, headers={"Authorization": f"Bearer {access}"})
    assert r.json()["diagnosis_usage"] == {"used": 0, "limit": 1}


def test_a_completed_session_counts_no_matter_how_long_ago(client, founder):
    """Lifetime, not monthly -- a diagnosis completed last year still spent the
    founder's one free slot today. There is no reset date to check against."""
    fid, _uid, access = founder
    db = SessionLocal()
    db.execute(text(
        "insert into sessions (founder_id, status, started_at) "
        "values (:f, 'completed', now() - interval '400 days')"
    ), {"f": fid})
    db.commit()
    db.close()

    r = client.get(BASE, headers={"Authorization": f"Bearer {access}"})
    assert r.json()["diagnosis_usage"] == {"used": 1, "limit": 1}
