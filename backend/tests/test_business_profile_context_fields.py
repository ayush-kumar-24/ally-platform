"""team_size, business_model and industry_mapped_id, end to end through the API.

These cover the write path that did not exist: a founder could answer a question
in onboarding and have the answer land nowhere. `BusinessInfoUpdate` is
`extra="forbid"`, so team_size was not merely ignored -- it was a 422, and the
guided flow's own save would have failed had it ever tried to send one.

The NULL cases matter as much as the write cases. Every founder onboarded before
these questions existed has NULL here, and NULL has to keep meaning "we did not
ask" rather than becoming an answer -- otherwise the diagnosis starts filtering
questions away from the people whose profiles are least complete.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.founder_context import Applicability, FounderContext
from app.core.auth import AuthUser, get_current_founder
from app.db.session import engine, get_db
from app.main import app
from app.models import Founder
from app.schemas.sections import BusinessInfoUpdate

URL = "/api/v1/profile/business"


@pytest.fixture
def founder_client():
    """A real founder row on a transaction that is rolled back afterwards.

    Same shape as tests/test_founder_context.py's fixture -- these tests need
    the actual endpoint, schema validation and repository write path, because
    the bug being fixed lived in the seam between them.
    """
    uid = uuid.uuid4()
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    conn.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                 {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    conn.execute(text("select set_config('app.current_founder_uuid', :u, true)"),
                 {"u": str(uid)})
    conn.execute(text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
                 dict(u=str(uid), n="Ctx Test", e=f"t{uid.hex[:8]}@x.com",
                      p="v1", t="v1", i="127.0.0.1", b="supabase"))
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_founder] = lambda: AuthUser(
        id=str(uid), email="x@y.com", provider="supabase"
    )
    try:
        client = TestClient(app)
        client.founder_uuid = uid          # type: ignore[attr-defined]
        client.session = session           # type: ignore[attr-defined]
        yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        trans.rollback()
        conn.close()


def _row(client) -> Founder:
    return client.session.query(Founder).filter_by(user_id=client.founder_uuid).one()


def _seeded_industry(client):
    """(label_to_send, expected_code, expected_id) for an industry present here.

    The local fixture database carries the original four industries and
    production carries thirty, so a test that hardcoded 'Agriculture' would pass
    in one environment and fail in the other for reasons that have nothing to do
    with the code under test.
    """
    from app.services.industry_mapping import INDUSTRY_LABEL_TO_CODE

    seeded = {
        code: iid
        for iid, code in client.session.execute(
            text("SELECT industry_id, industry_code FROM industries")
        ).all()
    }
    for label, code in INDUSTRY_LABEL_TO_CODE.items():
        if code and code in seeded:
            return label, code, seeded[code]
    pytest.skip("no mapped industry is seeded in this database")


# --- C. accepted by the schema ---------------------------------------------
def test_business_info_update_accepts_team_size_and_business_model():
    payload = BusinessInfoUpdate(team_size="solo", business_model="B2B")
    assert payload.team_size == "solo"
    assert payload.business_model == "B2B"


@pytest.mark.parametrize("size", ["solo", "2_5", "6_10", "11_25", "26_50", "50_plus"])
def test_every_canonical_team_size_is_accepted(size):
    assert BusinessInfoUpdate(team_size=size).team_size == size


@pytest.mark.parametrize("model", ["B2B", "B2C", "B2B2C", "marketplace", "D2C", "other"])
def test_every_canonical_business_model_is_accepted(model):
    assert BusinessInfoUpdate(business_model=model).business_model == model


def test_a_value_outside_the_canonical_vocabulary_is_rejected():
    # The CHECK constraint on founders.team_size is the source of truth; this
    # turns a 500 from the database into a clean 422 at the edge.
    with pytest.raises(Exception):
        BusinessInfoUpdate(team_size="a few people")
    with pytest.raises(Exception):
        BusinessInfoUpdate(business_model="B2G")


# --- D / E. persisted through the endpoint ----------------------------------
def test_team_size_is_persisted(founder_client):
    r = founder_client.patch(URL, json={"team_size": "solo"})
    assert r.status_code == 200, r.text
    assert r.json()["team_size"] == "solo"
    assert _row(founder_client).team_size == "solo"


def test_business_model_is_persisted(founder_client):
    r = founder_client.patch(URL, json={"business_model": "B2B"})
    assert r.status_code == 200, r.text
    assert r.json()["business_model"] == "B2B"
    assert _row(founder_client).business_model == "B2B"


def test_both_survive_a_later_partial_update(founder_client):
    founder_client.patch(URL, json={"team_size": "2_5", "business_model": "marketplace"})
    r = founder_client.patch(URL, json={"problem_statement": "Growth has stalled."})
    assert r.status_code == 200, r.text
    row = _row(founder_client)
    assert row.team_size == "2_5"
    assert row.business_model == "marketplace"


def test_the_read_schema_returns_them(founder_client):
    founder_client.patch(URL, json={"team_size": "6_10", "business_model": "B2C"})
    body = founder_client.get(URL).json()
    assert body["team_size"] == "6_10"
    assert body["business_model"] == "B2C"


def test_an_invalid_value_is_a_422_not_a_500(founder_client):
    assert founder_client.patch(URL, json={"team_size": "loads"}).status_code == 422
    assert founder_client.patch(URL, json={"business_model": "B2G"}).status_code == 422


# --- B. industry_mapped_id is actually written ------------------------------
def test_setting_industry_writes_industry_mapped_id(founder_client):
    label, code, industry_id = _seeded_industry(founder_client)
    r = founder_client.patch(URL, json={"industry": label})
    assert r.status_code == 200, r.text
    row = _row(founder_client)
    assert row.industry == label
    assert row.industry_mapped_id == industry_id, (
        f"{label!r} should have resolved to {code!r} (industry_id {industry_id})"
    )


def test_an_unmappable_industry_leaves_the_mapping_null(founder_client):
    r = founder_client.patch(URL, json={"industry": "Other"})
    assert r.status_code == 200, r.text
    row = _row(founder_client)
    assert row.industry == "Other"
    assert row.industry_mapped_id is None


def test_changing_to_an_unmappable_industry_clears_a_stale_mapping(founder_client):
    # A founder who moves from a known industry to one we cannot map is not
    # still in the old one. A stale mapping would filter their questions to an
    # industry they have left, which is worse than knowing nothing.
    label, _code, industry_id = _seeded_industry(founder_client)
    founder_client.patch(URL, json={"industry": label})
    assert _row(founder_client).industry_mapped_id == industry_id

    founder_client.patch(URL, json={"industry": "Quantum Widgets"})
    assert _row(founder_client).industry_mapped_id is None


def test_a_write_that_does_not_touch_industry_leaves_the_mapping_alone(founder_client):
    label, _code, industry_id = _seeded_industry(founder_client)
    founder_client.patch(URL, json={"industry": label})
    founder_client.patch(URL, json={"team_size": "solo"})
    assert _row(founder_client).industry_mapped_id == industry_id


# --- G / H. existing founders stay valid ------------------------------------
def test_a_founder_with_neither_field_is_still_valid(founder_client):
    # Nothing was made mandatory: these are not in ALWAYS_REQUIRED, so a founder
    # who never answers them can still complete their profile.
    row = _row(founder_client)
    assert row.team_size is None
    assert row.business_model is None
    assert founder_client.get(URL).status_code == 200
    assert founder_client.get("/api/v1/profile/validate").status_code == 200


def test_null_values_read_back_as_null_not_as_an_answer(founder_client):
    body = founder_client.get(URL).json()
    assert body["team_size"] is None
    assert body["business_model"] is None


def test_profile_completion_does_not_require_the_new_fields(founder_client):
    from app.services.profile_progress import ALWAYS_REQUIRED, PATH_1_REQUIRED, PATH_2_REQUIRED

    required = {c for c, _l, _s in (*ALWAYS_REQUIRED, *PATH_1_REQUIRED, *PATH_2_REQUIRED)}
    assert "team_size" not in required
    assert "business_model" not in required


# --- I. FounderContext reflects what was persisted --------------------------
def test_founder_context_sees_the_persisted_values(founder_client):
    label, code, _industry_id = _seeded_industry(founder_client)
    founder_client.patch(URL, json={
        "industry": label, "team_size": "solo", "business_model": "B2B",
    })
    row = _row(founder_client)

    ctx = FounderContext.from_founder(row, industry_code=code)
    assert ctx.team_size == "solo"
    assert ctx.business_model == "B2B"          # stored verbatim
    assert ctx.verdict("model:b2b") is Applicability.SATISFIED   # matched case-insensitively
    assert ctx.industry_code == code
    assert ctx.verdict("has_team") is Applicability.CONTRADICTED
    assert ctx.verdict(f"industry:{code}") is Applicability.SATISFIED


def test_founder_context_reports_unknown_for_a_founder_who_answered_neither(founder_client):
    ctx = FounderContext.from_founder(_row(founder_client))
    assert ctx.team_size is None
    assert ctx.business_model is None
    assert ctx.verdict("has_team") is Applicability.UNKNOWN
    assert ctx.verdict("model:b2b") is Applicability.UNKNOWN
