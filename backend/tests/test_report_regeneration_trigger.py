"""regenerate_report_for_founder -- live DB tests for the admin report-
regeneration recovery path (app/api/v1/reasoning/trigger.py).

Before this existed, AdminPanelService.report_regenerator was wired to None
(app/core/container.py) and a founder whose session completed but whose
best-effort inline reasoning run failed (see notify_session_completed's
docstring) was permanently stranded: COMPLETED session, no report, no
self-service or admin recovery path.

The pipeline-execution half of this function is not re-tested here -- it
calls the same ReasoningService.analyze_session(..., force=True) entry point
already covered (idempotency, rollback-on-failure) by the reasoning test
suite; seeding the full reference-data graph a real pipeline run needs is out
of scope for this fix. What's tested here is the lookup/dispatch logic that
is new: finding the right session for a founder, and behaving correctly when
there's nothing to regenerate.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.api.v1.reasoning.trigger import regenerate_report_for_founder
from app.db.session import SessionLocal


@pytest.fixture
def founder_id():
    db = SessionLocal()
    uid = uuid4()
    email = f"regen+{uid.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid), "e": email})
    db.commit()
    fid = db.execute(text(
        "insert into founders (user_id,full_name,email) values (:u,:n,:e) returning founder_id"
    ), {"u": str(uid), "n": "Regen Trigger Test", "e": email}).scalar()
    db.commit()
    db.close()
    yield fid
    cleanup = SessionLocal()
    cleanup.execute(text("delete from sessions where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from founders where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from auth.users where id=:u"), {"u": str(uid)})
    cleanup.commit()
    cleanup.close()


def test_unknown_founder_reports_not_found():
    db = SessionLocal()
    try:
        result = regenerate_report_for_founder(db, 999_999_999)
        assert result["status"] == "not_found"
    finally:
        db.close()


def test_founder_with_no_completed_session_reports_not_found(founder_id):
    """The exact shape of a founder who never finished a diagnosis at all --
    distinct from the actually-stranded case (completed, no report), but the
    lookup must not error or fabricate a session_id for either."""
    db = SessionLocal()
    try:
        result = regenerate_report_for_founder(db, founder_id)
        assert result == {"status": "not_found", "reason": "no completed diagnosis session for this founder"}
    finally:
        db.close()


def test_founder_with_only_in_progress_session_reports_not_found(founder_id):
    """An in-progress session must not be picked up as if it were the
    completed-but-report-less case this function exists to recover."""
    db = SessionLocal()
    try:
        db.execute(text(
            "insert into sessions (founder_id, status) "
            "values (:f, 'in_progress')"
        ), {"f": founder_id})
        db.commit()

        result = regenerate_report_for_founder(db, founder_id)
        assert result["status"] == "not_found"
    finally:
        db.close()


def test_founder_with_completed_session_is_found_and_dispatched(founder_id, monkeypatch):
    """The core fix: a COMPLETED session with no report must be found and
    handed to the reasoning pipeline (force=True) -- not silently ignored.
    The pipeline call itself is stubbed here; it is exercised for real by
    the reasoning test suite via the same analyze_session entry point."""
    db = SessionLocal()
    try:
        session_id = db.execute(text(
            "insert into sessions (founder_id, status) "
            "values (:f, 'completed') returning session_id"
        ), {"f": founder_id}).scalar()
        db.commit()

        calls = []

        class _StubService:
            async def analyze_session(self, founder, sid, *, force=False):
                calls.append((founder.founder_id, sid, force))
                return None  # simulate "ran, nothing new to persist"

        import app.api.v1.reasoning.trigger as trigger_module
        monkeypatch.setattr(trigger_module, "build_reasoning_service", lambda db: _StubService())

        result = regenerate_report_for_founder(db, founder_id)

        assert calls == [(founder_id, session_id, True)]
        assert result["status"] == "no_change"
        assert result["session_id"] == session_id
    finally:
        db.close()
