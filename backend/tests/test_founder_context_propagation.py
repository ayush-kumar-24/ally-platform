"""The acceptance test for Step 2: does real onboarding context reach the engine?

One deterministic founder -- Agriculture & AgriTech, Stage 0, solo, B2B -- saved
through the real profile endpoints, then read back the way the diagnosis path
reads it. The assertion is propagation, not filtering: no question is excluded
here, because industry eligibility is a later step. What this proves is that the
values are PRESENT at the points that will do the excluding.

Why that is worth a test of its own: before this change every one of these
values was structurally unreachable. `industry_mapped_id` had no writer,
`team_size` and `business_model` were rejected by the only endpoint the guided
flow writes business fields through, and `founder_brief` rendered "Team size"
and "Business model" lines that were therefore always empty. The engine was not
wrong about industry; it had never been told one.

Agriculture is seeded into the test transaction when the catalogue does not
already carry it, so this runs identically against the local fixture database
(4 industries) and production-shaped ones (30).
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.founder_brief import build_founder_brief
from app.api.v1.diagnosis.founder_context import (
    FAMILY_INDUSTRY,
    FAMILY_TEAM,
    Applicability,
    FounderContext,
)
from app.core.auth import AuthUser, get_current_founder
from app.db.session import engine, get_db
from app.main import app
from app.models import Founder
from app.services.industry_mapping import resolve_industry_code, resolve_industry_id

BUSINESS_URL = "/api/v1/profile/business"

#: The persona, exactly as specified for this step.
PERSONA = {
    "industry_label": "Agriculture",
    "expected_industry_code": "agritech",
    "stage_label": "Ideation",          # Stage 0
    "expected_stage_order": 1,
    "team_size": "solo",
    "business_model": "B2B",
}


@pytest.fixture
def founder_client():
    uid = uuid.uuid4()
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    conn.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                 {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    conn.execute(text("select set_config('app.current_founder_uuid', :u, true)"),
                 {"u": str(uid)})
    conn.execute(text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
                 dict(u=str(uid), n="Agri Founder", e=f"t{uid.hex[:8]}@x.com",
                      p="v1", t="v1", i="127.0.0.1", b="supabase"))

    # Agriculture & AgriTech, if this database does not already have it. Inside
    # the same rolled-back transaction, so nothing is left behind and the test
    # does not depend on which industries a given environment has seeded.
    existing = session.execute(
        text("SELECT industry_id FROM industries WHERE industry_code = 'agritech'")
    ).scalar()
    if existing is None:
        # An EXPLICIT id, because `industries_industry_id_seq` trails the
        # bulk-loaded reference rows -- the catalogue is seeded with literal ids
        # and nothing setvals the sequence afterwards, so a plain INSERT here
        # collides with industry_id 1. (Arya's production migration does call
        # setval for the same reason.)
        next_id = session.execute(
            text("SELECT coalesce(max(industry_id), 0) + 1 FROM industries")
        ).scalar()
        session.execute(
            text(
                "INSERT INTO industries (industry_id, industry_code, industry_name,"
                " industry_subtitle, why_industry_context_matters, description)"
                " VALUES (:i, 'agritech', 'Agriculture & AgriTech', 'test fixture',"
                " 'test fixture', 'test fixture')"
            ),
            {"i": next_id},
        )
        session.flush()

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_founder] = lambda: AuthUser(
        id=str(uid), email="x@y.com", provider="supabase"
    )
    try:
        client = TestClient(app)
        client.founder_uuid = uid       # type: ignore[attr-defined]
        client.session = session        # type: ignore[attr-defined]
        yield client
    finally:
        app.dependency_overrides.clear()
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def onboarded(founder_client):
    """The persona, saved through the real endpoint the guided flow uses."""
    response = founder_client.patch(BUSINESS_URL, json={
        "stage": PERSONA["stage_label"],
        "industry": PERSONA["industry_label"],
        "team_size": PERSONA["team_size"],
        "business_model": PERSONA["business_model"],
        "building_summary": "A mandi price app for smallholder farmers.",
        "problem_statement": "Farmers do not trust a price they cannot verify.",
    })
    assert response.status_code == 200, response.text
    return founder_client


def _founder(client) -> Founder:
    """The founder row, loaded the way the diagnosis path loads it."""
    return client.session.query(Founder).filter_by(user_id=client.founder_uuid).one()


# --- what was persisted -----------------------------------------------------
def test_the_persona_is_stored_with_a_resolved_industry(onboarded):
    row = _founder(onboarded)
    assert row.industry == PERSONA["industry_label"]
    assert row.team_size == PERSONA["team_size"]
    assert row.business_model == PERSONA["business_model"]
    assert row.industry_mapped_id is not None, "industry_mapped_id was not written"

    code = onboarded.session.execute(
        text("SELECT industry_code FROM industries WHERE industry_id = :i"),
        {"i": row.industry_mapped_id},
    ).scalar()
    assert code == PERSONA["expected_industry_code"]


def test_the_stage_resolved_to_stage_0(onboarded):
    row = _founder(onboarded)
    assert row.stage is not None
    assert row.stage.stage_order == PERSONA["expected_stage_order"]


# --- the acceptance assertion ----------------------------------------------
def test_founder_context_carries_the_whole_persona(onboarded):
    row = _founder(onboarded)
    ctx = FounderContext.from_founder(
        row, industry_code=resolve_industry_code(row.industry)
    )

    assert ctx.industry_code == PERSONA["expected_industry_code"]
    assert ctx.team_size == PERSONA["team_size"]
    assert ctx.business_model == PERSONA["business_model"]
    assert ctx.stage_order == PERSONA["expected_stage_order"]

    # ...and the verdicts those values imply. Nothing is filtered yet; these are
    # the answers the eligibility layer will consume in the next step.
    assert ctx.verdict("industry:agritech") is Applicability.SATISFIED
    assert ctx.verdict("industry:saas") is Applicability.CONTRADICTED
    assert ctx.verdict("has_team") is Applicability.CONTRADICTED
    assert ctx.verdict("model:b2b") is Applicability.SATISFIED
    assert FAMILY_INDUSTRY not in ctx.unknowns
    assert FAMILY_TEAM not in ctx.unknowns


def test_the_relationship_alone_is_enough_to_build_the_context(onboarded):
    # No caller needs to pass industry_code: industry_mapped_id is now written,
    # so the loaded relationship carries it. This is the path the service takes.
    row = _founder(onboarded)
    ctx = FounderContext.from_founder(row)
    assert ctx.industry_code == PERSONA["expected_industry_code"]
    assert ctx.knows_industry is True


def test_the_same_values_reach_the_advisor_brief(onboarded):
    # `founder_brief.py` has always rendered "Team size" and "Business model"
    # lines. They were unreachable because nothing wrote the columns, so every
    # brief omitted them. This is the propagation proof for the prompt path that
    # already exists -- the advisor now sees who it is talking to.
    row = _founder(onboarded)
    brief = build_founder_brief(onboarded.session, row)

    assert "Team size: solo" in brief
    assert "Business model: B2B" in brief
    assert "Industry: Agriculture" in brief
    assert "Stage: Ideation" in brief


def test_resolution_is_stable_through_the_repository_and_the_resolver(onboarded):
    # The two paths that can produce an industry id -- the repository's write
    # and a direct resolver call -- must agree, or a founder's stored mapping
    # and a freshly computed one could differ.
    row = _founder(onboarded)
    assert resolve_industry_id(onboarded.session, row.industry) == row.industry_mapped_id


# --- the fail-open half -----------------------------------------------------
def test_a_founder_who_answered_none_of_it_is_unknown_everywhere(founder_client):
    # The 46-of-47 case. Nothing is contradicted, so nothing will be filtered.
    ctx = FounderContext.from_founder(_founder(founder_client))
    assert ctx.industry_code is None
    assert ctx.team_size is None
    assert ctx.business_model is None
    assert ctx.verdict("industry:agritech") is Applicability.UNKNOWN
    assert ctx.verdict("has_team") is Applicability.UNKNOWN
    assert ctx.verdict("model:b2b") is Applicability.UNKNOWN
    assert ctx.knows_industry is False
