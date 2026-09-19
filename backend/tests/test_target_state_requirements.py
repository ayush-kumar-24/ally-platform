"""Step 6: the target-state knowledge base and its specificity cascade.

THE CASCADE IS THE WHOLE STEP, so most of this file is about it. Synthetic rows
throughout: the resolver is data-driven, and a test built on the 54 seeded rows
would prove the curation rather than the mechanism, and would break the day
anyone adds a rule. The live seed is checked separately, at the bottom.

THE TWO TESTS THAT MATTER MOST are the ones guarding principles the rest of the
Future-State design rests on:

  test_unknown_context_never_activates_a_specific_rule
  test_unknown_context_keeps_every_wildcard_rule
      together: unknown narrows nothing and fabricates nothing. An incomplete
      profile yields a MORE GENERIC requirement set, never an empty one and
      never a specific one nobody established.

  test_equally_specific_disagreement_raises
      a curation error must not resolve silently, or a founder's requirements
      would depend on insertion order and nobody would ever find out.

And one that is about the step's boundary rather than its logic:

  test_resolution_never_looks_at_an_answer
      Step 6 produces requirements, not findings. No evidence is consulted, so
      no gap can be claimed.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.api.v1.diagnosis.target_state import (
    NECESSITY_VALUES,
    AmbiguousRequirementError,
    TargetStateContext,
    resolve_requirements,
)
from app.db.session import engine as db_engine

BAND = "1Cr_5Cr"
HORIZON = "12_months"


@pytest.fixture
def db():
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


def founder_ctx(industry="saas", business_model="B2B", stage_order=5):
    """A FounderContext double carrying only what the resolver reads."""
    return SimpleNamespace(
        industry_code=industry, business_model=business_model, stage_order=stage_order)


def row(requirement_id, *, capability_id=1, code="GTM-SALES", industry=None,
        business_model=None, from_stage_order=None, band=None, horizon=None,
        level=2, necessity="core", rationale="because"):
    """A capability_requirements row as the repository returns it."""
    return {
        "requirement_id": requirement_id, "capability_id": capability_id,
        "capability_code": code, "industry_code": industry,
        "business_model": business_model, "from_stage_order": from_stage_order,
        "target_revenue_band": band, "target_time_horizon": horizon,
        "required_level": level, "necessity": necessity, "rationale": rationale,
    }


def only(result):
    assert len(result) == 1, [r.capability_code for r in result]
    return result[0]


# =========================================================== 4-11: the cascade
def test_a_full_wildcard_rule_matches_everyone():
    """Case 4. Every dimension NULL -- applies whatever the founder's values."""
    got = only(resolve_requirements([row(1)], founder_ctx(), TargetStateContext(BAND)))
    assert got.required_level == CapabilityLevel.DOCUMENTED
    assert got.specificity == 0
    assert got.matched_on == ()


def test_a_more_specific_rule_overrides_the_wildcard():
    """Case 5."""
    rows = [row(1, level=1), row(2, band=BAND, level=3)]
    got = only(resolve_requirements(rows, founder_ctx(), TargetStateContext(BAND)))
    assert got.requirement_id == 2
    assert got.required_level == CapabilityLevel.OWNED


def test_an_industry_rule_overrides_a_generic_one():
    """Case 6."""
    rows = [row(1, band=BAND, level=1), row(2, band=BAND, industry="saas", level=3)]
    got = only(resolve_requirements(rows, founder_ctx(industry="saas"),
                                    TargetStateContext(BAND)))
    assert got.requirement_id == 2
    assert got.matched_on == ("industry_code", "target_revenue_band")


def test_a_business_model_rule_overrides_a_generic_one():
    """Case 7."""
    rows = [row(1, band=BAND, level=1), row(2, band=BAND, business_model="B2B", level=3)]
    got = only(resolve_requirements(rows, founder_ctx(business_model="B2B"),
                                    TargetStateContext(BAND)))
    assert got.requirement_id == 2


def test_a_stage_rule_applies_from_that_stage_onward():
    """Case 8. `from_stage_order` is an inclusive lower bound, not an equality."""
    rows = [row(1, band=BAND, from_stage_order=4, level=3)]
    for stage, expected in ((3, 0), (4, 1), (7, 1)):
        got = resolve_requirements(rows, founder_ctx(stage_order=stage),
                                   TargetStateContext(BAND))
        assert len(got) == expected, f"stage {stage}"


def test_a_revenue_band_rule_only_fires_for_that_band():
    """Case 9."""
    rows = [row(1, band="5Cr_25Cr")]
    assert resolve_requirements(rows, founder_ctx(), TargetStateContext("5Cr_25Cr"))
    assert resolve_requirements(rows, founder_ctx(), TargetStateContext("1Cr_5Cr")) == ()


def test_a_horizon_rule_only_fires_for_that_horizon():
    """Case 10."""
    rows = [row(1, band=BAND, horizon="6_months", level=3)]
    assert resolve_requirements(rows, founder_ctx(), TargetStateContext(BAND, "6_months"))
    assert resolve_requirements(rows, founder_ctx(),
                                TargetStateContext(BAND, "24_months")) == ()


def test_more_dimensions_beats_fewer():
    """Case 11. Specificity is the count of constrained dimensions."""
    rows = [
        row(1, band=BAND, level=0),
        row(2, band=BAND, industry="saas", level=1),
        row(3, band=BAND, industry="saas", business_model="B2B", level=2),
        row(4, band=BAND, industry="saas", business_model="B2B",
            from_stage_order=4, horizon=HORIZON, level=3),
    ]
    got = only(resolve_requirements(rows, founder_ctx(), TargetStateContext(BAND, HORIZON)))
    assert got.requirement_id == 4
    assert got.specificity == 5


def test_the_winner_is_independent_of_row_order():
    """Case 15. Determinism, asserted by shuffling the input."""
    rows = [row(1, band=BAND, level=0), row(2, band=BAND, industry="saas", level=3)]
    forward = only(resolve_requirements(rows, founder_ctx(), TargetStateContext(BAND)))
    backward = only(resolve_requirements(list(reversed(rows)), founder_ctx(),
                                         TargetStateContext(BAND)))
    assert forward.requirement_id == backward.requirement_id == 2


def test_results_are_ordered_by_capability_code():
    rows = [row(1, capability_id=2, code="ZZZ-LAST", band=BAND),
            row(2, capability_id=1, code="AAA-FIRST", band=BAND)]
    got = resolve_requirements(rows, founder_ctx(), TargetStateContext(BAND))
    assert [r.capability_code for r in got] == ["AAA-FIRST", "ZZZ-LAST"]


# =========================================================== 12: ambiguity
def test_equally_specific_disagreement_raises():
    """Case 12. A curation error must be loud, not silently resolved.

    Two rules of equal weight that disagree would otherwise make a founder's
    requirements depend on which row was inserted first.
    """
    rows = [row(1, industry="saas", level=1), row(2, business_model="B2B", level=3)]
    with pytest.raises(AmbiguousRequirementError) as exc:
        resolve_requirements(rows, founder_ctx(), TargetStateContext(BAND))
    assert "requirement 1" in str(exc.value) and "requirement 2" in str(exc.value)


def test_equally_specific_agreement_is_not_an_error():
    # Two predicates, one answer. Nothing to disagree about, so say it.
    rows = [row(1, industry="saas", level=2, necessity="core"),
            row(2, business_model="B2B", level=2, necessity="core")]
    got = only(resolve_requirements(rows, founder_ctx(), TargetStateContext(BAND)))
    assert got.required_level == CapabilityLevel.DOCUMENTED


def test_a_tighter_stage_bound_breaks_a_specificity_tie():
    """The one tie-break, and the only one: a narrower claim wins."""
    rows = [row(1, from_stage_order=2, level=1), row(2, from_stage_order=5, level=3)]
    got = only(resolve_requirements(rows, founder_ctx(stage_order=6),
                                    TargetStateContext(BAND)))
    assert got.requirement_id == 2


def test_ambiguity_in_one_capability_does_not_hide_the_others():
    # The error names the capability, so a curator fixes one row rather than
    # hunting through the table.
    rows = [row(1, capability_id=1, code="A", industry="saas", level=1),
            row(2, capability_id=1, code="A", business_model="B2B", level=3),
            row(3, capability_id=2, code="B", band=BAND)]
    with pytest.raises(AmbiguousRequirementError) as exc:
        resolve_requirements(rows, founder_ctx(), TargetStateContext(BAND))
    assert "capability_id 1" in str(exc.value)


# =========================================================== 13-14: unknown
def test_unknown_context_never_activates_a_specific_rule():
    """Case 13. Unknown cannot satisfy a constraint -- nothing is fabricated."""
    rows = [row(1, industry="saas", level=3), row(2, business_model="B2B", level=3),
            row(3, from_stage_order=4, level=3)]
    blank = founder_ctx(industry=None, business_model=None, stage_order=None)
    assert resolve_requirements(rows, blank, TargetStateContext(BAND)) == ()


def test_unknown_context_keeps_every_wildcard_rule():
    """Case 14. The failure mode: an incomplete profile losing its requirements."""
    rows = [row(1, band=BAND, level=2), row(2, band=BAND, industry="saas", level=3)]
    blank = founder_ctx(industry=None, business_model=None, stage_order=None)
    got = only(resolve_requirements(rows, blank, TargetStateContext(BAND)))
    assert got.requirement_id == 1, "the wildcard rule must survive unknown context"


def test_a_known_but_different_value_is_treated_like_unknown_for_that_rule():
    # Both fail to activate the saas rule; neither loses the wildcard.
    rows = [row(1, band=BAND, level=2), row(2, band=BAND, industry="saas", level=3)]
    for industry in (None, "fintech"):
        got = only(resolve_requirements(rows, founder_ctx(industry=industry),
                                        TargetStateContext(BAND)))
        assert got.requirement_id == 1


def test_no_target_resolves_to_no_band_specific_requirements():
    rows = [row(1, band=BAND), row(2, band="5Cr_25Cr")]
    assert resolve_requirements(rows, founder_ctx(), TargetStateContext()) == ()


def test_a_context_with_no_target_reports_that_it_was_never_stated():
    assert TargetStateContext().is_stated is False
    assert TargetStateContext(BAND).is_stated is True
    assert TargetStateContext(None, HORIZON).is_stated is True


# =========================================================== the boundary
def test_resolution_never_looks_at_an_answer():
    """Step 6 produces requirements, not findings.

    Asserted structurally: the resolver's inputs are rows, a founder context and
    a target -- there is no parameter through which evidence could arrive, and
    RequiredCapability has no field in which an observation could be stored.
    """
    import inspect

    from app.api.v1.diagnosis.target_state import RequiredCapability

    params = set(inspect.signature(resolve_requirements).parameters)
    assert params == {"rows", "founder_context", "target"}
    fields = set(RequiredCapability.__dataclass_fields__)
    for forbidden in ("observed_level", "evidence", "gap", "status", "is_met"):
        assert forbidden not in fields, f"{forbidden} belongs to Step 7/8"


def test_a_target_alone_produces_no_verdict():
    """The principle in one assertion: a 10x ambition, and no claim about it."""
    rows = [row(1, band="above_25Cr", level=3)]
    got = only(resolve_requirements(rows, founder_ctx(), TargetStateContext("above_25Cr")))
    assert got.required_level == CapabilityLevel.OWNED
    assert not hasattr(got, "gap")
    assert not hasattr(got, "status")


# =========================================================== 16-18: the live data
def test_every_requirement_references_a_real_capability(db):
    """Case 16."""
    orphans = db.execute(text(
        "SELECT r.requirement_id FROM capability_requirements r"
        "  LEFT JOIN capabilities c ON c.capability_id = r.capability_id"
        " WHERE c.capability_id IS NULL")).all()
    assert orphans == []


def test_required_level_is_within_the_capability_level_scale(db):
    """Case 17. Enforced by CHECK; asserted here against the live rows too."""
    levels = {lvl for (lvl,) in db.execute(text(
        "SELECT DISTINCT required_level FROM capability_requirements")).all()}
    assert levels
    assert levels <= {int(x) for x in CapabilityLevel}
    with pytest.raises(Exception):
        db.execute(text(
            "INSERT INTO capability_requirements"
            " (capability_id, required_level, necessity, rationale)"
            " VALUES ((SELECT capability_id FROM capabilities LIMIT 1), 4, 'core', 'x')"))
        db.flush()


def test_necessity_accepts_only_core_or_contextual(db):
    """Case 18."""
    values = {v for (v,) in db.execute(text(
        "SELECT DISTINCT necessity FROM capability_requirements")).all()}
    assert values <= NECESSITY_VALUES
    with pytest.raises(Exception):
        db.execute(text(
            "INSERT INTO capability_requirements"
            " (capability_id, required_level, necessity, rationale)"
            " VALUES ((SELECT capability_id FROM capabilities LIMIT 1), 2, 'nice', 'x')"))
        db.flush()


def test_every_requirement_carries_a_rationale(db):
    # A requirement nobody can explain is a rule nobody can challenge.
    blank = db.execute(text(
        "SELECT count(*) FROM capability_requirements"
        " WHERE rationale IS NULL OR length(trim(rationale)) < 20")).scalar()
    assert blank == 0


def test_the_database_refuses_two_rows_with_the_same_predicate(db):
    """The unique index with NULLS NOT DISTINCT is what keeps the resolver's
    ambiguity error for genuinely DIFFERENT predicates of equal weight."""
    existing = db.execute(text(
        "SELECT capability_id, industry_code, business_model, from_stage_order,"
        "       target_revenue_band, target_time_horizon"
        "  FROM capability_requirements LIMIT 1")).mappings().first()
    with pytest.raises(Exception):
        db.execute(text(
            "INSERT INTO capability_requirements"
            " (capability_id, industry_code, business_model, from_stage_order,"
            "  target_revenue_band, target_time_horizon, required_level,"
            "  necessity, rationale)"
            " VALUES (:capability_id, :industry_code, :business_model,"
            "         :from_stage_order, :target_revenue_band,"
            "         :target_time_horizon, 3, 'core', 'a duplicate predicate')"),
            dict(existing))
        db.flush()


def test_the_seeded_knowledge_base_resolves_without_ambiguity(db, capsys):
    """Every plausible context, against the real rows. No exceptions allowed.

    This is what makes the curation safe to extend: adding a rule that collides
    with an existing one fails here rather than in front of a founder.
    """
    rows = DiagnosisRepository(db).capability_requirement_rows()
    assert rows, "no requirements seeded"

    bands = ["under_1L", "1L_5L", "5L_25L", "25L_1Cr", "1Cr_5Cr", "5Cr_25Cr", "above_25Cr"]
    horizons = [None, "6_months", "12_months", "24_months", "36_months_plus"]
    # Every seeded industry plus two that no rule names (they must behave
    # exactly like unknown), and the full business_model and stage vocabularies.
    industries = [None, "saas", "fintech", "ecommerce_d2c", "agritech", "logistics"]
    models = [None, "B2B", "B2C", "B2B2C", "marketplace", "D2C", "other"]

    checked = widest = 0
    for band in bands:
        for horizon in horizons:
            for industry in industries:
                for model in models:
                    for stage in (None, 1, 2, 4, 5, 8):
                        got = resolve_requirements(
                            rows, founder_ctx(industry, model, stage),
                            TargetStateContext(band, horizon))
                        checked += 1
                        widest = max(widest, len(got))
    with capsys.disabled():
        print(f"\n    cascade: {checked} contexts resolved, "
              f"largest requirement set {widest}")


def test_unknown_context_yields_a_subset_not_an_empty_set(db):
    """The live-data form of cases 13-14, and the one that would bite hardest."""
    rows = DiagnosisRepository(db).capability_requirement_rows()
    target = TargetStateContext("1Cr_5Cr", "12_months")

    known = resolve_requirements(rows, founder_ctx("saas", "B2B", 5), target)
    unknown = resolve_requirements(rows, founder_ctx(None, None, None), target)

    assert unknown, "an unknown profile must still get the generic requirements"
    known_codes = {r.capability_code for r in known}
    unknown_codes = {r.capability_code for r in unknown}
    assert unknown_codes <= known_codes, (
        "unknown context must not produce a requirement a known context does not"
    )
    assert all(r.specificity <= 1 for r in unknown), (
        "no specific rule may activate on unknown context"
    )


# =========================================================== 1-3: persistence
def test_target_fields_persist_and_read_back(db):
    """Cases 1 and 2, in the database rather than through the schema."""
    founder_id = db.execute(text(
        "SELECT founder_id FROM founders ORDER BY founder_id LIMIT 1")).scalar()
    assert founder_id is not None, "this database has no founders"

    db.execute(text(
        "UPDATE founders SET target_revenue_band = :b, target_time_horizon = :h"
        " WHERE founder_id = :f"),
        {"b": "5Cr_25Cr", "h": "12_months", "f": founder_id})
    db.flush()

    band, horizon = db.execute(text(
        "SELECT target_revenue_band, target_time_horizon FROM founders"
        " WHERE founder_id = :f"), {"f": founder_id}).first()
    assert (band, horizon) == ("5Cr_25Cr", "12_months")


def test_a_founder_with_no_target_still_works(db):
    """Case 3. Every existing founder has NULL here and must be unaffected."""
    nulls = db.execute(text(
        "SELECT count(*) FROM founders WHERE target_revenue_band IS NULL")).scalar()
    total = db.execute(text("SELECT count(*) FROM founders")).scalar()
    assert nulls == total, "the migration must not have backfilled a target"

    founder = db.execute(text(
        "SELECT target_revenue_band, target_time_horizon FROM founders LIMIT 1")).first()
    target = TargetStateContext.from_founder(
        SimpleNamespace(target_revenue_band=founder[0], target_time_horizon=founder[1]))
    assert target.is_stated is False
    rows = DiagnosisRepository(db).capability_requirement_rows()
    assert resolve_requirements(rows, founder_ctx(), target) == (), (
        "a founder who never stated a target must get no requirements, not a "
        "default set somebody invented for them"
    )


def test_the_database_refuses_a_current_revenue_band_as_a_target(db):
    """`above_1Cr` is a CurrentRevenue value and must not be storable as a target.

    The two vocabularies overlap on the lower four names by design; this pins
    that the overlap does not extend to the top band, which is the whole reason
    the target vocabulary exists.
    """
    founder_id = db.execute(text("SELECT founder_id FROM founders LIMIT 1")).scalar()
    with pytest.raises(Exception):
        db.execute(text(
            "UPDATE founders SET target_revenue_band = 'above_1Cr' WHERE founder_id = :f"),
            {"f": founder_id})
        db.flush()


def test_target_context_reads_off_a_founder_row():
    target = TargetStateContext.from_founder(SimpleNamespace(
        target_revenue_band="  1Cr_5Cr  ", target_time_horizon=""))
    assert target.target_revenue_band == "1Cr_5Cr"      # stripped
    assert target.target_time_horizon is None           # empty reads as absent
    assert target.describe()["target_stated"] is True


def test_target_context_never_raises_on_an_odd_row():
    # Same contract as FounderContext.from_founder: pure, cheap, never raises.
    for bad in (SimpleNamespace(), SimpleNamespace(target_revenue_band=42),
                SimpleNamespace(target_revenue_band=None, target_time_horizon=None)):
        assert TargetStateContext.from_founder(bad).is_stated is False
