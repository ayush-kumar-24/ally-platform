"""The composition layer: Steps 10A and 10B as two additive Founder Report sections.

These test COMPOSITION, not the engines -- the engines have their own suites.
What is pinned here: the existing report is byte-for-byte unchanged when the
new sections are absent; the two sections are additive `Section`s on the
existing mechanism (no schema, serialisation or renderer change); every domain
state the engines name stays visible and structured; UNASSESSED never reads
as a gap; provenance survives into the cached snapshot under `_provenance`;
the narrator cannot touch a deterministic field; and entitlement is applied
at read, at every founder-facing door, through the existing seam.
"""

import re
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from sqlalchemy import text
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
    strategic_direction_facts,
    twenty_day_target_facts,
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


def _selected():
    return TwentyDayTargetResult(
        status=TARGET_SELECTED, target=_target(),
        skipped_gaps=(SkippedGap(5, "GTM-OWN", 1, 2, "core", "all_candidates_filtered", (56, 64)),),
        considered_gap_count=2)


def _no_target():
    return TwentyDayTargetResult(
        status=NO_ACTIONABLE_TARGET, target=None,
        skipped_gaps=(SkippedGap(5, "GTM-OWN", 1, 2, "core", "no_mapped_intervention"),),
        considered_gap_count=1)


def _trajectory(seq, cid, code, name, cur, req, nec="core"):
    return CapabilityTrajectory(
        capability_id=cid, capability_code=code, capability_name=name,
        capability_description=f"What {name} is.", current_level=CapabilityLevel(cur),
        required_level=CapabilityLevel(req), gap_size=req - cur, necessity=nec,
        rationale=f"Why the destination needs {name}.", sequence=seq,
        requirement_id=900 + cid, supporting_evidence_ids=(cid,))


def _direction():
    return StrategicDirection(
        status=DIRECTION_RESOLVED,
        trajectory=(_trajectory(1, 3, "GTM-SALES", "Repeatable Sales System", 1, 3),
                    _trajectory(2, 22, "FIN-VIS", "Financial Visibility", 2, 3)),
        unplaced=(UnplacedRequirement(24, "FIN-CASH", "Cash Discipline",
                                      CapabilityLevel.DOCUMENTED, "core", "why", 924),),
        target=TargetStateContext("5Cr_25Cr", "12_months"))


def _gen(payload, **kw):
    return ReportNarrativeGenerator().generate(payload, **kw)


def _keys(n):
    return [s.key for s in n.sections]


def _section(n, key):
    return next((s for s in n.sections if s.key == key), None)


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
    """Case 1 / 19. Defaults are None; nothing about the existing report moves."""
    n = _gen(_payload())
    assert TWENTY_DAY_TARGET_KEY not in _keys(n)
    assert STRATEGIC_DIRECTION_KEY not in _keys(n)
    assert _keys(n)[:9] == ["founder_summary", "founder_dna", "business_dna", "problem_path",
                            "supporting_evidence", "priority_actions", "recommended_roadmap",
                            "why_steps", "discovery_cta"]


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


def test_new_sections_sit_after_the_actions_and_before_the_cta():
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    keys = _keys(n)
    assert keys.index("why_steps") < keys.index(TWENTY_DAY_TARGET_KEY)
    assert keys.index(TWENTY_DAY_TARGET_KEY) < keys.index(STRATEGIC_DIRECTION_KEY)
    assert keys[-1] == "discovery_cta"


def test_a_missing_engine_output_omits_only_its_own_section():
    """Case 19. One engine's absence never breaks the report or the other."""
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=None))
    assert TWENTY_DAY_TARGET_KEY in _keys(n)
    assert STRATEGIC_DIRECTION_KEY not in _keys(n)


def test_distress_variant_carries_neither_section():
    """The existing rule: no execution content reaches a distressed founder."""
    p = _payload(session_state="high_distress", distress_acknowledged_first=True,
                 twenty_day_target=_selected(), strategic_direction=_direction())
    n = _gen(p, distress_protocol="You are not alone.")
    assert n.variant is ReportVariant.DISTRESS
    assert TWENTY_DAY_TARGET_KEY not in _keys(n)
    assert STRATEGIC_DIRECTION_KEY not in _keys(n)


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
    entitled founder gets the cached narrative object itself back -- the gate
    computes nothing and copies nothing."""
    patched({Feature.STRATEGIC_DIRECTION, Feature.RECOMMENDATIONS})
    n = _narrative_with_both()
    out = routes._visible_to(n, _Founder(PlanTier.PRO), db=None)
    assert out is n
    assert STRATEGIC_DIRECTION_KEY in _keys(out)


def test_the_catalog_places_strategic_direction_at_the_workspace_tier():
    assert Feature.STRATEGIC_DIRECTION not in PLANS[PlanTier.BASIC].features
    assert Feature.STRATEGIC_DIRECTION in PLANS[PlanTier.STARTER].features
    assert Feature.STRATEGIC_DIRECTION in PLANS[PlanTier.PRO].features


def test_the_two_gates_are_independent(patched):
    """A founder may hold one feature and not the other; each strips only its own."""
    patched({Feature.RECOMMENDATIONS})
    out = routes._visible_to(_narrative_with_both(), _Founder(PlanTier.BASIC), db=None)
    assert "priority_actions" in _keys(out) and STRATEGIC_DIRECTION_KEY not in _keys(out)
    patched({Feature.STRATEGIC_DIRECTION})
    out = routes._visible_to(_narrative_with_both(), _Founder(PlanTier.BASIC), db=None)
    assert "priority_actions" not in _keys(out) and STRATEGIC_DIRECTION_KEY in _keys(out)


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


# =========================================================== 5-7: domain states stay visible
def test_no_actionable_target_remains_visible_and_structured():
    """Case 5."""
    n = _gen(_payload(twenty_day_target=_no_target()))
    s = _section(n, TWENTY_DAY_TARGET_KEY)
    assert s is not None
    assert s.facts["status"] == NO_ACTIONABLE_TARGET
    assert s.facts["gaps_considered"] == 1
    assert s.facts["why_no_target"] == ["GTM-OWN: no_mapped_intervention"]
    assert "focus" not in s.facts and "actions" not in s.facts   # nothing fabricated


def test_no_target_context_remains_visible_and_structured():
    """Case 6."""
    d = StrategicDirection(status=NO_TARGET_CONTEXT, trajectory=(), unplaced=(),
                           target=TargetStateContext(None, None))
    n = _gen(_payload(strategic_direction=d))
    s = _section(n, STRATEGIC_DIRECTION_KEY)
    assert s is not None
    assert s.facts["status"] == NO_TARGET_CONTEXT
    assert "trajectory" not in s.facts


def test_ambiguous_requirements_remains_visible_with_the_resolvers_message():
    """Case 7."""
    d = StrategicDirection(status=AMBIGUOUS_REQUIREMENTS, trajectory=(), unplaced=(),
                           target=TargetStateContext("1Cr_5Cr", None),
                           ambiguity="capability_id 7 has 2 equally specific rows that disagree")
    n = _gen(_payload(strategic_direction=d))
    s = _section(n, STRATEGIC_DIRECTION_KEY)
    assert s.facts["status"] == AMBIGUOUS_REQUIREMENTS
    assert "disagree" in s.facts["ambiguity"]
    assert "trajectory" not in s.facts


# =========================================================== 8: UNASSESSED safety
def test_unassessed_is_never_shown_as_a_gap():
    """Case 8. Unplaced requirements are labelled as not yet assessed, never
    listed with the trajectory, never counted as gaps."""
    n = _gen(_payload(strategic_direction=_direction()))
    s = _section(n, STRATEGIC_DIRECTION_KEY)
    assert len(s.facts["trajectory"]) == 2
    assert s.facts["required_but_not_yet_assessed"] == ["Cash Discipline (needs: documented)"]
    assert not any("FIN-CASH" in line or "Cash Discipline" in line for line in s.facts["trajectory"])
    prov = s.facts["_provenance"]
    assert {e["capability_code"] for e in prov["trajectory"]} == {"GTM-SALES", "FIN-VIS"}
    assert [u["capability_code"] for u in prov["unplaced"]] == ["FIN-CASH"]
    for key in s.facts:
        assert "gap" not in key.lower() or key == "_provenance"


# =========================================================== 12-13: provenance
def test_target_retains_intervention_capability_gap_and_evidence_provenance():
    """Case 12."""
    n = _gen(_payload(twenty_day_target=_selected()))
    f = _section(n, TWENTY_DAY_TARGET_KEY).facts
    assert f["intervention"] == "INT-157"
    p = f["_provenance"]
    assert p["source_intervention_id"] == 157
    assert p["primary_capability_id"] == 3 and p["gap_rank"] == 2 and p["gap_size"] == 2
    assert p["requirement_id"] == 903 and p["supporting_evidence_ids"] == [11, 12]
    assert [a["source_intervention_id"] for a in p["actions"]] == [157, 157]
    assert [c["criterion_id"] for c in p["success_criteria"]] == [9, 10]
    assert p["skipped_gaps"][0]["excluded_intervention_ids"] == [56, 64]


def test_direction_retains_requirement_and_evidence_provenance():
    """Case 13."""
    n = _gen(_payload(strategic_direction=_direction()))
    p = _section(n, STRATEGIC_DIRECTION_KEY).facts["_provenance"]
    assert [e["requirement_id"] for e in p["trajectory"]] == [903, 922]
    assert [e["sequence"] for e in p["trajectory"]] == [1, 2]
    assert p["target_revenue_band"] == "5Cr_25Cr"


def test_provenance_survives_the_snapshot_round_trip():
    """The cached narrative is what every later read serves."""
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    back = ReportNarrative.from_dict(n.report_id, n.as_dict())
    for key in (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY):
        assert _section(back, key).facts == _section(n, key).facts


def test_founder_facing_facts_are_scalars_or_lists_of_strings():
    """Both renderers print only scalars and lists of scalars; structured
    provenance is confined to the underscore key they hide."""
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    for key in (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY):
        for k, v in _section(n, key).facts.items():
            if k.startswith("_"):
                continue
            assert isinstance(v, (str, int)) or (
                isinstance(v, list) and all(isinstance(x, str) for x in v)), (key, k, v)


# =========================================================== 14-17: nothing invented
def test_no_invented_kpi():
    """Case 14. The only numbers in the founder-facing facts are ones the
    engines emit: the fixed horizon and the count of gaps considered."""
    n = _gen(_payload(twenty_day_target=_selected(), strategic_direction=_direction()))
    t = _section(n, TWENTY_DAY_TARGET_KEY).facts
    assert t["horizon_days"] == 20
    for k, v in t.items():
        if isinstance(v, str) and not k.startswith("_"):
            assert "%" not in v
    d = _section(n, STRATEGIC_DIRECTION_KEY).facts
    assert d["target_revenue_band"] == "5Cr_25Cr"          # carried verbatim, never a number
    for line in d["trajectory"] + d["why_each_matters"]:
        assert "%" not in line and "Cr" not in line.replace("Cr_", "")
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
    """Case 18. The new sections are emitted with empty slots, so no narrator
    -- template or LLM -- writes for them; and a narrator only ever returns
    prose, so facts are unreachable by construction."""
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
def _founder_reports(db, n=2):
    return db.execute(text(
        "SELECT report_id, founder_id, session_id FROM founder_reports"
        " WHERE is_active ORDER BY report_id DESC LIMIT :n"), {"n": n}).all()


def test_founder_a_cannot_receive_founder_b_capability_state(db):
    """Case 20 / section 15. Founder A gets a stated destination and confident
    evidence; founder B gets neither. B's report must show none of A's."""
    row = db.execute(text(
        "SELECT a.answer_id, a.question_id, a.session_id, s.founder_id"
        "  FROM answers a JOIN question_capabilities qc ON qc.question_id = a.question_id"
        "  JOIN sessions s ON s.session_id = a.session_id LIMIT 1")).first()
    if row is None:
        pytest.skip("no answer to a mapped question in this database")
    answer_id, question_id, session_a, founder_a = row
    other = db.execute(text(
        "SELECT founder_id, session_id FROM sessions WHERE founder_id <> :f LIMIT 1"),
        {"f": founder_a}).first()
    if other is None:
        pytest.skip("need a second founder")
    founder_b, session_b = other

    from app.api.v1.diagnosis.repository import DiagnosisRepository
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": question_id}).scalar()
    DiagnosisRepository(db).record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=0, confidence=0.95, evidence_text="isolation probe")
    db.execute(text("UPDATE founders SET target_revenue_band = '5Cr_25Cr',"
                    " target_time_horizon = '12_months', stage_id = 5 WHERE founder_id = :f"),
               {"f": founder_a})
    db.execute(text("UPDATE founders SET target_revenue_band = NULL,"
                    " target_time_horizon = NULL WHERE founder_id = :f"), {"f": founder_b})

    a = _capability_outputs(db, SimpleNamespace(report_id=1, founder_id=founder_a, session_id=session_a))
    b = _capability_outputs(db, SimpleNamespace(report_id=2, founder_id=founder_b, session_id=session_b))

    assert a[1].status == DIRECTION_RESOLVED
    assert b[1].status == NO_TARGET_CONTEXT               # B never stated a destination
    assert b[1].trajectory == () and b[1].unplaced == ()
    assert b[0].status == NO_ACTIONABLE_TARGET and b[0].considered_gap_count == 0
    a_ids = set(a[1].capability_ids) | {u.capability_id for u in a[1].unplaced}
    assert capability_id in a_ids or a[1].unplaced       # A's state exists and is A's
    assert not (set(b[1].capability_ids) & a_ids)


def test_empty_capability_evidence_fabricates_no_strategic_gap(db):
    """Case 21. A destination with no evidence yields unplaced requirements
    and an empty trajectory -- never a gap, never a target."""
    rows = _founder_reports(db, 1)
    if not rows:
        pytest.skip("no report")
    report_id, founder_id, session_id = rows[0]
    db.execute(text("DELETE FROM capability_evidence WHERE answer_id IN"
                    " (SELECT answer_id FROM answers WHERE session_id = :s)"), {"s": session_id})
    db.execute(text("UPDATE founders SET target_revenue_band = '1Cr_5Cr', stage_id = 5"
                    " WHERE founder_id = :f"), {"f": founder_id})
    target, direction = _capability_outputs(
        db, SimpleNamespace(report_id=report_id, founder_id=founder_id, session_id=session_id))
    assert direction.status == DIRECTION_RESOLVED
    assert direction.trajectory == ()
    assert direction.unplaced                           # required, not yet assessed
    assert target.status == NO_ACTIONABLE_TARGET


def test_production_like_reports_still_compose_a_valid_founder_report(db):
    """Case 22. Every recent real report builds, round-trips, and keeps every
    pre-existing section it had."""
    from app.api.v1.reports.payload import build_report_payload
    from app.models import FounderReport
    rows = _founder_reports(db, 5)
    if not rows:
        pytest.skip("no report")
    for report_id, _founder_id, _session_id in rows:
        report = db.get(FounderReport, report_id)
        n = _gen(build_report_payload(db, report))
        keys = _keys(n)
        assert "founder_dna" in keys and "business_dna" in keys
        assert keys[-1] == "discovery_cta" or n.variant is ReportVariant.DISTRESS
        back = ReportNarrative.from_dict(report_id, n.as_dict())
        assert _keys(back) == keys
        for key in (TWENTY_DAY_TARGET_KEY, STRATEGIC_DIRECTION_KEY):
            s = _section(n, key)
            if s is not None:
                assert s.facts["status"]                 # a named state, never a hole


def test_golden_trace_full_founder_report_on_real_data(db, capsys):
    """Section 20. A real founder's report with a stated destination and
    confident evidence: every new section traced back to its rows."""
    from app.api.v1.reports.payload import build_report_payload
    from app.models import FounderReport
    row = db.execute(text(
        "SELECT a.answer_id, a.question_id, a.session_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        "  JOIN founder_reports r ON r.session_id = a.session_id AND r.is_active LIMIT 1")).first()
    if row is None:
        pytest.skip("no active report on a session with a mapped answer")
    answer_id, question_id, session_id = row
    report = db.execute(text(
        "SELECT report_id FROM founder_reports WHERE session_id = :s AND is_active LIMIT 1"),
        {"s": session_id}).scalar()
    report = db.get(FounderReport, report)
    from app.api.v1.diagnosis.repository import DiagnosisRepository
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": question_id}).scalar()
    DiagnosisRepository(db).record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=1, confidence=0.95, evidence_text="golden trace")
    db.execute(text("UPDATE founders SET target_revenue_band = '5Cr_25Cr',"
                    " target_time_horizon = '12_months', stage_id = 5 WHERE founder_id = :f"),
               {"f": report.founder_id})

    n = _gen(build_report_payload(db, report))
    t = _section(n, TWENTY_DAY_TARGET_KEY)
    d = _section(n, STRATEGIC_DIRECTION_KEY)
    assert t is not None and d is not None

    with capsys.disabled():
        print(f"\n    FOUNDER REPORT {report.report_id} (founder {report.founder_id}, "
              f"session {session_id}) variant={n.variant.value}")
        print(f"    sections: {_keys(n)}")
        for s in (t, d):
            print(f"\n    [{s.key}] {s.heading}")
            for k, v in s.facts.items():
                if k.startswith("_"):
                    continue
                print(f"      {k}: {v}")
            prov = s.facts.get("_provenance", {})
            print(f"      _provenance: {sorted(prov.keys())}")
        if d.facts.get("status") == DIRECTION_RESOLVED:
            for e in d.facts["_provenance"]["trajectory"]:
                print(f"      trace: {e['capability_code']} <- requirement {e['requirement_id']}"
                      f" <- evidence {e['supporting_evidence_ids']}")
        if t.facts.get("status") == TARGET_SELECTED:
            p = t.facts["_provenance"]
            print(f"      trace: {p['primary_capability_code']} <- intervention "
                  f"{p['source_intervention_id']} <- requirement {p['requirement_id']}"
                  f" <- evidence {p['supporting_evidence_ids']} ; criteria "
                  f"{[c['criterion_id'] for c in p['success_criteria']]}")
