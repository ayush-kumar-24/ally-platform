"""Ally's recommendations are the Rs 999 tier's, and now something enforces it.

`Feature.RECOMMENDATIONS` has sat in `_ADVISOR` since the tiers were written.
Free carries it only through `_FREE_TESTING`; `_FREE_AT_LAUNCH` drops it. So the
catalog describes a boundary that arrives the moment PUBLIC_LAUNCH is set.

Nothing checked the flag. A grep for `Feature.RECOMMENDATIONS` outside
catalog.py returned NOTHING, which means flipping PUBLIC_LAUNCH would have
withheld Vision and the knowledge base and gone on serving recommendations to
Free -- a launch-day surprise that looks like a pricing bug to whoever notices.

The product decision these pin: every tier gets the diagnosis, the report and
their next three priorities. Being told what to DO about them is paid.
"""

from dataclasses import dataclass

import pytest

from app.api.v1.reports.routes import _RECOMMENDATION_SECTIONS, _visible_to
from app.plans.catalog import Feature, PlanTier, _FREE_AT_LAUNCH, _FREE_TESTING


# --- the catalog's own promise ----------------------------------------


def test_recommendations_is_an_advisor_feature():
    from app.plans.catalog import PLANS

    assert Feature.RECOMMENDATIONS in PLANS[PlanTier.PRO].features
    assert Feature.RECOMMENDATIONS not in PLANS[PlanTier.BASIC].features


def test_free_carries_it_only_until_public_launch():
    """The whole reason this gate can be added safely today."""
    assert Feature.RECOMMENDATIONS in _FREE_TESTING
    assert Feature.RECOMMENDATIONS not in _FREE_AT_LAUNCH


def test_the_flag_is_what_switches_the_two():
    from app.plans import catalog

    source = __import__("pathlib").Path(catalog.__file__).read_text(encoding="utf-8")
    assert "_FREE_FEATURES = _FREE_AT_LAUNCH if settings.PUBLIC_LAUNCH else _FREE_TESTING" in source


# --- withholding -------------------------------------------------------


@dataclass(frozen=True)
class _Section:
    key: str
    heading: str = "h"
    prose: str = "p"
    facts: tuple = ()


@dataclass(frozen=True)
class _Narrative:
    sections: tuple
    unpopulated_sections: tuple = ()


class _Founder:
    def __init__(self, tier):
        self.plan_type = tier


class _Entitlements:
    def __init__(self, allowed):
        self.allowed = allowed

    def has_feature(self, tier, feature):
        return feature in self.allowed


@pytest.fixture
def patched(monkeypatch):
    def _apply(allowed):
        from app.api.v1.reports import routes

        monkeypatch.setattr(routes.container, "entitlement_service",
                            lambda db: _Entitlements(allowed))
    return _apply


def _narrative():
    return _Narrative(sections=(
        _Section("founder_dna"), _Section("business_dna"),
        _Section("priority_actions"), _Section("closing"),
    ))


def test_an_entitled_founder_sees_every_section(patched):
    patched({Feature.RECOMMENDATIONS})
    out = _visible_to(_narrative(), _Founder(PlanTier.PRO), db=None)
    assert [s.key for s in out.sections] == [
        "founder_dna", "business_dna", "priority_actions", "closing"]


def test_an_unentitled_founder_loses_only_the_recommendations(patched):
    """Everything they paid nothing for, they still get."""
    patched(set())
    out = _visible_to(_narrative(), _Founder(PlanTier.FREE), db=None)
    assert [s.key for s in out.sections] == [
        "founder_dna", "business_dna", "closing"]


def test_the_withheld_section_is_reported_as_unpopulated(patched):
    """So the client renders "not in your plan" rather than a silent hole."""
    patched(set())
    out = _visible_to(_narrative(), _Founder(PlanTier.FREE), db=None)
    assert "priority_actions" in out.unpopulated_sections


def test_unpopulated_sections_are_not_duplicated(patched):
    patched(set())
    n = _Narrative(sections=(_Section("founder_dna"),),
                   unpopulated_sections=("priority_actions", "closing"))
    out = _visible_to(n, _Founder(PlanTier.FREE), db=None)
    assert list(out.unpopulated_sections).count("priority_actions") == 1


def test_the_original_narrative_is_not_mutated(patched):
    """It is the cached narrative_snapshot for every other reader of this
    report, including the share link -- filtering it in place would withhold
    the section from people whose plan was never consulted."""
    patched(set())
    original = _narrative()
    _visible_to(original, _Founder(PlanTier.FREE), db=None)
    assert [s.key for s in original.sections] == [
        "founder_dna", "business_dna", "priority_actions", "closing"]


# --- every door, not just the one named after the feature --------------


def test_all_three_founder_facing_routes_filter():
    """`/reports/{id}` returns every section inline and `/document` renders
    them into the PDF's markup, so gating only the recommendations endpoint
    leaves the same prose readable through two other routes."""
    from pathlib import Path

    from app.core.paths import BACKEND_DIR

    source = (BACKEND_DIR / "app" / "api" / "v1" / "reports" / "routes.py").read_text(
        encoding="utf-8")
    # Three, not two: /export joined /reports/{id} and /document when the
    # strategic-direction section became paid -- a plan-filtered PDF is
    # rendered per download and never stored (see export_pdf). /insights is
    # gated too, through a differently-shaped call that
    # test_report_capability_sections pins separately.
    assert source.count("_visible_to(_build_narrative(db, report), founder, db)") == 3
    assert 'dependencies=[Depends(require_recommendations)]' in source


def test_the_dedicated_endpoint_refuses_rather_than_returning_empty():
    from app.api.v1.reports import routes

    assert routes.require_recommendations is not None
    source = __import__("pathlib").Path(routes.__file__).read_text(encoding="utf-8")
    block = source.split('@router.get("/{report_id}/recommendations"', 1)[1][:400]
    assert "require_recommendations" in block


def test_the_share_route_is_deliberately_untouched():
    """A share token is a credential the founder chose to hand out; the viewer
    has no founder row and no plan to evaluate. Gating it would 500 or, worse,
    read an entitlement for somebody who is not the viewer."""
    from app.core.paths import BACKEND_DIR

    source = (BACKEND_DIR / "app" / "api" / "v1" / "reports" / "routes.py").read_text(
        encoding="utf-8")
    shared = source.split("def shared_report(", 1)[1].split("@", 1)[0]
    assert "_visible_to" not in shared
