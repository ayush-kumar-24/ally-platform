"""start_session under real concurrency -- live-reproduced gap: two
near-simultaneous POST /diagnosis/start calls for the same founder both read
"no active session, 0 used this month" before either had committed, so both
passed the monthly limit check and both created an in-progress session. A
limit of 1 became 2 in the real database. Needs a real DB and real threads,
not the fake-repository unit tests in test_diagnosis_monthly_limit.py -- a
lock only means something against real concurrent transactions.
"""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.api.v1.diagnosis.service import DiagnosisService
from app.db.session import SessionLocal
from app.models import Founder


@pytest.fixture
def founder_id():
    """A throwaway free-tier founder (diagnosis_lifetime_limit == 1), cleaned
    up in reverse-FK order."""
    db = SessionLocal()
    uid = uuid4()
    email = f"diag-race-test+{uid.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid), "e": email})
    db.commit()
    fid = db.execute(text(
        "insert into founders (user_id,full_name,email,plan_type) values (:u,:n,:e,'free') "
        "returning founder_id"
    ), {"u": str(uid), "n": "Diag Race Test", "e": email}).scalar()
    db.commit()
    db.close()
    yield fid
    cleanup = SessionLocal()
    for t in ("sessions", "founders"):
        cleanup.execute(text(f"delete from {t} where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from auth.users where id=:u"), {"u": str(uid)})
    cleanup.commit()
    cleanup.close()


def _start(founder_id: int):
    """Each thread gets its OWN db session/connection -- sharing one across
    threads would not exercise real transaction-level locking at all."""
    db = SessionLocal()
    try:
        founder = db.get(Founder, founder_id)
        service = DiagnosisService(db)
        result = service.start_session(founder)
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001 -- the monthly-limit refusal is expected for one caller
        db.rollback()
        return exc
    finally:
        db.close()


def test_two_simultaneous_starts_never_create_two_sessions(founder_id):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_start, [founder_id, founder_id]))

    # Exactly one call creates a fresh (not resumed) session; the other must
    # either resume that same session or hit the monthly limit -- never both
    # succeeding as fresh creates, which is what "used 2, limit 1" looked like
    # live.
    fresh_creates = [r for r in results if not isinstance(r, Exception) and r[2] is False]
    assert len(fresh_creates) == 1, f"expected exactly 1 fresh session, got: {results}"

    db = SessionLocal()
    count = db.execute(
        text("select count(*) from sessions where founder_id = :f"), {"f": founder_id},
    ).scalar()
    db.close()
    assert count == 1, "the lock must prevent a second session row, not just a second success response"
