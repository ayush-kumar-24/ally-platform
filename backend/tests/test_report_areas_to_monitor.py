"""The "areas to monitor" report, and the missing write that made it unreachable.

NO_CATEGORY_ABOVE_THRESHOLD_ACTION says that when every category sits below its
risk threshold the report must not force a diagnosis -- it should say no single
critical issue was found and surface the highest sub-threshold categories to
watch instead.

All of that was already built: the NO_CLEAR_DIAGNOSIS variant, its section
order, the slot builder that passes category NAMES only (never the raw 0..1
score), and the narrator copy. None of it could ever run.

`select_variant` gates the variant on `payload.category_risk_scores and not
payload.any_category_flagged`. `sessions.category_risk_scores` had readers and
no writer -- every row sat at the `{}` server default -- and an empty dict is
falsy, so the first half of that condition was never true. Every clean session
fell through to LOW_CONFIDENCE and the founder got a hedged diagnosis instead of
an all-clear.

These tests pin the write, its shape, and the variant it unlocks.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.api.v1.reasoning.service import category_risk_map
from app.api.v1.reports.payload import ReportPayload
from app.api.v1.reports.variants import ReportVariant, select_variant


def _risk(category, normalised, flagged):
    return SimpleNamespace(
        category=category, normalised_risk=Decimal(normalised), is_flagged=flagged,
        raw_score=Decimal("0"), max_score=Decimal("1"),
    )


def _payload(**kw):
    defaults = dict(
        report_id=1, founder_id=1, session_id=1, founder_name="A",
        tone_code=None, tone_persona=None, session_state=None,
        distress_acknowledged_first=False, overall_confidence_score=45.0,
        business_health_overall=None, business_health_band=None,
        pillars=(), red_flag_pillars=(), archetype=None, top_root_causes=(),
        confirm_actions=(), solve_actions=(), cat_risk_threshold=0.30,
        generate_report_min=80.0,
    )
    defaults.update(kw)
    return ReportPayload(**defaults)


# --- the shape written onto the session ------------------------------------

#: The real writer, so these tests cannot pass against a shape production
#: stopped producing.
_written = category_risk_map


def test_scores_are_stored_per_category_as_the_payload_reads_them():
    written = _written([
        _risk("Product", "0.20", False), _risk("Sales & Revenue", "0.14", False),
    ])
    payload = _payload(category_risk_scores=written)

    assert payload.any_category_flagged is False
    assert dict(payload.top_sub_threshold_categories)["Product"] == 0.20


def test_a_flagged_category_reads_back_as_flagged():
    written = _written([_risk("Product", "0.55", True), _risk("Sales", "0.10", False)])
    assert _payload(category_risk_scores=written).any_category_flagged is True


def test_the_threshold_boundary_counts_as_flagged():
    """>= CAT_RISK_THRESHOLD, matching the engine's own is_flagged rule."""
    written = _written([_risk("Product", "0.30", True)])
    assert _payload(category_risk_scores=written).any_category_flagged is True


def test_scores_survive_as_text_without_float_drift():
    """Stored via str(Decimal), not float(): a threshold test reads these back,
    and binary-float drift on a boundary value would flip a variant."""
    written = _written([_risk("Product", "0.30", True)])
    assert written == {"Product": "0.30"}
    assert _payload(category_risk_scores=written)._category_value("Product") == 0.30


# --- the variant the write unlocks -----------------------------------------

def test_a_clean_session_now_reaches_the_no_clear_diagnosis_variant():
    written = _written([
        _risk("Product", "0.20", False), _risk("Sales", "0.14", False),
        _risk("Team & Leadership", "0.05", False),
    ])
    assert select_variant(_payload(category_risk_scores=written)) is (
        ReportVariant.NO_CLEAR_DIAGNOSIS)


def test_the_regression_an_unwritten_column_makes_the_variant_unreachable():
    """The bug itself. With `{}` the founder gets a hedged diagnosis rather than
    an all-clear, however clean their answers were."""
    assert select_variant(_payload(category_risk_scores={})) is (
        ReportVariant.LOW_CONFIDENCE)


def test_a_flagged_session_still_gets_a_real_diagnosis():
    written = _written([_risk("Product", "0.65", True), _risk("Sales", "0.10", False)])
    payload = _payload(category_risk_scores=written, overall_confidence_score=89.0)
    assert select_variant(payload) is ReportVariant.STANDARD


def test_distress_still_outranks_an_all_clear():
    """Wellbeing before diagnostic completeness -- a founder in distress is not
    all-clear however clean their business answers were."""
    written = _written([_risk("Product", "0.10", False)])
    payload = _payload(category_risk_scores=written, distress_acknowledged_first=True)
    assert select_variant(payload) is ReportVariant.DISTRESS


# --- what the founder actually reads ---------------------------------------

def test_only_the_top_three_areas_are_named():
    """The doc asks for 2-3. Naming eight areas to watch ranks none of them --
    the same failure the flagged-category headline was already fixed for."""
    written = _written([
        _risk(f"Cat {i}", f"0.{20 - i}", False) for i in range(8)
    ])
    assert len(_payload(category_risk_scores=written).top_sub_threshold_categories) == 3


def test_areas_are_ordered_worst_first():
    written = _written([
        _risk("Low", "0.05", False), _risk("High", "0.28", False),
        _risk("Mid", "0.17", False),
    ])
    names = [c for c, _ in _payload(
        category_risk_scores=written).top_sub_threshold_categories]
    assert names == ["High", "Mid", "Low"]


def test_the_copy_names_categories_without_leaking_the_raw_score():
    """The score is an internal 0..1 number. Handing it to the narrator let it
    surface as "(scoring 0.2 and 0.18)" in founder-facing prose."""
    from app.api.v1.reports.narrator import TemplateNarrator

    prose = TemplateNarrator()._areas_to_monitor(
        {"categories": ["Product", "Sales"]}, None)

    assert "no single critical issue" in prose.lower()
    assert "Product" in prose and "Sales" in prose
    assert "0." not in prose


def test_the_copy_holds_up_when_there_are_no_categories_to_name():
    from app.api.v1.reports.narrator import TemplateNarrator

    prose = TemplateNarrator()._areas_to_monitor({"categories": []}, None)
    assert prose and "critical issue" in prose.lower()
