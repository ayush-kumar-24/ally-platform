"""Does every promise on the pricing page have a gate behind it?

The pricing page is a claim about what each tier can and cannot do. A claim with
no server-side enforcement is not a plan boundary -- it is a suggestion, and any
founder who opens devtools can ignore it. This file drives the REAL routes with a
founder on each tier and records what actually happens, so the page and the API
cannot drift apart silently.

`get_db` is stubbed: every gate under test resolves through
`EntitlementService.require_feature`, which is pure catalog (see
plans/service.py) and touches no table. What is being tested is the WIRING --
whether the route asks at all -- not the catalog, which test_plans.py covers.
"""

from __future__ import annotations

import pytest

from app.api.deps import get_founder_record
from app.db.session import get_db
from app.main import app
from app.plans.catalog import PLANS, Feature, PlanTier

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

PAID = (PlanTier.BASIC, PlanTier.STARTER, PlanTier.PRO)


class _Founder:
    """The two attributes every gate reads off the founder row."""

    def __init__(self, tier: PlanTier):
        self.founder_id = 1
        self.plan_type = tier.value
        self.email = "f@example.com"
        self.user_id = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def client_for():
    from fastapi.testclient import TestClient

    def _make(tier: PlanTier):
        app.dependency_overrides[get_founder_record] = lambda: _Founder(tier)
        app.dependency_overrides[get_db] = lambda: None
        return TestClient(app, raise_server_exceptions=False)

    yield _make
    for dep in (get_founder_record, get_db):
        app.dependency_overrides.pop(dep, None)


def _refused_for_plan(response) -> bool:
    """Did the plan gate refuse this, as opposed to anything else going wrong?

    402/403 is the entitlement refusal. Anything else -- including a 500 from the
    stubbed session once the gate has ALLOWED the request through -- is not a
    refusal, which is the distinction these tests turn on.
    """
    return response.status_code in (402, 403)


# --- Vision: promised on Pro only -------------------------------------------


@pytest.mark.parametrize("tier", PAID)
def test_vision_is_refused_below_pro_and_allowed_on_pro(client_for, tier):
    r = client_for(tier).get("/api/v1/vision")
    expected = tier is not PlanTier.PRO
    assert _refused_for_plan(r) is expected, (tier, r.status_code)


@pytest.mark.parametrize("tier", PAID)
def test_saving_a_vision_territory_is_gated_too(client_for, tier):
    """The write path matters more than the read: an ungated PUT would let an
    off-plan founder store territories they cannot read back."""
    r = client_for(tier).put("/api/v1/vision/territories/wealth",
                             json={"statement": "x", "tag1": None, "tag2": None})
    expected = tier is not PlanTier.PRO
    assert _refused_for_plan(r) is expected, (tier, r.status_code)


def test_the_vision_image_route_is_not_behind_the_plan_gate():
    """It is unauthenticated by necessity -- an <img src> sends no Authorization
    header -- so a plan gate here would 401/403 every vision picture, including
    for the Pro founders the gate exists to serve."""
    from fastapi.testclient import TestClient

    r = TestClient(app, raise_server_exceptions=False).get(
        "/api/v1/vision/image/1/nope.png")
    assert not _refused_for_plan(r), r.status_code


# --- Plan Your Day: promised on Plus and Pro --------------------------------


@pytest.mark.parametrize("tier", PAID)
def test_plan_your_day_is_refused_on_the_report_only_tier(client_for, tier):
    r = client_for(tier).get("/api/v1/planning/plans/today")
    expected = tier is PlanTier.BASIC
    assert _refused_for_plan(r) is expected, (tier, r.status_code)


# --- Goals: promised on Plus and Pro ----------------------------------------


@pytest.mark.parametrize("tier", PAID)
def test_goals_are_refused_on_the_report_only_tier(client_for, tier):
    r = client_for(tier).get("/api/v1/goals")
    expected = tier is PlanTier.BASIC
    assert _refused_for_plan(r) is expected, (tier, r.status_code)


@pytest.mark.parametrize("tier", PAID)
def test_creating_a_goal_is_gated_too(client_for, tier):
    r = client_for(tier).post("/api/v1/goals", json={"title": "ship it"})
    expected = tier is PlanTier.BASIC
    assert _refused_for_plan(r) is expected, (tier, r.status_code)


# --- The catalog's own promises need somewhere to be enforced ---------------


#: Feature -> whether any route enforces it today. Every False here is a line on
#: the pricing page with nothing behind it; see test below.
_ENFORCED = {
    Feature.ALLY_CHAT: True,        # plans/service.py check_chat_allowed
    Feature.VOICE_CHAT: True,       # voice/router.py
    Feature.VOICE_DIAGNOSIS: True,  # voice/router.py
    Feature.PLAN_YOUR_DAY: True,    # planning/dependencies.py
    Feature.VISION: True,           # vision/dependencies.py
    Feature.KNOWLEDGE_CHAT: True,   # plans/dependencies.py -> context window
    Feature.PRIORITY_CALL: True,    # discovery/routes.py
    Feature.DIAGNOSIS: True,        # universal; nothing to refuse
    Feature.REPORTS: True,          # universal
    Feature.CALL_BOOKING: True,     # universal
    Feature.GOALS: True,            # founder_goals/dependencies.py
    # Served by /reports/{id}/recommendations -- a SLICE OF THE REPORT that
    # Rs 199 pays for, not a separate module. Gating it would withhold part
    # of the report that tier buys, so it needs a product decision, not a
    # dependency. Same endpoint backs RECOMMENDATIONS below.
    Feature.NEXT_STEPS: False,
    Feature.RECOMMENDATIONS: False,
    Feature.EMAIL_NOTIFICATIONS: False,
    Feature.KNOW_MY_ENERGY: False,
}


def test_every_feature_is_accounted_for_in_the_enforcement_map():
    """A feature added to the catalog without a decision about enforcement is
    how an ungated promise reaches the pricing page unnoticed."""
    assert set(_ENFORCED) == set(Feature), set(Feature) ^ set(_ENFORCED)


@pytest.mark.xfail(strict=True, reason=(
    "Four advertised paid differences have no server-side enforcement. Marked "
    "xfail(strict) rather than deleted or loosened: a permanently red test "
    "blocks deploys and gets ignored, while strict xfail keeps the gap visible "
    "AND fails the moment someone closes it without updating _ENFORCED."))
def test_a_tier_difference_the_page_advertises_is_actually_enforced():
    """Any feature that DIFFERS between paid tiers is a paywall the page draws.
    If it is unenforced, the cheaper tier can simply call the endpoint.

    Still failing for four, each for a different reason and none of them an
    oversight to fix by adding a dependency:

      next_steps, recommendations -- both served by
        /reports/{id}/recommendations, which is report content Rs 199 pays for.
        Splitting the report needs a product decision.
      email_notifications -- there is no email-sending path in the backend at
        all, so there is nothing yet to refuse.
      know_my_energy -- declared in the catalog before the feature is built
        (see the catalog's own note).

    Recorded rather than hidden: this belongs in CI, not in a founder's
    devtools.
    """
    differing = [f for f in Feature
                 if len({PLANS[t].includes(f) for t in PAID}) > 1]
    unenforced = sorted(f.value for f in differing if not _ENFORCED[f])
    assert unenforced == [], (
        "advertised as a paid difference but not enforced anywhere: "
        f"{unenforced}")
