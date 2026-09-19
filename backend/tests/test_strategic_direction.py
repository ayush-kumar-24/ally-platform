"""Step 10B: CURRENT CAPABILITY STATE + TARGET REQUIREMENTS -> CAPABILITY TRAJECTORY.

THE RULES THIS FILE PROTECTS: `sequence` is reading order and NEVER a
dependency claim (no data in this system establishes one); UNASSESSED is never
placed on the trajectory; Step 6's ambiguity is preserved rather than guessed
past; the destination never becomes a fabricated numeric milestone; and no
year, quarter, month or date appears anywhere.

Requirement-resolution cases go through the real Step 6 resolver with
synthetic rows -- the same discipline test_gap_engine.py established -- so the
tests prove the resolver is USED rather than bypassed, without proving the
seed data. The golden trace then runs the whole chain on real reference rows.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.capability_assessment import CapabilityAssessment
from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.gap_engine import compute_capability_gaps
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.api.v1.diagnosis.strategic_direction import (
    AMBIGUOUS_REQUIREMENTS,
    DIRECTION_RESOLVED,
    NO_TARGET_CONTEXT,
    CapabilityTrajectory,
    DirectionNarration,
    StrategicDirection,
    ambiguous_direction,
    build_strategic_direction,
    narrate_direction,
)
from app.api.v1.diagnosis.target_state import (
    AmbiguousRequirementError,
    TargetStateContext,
    resolve_requirements,
)
from app.db.session import engine as db_engine

ENGINE = "app/api/v1/diagnosis/strategic_direction.py"


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


def ctx(industry=None, business_model=None, stage_order=None):
    return SimpleNamespace(industry_code=industry, business_model=business_model,
                           stage_order=stage_order)


def row(requirement_id=1, capability_id=1, code="X", level=2, necessity="core",
        industry=None, model=None, stage=None, band=None, horizon=None,
        rationale="because the destination needs it"):
    return {"requirement_id": requirement_id, "capability_id": capability_id,
            "capability_code": code, "industry_code": industry,
            "business_model": model, "from_stage_order": stage,
            "target_revenue_band": band, "target_time_horizon": horizon,
            "required_level": level, "necessity": necessity, "rationale": rationale}


def asmt(capability_id, code="X", level=1, evidence=(5,)):
    return CapabilityAssessment(
        capability_id=capability_id, capability_code=code,
        current_level=None if level is None else CapabilityLevel(level),
        supporting_evidence_ids=evidence if level is not None else (),
        considered_evidence_ids=evidence, excluded_evidence_ids=())


DETAIL = {cid: {"capability_id": cid, "capability_name": f"Outcome {cid}",
                "description": f"What capability {cid} is."}
          for cid in range(1, 20)}
NAMES = {cid: f"Outcome {cid}" for cid in range(1, 20)}


def direction(requirements, assessments, target=None):
    target = target or TargetStateContext("1Cr_5Cr", None)
    gaps = compute_capability_gaps(requirements, tuple(assessments), NAMES)
    return build_strategic_direction(gaps, requirements, DETAIL, target)


def _executable_code(path):
    """The file's executable code only -- every docstring and comment removed,
    so a guard looking for real usage is never tripped by prose that
    legitimately explains what the module does NOT do."""
    import ast
    tree = ast.parse(open(path).read())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = node.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


# =========================================================== 1-2: target context
def test_no_target_context_produces_no_direction():
    """Case 1. Step 6's own behaviour is preserved: an unstated destination
    activates nothing, so there is no target state to move toward."""
    rows = [row(band="5Cr_25Cr")]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext(None, None))
    assert requirements == ()
    result = direction(requirements, [asmt(1, level=1)], TargetStateContext(None, None))
    assert result.status == NO_TARGET_CONTEXT
    assert result.trajectory == ()
    assert result.unplaced == ()


def test_generic_wildcard_requirement_applies_to_everyone():
    """Case 2. A row constraining only the band is generic across industry,
    business model and stage."""
    rows = [row(band="1Cr_5Cr", level=3)]
    for founder in (ctx(), ctx("saas", "B2B", 5), ctx("fintech", "B2C", 2)):
        requirements = resolve_requirements(rows, founder, TargetStateContext("1Cr_5Cr", None))
        assert len(requirements) == 1
        result = direction(requirements, [asmt(1, level=1)])
        assert result.status == DIRECTION_RESOLVED
        assert result.trajectory[0].required_level == CapabilityLevel.OWNED


# =========================================================== 3-7: specificity axes
def test_industry_specific_requirement_is_resolved_not_reimplemented():
    """Case 3."""
    rows = [row(band="1Cr_5Cr", industry="saas", level=3)]
    hit = resolve_requirements(rows, ctx(industry="saas"), TargetStateContext("1Cr_5Cr", None))
    miss = resolve_requirements(rows, ctx(industry="fintech"), TargetStateContext("1Cr_5Cr", None))
    assert len(hit) == 1 and miss == ()
    assert direction(hit, [asmt(1, level=1)]).has_direction
    assert direction(miss, [asmt(1, level=1)]).status == NO_TARGET_CONTEXT


def test_business_model_specific_requirement():
    """Case 4."""
    rows = [row(band="1Cr_5Cr", model="B2B", level=3)]
    hit = resolve_requirements(rows, ctx(business_model="B2B"), TargetStateContext("1Cr_5Cr", None))
    miss = resolve_requirements(rows, ctx(business_model="B2C"), TargetStateContext("1Cr_5Cr", None))
    assert len(hit) == 1 and miss == ()


def test_stage_specific_requirement():
    """Case 5."""
    rows = [row(band="1Cr_5Cr", stage=5, level=3)]
    hit = resolve_requirements(rows, ctx(stage_order=6), TargetStateContext("1Cr_5Cr", None))
    miss = resolve_requirements(rows, ctx(stage_order=2), TargetStateContext("1Cr_5Cr", None))
    assert len(hit) == 1 and miss == ()


def test_revenue_band_specific_requirement():
    """Case 6."""
    rows = [row(band="5Cr_25Cr", level=3)]
    hit = resolve_requirements(rows, ctx(), TargetStateContext("5Cr_25Cr", None))
    miss = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    assert len(hit) == 1 and miss == ()


def test_time_horizon_specific_requirement():
    """Case 7."""
    rows = [row(band="1Cr_5Cr", horizon="6_months", level=3)]
    hit = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", "6_months"))
    miss = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", "12_months"))
    assert len(hit) == 1 and miss == ()


def test_multiple_applicable_requirements_all_become_trajectory_entries():
    """Case 8."""
    rows = [row(1, 1, "A", band="1Cr_5Cr", level=3),
            row(2, 2, "B", band="1Cr_5Cr", level=2),
            row(3, 3, "C", band="1Cr_5Cr", level=3)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    assert len(requirements) == 3
    result = direction(requirements,
                       [asmt(1, "A", 1), asmt(2, "B", 1), asmt(3, "C", 1)])
    assert len(result.trajectory) == 3


# =========================================================== 9: ambiguity
def test_ambiguous_requirements_are_preserved_not_guessed():
    """Case 9. Step 6 raises for two equally specific rules that disagree;
    this step reports that verbatim instead of picking one."""
    rows = [row(1, 1, "A", band="1Cr_5Cr", level=3, necessity="core"),
            row(2, 1, "A", band="1Cr_5Cr", level=1, necessity="contextual")]
    with pytest.raises(AmbiguousRequirementError) as raised:
        resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))

    result = ambiguous_direction(TargetStateContext("1Cr_5Cr", None), str(raised.value))
    assert result.status == AMBIGUOUS_REQUIREMENTS
    assert result.trajectory == ()
    assert "equally specific" in result.ambiguity
    assert "requirement 1" in result.ambiguity and "requirement 2" in result.ambiguity


def test_the_repository_catches_ambiguity_instead_of_aborting(db, monkeypatch):
    """A single undecidable capability must not take a founder's whole
    direction down with it."""
    repo = DiagnosisRepository(db)
    import app.api.v1.diagnosis.target_state as target_state

    def boom(*args, **kwargs):
        raise AmbiguousRequirementError("capability_id 7 has 2 rows that disagree")
    monkeypatch.setattr(target_state, "resolve_requirements", boom)

    result = repo.strategic_direction_for_session(
        1, ctx("saas", "B2B", 5), TargetStateContext("1Cr_5Cr", None))
    assert result.status == AMBIGUOUS_REQUIREMENTS
    assert "disagree" in result.ambiguity


# =========================================================== 10-14: level cases
def test_no_current_evidence_is_named_but_never_placed_on_the_trajectory():
    """Case 10. UNKNOWN is not a value: a direction would assert a current
    state nobody measured."""
    rows = [row(band="1Cr_5Cr", level=3)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    result = direction(requirements, [])
    assert result.trajectory == ()
    assert len(result.unplaced) == 1
    assert result.unplaced[0].capability_id == 1
    assert result.unplaced[0].required_level == CapabilityLevel.OWNED


def test_current_below_required_becomes_a_trajectory_entry():
    """Case 11."""
    rows = [row(band="1Cr_5Cr", level=3)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    result = direction(requirements, [asmt(1, level=1)])
    entry = result.trajectory[0]
    assert entry.current_level == CapabilityLevel.PERSONAL
    assert entry.required_level == CapabilityLevel.OWNED
    assert entry.gap_size == 2
    assert entry.transition_label == "founder-dependent -> owned by someone else"


def test_current_equal_to_required_produces_no_direction():
    """Case 12. Nothing to evolve."""
    rows = [row(band="1Cr_5Cr", level=2)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    result = direction(requirements, [asmt(1, level=2)])
    assert result.trajectory == ()
    assert result.unplaced == ()


def test_current_above_required_produces_no_direction():
    """Case 13. Exceeding is never a reverse trajectory."""
    rows = [row(band="1Cr_5Cr", level=1)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    result = direction(requirements, [asmt(1, level=3)])
    assert result.trajectory == ()


def test_required_level_zero_is_a_real_requirement():
    """Case 14. Level 0 is satisfiable, not an absence of requirement."""
    rows = [row(band="1Cr_5Cr", level=0)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    assert requirements[0].required_level == CapabilityLevel.ABSENT
    assert direction(requirements, [asmt(1, level=0)]).trajectory == ()
    # and with no evidence it is unassessed, never auto-satisfied
    assert direction(requirements, []).unplaced


# =========================================================== 15-16: ordering
def test_multiple_strategic_gaps_are_ordered_by_step_9a_priority():
    """Cases 15, 16. Necessity first, then gap magnitude, then capability_id --
    Step 9A's ordering, reused by calling it."""
    rows = [row(1, 1, "A", band="1Cr_5Cr", level=2, necessity="contextual"),
            row(2, 2, "B", band="1Cr_5Cr", level=3, necessity="core"),
            row(3, 3, "C", band="1Cr_5Cr", level=2, necessity="core")]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    result = direction(requirements,
                       [asmt(1, "A", 0), asmt(2, "B", 1), asmt(3, "C", 1)])
    # B (core, gap 2) then C (core, gap 1) then A (contextual)
    assert [t.capability_code for t in result.trajectory] == ["B", "C", "A"]
    assert [t.sequence for t in result.trajectory] == [1, 2, 3]


def test_ordering_is_stable_and_insertion_order_independent():
    """Case 16."""
    rows = [row(1, 1, "A", band="1Cr_5Cr", level=3),
            row(2, 2, "B", band="1Cr_5Cr", level=3),
            row(3, 3, "C", band="1Cr_5Cr", level=3)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    assessments = [asmt(1, "A", 1), asmt(2, "B", 1), asmt(3, "C", 1)]
    first = direction(requirements, assessments)
    second = direction(tuple(reversed(requirements)), list(reversed(assessments)))
    assert first.capability_ids == second.capability_ids


def test_sequence_is_never_a_dependency_claim():
    """Case 19. No data in this system establishes capability dependency, so
    the output cannot express one."""
    fields = set(CapabilityTrajectory.__dataclass_fields__)
    for forbidden in ("depends_on", "dependencies", "prerequisite", "prerequisites",
                      "blocks", "blocked_by", "phase", "stage_of_plan", "after",
                      "before", "unlocks"):
        assert forbidden not in fields
    code = _executable_code(ENGINE)
    for forbidden in ("depends_on", "prerequisite", "unlocks", "blocked_by"):
        assert forbidden not in code.lower()


# =========================================================== 17-18: no invention
def test_no_capability_is_invented():
    """Case 17. Every trajectory entry traces to a resolved requirement and a
    real capability id."""
    rows = [row(1, 1, "A", band="1Cr_5Cr", level=3),
            row(2, 2, "B", band="1Cr_5Cr", level=3)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    result = direction(requirements, [asmt(1, "A", 1), asmt(2, "B", 1)])
    required_ids = {r.capability_id for r in requirements}
    assert {t.capability_id for t in result.trajectory} <= required_ids
    assert all(t.requirement_id is not None for t in result.trajectory)


def test_no_numeric_kpi_or_milestone_is_generated():
    """Case 18. The destination selects requirements; it never becomes a number
    to hit or a date to hit it by."""
    rows = [row(band="5Cr_25Cr", level=3)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("5Cr_25Cr", "12_months"))
    result = direction(requirements, [asmt(1, level=1)],
                       TargetStateContext("5Cr_25Cr", "12_months"))
    entry = result.trajectory[0]
    # the band is carried as context, never transformed into a target number
    assert result.target.target_revenue_band == "5Cr_25Cr"
    assert "5Cr" not in entry.transition_label
    assert not any(ch.isdigit() for ch in entry.transition_label)
    fields = set(CapabilityTrajectory.__dataclass_fields__)
    for forbidden in ("target_revenue", "revenue_target", "kpi", "metric",
                      "target_value", "by_month", "target_date", "deadline"):
        assert forbidden not in fields
    code = _executable_code(ENGINE)
    for forbidden in ("increase", "revenue by", "%", "kpi"):
        assert forbidden not in code.lower()


# =========================================================== 20-24: no leakage
def test_no_intervention_selection_leakage():
    """Case 20. 10B never touches the intervention library."""
    code = _executable_code(ENGINE)
    for forbidden in ("intervention", "gap_intervention", "immediate_next_steps",
                      "select_interventions"):
        assert forbidden not in code.lower()
    assert "intervention" not in str(set(CapabilityTrajectory.__dataclass_fields__))


def test_no_root_cause_ranking_leakage():
    """Case 21. Strategic capability importance is never root-cause rank."""
    code = _executable_code(ENGINE)
    for forbidden in ("root_cause", "detection_score", "final_weighted_score",
                      "scoredrootcause", "confirmation_status"):
        assert forbidden not in code.lower()


def test_no_billing_or_plan_references():
    """Case 22."""
    code = _executable_code(ENGINE)
    for forbidden in ("199", "499", "999", "plan_tier", "entitlement",
                      "subscription", "feature.", "price", "billing", "tier"):
        assert forbidden not in code.lower()


def test_no_twenty_day_task_leakage():
    """Case 23. 10B neither reads, writes nor waits on the 20-day target."""
    code = _executable_code(ENGINE)
    for forbidden in ("twenty_day", "twentyday", "horizon_days", "target_action",
                      "success_criteri", "20"):
        assert forbidden not in code.lower()
    fields = set(CapabilityTrajectory.__dataclass_fields__)
    for forbidden in ("actions", "tasks", "next_steps", "success_criteria"):
        assert forbidden not in fields


def test_no_year_by_year_roadmap_is_generated():
    """Case 24. The engine attaches no time to anything at all."""
    code = _executable_code(ENGINE)
    for forbidden in ("year", "quarter", "month", "week", "day", "roadmap",
                      "milestone", "schedule", "timeline", "date", "deadline"):
        assert forbidden not in code.lower(), f"engine mentions {forbidden!r}"
    for cls in (CapabilityTrajectory, StrategicDirection):
        fields = set(cls.__dataclass_fields__)
        for forbidden in ("year", "year_one", "years", "quarter", "months",
                          "roadmap", "milestones", "timeline", "schedule"):
            assert forbidden not in fields


# =========================================================== 25: LLM boundary
class _Rewriter:
    def narrate(self, direction):
        return DirectionNarration(
            summary="a different summary",
            trajectory_lines=tuple(f"rewritten {i}" for i in range(len(direction.trajectory))))


class _Exploder:
    def narrate(self, direction):
        raise RuntimeError("provider down")


class _DropsLines:
    def narrate(self, direction):
        return DirectionNarration(summary="s", trajectory_lines=("only one",))


def _resolved():
    rows = [row(1, 1, "A", band="1Cr_5Cr", level=3),
            row(2, 2, "B", band="1Cr_5Cr", level=2)]
    requirements = resolve_requirements(rows, ctx(), TargetStateContext("1Cr_5Cr", None))
    return direction(requirements, [asmt(1, "A", 1), asmt(2, "B", 1)])


def test_narration_cannot_mutate_the_deterministic_selection():
    """Case 25. Structural: DirectionNarration carries no identifier, level,
    sequence or requirement id, so there is nothing in it able to change one."""
    narration_fields = set(DirectionNarration.__dataclass_fields__)
    for forbidden in ("capability_id", "capability_code", "requirement_id",
                      "current_level", "required_level", "sequence", "gap_size",
                      "necessity", "evidence"):
        assert forbidden not in narration_fields

    before = _resolved()
    after = narrate_direction(before, _Rewriter())
    assert after.capability_ids == before.capability_ids
    assert [t.sequence for t in after.trajectory] == [t.sequence for t in before.trajectory]
    assert [t.required_level for t in after.trajectory] == [t.required_level for t in before.trajectory]
    assert [t.current_level for t in after.trajectory] == [t.current_level for t in before.trajectory]
    assert after.trajectory == before.trajectory          # untouched entirely
    assert after.narration.summary == "a different summary"


def test_narration_failure_leaves_the_direction_intact():
    before = _resolved()
    after = narrate_direction(before, _Exploder())
    assert after is before
    assert after.narration is None


def test_a_narration_that_changes_the_trajectory_length_is_discarded():
    before = _resolved()
    after = narrate_direction(before, _DropsLines())
    assert after.narration is None
    assert len(after.trajectory) == 2


def test_no_narrator_is_the_default_and_the_direction_is_already_complete():
    """The deterministic core alone is usable: every word is reference data."""
    result = _resolved()
    assert narrate_direction(result, None) is result
    assert result.narration is None
    entry = result.trajectory[0]
    assert entry.capability_name and entry.capability_description
    assert entry.rationale and entry.transition_label


# =========================================================== structural guards (14)
def test_the_engine_performs_no_persistence_and_no_capability_mutation():
    code = _executable_code(ENGINE)
    for forbidden in ("insert", "update ", "delete", "commit", "flush",
                      "session", "sqlalchemy", "execute(", "self.db",
                      "capability_evidence", "current_level ="):
        assert forbidden not in code.lower(), f"engine may write: {forbidden!r}"


def test_the_engine_reuses_steps_6_8_and_9a_without_restating_them():
    code = _executable_code(ENGINE)
    assert "prioritize_capability_gaps" in code        # Step 9A, called
    assert "CapabilityGap" in code                     # Step 8, consumed
    assert "RequiredCapability" in code                # Step 6, consumed
    for restated in ("necessity_rank", "_applies(", "_pick(", "specificity",
                     "from_stage_order", "MIN_CONFIDENCE", "observed_level"):
        assert restated not in code, f"strategic_direction.py restates {restated!r}"


@pytest.mark.parametrize("module", [
    "app/api/v1/reasoning/engines/diagnostic.py",
    "app/api/v1/reasoning/engines/root_cause.py",
    "app/api/v1/reasoning/engines/recommendation.py",
    # app/api/v1/reports/generator.py is no longer here: the Founder Report
    # composition layer is the intended consumer of this engine, and the
    # dependency runs one way (report -> engine). The reverse direction is
    # pinned in test_report_capability_sections.
    "app/api/v1/diagnosis/engine.py",
    "app/api/v1/diagnosis/advisor.py",
    "app/api/v1/diagnosis/gap_engine.py",
    "app/api/v1/diagnosis/gap_priority.py",
    "app/api/v1/diagnosis/gap_intervention.py",
    "app/api/v1/diagnosis/twenty_day_target.py",
    "app/api/v1/diagnosis/target_state.py",
    "app/api/v1/diagnosis/capability_assessment.py",
])
def test_existing_module_has_no_dependency_on_the_direction_engine(module):
    """Steps 6, 7C, 8, 9A, 9B and 10A are all unchanged: the dependency runs
    one way only, and 10A in particular neither knows about nor gates 10B."""
    source = open(module).read()
    for forbidden in ("strategic_direction", "StrategicDirection",
                      "build_strategic_direction", "CapabilityTrajectory"):
        assert forbidden not in source


def test_tenb_does_not_depend_on_a_twenty_day_target(db):
    """Case 23, behaviourally: a direction is computable without ever building
    a 20-day target, and building one changes nothing here."""
    repo = DiagnosisRepository(db)
    founder = ctx("saas", "B2B", 5)
    target = TargetStateContext("5Cr_25Cr", "12_months")
    session_id = db.execute(text("SELECT session_id FROM sessions LIMIT 1")).scalar()
    if session_id is None:
        pytest.skip("no session")

    before = repo.strategic_direction_for_session(session_id, founder, target)
    repo.twenty_day_target_for_session(session_id, founder, target)
    after = repo.strategic_direction_for_session(session_id, founder, target)
    assert before.status == after.status
    assert before.capability_ids == after.capability_ids


def test_building_a_direction_writes_nothing(db):
    repo = DiagnosisRepository(db)
    tables = ("capability_evidence", "capability_requirements", "capabilities",
              "capability_evidence_criteria")
    before = {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in tables}
    session_id = db.execute(text("SELECT session_id FROM sessions LIMIT 1")).scalar()
    if session_id is None:
        pytest.skip("no session")
    repo.strategic_direction_for_session(
        session_id, ctx("saas", "B2B", 5), TargetStateContext("5Cr_25Cr", "12_months"))
    after = {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in tables}
    assert before == after


# =========================================================== 26: golden trace
def test_golden_trace_on_real_reference_data(db, capsys):
    """Case 26. The whole chain on real seeded rows, printed end to end:
    target context -> resolved requirements -> current assessments -> gaps ->
    strategic directions -> final ordered trajectory."""
    repo = DiagnosisRepository(db)
    founder = ctx("saas", "B2B", 5)
    target = TargetStateContext("5Cr_25Cr", "12_months")

    requirements = resolve_requirements(repo.capability_requirement_rows(), founder, target)
    assert requirements, "no requirements resolved from real data"

    def cap(code):
        return db.execute(text(
            "SELECT capability_id FROM capabilities WHERE capability_code = :c"),
            {"c": code}).scalar()

    # Real capabilities, deliberately spanning below / equal / above required.
    assessments = [asmt(cap("GTM-SALES"), "GTM-SALES", 1),
                   asmt(cap("FIN-VIS"), "FIN-VIS", 2),
                   asmt(cap("FIN-CASH"), "FIN-CASH", 3)]
    gaps = compute_capability_gaps(requirements, tuple(assessments), repo.capability_names())
    result = build_strategic_direction(
        gaps, requirements,
        repo.capability_detail([g.capability_id for g in gaps]), target)

    assert result.status == DIRECTION_RESOLVED
    assert result.trajectory, "real data produced no trajectory"

    # Every entry is reference data, traceable to a real requirement row.
    real_rationales = {r[0] for r in db.execute(text(
        "SELECT rationale FROM capability_requirements")).all()}
    real_names = {r[0] for r in db.execute(text(
        "SELECT capability_name FROM capabilities")).all()}
    for entry in result.trajectory:
        assert entry.capability_name in real_names
        assert entry.rationale in real_rationales
        assert entry.requirement_id in {r.requirement_id for r in requirements}
        assert entry.current_level < entry.required_level

    with capsys.disabled():
        print(f"\n    TARGET CONTEXT : {target.describe()}")
        print(f"    REQUIREMENTS   : {len(requirements)} resolved "
              f"({sum(1 for r in requirements if r.is_core)} core)")
        print(f"    ASSESSMENTS    : "
              f"{[(a.capability_code, int(a.current_level)) for a in assessments]}")
        counts = {s: sum(1 for g in gaps if g.status == s) for g in gaps for s in [g.status]}
        print(f"    GAPS           : {counts}")
        print(f"    TRAJECTORY     : {len(result.trajectory)} | "
              f"unplaced {len(result.unplaced)}")
        for entry in result.trajectory:
            print(f"      {entry.sequence}. {entry.capability_code}  {entry.capability_name}")
            print(f"         direction : {entry.transition_label} "
                  f"(gap {entry.gap_size}, {entry.necessity})")
            print(f"         what      : {entry.capability_description}")
            print(f"         why       : {entry.rationale}")
        print(f"    UNPLACED       : {[u.capability_code for u in result.unplaced]}")


def test_live_end_to_end_through_the_repository(db):
    """The composed pipeline: Steps 6, 7B, 7C, 8, 9A, 10B."""
    row_ = db.execute(text(
        "SELECT a.answer_id, a.question_id, a.session_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " LIMIT 1")).first()
    if row_ is None:
        pytest.skip("no answer to a mapped question in this database")
    answer_id, question_id, session_id = row_
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": question_id}).scalar()

    repo = DiagnosisRepository(db)
    repo.record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=0, confidence=0.95, evidence_text="live 10B probe")

    result = repo.strategic_direction_for_session(
        session_id, ctx("saas", "B2B", 5), TargetStateContext("5Cr_25Cr", "12_months"))
    assert isinstance(result, StrategicDirection)
    assert result.status in (DIRECTION_RESOLVED, NO_TARGET_CONTEXT, AMBIGUOUS_REQUIREMENTS)

    again = repo.strategic_direction_for_session(
        session_id, ctx("saas", "B2B", 5), TargetStateContext("5Cr_25Cr", "12_months"))
    assert again.capability_ids == result.capability_ids
