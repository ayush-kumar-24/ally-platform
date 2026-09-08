"""The features that had no server-side gate, and now do.

The bug these cover: PUBLIC_LAUNCH=true empties the Free tier and the frontend
redirects a plan-less founder to billing -- but DIAGNOSIS, REPORTS and GOALS
had no `require_feature` call anywhere, so every one of those endpoints still
answered a direct API call. The UI said "buy a plan"; the API said "here you
go".

Two layers here on purpose:

  STRUCTURAL -- the router carries the dependency. This is what actually
  regresses: somebody adds an endpoint, or refactors a router declaration, and
  the gate quietly stops being applied to anything. Asserting on
  `router.dependencies` catches that; asserting only on the gate function would
  keep passing while nothing called it.

  BEHAVIOURAL -- the gate refuses an empty plan and admits a sufficient one.

Hermetic: no database. The gates take a Founder and a Session, but the Session
is only handed to the entitlement service, which for a pure feature check
consults the catalog and never queries.
"""

import pytest

from app.api.v1.entitlement_gates import require_diagnosis, require_goals, require_reports
from app.plans.catalog import _FREE_AT_LAUNCH, PLANS, Feature, PlanTier
from app.plans.errors import FeatureNotInPlanError
from app.plans.service import build_entitlement_service


class Founder:
    """Just the attribute the gates read."""

    def __init__(self, plan_type):
        self.plan_type = plan_type
        self.founder_id = 1


@pytest.fixture(autouse=True)
def _catalog_only_service(monkeypatch):
    """Point container.entitlement_service at a database-free service.

    The real one builds a SqlAlchemyUsageRepository; a feature check never
    touches it, but constructing it needs a live Session.
    """
    from app.core import container as container_mod

    monkeypatch.setattr(
        container_mod.container, "entitlement_service",
        lambda db: build_entitlement_service(),
    )


# --- the catalog invariant these gates rely on ------------------------------


def test_free_at_launch_is_empty():
    """Everything else here is pointless if this ever stops being true: the
    gates are what turn 'Free has no features' into 'Free can do nothing'."""
    assert _FREE_AT_LAUNCH == frozenset()


# --- structural: the routers actually carry the gates -----------------------


def _router_gates(router):
    return {d.dependency for d in router.dependencies}


def test_diagnosis_router_is_gated():
    from app.api.v1.diagnosis.router import router
    assert require_diagnosis in _router_gates(router)


def test_goals_router_is_gated():
    from app.api.v1.founder_goals.router import router
    assert require_goals in _router_gates(router)


def test_reports_router_is_gated():
    from app.api.v1.reports.routes import router
    assert require_reports in _router_gates(router)


def test_intelligence_router_is_gated():
    """The second door to the same report content. Gating /reports and leaving
    /intelligence/reports/* open would have left the report readable anyway."""
    from app.api.v1.intelligence.routes import router
    assert require_reports in _router_gates(router)


def test_the_share_token_router_is_NOT_gated():
    """A share link is read by somebody who is not a founder and has no plan.
    Gating it would break every report a founder has ever sent to anyone."""
    from app.api.v1.reports.routes import public_router
    assert _router_gates(public_router) == set()


def test_share_endpoints_are_on_the_public_router_only():
    from app.api.v1.reports.routes import public_router, router

    public_paths = {r.path for r in public_router.routes}
    gated_paths = {r.path for r in router.routes}

    assert "/reports/shared/{token}" in public_paths
    assert "/reports/shared/{token}/view" in public_paths
    # And crucially, not also behind the gate.
    assert not any(p.startswith("/reports/shared/") for p in gated_paths)


# --- behavioural: refuse the plan-less, admit the entitled ------------------


@pytest.mark.parametrize("gate", [require_diagnosis, require_reports, require_goals])
def test_a_founder_with_no_features_is_refused(gate, monkeypatch):
    """The public-launch state: Free is empty, so every one of these refuses."""
    monkeypatch.setitem(
        PLANS, PlanTier.FREE, PLANS[PlanTier.FREE].__class__(
            **{**PLANS[PlanTier.FREE].__dict__, "features": frozenset()}
        ),
    )
    with pytest.raises(FeatureNotInPlanError):
        gate(founder=Founder("free"), db=None)


@pytest.mark.parametrize(
    "gate,feature",
    [
        (require_diagnosis, Feature.DIAGNOSIS),
        (require_reports, Feature.REPORTS),
        (require_goals, Feature.GOALS),
    ],
)
def test_the_error_names_the_feature_and_an_upgrade(gate, feature, monkeypatch):
    """A 403 that does not say what to buy is a dead end for the founder."""
    monkeypatch.setitem(
        PLANS, PlanTier.FREE, PLANS[PlanTier.FREE].__class__(
            **{**PLANS[PlanTier.FREE].__dict__, "features": frozenset()}
        ),
    )
    with pytest.raises(FeatureNotInPlanError) as exc:
        gate(founder=Founder("free"), db=None)
    assert exc.value.feature == feature.value
    assert exc.value.status_code == 403
    assert exc.value.required_plan, "the refusal must name the tier that includes it"


def test_a_paid_founder_passes_every_gate():
    """Pro carries the whole product, so none of these may refuse it."""
    for gate in (require_diagnosis, require_reports, require_goals):
        gate(founder=Founder("pro"), db=None)   # must not raise


def test_diagnosis_and_reports_are_included_from_the_cheapest_paid_tier():
    """Both are _BASE features. If the Rs 199 tier stopped including them the
    gates above would lock out the very people who paid for the diagnosis."""
    paid = [p for t, p in PLANS.items() if t is not PlanTier.FREE and p.price_inr > 0]
    cheapest = min(paid, key=lambda p: p.price_inr)
    assert cheapest.includes(Feature.DIAGNOSIS)
    assert cheapest.includes(Feature.REPORTS)
