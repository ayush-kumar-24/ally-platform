"""The composition layer: Steps 10A and 10B as two additive Founder Report sections.

These test COMPOSITION, not the engines -- the engines have their own suites.
What is pinned here: the existing report is byte-for-byte unchanged when the
new sections are absent; the two sections are additive `Section`s on the
existing mechanism (no schema, serialisation or renderer change); a state the
engines name but that gives the founder nothing true to read is LEFT OUT AND
NAMED in `unpopulated_sections` (the report's existing honesty convention),
while meaningful states stay, compactly, by capability name; UNASSESSED never
reads as a gap; provenance survives into the cached snapshot under
`_provenance`; the narrator cannot touch a deterministic field; entitlement is
applied at read, at every founder-facing door, through the existing seam; and
one founder's state can never compose into another's report.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.strategic_direction import (
    AMBIGUOUS_REQUIREMENTS,
    DIRECTION_RESOLVED,
    NO_TARGET_CONTEXT,
    CapabilityTrajectory,
    StrategicDirection,
    UnplacedRequirement,
)
from app.api.v1.diagnosis.target_state import TargetStateContext
from app.api.v1.diagnosis.twenty_day_target import (
    NO_ACTIONABLE_TARGET,
    TARGET_SELECTED,
    SkippedGap,
    SuccessCriterion,
    TargetAction,
    TwentyDayTarget,
    TwentyDayTargetResult,
)
from app.api.v1.reports.capability_sections import (
    STRATEGIC_DIRECTION_KEY,
    TWENTY_DAY_TARGET_KEY,
)
from app.api.v1.reports.generator import ReportNarrative, ReportNarrativeGenerator
from app.api.v1.reports.narrator import LLMSectionNarrator
from app.api.v1.reports.payload import (
    ActionItem, ArchetypeFinding, PillarFinding, ReportPayload, RootCauseFinding,
    _capability_outputs,
)
from app.api.v1.reports import routes
from app.api.v1.reports.variants import ReportVariant
from app.db.session import engine as db_engine
from app.plans.catalog import PLANS, Feature, PlanTier


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


# --- fixtures: the same payload shape test_report_narrative.py uses -------
def _pillar(name, score, flag=False, note=None, band="Developing", desc=None):
    return PillarFinding(pillar_id=1, name=name, score=score, band=band,
                         band_description=desc, red_flag_triggered=flag, red_flag_note=note)


NAMES = {3: "Repeatable Sales System", 5: "Sales Ownership Beyond the Founder",
         22: "Financial Visibility", 24: "Cash Discipline"}


def _payload(**over):
    base = dict(
        report_id=1, founder_id=7, session_id=3, founder_name="Rahul",
        tone_code="PROMPT-STAGE01-TONE", tone_persona="Compass",
        session_state="stable", distress_acknowledged_first=False,
        overall_confidence_score=85.0,
        business_health_overall=64, business_health_band="Needs Attention",
        pillars=(_pillar("Founder Readiness", 62), _pillar("Market Clarity", 48)),
        red_flag_pillars=(),
        archetype=ArchetypeFinding("Operator", "ARCH-002", "Mastery", True, 0.31),
        top_root_causes=(
            RootCauseFinding(10, "Weak pipeline", "Sales & Revenue", "confirmed", True, 1),
            RootCauseFinding(11, "Unclear ICP", "Go-To-Market", "not_tested", True, 2),
        ),
        confirm_actions=(ActionItem(5, 1, ("Confirm your ICP",), "why"),),
        solve_actions=(ActionItem(6, 1, ("Build a pipeline tracker",), "why"),),
        category_risk_scores={"Sales & Revenue": 0.6, "Founder Psychology": 0.1},
        capability_names=NAMES,
    )
    base.update(over)
    return ReportPayload(**base)


def _target(**over):
    base = dict(
        primary_capability_id=3, primary_capability_code="GTM-SALES",
        primary_capability_name="Repeatable Sales System",
        target_outcome="A defined, teachable sales process rather than a series of improvisations.",
        current_level=CapabilityLevel.PERSONAL, required_level=CapabilityLevel.OWNED,
        gap_size=2, necessity="core", gap_rank=2,
        source_intervention_id=157, source_intervention_code="INT-157",
        source_section="Sales Execution",
        actions=(TargetAction(1, "Build one reusable proposal template.", 157),
                 TargetAction(2, "Start tracking why each proposal is accepted or rejected.", 157)),
        success_criteria=(SuccessCriterion(9, 1, "A sales process exists and is written down"),
                          SuccessCriterion(10, 2, "The same steps are followed across deals")),
        requirement_id=903, supporting_evidence_ids=(11, 12),
        supporting_capability_ids=(3,),
    )
    base.update(over)
    return TwentyDayTarget(**base)


SKIPPED_GTM_OWN = SkippedGap(5, "GTM-OWN", 1, 2, "core", "all_candidates_filtered", (56, 64))


def _selected():
    return TwentyDayTargetResult(status=TARGET_SELECTED, target=_target(),
                                 skipped_gaps=(SKIPPED_GTM_OWN,), considered_gap_count=2)


def _no_target(considered=1):
    return TwentyDayTargetResult(
        status=NO_ACTIONABLE_TARGET, target=None,
        skipped_gaps=(SKIPPED_GTM_OWN,) if considered else (),
        considered_gap_count=considered)


def _trajectory(seq, cid, code, name, cur, req, nec="core"):
    return CapabilityTrajectory(
        capability_id=cid, capability_code=code, capability_name=name,
        capability_description=f"What {name} is.", current_level=CapabilityLevel(cur),
        required_level=CapabilityLevel(req), gap_size=req - cur, necessity=nec,
        rationale=f"Why the destination needs {name}.", sequence=seq,
        requirement_id=900 + cid, supporting_evidence_ids=(cid,))


UNPLACED_FIN_CASH = UnplacedRequirement(24, "FIN-CASH", "Cash Discipline",
                                        CapabilityLevel.DOCUMENTED, "core", "why", 924)


def _direction(unplaced=(UNPLACED_FIN_CASH,)):
    return StrategicDirection(
        status=DIRECTION_RESOLVED,
        trajectory=(_trajectory(1, 3, "GTM-SALES", "Repeatable Sales System", 1, 3),
                    _trajectory(2, 22, "FIN-VIS", "Financial Visibility", 2, 3)),
        unplaced=tuple(unplaced), target=TargetStateContext("5Cr_25Cr", "12_months"))


def _gen(payload, **kw):
    return ReportNarrativeGenerator().generate(payload, **kw)


def _keys(n):
    return [s.key for s in n.sections]


def _section(n, key):
    return next((s for s in n.sections if s.key == key), None)


def _founder_facing(section):
    return {k: v for k, v in section.facts.items() if not k.startswith("_")}


# --- entitlement stubs: test_recommendations_entitlement.py's pattern ------
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
        monkeypatch.setattr(routes.container, "entitlement_service",
                            lambda db: _Entitlements(allowed))
    return _apply


def _executable_code(path):
    import ast
    tree = ast.parse(open(path).read())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = node.body
        if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


# =========================================================== 1, 11, 19: unchanged
def test_existing_report_is_unchanged_when_the_new_sections_are_absent():
    """Case 1 / 19. Defaults are None; nothing about the existing report moves,
    and the absent engine sections are named rather than silently missing."""
    n = _gen(_payload())
    assert TWENTY_DAY_TARGET_KEY not in _keys(n)
    assert STRATEGIC_DIRECTION_KEY not in _keys(n)
    assert _keys(n)[:9] == ["founder_summary", "founder_dna", "business_dna", "problem_path",
                            "supporting_evidence", "priority_actions", "recommended_roadmap",
                            "why_steps", "discovery_cta"]
    assert n.unpopulated_sections == ("expected_impact", TWENTY_DAY_TARGET_KEY,
                                      STRATEGIC_DIRECTION_KEY)


def test_existing_sections_are_identical_with_and_without_the_new_ones():
    """Cases 9, 10, 11. Root causes, Business Health and every other existing
    section are byte-identical -- the new sections are purely additive."""
    without = _gen(_payload())
    with_ = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    for s in without.sections:
        twin = _section(with_, s.key)
        assert twin is not None, s.key
        assert twin.heading == s.heading and twin.prose == s.prose and twin.facts == s.facts
    assert without.as_dict().keys() == with_.as_dict().keys()
    assert with_.unpopulated_sections == ("expected_impact",)


def test_new_sections_sit_after_the_actions_and_before_the_cta():
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    keys = _keys(n)
    assert keys.index("why_steps") < keys.index(TWENTY_DAY_TARGET_KEY)
    assert keys.index(TWENTY_DAY_TARGET_KEY) < keys.index(STRATEGIC_DIRECTION_KEY)
    assert keys[-1] == "discovery_cta"


def test_a_missing_engine_output_omits_and_names_only_its_own_section():
    """Case 19."""
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=None))
    assert TWENTY_DAY_TARGET_KEY in _keys(n)
    assert STRATEGIC_DIRECTION_KEY not in _keys(n)
    assert STRATEGIC_DIRECTION_KEY in n.unpopulated_sections
    assert TWENTY_DAY_TARGET_KEY not in n.unpopulated_sections


def test_distress_variant_carries_neither_section_and_names_neither():
    """The existing rule: no execution content reaches a distressed founder --
    and a section that was never in scope is not reported as 'not included'."""
    p = _payload(session_state="high_distress", distress_acknowledged_first=True,
                 twenty_day_target=_selected(), strategic_direction=_direction())
    n = _gen(p, distress_protocol="You are not alone.")
    assert n.variant is ReportVariant.DISTRESS
    assert TWENTY_DAY_TARGET_KEY not in _keys(n) and STRATEGIC_DIRECTION_KEY not in _keys(n)
    assert TWENTY_DAY_TARGET_KEY not in n.unpopulated_sections
    assert STRATEGIC_DIRECTION_KEY not in n.unpopulated_sections


# =========================================================== 5-7: no-state UX
def test_no_target_context_is_left_out_and_named():
    """Case 6. An unstated destination is absent input, not diagnostic
    uncertainty: the section is omitted and named, never shown as a raw state."""
    d = StrategicDirection(status=NO_TARGET_CONTEXT, trajectory=(), unplaced=(),
                           target=TargetStateContext(None, None))
    n = _gen(_payload(strategic_direction=d))
    assert STRATEGIC_DIRECTION_KEY not in _keys(n)
    assert STRATEGIC_DIRECTION_KEY in n.unpopulated_sections


def test_ambiguous_requirements_is_left_out_and_named():
    """Case 7. A curation error the engine already logs for the people who can
    fix it; not a message for a founder. Nothing is guessed in its place."""
    d = StrategicDirection(status=AMBIGUOUS_REQUIREMENTS, trajectory=(), unplaced=(),
                           target=TargetStateContext("1Cr_5Cr", None),
                           ambiguity="capability_id 7 has 2 equally specific rows that disagree")
    n = _gen(_payload(strategic_direction=d))
    assert STRATEGIC_DIRECTION_KEY not in _keys(n)
    assert STRATEGIC_DIRECTION_KEY in n.unpopulated_sections


def test_no_actionable_target_with_nothing_diagnosed_is_left_out_and_named():
    """Case 5a. Zero gaps considered: there is nothing true to say."""
    n = _gen(_payload(twenty_day_target=_no_target(considered=0)))
    assert TWENTY_DAY_TARGET_KEY not in _keys(n)
    assert TWENTY_DAY_TARGET_KEY in n.unpopulated_sections


def test_no_actionable_target_with_real_gaps_is_kept_compactly_by_name():
    """Case 5b. Gaps were found but the library cannot yet serve them --
    meaningful uncertainty, shown by capability NAME with codes underneath.
    Nothing is fabricated in place of a target."""
    n = _gen(_payload(twenty_day_target=_no_target(considered=1)))
    s = _section(n, TWENTY_DAY_TARGET_KEY)
    assert s is not None and TWENTY_DAY_TARGET_KEY not in n.unpopulated_sections
    assert _founder_facing(s) == {"gaps_identified": 1,
                                  "not_yet_addressable": ["Sales Ownership Beyond the Founder"]}
    prov = s.facts["_provenance"]
    assert prov["status"] == NO_ACTIONABLE_TARGET
    assert prov["skipped_gaps"][0]["reason"] == "all_candidates_filtered"
    assert prov["skipped_gaps"][0]["capability_code"] == "GTM-OWN"


def test_raw_enums_and_internal_codes_never_reach_founder_facing_facts():
    """The founder sees names, labels and the library's own text. Status
    strings, band codes, INT- codes, necessity and reason codes live only in
    `_provenance`."""
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    for key in (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY):
        s = _section(n, key)
        flat = " ".join(str(v) for v in _founder_facing(s).values())
        for raw in ("target_selected", "resolved", "5Cr_25Cr", "12_months", "INT-", "GTM-",
                    "FIN-", "core", "all_candidates_filtered", "no_mapped_intervention"):
            assert raw not in flat, (key, raw)
        assert "status" in s.facts["_provenance"]


# =========================================================== 2-4: entitlement
def _narrative_with_both():
    return _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))


def test_basic_equivalent_gets_core_report_and_target_but_not_direction(patched):
    """Case 2. Rs 199 = REPORTS only: the router already requires REPORTS, so
    the 20-day target rides along; the direction is withheld at read."""
    patched(set())
    out = routes._visible_to(_narrative_with_both(), _Founder(PlanTier.BASIC), db=None)
    keys = _keys(out)
    assert {"founder_dna", "business_dna", "problem_path"} <= set(keys)
    assert TWENTY_DAY_TARGET_KEY in keys
    assert STRATEGIC_DIRECTION_KEY not in keys
    assert STRATEGIC_DIRECTION_KEY in out.unpopulated_sections


def test_starter_equivalent_gets_target_and_direction(patched):
    """Case 3. Rs 499 adds STRATEGIC_DIRECTION."""
    patched({Feature.STRATEGIC_DIRECTION})
    out = routes._visible_to(_narrative_with_both(), _Founder(PlanTier.STARTER), db=None)
    assert TWENTY_DAY_TARGET_KEY in _keys(out)
    assert STRATEGIC_DIRECTION_KEY in _keys(out)


def test_pro_equivalent_gets_the_same_direction_with_no_recomputation(patched):
    """Case 4. Rs 999 sees exactly what Rs 499 sees for these sections, and an
    entitled founder gets the cached narrative object itself back."""
    patched({Feature.STRATEGIC_DIRECTION, Feature.RECOMMENDATIONS})
    n = _narrative_with_both()
    out = routes._visible_to(n, _Founder(PlanTier.PRO), db=None)
    assert out is n
    assert STRATEGIC_DIRECTION_KEY in _keys(out)


def test_the_catalog_places_strategic_direction_at_the_workspace_tier():
    assert Feature.STRATEGIC_DIRECTION not in PLANS[PlanTier.BASIC].features
    assert Feature.STRATEGIC_DIRECTION in PLANS[PlanTier.STARTER].features
    assert Feature.STRATEGIC_DIRECTION in PLANS[PlanTier.PRO].features
    assert Feature.REPORTS in PLANS[PlanTier.BASIC].features


def test_strategic_direction_is_the_sole_feature_gate_for_the_new_sections():
    gated = dict(routes._GATED_SECTIONS)
    assert gated[Feature.STRATEGIC_DIRECTION] == frozenset({STRATEGIC_DIRECTION_KEY})
    assert not any(TWENTY_DAY_TARGET_KEY in keys for keys in gated.values())


def test_the_two_gates_are_independent(patched):
    patched({Feature.RECOMMENDATIONS})
    out = routes._visible_to(_narrative_with_both(), _Founder(PlanTier.BASIC), db=None)
    assert "priority_actions" in _keys(out) and STRATEGIC_DIRECTION_KEY not in _keys(out)
    patched({Feature.STRATEGIC_DIRECTION})
    out = routes._visible_to(_narrative_with_both(), _Founder(PlanTier.BASIC), db=None)
    assert "priority_actions" not in _keys(out) and STRATEGIC_DIRECTION_KEY in _keys(out)


def test_a_withheld_section_that_was_also_omitted_is_named_once(patched):
    patched(set())
    n = _gen(_payload(strategic_direction=StrategicDirection(
        status=NO_TARGET_CONTEXT, trajectory=(), unplaced=(), target=TargetStateContext(None, None))))
    out = routes._visible_to(n, _Founder(PlanTier.BASIC), db=None)
    assert list(out.unpopulated_sections).count(STRATEGIC_DIRECTION_KEY) == 1


def test_every_founder_facing_door_is_gated():
    """/insights and /export joined /reports/{id} and /document. A
    plan-filtered PDF is rendered per download and never stored."""
    source = open("app/api/v1/reports/routes.py").read()
    insights = source.split('@router.get("/{report_id}/insights"', 1)[1][:500]
    assert "_visible_to(" in insights
    export = source.split('@router.post("/{report_id}/export"', 1)[1]
    gated = export.split("if _withheld_sections(founder, db):", 1)[1].split("else:", 1)[0]
    assert "render_pdf(build_report_html(" in gated
    assert "render_and_store" not in gated and "store.put" not in gated
    assert "pdf_storage_key" not in gated and "_clear_pending" not in gated


def test_intelligence_endpoints_never_expose_the_narrative_snapshot():
    """The new sections live only in narrative_snapshot; /intelligence returns
    founder_reports columns and never that one, so the paid section cannot
    leak there. (Its pre-existing exposure of confirm/solve actions is
    documented, not touched.)"""
    source = open("app/api/v1/intelligence/routes.py").read()
    assert "narrative_snapshot" not in source
    schema = open("app/schemas/intelligence.py").read()
    assert "narrative" not in schema.lower()


# =========================================================== 8: UNASSESSED safety
def test_unassessed_is_never_shown_as_a_gap():
    """Case 8."""
    n = _gen(_payload(strategic_direction=_direction()))
    s = _section(n, STRATEGIC_DIRECTION_KEY)
    assert len(s.facts["trajectory"]) == 2
    assert s.facts["required_but_not_yet_assessed"] == ["Cash Discipline (needs: documented)"]
    assert not any("Cash Discipline" in line for line in s.facts["trajectory"])
    prov = s.facts["_provenance"]
    assert {e["capability_code"] for e in prov["trajectory"]} == {"GTM-SALES", "FIN-VIS"}
    assert [u["capability_code"] for u in prov["unplaced"]] == ["FIN-CASH"]
    for key in _founder_facing(s):
        assert "gap" not in key.lower()


def test_a_destination_with_only_unassessed_requirements_is_still_worth_showing():
    """Resolved, nothing to evolve yet, but the destination requires things
    the diagnosis has not measured -- the founder should know what those are."""
    d = StrategicDirection(status=DIRECTION_RESOLVED, trajectory=(),
                           unplaced=(UNPLACED_FIN_CASH,),
                           target=TargetStateContext("1Cr_5Cr", None))
    n = _gen(_payload(strategic_direction=d))
    s = _section(n, STRATEGIC_DIRECTION_KEY)
    assert _founder_facing(s) == {
        "required_but_not_yet_assessed": ["Cash Discipline (needs: documented)"]}


def test_a_resolved_direction_with_nothing_outstanding_is_left_out_and_named():
    d = StrategicDirection(status=DIRECTION_RESOLVED, trajectory=(), unplaced=(),
                           target=TargetStateContext("1Cr_5Cr", None))
    n = _gen(_payload(strategic_direction=d))
    assert STRATEGIC_DIRECTION_KEY not in _keys(n)
    assert STRATEGIC_DIRECTION_KEY in n.unpopulated_sections


# =========================================================== 12-13: provenance
def test_target_retains_intervention_capability_gap_and_evidence_provenance():
    """Case 12."""
    n = _gen(_payload(twenty_day_target=_selected()))
    s = _section(n, TWENTY_DAY_TARGET_KEY)
    assert s.facts["focus_area"] == "Sales Execution"
    p = s.facts["_provenance"]
    assert p["source_intervention_id"] == 157 and p["source_intervention_code"] == "INT-157"
    assert p["primary_capability_id"] == 3 and p["gap_rank"] == 2 and p["gap_size"] == 2
    assert p["requirement_id"] == 903 and p["supporting_evidence_ids"] == [11, 12]
    assert p["status"] == TARGET_SELECTED and p["horizon_days"] == 20 and p["necessity"] == "core"
    assert [a["source_intervention_id"] for a in p["actions"]] == [157, 157]
    assert [c["criterion_id"] for c in p["success_criteria"]] == [9, 10]
    assert p["skipped_gaps"][0]["excluded_intervention_ids"] == [56, 64]
    assert s.facts["not_yet_addressable"] == ["Sales Ownership Beyond the Founder"]


def test_direction_retains_requirement_and_evidence_provenance():
    """Case 13."""
    n = _gen(_payload(strategic_direction=_direction()))
    p = _section(n, STRATEGIC_DIRECTION_KEY).facts["_provenance"]
    assert [e["requirement_id"] for e in p["trajectory"]] == [903, 922]
    assert [e["sequence"] for e in p["trajectory"]] == [1, 2]
    assert p["status"] == DIRECTION_RESOLVED
    assert p["target_revenue_band"] == "5Cr_25Cr" and p["target_time_horizon"] == "12_months"


def test_provenance_survives_the_snapshot_round_trip():
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    back = ReportNarrative.from_dict(n.report_id, n.as_dict())
    for key in (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY):
        assert _section(back, key).facts == _section(n, key).facts
    assert back.unpopulated_sections == n.unpopulated_sections


def test_founder_facing_facts_are_scalars_or_lists_of_strings():
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    for key in (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY):
        for k, v in _founder_facing(_section(n, key)).items():
            assert isinstance(v, (str, int)) or (
                isinstance(v, list) and all(isinstance(x, str) for x in v)), (key, k, v)


# =========================================================== 14-17: nothing invented
def test_no_invented_kpi():
    """Case 14. The only number in the founder-facing facts is the count of
    gaps the engine itself reported."""
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    for key in (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY):
        for k, v in _founder_facing(_section(n, key)).items():
            if isinstance(v, str):
                assert "%" not in v
    code = _executable_code("app/api/v1/reports/capability_sections.py")
    for forbidden in ("increase", "revenue by", "%", "kpi"):
        assert forbidden not in code.lower()


def test_no_invented_dependency_and_no_three_year_task_list():
    """Cases 15, 16."""
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    d = _section(n, STRATEGIC_DIRECTION_KEY)
    for k in list(d.facts) + list(d.facts["_provenance"]):
        for forbidden in ("depends", "prerequisite", "blocks", "year", "quarter", "month",
                          "roadmap", "milestone", "task", "deadline", "date"):
            assert forbidden not in k.lower(), k
    for e in d.facts["_provenance"]["trajectory"]:
        for forbidden in ("depends_on", "prerequisite", "year", "phase", "date"):
            assert forbidden not in e


def test_no_plan_or_price_reference_in_any_diagnostic_engine():
    """Case 17."""
    for path in ("app/api/v1/diagnosis/twenty_day_target.py",
                 "app/api/v1/diagnosis/strategic_direction.py",
                 "app/api/v1/diagnosis/gap_intervention.py",
                 "app/api/v1/diagnosis/gap_priority.py",
                 "app/api/v1/diagnosis/gap_engine.py",
                 "app/api/v1/reports/capability_sections.py"):
        code = _executable_code(path)
        for forbidden in ("199", "499", "999", "plan_tier", "plantier", "entitlement",
                          "subscription", "feature.", "billing", "tier"):
            assert forbidden not in code.lower(), (path, forbidden)


# =========================================================== 18: the narrator
def test_llm_narration_cannot_alter_a_deterministic_field():
    """Case 18. Empty slots, so no narrator writes for these sections; and a
    narrator only ever returns prose, so facts are unreachable by construction."""
    invented = LLMSectionNarrator(llm=lambda prompt: "INVENTED CLAIM: reach Rs 10Cr by month 18")
    p = _payload(twenty_day_target=_selected(), strategic_direction=_direction())
    plain = _gen(p)
    narrated = ReportNarrativeGenerator(narrator=invented).generate(p)
    for key in (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY):
        assert _section(narrated, key).prose == ""
        assert _section(narrated, key).facts == _section(plain, key).facts
        assert "INVENTED" not in str(_section(narrated, key).facts)


def test_the_facts_builders_never_recompute():
    code = _executable_code("app/api/v1/reports/capability_sections.py")
    for forbidden in ("prioritize_capability_gaps", "compute_capability_gaps",
                      "select_interventions", "build_twenty_day_target",
                      "build_strategic_direction", "resolve_requirements", "min(", "sorted("):
        assert forbidden not in code


def test_the_composition_layer_only_calls_the_engines_entry_points():
    """Section 9: no gap selection, intervention selection, requirement
    resolution, assessment or prioritisation is reimplemented in the report
    layer -- it consumes 10A/10B through their repository entry points."""
    code = _executable_code("app/api/v1/reports/payload.py")
    assert "twenty_day_target_for_session" in code
    assert "strategic_direction_for_session" in code
    for forbidden in ("resolve_requirements", "compute_capability_gaps",
                      "prioritize_capability_gaps", "select_interventions_for_gaps",
                      "assess_capabilities", "build_twenty_day_target",
                      "build_strategic_direction", "DefaultInterventionRelevance"):
        assert forbidden not in code, forbidden


def test_the_dependency_runs_one_way_report_to_engine():
    """The composition layer consumes the engines; no engine knows the report
    exists. This is the boundary Steps 10A/10B's own guards used to pin from
    the other side before integration, kept from the side that still holds."""
    for path in ("app/api/v1/diagnosis/twenty_day_target.py",
                 "app/api/v1/diagnosis/strategic_direction.py",
                 "app/api/v1/diagnosis/gap_intervention.py",
                 "app/api/v1/diagnosis/gap_priority.py",
                 "app/api/v1/diagnosis/gap_engine.py",
                 "app/api/v1/diagnosis/target_state.py",
                 "app/api/v1/diagnosis/capability_assessment.py",
                 "app/api/v1/diagnosis/repository.py"):
        code = _executable_code(path)
        assert "app.api.v1.reports" not in code, f"{path} imports the report layer"
        assert "capability_sections" not in code, f"{path} imports the report layer"


# =========================================================== 20-22: live
def _mapped_answer_for_a_founder(db, exclude_founder=None):
    sql = ("SELECT a.answer_id, a.question_id, a.session_id, s.founder_id, qc.capability_id"
           "  FROM answers a JOIN question_capabilities qc ON qc.question_id = a.question_id"
           "  JOIN sessions s ON s.session_id = a.session_id")
    if exclude_founder is not None:
        sql += " WHERE s.founder_id <> :f"
    return db.execute(text(sql + " ORDER BY a.answer_id LIMIT 1"),
                      {"f": exclude_founder} if exclude_founder is not None else {}).first()


def _give(db, founder_id, session_id, answer_id, question_id, capability_id, band, level):
    from app.api.v1.diagnosis.repository import DiagnosisRepository
    DiagnosisRepository(db).record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=level, confidence=0.95, evidence_text="isolation probe")
    db.execute(text("UPDATE founders SET target_revenue_band = :b,"
                    " target_time_horizon = '12_months', stage_id = 5 WHERE founder_id = :f"),
               {"b": band, "f": founder_id})


def test_founder_a_cannot_receive_founder_b_capability_state(db):
    """Case 20 / section 15. TWO founders, each with a genuinely different
    destination and their own evidence on a different capability. Each
    report's requirements, gaps, target and direction are its own."""
    a = _mapped_answer_for_a_founder(db)
    if a is None:
        pytest.skip("no answer to a mapped question in this database")
    b = _mapped_answer_for_a_founder(db, exclude_founder=a.founder_id)
    if b is None:
        pytest.skip("need a second founder with a mapped answer")

    _give(db, a.founder_id, a.session_id, a.answer_id, a.question_id, a.capability_id, "5Cr_25Cr", 0)
    _give(db, b.founder_id, b.session_id, b.answer_id, b.question_id, b.capability_id, "1Cr_5Cr", 1)

    ta, da, _ = _capability_outputs(db, SimpleNamespace(report_id=1, founder_id=a.founder_id, session_id=a.session_id))
    tb, db_, _ = _capability_outputs(db, SimpleNamespace(report_id=2, founder_id=b.founder_id, session_id=b.session_id))

    assert da.target.target_revenue_band == "5Cr_25Cr"
    assert db_.target.target_revenue_band == "1Cr_5Cr"
    # Each direction's evidence ids come only from that founder's own session.
    def evidence_sessions(direction):
        ids = [e for t in direction.trajectory for e in t.supporting_evidence_ids]
        if not ids:
            return set()
        rows = db.execute(text(
            "SELECT DISTINCT an.session_id FROM capability_evidence ce"
            "  JOIN answers an ON an.answer_id = ce.answer_id"
            " WHERE ce.evidence_id = ANY(:ids)"), {"ids": ids}).all()
        return {r[0] for r in rows}
    assert evidence_sessions(da) <= {a.session_id}
    assert evidence_sessions(db_) <= {b.session_id}
    if ta.target is not None and tb.target is not None:
        assert set(ta.target.supporting_evidence_ids).isdisjoint(tb.target.supporting_evidence_ids)


def test_composition_query_count_is_bounded_and_independent_of_gap_count(db):
    """Section 10. No N+1: the statements issued to compose both engines'
    output do not grow with the number of requirements or gaps. Measured, not
    assumed -- once for a founder with no destination and once with a
    destination that activates twenty requirements."""
    row = _mapped_answer_for_a_founder(db)
    if row is None:
        pytest.skip("no answer to a mapped question in this database")

    counts = []

    def count_statements(fn):
        n = 0
        def before(*_a, **_k):
            nonlocal n
            n += 1
        event.listen(db_engine, "before_cursor_execute", before)
        try:
            fn()
        finally:
            event.remove(db_engine, "before_cursor_execute", before)
        return n

    report = SimpleNamespace(report_id=1, founder_id=row.founder_id, session_id=row.session_id)
    db.execute(text("UPDATE founders SET target_revenue_band = NULL, target_time_horizon = NULL"
                    " WHERE founder_id = :f"), {"f": row.founder_id})
    counts.append(count_statements(lambda: _capability_outputs(db, report)))
    _give(db, row.founder_id, row.session_id, row.answer_id, row.question_id, row.capability_id,
          "5Cr_25Cr", 0)
    counts.append(count_statements(lambda: _capability_outputs(db, report)))

    assert all(c <= 24 for c in counts), counts          # bounded reads, no per-row loops
    assert counts[1] - counts[0] <= 6, counts             # activating 20 requirements adds no loop


def test_regeneration_is_deterministic_and_tracks_the_diagnosis(db):
    """Section 6. Same diagnosis -> equivalent output; changed diagnosis ->
    changed output. The snapshot follows the diagnosis, never the plan."""
    row = _mapped_answer_for_a_founder(db)
    if row is None:
        pytest.skip("no answer to a mapped question in this database")
    from app.api.v1.reports.capability_sections import (
        strategic_direction_facts, twenty_day_target_facts)
    report = SimpleNamespace(report_id=1, founder_id=row.founder_id, session_id=row.session_id)
    _give(db, row.founder_id, row.session_id, row.answer_id, row.question_id, row.capability_id,
          "5Cr_25Cr", 0)

    def facts():
        t, d, names = _capability_outputs(db, report)
        return twenty_day_target_facts(t, names), strategic_direction_facts(d)

    first, second = facts(), facts()
    assert first == second                                  # unchanged diagnosis
    db.execute(text("UPDATE capability_evidence SET observed_level = 3 WHERE answer_id = :a"),
               {"a": row.answer_id})
    changed = facts()
    assert changed != first                                 # changed diagnosis


def test_empty_capability_evidence_fabricates_no_strategic_gap(db):
    """Case 21."""
    row = db.execute(text("SELECT founder_id, session_id FROM sessions LIMIT 1")).first()
    if row is None:
        pytest.skip("no session")
    founder_id, session_id = row
    db.execute(text("DELETE FROM capability_evidence WHERE answer_id IN"
                    " (SELECT answer_id FROM answers WHERE session_id = :s)"), {"s": session_id})
    db.execute(text("UPDATE founders SET target_revenue_band = '1Cr_5Cr', stage_id = 5"
                    " WHERE founder_id = :f"), {"f": founder_id})
    target, direction, _ = _capability_outputs(
        db, SimpleNamespace(report_id=1, founder_id=founder_id, session_id=session_id))
    assert direction.status == DIRECTION_RESOLVED and direction.trajectory == ()
    assert direction.unplaced
    assert target.status == NO_ACTIONABLE_TARGET and target.considered_gap_count == 0


def test_production_like_reports_still_compose_a_valid_founder_report(db):
    """Case 22. Every recent real report builds, round-trips, keeps every
    pre-existing section, and either carries a real engine section or names it."""
    from app.api.v1.reports.payload import build_report_payload
    from app.models import FounderReport
    rows = db.execute(text("SELECT report_id FROM founder_reports WHERE is_active"
                           " ORDER BY report_id DESC LIMIT 5")).all()
    if not rows:
        pytest.skip("no report")
    for (report_id,) in rows:
        n = _gen(build_report_payload(db, db.get(FounderReport, report_id)))
        keys = _keys(n)
        assert "founder_dna" in keys and "business_dna" in keys
        back = ReportNarrative.from_dict(report_id, n.as_dict())
        assert _keys(back) == keys and back.unpopulated_sections == n.unpopulated_sections
        if n.variant is not ReportVariant.DISTRESS:
            for key in (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY):
                assert (key in keys) != (key in n.unpopulated_sections), key


def test_golden_trace_full_founder_report_on_real_data(db, capsys):
    """Section 20. A real founder's report with a stated destination and
    confident evidence: every new section traced back to its rows."""
    from app.api.v1.reports.payload import build_report_payload
    from app.models import FounderReport
    row = db.execute(text(
        "SELECT a.answer_id, a.question_id, a.session_id, qc.capability_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        "  JOIN founder_reports r ON r.session_id = a.session_id AND r.is_active LIMIT 1")).first()
    if row is None:
        pytest.skip("no active report on a session with a mapped answer")
    report_id = db.execute(text(
        "SELECT report_id FROM founder_reports WHERE session_id = :s AND is_active LIMIT 1"),
        {"s": row.session_id}).scalar()
    report = db.get(FounderReport, report_id)
    _give(db, report.founder_id, row.session_id, row.answer_id, row.question_id,
          row.capability_id, "5Cr_25Cr", 1)

    n = _gen(build_report_payload(db, report))
    t = _section(n, TWENTY_DAY_TARGET_KEY)
    d = _section(n, STRATEGIC_DIRECTION_KEY)
    assert t is not None and d is not None

    with capsys.disabled():
        print(f"\n    FOUNDER REPORT {report.report_id} (founder {report.founder_id}, "
              f"session {row.session_id}) variant={n.variant.value}")
        print(f"    sections: {_keys(n)}   not included: {n.unpopulated_sections}")
        for s in (t, d):
            print(f"\n    [{s.key}] {s.heading}")
            for k, v in _founder_facing(s).items():
                print(f"      {k}: {v}")
            print(f"      _provenance: {sorted(s.facts['_provenance'].keys())}")
        p = t.facts["_provenance"]
        if p["status"] == TARGET_SELECTED:
            print(f"      trace: {p['primary_capability_code']} <- intervention "
                  f"{p['source_intervention_id']} ({p['source_intervention_code']}) <- requirement "
                  f"{p['requirement_id']} <- evidence {p['supporting_evidence_ids']} ; criteria "
                  f"{[c['criterion_id'] for c in p['success_criteria']]}")
        for e in d.facts["_provenance"]["trajectory"]:
            print(f"      trace: {e['capability_code']} <- requirement {e['requirement_id']}"
                  f" <- evidence {e['supporting_evidence_ids']}")
