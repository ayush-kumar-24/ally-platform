"""POST /frontend-errors -- the self-hosted crash-report sink.

Public-tolerant is the whole point: an error before login (the landing page,
a broken auth handshake) must still be accepted and logged, not 401'd away
for lacking a token. founder_id is best-effort, not required.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.core.auth.base import AuthUser
from app.core.auth.tokens import create_access_token
from app.db.session import SessionLocal

BASE = "/api/v1/frontend-errors"


def _payload(**over):
    base = dict(message="TypeError: cannot read properties of undefined", url="https://goxlally.ai/app")
    base.update(over)
    return base


@pytest.fixture
def real_founder():
    """A throwaway founder + matching access token, for the one test that
    needs founder_id to actually resolve to something real rather than None.
    Cleaned up in reverse-FK order, same pattern as
    test_sql_conversation_repository.py's founder_id fixture.
    """
    db = SessionLocal()
    uid = uuid4()
    email = f"fe-errors-test+{uid.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid), "e": email})
    db.commit()
    fid = db.execute(text(
        "insert into founders (user_id,full_name,email) values (:u,:n,:e) returning founder_id"
    ), {"u": str(uid), "n": "FE Errors Test", "e": email}).scalar()
    db.commit()
    db.close()

    access, _ = create_access_token(AuthUser(id=str(uid), email=email, provider="test"))
    yield fid, access

    cleanup = SessionLocal()
    cleanup.execute(text("delete from founders where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from auth.users where id=:u"), {"u": str(uid)})
    cleanup.commit()
    cleanup.close()


def test_accepted_without_any_auth(client, caplog):
    with caplog.at_level("ERROR", logger="ally"):
        r = client.post(BASE, json=_payload())
    assert r.status_code == 202
    assert r.json() == {"received": True}

    record = next(rec for rec in caplog.records if rec.getMessage() == "frontend error reported")
    assert record.fe_message == "TypeError: cannot read properties of undefined"
    assert record.founder_id is None


def test_accepted_with_a_garbage_token(client, caplog):
    """A malformed/expired token must not turn a crash report into a 401 --
    that would drop exactly the reports coming from a founder mid-auth-failure."""
    with caplog.at_level("ERROR", logger="ally"):
        r = client.post(BASE, json=_payload(), headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 202
    record = next(rec for rec in caplog.records if rec.getMessage() == "frontend error reported")
    assert record.founder_id is None


def test_founder_id_attached_when_authenticated(client, caplog, real_founder):
    fid, access = real_founder
    with caplog.at_level("ERROR", logger="ally"):
        r = client.post(BASE, json=_payload(), headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 202
    record = next(rec for rec in caplog.records if rec.getMessage() == "frontend error reported")
    assert record.founder_id == fid


def test_all_reported_fields_land_in_the_log(caplog, client):
    with caplog.at_level("ERROR", logger="ally"):
        client.post(BASE, json=_payload(
            stack="at Component (App.jsx:42)",
            component_stack="in Component\n    in App",
            user_agent="Mozilla/5.0 test",
            source="error_boundary",
            event_id="abc-123",
        ))
    record = next(rec for rec in caplog.records if rec.getMessage() == "frontend error reported")
    assert record.fe_stack == "at Component (App.jsx:42)"
    assert record.fe_component_stack == "in Component\n    in App"
    assert record.fe_source == "error_boundary"
    assert record.fe_event_id == "abc-123"
    assert record.fe_url == "https://goxlally.ai/app"


def test_missing_message_is_422():
    from app.api.v1.frontend_errors.router import FrontendErrorReport
    with pytest.raises(ValidationError):
        FrontendErrorReport(url="https://goxlally.ai")


def test_oversized_fields_are_rejected_not_silently_truncated():
    """A cap that silently truncated would still let a bad actor push
    megabytes through per request before truncation kicks in server-side;
    rejecting outright bounds the request body itself."""
    from app.api.v1.frontend_errors.router import FrontendErrorReport
    with pytest.raises(ValidationError):
        FrontendErrorReport(message="x" * 2001, url="https://goxlally.ai")
