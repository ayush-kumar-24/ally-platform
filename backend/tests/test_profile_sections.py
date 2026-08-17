"""Section endpoints (founder / business / goals) + provisioning.

Drives the real endpoints against a founder seeded inside a rolled-back
transaction, so nothing persists.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, get_current_founder
from app.db.session import engine, get_db
from app.main import app
from app.services.provisioning import ensure_founder

BASE = "/api/v1/profile"


@pytest.fixture
def founder_client():
    """A client authenticated as a freshly-seeded founder; all rolled back."""
    uid = uuid.uuid4()
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    conn.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                 {"i": str(uid), "e": f"t{uid.hex[:8]}@x.com"})
    fid = conn.execute(
        text("select create_founder_on_signup(:u,:n,:e,:p,:t,:i,:b)"),
        dict(u=str(uid), n="Sec Test", e=f"t{uid.hex[:8]}@x.com", p="v1", t="v1", i="127.0.0.1", b="test"),
    ).scalar()

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_founder] = lambda: AuthUser(id=str(uid), email="x@y.com", provider="test")
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()
        session.close()
        trans.rollback()
        conn.close()


def test_founder_section_update_and_read(founder_client):
    """Post 2026-08-17 onboarding redesign, /profile/founder only carries name
    + experience -- founder_motivation/support_preferences/emotional_state/
    decision_making_style/adaptive_reflection were retired from onboarding and
    are no longer accepted here (they still exist as founders columns, still
    readable via GET /profile, just no longer written by this section)."""
    client, _ = founder_client
    r = client.patch(f"{BASE}/founder", json={"experience_level": "serial"})
    assert r.status_code == 200, r.text
    assert r.json()["experience_level"] == "serial"
    # read back
    assert client.get(f"{BASE}/founder").json()["experience_level"] == "serial"


def test_founder_section_rejects_retired_fields(founder_client):
    """The 5 fields this section dropped in the redesign must 422 as unknown,
    not be silently accepted and dropped -- a client relying on the old
    contract should find out immediately, not lose data quietly."""
    client, _ = founder_client
    r = client.patch(f"{BASE}/founder", json={
        "founder_motivation": "to fix churn",
        "support_preferences": ["sales", "hiring"],
        "emotional_state": ["determined", "hopeful"],
        "decision_making_style": "fast",
        "adaptive_reflection": "reflecting",
    })
    assert r.status_code == 422
    for field in ("founder_motivation", "support_preferences", "emotional_state",
                  "decision_making_style", "adaptive_reflection"):
        assert field in r.text


def test_founder_section_rejects_foreign_field(founder_client):
    client, _ = founder_client
    # goal_90_day belongs to /goals, not /founder
    r = client.patch(f"{BASE}/founder", json={"goal_90_day": "x"})
    assert r.status_code == 422


def test_business_section_resolves_stage_name(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={
        "stage": "Validation",
        "building_summary": "an AI copilot",
        "current_challenges": ["retention"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["stage_id"] == 2          # Validation -> stage_id 2
    assert r.json()["building_summary"] == "an AI copilot"


def test_business_section_rejects_bad_stage(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={"stage": "Plateau"})
    assert r.status_code == 422


# --- onboarding multi-selects ------------------------------------------------

def test_customer_segment_stores_multiple_chips(founder_client):
    """"Who are you building this for?" is a multi-select, so several segments
    have to survive the round trip rather than the last one winning."""
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={
        "customer_segment": ["Businesses", "Developers", "Enterprises"],
        "customer_segment_other": "Independent research labs",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["customer_segment"] == ["Businesses", "Developers", "Enterprises"]
    assert body["customer_segment_other"] == "Independent research labs"


def test_customer_segment_dedupes_and_trims(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={
        "customer_segment": ["Businesses", "  businesses ", "", "Students"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["customer_segment"] == ["Businesses", "Students"]


def test_challenges_uncapped(founder_client):
    """The old onboarding capped this at 3; the 2026-08-17 redesign's biggest-
    challenge question does not, so more than 3 must now go through cleanly."""
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={
        "current_challenges": ["Sales", "Hiring", "Cash flow", "Scaling"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["current_challenges"] == ["Sales", "Hiring", "Cash flow", "Scaling"]


def test_challenges_other_captures_free_text(founder_client):
    """Live-reproduced bug this redesign fixes: picking "Other" on the
    biggest-challenge question had nowhere for the typed text to land, so it
    was silently discarded. current_challenges_other is that missing field."""
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={
        "current_challenges": ["Sales", "Other"],
        "current_challenges_other": "Investor relations",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["current_challenges"] == ["Sales", "Other"]
    assert body["current_challenges_other"] == "Investor relations"


def test_product_description_distinct_from_building_summary(founder_client):
    """Path 2's "What are you building?" (building_summary, the name) and
    "What is it?" (product_description, the one-liner) must be two real,
    independently-readable fields, not the same value doing double duty."""
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={
        "building_summary": "Ally",
        "product_description": "A founder diagnosis engine that finds root causes.",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["building_summary"] == "Ally"
    assert body["product_description"] == "A founder diagnosis engine that finds root causes."


def test_founder_reality_signals_round_trip(founder_client):
    """Shown to both paths -- all 5 fixed keys, submitted as one object."""
    client, _ = founder_client
    signals = {
        "clear_next_priorities": True, "decisive": False,
        "effort_aligned_to_growth": True, "executes_consistently": False,
        "mentally_clear": True,
    }
    r = client.patch(f"{BASE}/business", json={"founder_reality_signals": signals})
    assert r.status_code == 200, r.text
    assert r.json()["founder_reality_signals"] == signals


def test_founder_reality_signals_rejects_partial_submission(founder_client):
    """All 5 are answered together as one screen -- a partial object (missing
    a key) is rejected rather than silently stored as an incomplete read."""
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={
        "founder_reality_signals": {"clear_next_priorities": True},
    })
    assert r.status_code == 422


def test_business_reality_signals_stays_null_until_written(founder_client):
    """The whole point of no server_default on this column: a Stage 0 founder
    who never sees this question (not applicable) and a Path 2 founder who
    hasn't reached it yet (not answered yet) must both read back as null --
    there is no third state to fake a distinction with, so this just confirms
    the column truly starts and stays null until explicitly written."""
    client, _ = founder_client
    assert client.get(f"{BASE}/business").json()["business_reality_signals"] is None

    signals = {
        "revenue_predictable": True, "systems_defined": True,
        "plans_become_execution": False, "team_independent": False,
        "financials_clear": True,
    }
    r = client.patch(f"{BASE}/business", json={"business_reality_signals": signals})
    assert r.status_code == 200, r.text
    assert r.json()["business_reality_signals"] == signals


def test_monthly_revenue_keeps_existing_bands(founder_client):
    """Revenue is new to onboarding, but writes into an already-live column --
    kept on the existing coded bands (pre_revenue..above_1Cr) rather than the
    redesign brief's proposed new ones, per an explicit product call."""
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={"current_revenue": "5L_25L"})
    assert r.status_code == 200, r.text
    assert r.json()["current_revenue"] == "5L_25L"

    bad = client.patch(f"{BASE}/business", json={"current_revenue": "5L_20L"})
    assert bad.status_code == 422  # not a real band -- the redesign brief's proposal, not ours


# --- social handle (Instagram or LinkedIn) via generic PATCH /profile -------

def test_social_handle_normalises_bare_domain_to_https(founder_client):
    """The most likely thing someone actually types here has no scheme --
    accepted and normalised rather than rejected."""
    client, _ = founder_client
    r = client.patch(BASE, json={"linkedin_url": "instagram.com/somefounder"})
    assert r.status_code == 200, r.text
    assert r.json()["linkedin_url"] == "https://instagram.com/somefounder"


def test_social_handle_rejects_garbage(founder_client):
    client, _ = founder_client
    r = client.patch(BASE, json={"linkedin_url": "not a url at all"})
    assert r.status_code == 422


def test_invisible_gaps_multi_select(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/business", json={
        "invisible_gaps": ["Business depends heavily on me", "No clear roadmap"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["invisible_gaps"] == ["Business depends heavily on me", "No clear roadmap"]


def test_goals_section(founder_client):
    client, _ = founder_client
    r = client.patch(f"{BASE}/goals", json={"goal_90_day": "ship v1", "vision_1_year": "1000 users"})
    assert r.status_code == 200
    assert r.json() == {"goal_90_day": "ship v1", "vision_1_year": "1000 users"}


def test_partial_update_leaves_other_fields(founder_client):
    client, _ = founder_client
    client.patch(f"{BASE}/founder", json={"experience_level": "mentor"})
    client.patch(f"{BASE}/goals", json={"goal_90_day": "unrelated"})
    # the founder-section field survived a goals update
    assert client.get(f"{BASE}/founder").json()["experience_level"] == "mentor"


# --- provisioning -----------------------------------------------------------

def test_provisioning_is_idempotent(founder_client):
    _, uid = founder_client
    # a second ensure_founder for the same identity returns the existing row, no dup
    conn = engine.connect(); trans = conn.begin(); session = Session(bind=conn)
    try:
        session.execute(text("insert into auth.users (id, email) values (:i, :e)"),
                        {"i": str(uid_2 := uuid.uuid4()), "e": f"t{uid_2.hex[:8]}@x.com"})
        ident = AuthUser(id=str(uid_2), email=f"t{uid_2.hex[:8]}@x.com", provider="supabase")
        f1 = ensure_founder(ident, session)
        f2 = ensure_founder(ident, session)
        assert f1 is not None and f1.founder_id == f2.founder_id
    finally:
        session.close(); trans.rollback(); conn.close()


def test_dev_identity_not_provisioned():
    conn = engine.connect(); trans = conn.begin(); session = Session(bind=conn)
    try:
        ident = AuthUser(id="00000000-0000-0000-0000-000000000001", email="dev@ally.local", provider="dev")
        assert ensure_founder(ident, session) is None  # dev never provisions
    finally:
        session.close(); trans.rollback(); conn.close()
