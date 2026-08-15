"""GET /plans/me -> diagnosis_usage. Live-confirmed gap: the profile page's
"AI Business Diagnosis" usage meter was hardcoded to "1 / 1" for every founder
regardless of whether they had ever actually started one -- a founder who had
never run a diagnosis saw the same "fully used" state as one who genuinely had.
_diagnosis_usage (plans/router.py) reuses the exact count/limit
_check_monthly_diagnosis_limit (diagnosis/service.py) already enforces, so the
two can never disagree.
"""

from datetime import datetime, timedelta, timezone
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


def test_no_sessions_this_month_reports_zero_used(client, founder):
    _fid, _uid, access = founder
    r = client.get(BASE, headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200
    assert r.json()["diagnosis_usage"] == {"used": 0, "limit": 1}


def test_a_session_started_this_month_counts_even_if_abandoned(client, founder):
    """count_sessions_started_since counts by START, not completion -- an
    abandoned session still spent the founder's monthly allowance, and the
    usage meter must reflect that, not just completed diagnoses."""
    fid, _uid, access = founder
    db = SessionLocal()
    db.execute(text(
        "insert into sessions (founder_id, status, started_at) "
        "values (:f, 'abandoned', now())"
    ), {"f": fid})
    db.commit()
    db.close()

    r = client.get(BASE, headers={"Authorization": f"Bearer {access}"})
    assert r.json()["diagnosis_usage"] == {"used": 1, "limit": 1}


def test_a_session_started_last_month_does_not_count(client, founder):
    """The window is the calendar month, not a rolling count -- a session from
    before this month must not still be charged against this month's limit."""
    fid, _uid, access = founder
    last_month = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
    db = SessionLocal()
    db.execute(text(
        "insert into sessions (founder_id, status, started_at) values (:f, 'abandoned', :s)"
    ), {"f": fid, "s": last_month})
    db.commit()
    db.close()

    r = client.get(BASE, headers={"Authorization": f"Bearer {access}"})
    assert r.json()["diagnosis_usage"] == {"used": 0, "limit": 1}
