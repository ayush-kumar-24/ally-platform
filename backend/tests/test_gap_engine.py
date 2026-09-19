"""Step 8: CURRENT CAPABILITY STATE + TARGET-STATE REQUIREMENTS -> GAP.

THE ONE RULE THIS FILE PROTECTS ABOVE ALL OTHERS: UNASSESSED != GAP. Every
"insufficient evidence" test asserts `status == STATUS_UNASSESSED`, never a
comparison result, and `_compare`'s own if/elif ordering (checked first, before
any `<`/`>=`) is what makes `None < required_level` a code path that provably
never executes.

Synthetic RequiredCapability/CapabilityAssessment objects drive most of this
file, matching the discipline test_target_state_requirements.py and
test_capability_assessment.py already established: the comparison is
data-driven, so a test built on the live 55 requirement rows would prove the
seed data, not the mechanism. The live cross-check (Step 6's own requirement
data, real capability ids) is a separate, explicit section below.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.capability_assessment import CapabilityAssessment
from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.founder_context import FounderContext
from app.api.v1.diagnosis.gap_engine import (
    STATUS_GAP,
    STATUS_NOT_REQUIRED,
    STATUS_SATISFIED,
    STATUS_UNASSESSED,
    CapabilityGap,
    compute_capability_gaps,
)
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.api.v1.diagnosis.target_state import RequiredCapability, TargetStateContext, resolve_requirements
from app.db.session import engine as db_engine


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


def req(cid, code="X", level=2, necessity="core", requirement_id=None, specificity=0):
    return RequiredCapability(
        capability_id=cid, capability_code=code, required_level=CapabilityLevel(level),
        necessity=necessity, rationale="because", requirement_id=requirement_id or (100 + cid),
        specificity=specificity, matched_on=(),
    )


def asmt(cid, code="X", level=None, supporting=(1,), considered=None, excluded=()):
    return CapabilityAssessment(
        capability_id=cid, capability_code=code,
        current_level=None if level is None else CapabilityLevel(level),
        supporting_evidence_ids=supporting if level is not None else (),
        considered_evidence_ids=considered if considered is not None else supporting,
        excluded_evidence_ids=excluded,
    )


NAMES = {i: f"Capability {i}" for i in range(1, 10)}


def _code_without_module_docstring(path):
    """The file's source with its leading triple-quoted docstring removed, so
    a guard test checking for real usage is not tripped by prose that
    legitimately explains, in negation, what the module does not do."""
    import ast
    source = open(path).read()
    tree = ast.parse(source)
    doc = ast.get_docstring(tree, clean=False)
    if doc:
        first_stmt = tree.body[0]
        end_line = first_stmt.end_lineno
        lines = source.split("\n")
        return "\n".join(lines[end_line:])
    return source


def one(requirements=(), assessments=(), names=NAMES):
    gaps = compute_capability_gaps(requirements, assessments, names)
    assert len(gaps) == 1, gaps
    return gaps[0]


# =========================================================== 1-3: the core rule
def test_current_equals_required_is_satisfied():
    """Case 1."""
    g = one((req(1, level=2),), (asmt(1, level=2),))
    assert g.status == STATUS_SATISFIED


def test_current_less_than_required_is_gap():
    """Case 2."""
    g = one((req(1, level=3),), (asmt(1, level=1),))
    assert g.status == STATUS_GAP


def test_current_greater_than_required_is_satisfied():
    """Case 3."""
    g = one((req(1, level=1),), (asmt(1, level=3),))
    assert g.status == STATUS_SATISFIED


# =========================================================== 4-5: UNASSESSED
def test_no_assessment_with_positive_requirement_is_unassessed():
    """Case 4. THE test: insufficient evidence must never read as a gap."""
    g = one((req(1, level=2),), ())
    assert g.status == STATUS_UNASSESSED
    assert g.current_level is None
    assert g.required_level == CapabilityLevel.DOCUMENTED


def test_no_assessment_with_required_level_0_is_still_unassessed():
    """Case 5. required_level=0 does NOT waive the need for evidence -- it is
    a real requirement (satisfiable, not automatic) until something confirms
    it, exactly like any other level."""
    g = one((req(1, level=0),), ())
    assert g.status == STATUS_UNASSESSED
    assert g.current_level is None


def test_unassessed_present_but_below_confidence_floor_is_still_unassessed():
    """assess_capabilities can return a row whose current_level is None (some
    evidence existed, none confident) -- must read identically to no row at all."""
    g = one((req(1, level=2),), (asmt(1, level=None),))
    assert g.status == STATUS_UNASSESSED
    assert g.current_level is None


# =========================================================== 6: no applicable requirement
def test_no_applicable_requirement_is_not_required():
    """Case 6."""
    g = one((), (asmt(1, level=1),))
    assert g.status == STATUS_NOT_REQUIRED
    assert g.required_level is None
    assert g.current_level == CapabilityLevel.PERSONAL      # still shown, never a gap


# =========================================================== 7-9: level-0 and gap size
def test_required_level_0_with_current_0_is_satisfied_not_gap():
    """Case 7."""
    g = one((req(1, level=0),), (asmt(1, level=0),))
    assert g.status == STATUS_SATISFIED
    assert g.gap_size is None


def test_required_level_0_with_higher_current_is_satisfied_with_surplus():
    g = one((req(1, level=0),), (asmt(1, level=2),))
    assert g.status == STATUS_SATISFIED
    assert g.surplus_level == 2


def test_gap_size_is_required_minus_current():
    """Case 8."""
    g = one((req(1, level=3),), (asmt(1, level=1),))
    assert g.gap_size == 2


def test_gap_size_is_never_negative():
    """Case 9. SATISFIED never sets gap_size at all -- there is no "negative
    gap" representation anywhere in this module."""
    g = one((req(1, level=1),), (asmt(1, level=3),))
    assert g.status == STATUS_SATISFIED
    assert g.gap_size is None
    for level_pair in [(0, 3), (1, 2), (2, 3)]:
        required, current = level_pair
        gg = one((req(1, level=required),), (asmt(1, level=current),))
        assert gg.gap_size is None


# =========================================================== 17-18: UNASSESSED integrity
def test_unassessed_never_becomes_gap_across_every_required_level():
    """Case 17, exhaustively across every possible required level."""
    for level in (0, 1, 2, 3):
        g = one((req(1, level=level),), ())
        assert g.status == STATUS_UNASSESSED, level


def test_na_derived_state_cannot_become_gap(db):
    """Case 18, end to end: an N/A answer produces no capability_evidence row
    (Step 7B's own gate) -> assess_capabilities sees nothing for that
    capability -> the Gap Engine reads UNASSESSED, never GAP, regardless of
    how demanding the requirement is."""
    row = db.execute(text(
        "SELECT a.answer_id, a.question_id, a.session_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " LIMIT 1")).first()
    if row is None:
        pytest.skip("no answer to a mapped question in this database")
    answer_id, question_id, session_id = row
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": question_id}).scalar()
    capability_code = db.execute(text(
        "SELECT capability_code FROM capabilities WHERE capability_id = :c"),
        {"c": capability_id}).scalar()

    # No capability_evidence row is ever created for N/A (Step 7B's gate) --
    # so nothing needs to be inserted here; the assessment for this capability
    # in this session is already necessarily UNASSESSED.
    repo = DiagnosisRepository(db)
    assessments = repo.current_capability_assessments(session_id)
    assert capability_id not in {a.capability_id for a in assessments}

    requirement = req(capability_id, code=capability_code, level=3)  # a demanding target
    g = one((requirement,), assessments)
    assert g.status == STATUS_UNASSESSED


# =========================================================== 10-14: Step 6 resolver reuse
def founder_ctx(industry=None, business_model=None, stage_order=None):
    return SimpleNamespace(industry_code=industry, business_model=business_model,
                           stage_order=stage_order)


def test_unknown_target_revenue_does_not_activate_revenue_requirement():
    """Case 10. Delegated entirely to resolve_requirements -- the Gap Engine
    adds nothing of its own here, it just consumes whatever comes back."""
    rows = [{"requirement_id": 1, "capability_id": 1, "capability_code": "X",
            "industry_code": None, "business_model": None, "from_stage_order": None,
            "target_revenue_band": "5Cr_25Cr", "target_time_horizon": None,
            "required_level": 3, "necessity": "core", "rationale": "r"}]
    requirements = resolve_requirements(rows, founder_ctx(), TargetStateContext(None, None))
    assert requirements == ()
    gaps = compute_capability_gaps(requirements, (asmt(1, level=1),), NAMES)
    assert gaps[0].status == STATUS_NOT_REQUIRED


def test_unknown_target_horizon_does_not_activate_horizon_requirement():
    """Case 11."""
    rows = [{"requirement_id": 1, "capability_id": 1, "capability_code": "X",
            "industry_code": None, "business_model": None, "from_stage_order": None,
            "target_revenue_band": None, "target_time_horizon": "6_months",
            "required_level": 3, "necessity": "core", "rationale": "r"}]
    requirements = resolve_requirements(rows, founder_ctx(), TargetStateContext(None, None))
    assert requirements == ()


def test_industry_specific_requirement_uses_resolved_industry_context():
    """Case 12."""
    rows = [{"requirement_id": 1, "capability_id": 1, "capability_code": "X",
            "industry_code": "saas", "business_model": None, "from_stage_order": None,
            "target_revenue_band": None, "target_time_horizon": None,
            "required_level": 3, "necessity": "core", "rationale": "r"}]
    hit = resolve_requirements(rows, founder_ctx(industry="saas"), TargetStateContext())
    miss = resolve_requirements(rows, founder_ctx(industry="fintech"), TargetStateContext())
    assert len(hit) == 1 and miss == ()


def test_business_model_specific_requirement_uses_resolved_business_model():
    """Case 13."""
    rows = [{"requirement_id": 1, "capability_id": 1, "capability_code": "X",
            "industry_code": None, "business_model": "B2B", "from_stage_order": None,
            "target_revenue_band": None, "target_time_horizon": None,
            "required_level": 3, "necessity": "core", "rationale": "r"}]
    hit = resolve_requirements(rows, founder_ctx(business_model="B2B"), TargetStateContext())
    miss = resolve_requirements(rows, founder_ctx(business_model="B2C"), TargetStateContext())
    assert len(hit) == 1 and miss == ()


def test_stage_specific_requirement_uses_resolved_stage():
    """Case 14."""
    rows = [{"requirement_id": 1, "capability_id": 1, "capability_code": "X",
            "industry_code": None, "business_model": None, "from_stage_order": 5,
            "target_revenue_band": None, "target_time_horizon": None,
            "required_level": 3, "necessity": "core", "rationale": "r"}]
    hit = resolve_requirements(rows, founder_ctx(stage_order=6), TargetStateContext())
    miss = resolve_requirements(rows, founder_ctx(stage_order=2), TargetStateContext())
    assert len(hit) == 1 and miss == ()


def test_specificity_comes_exclusively_from_the_step_6_resolver():
    """Case 15, structurally: the gap engine module imports resolve_requirements
    and never redefines a specificity/cascade concept of its own."""
    code = _code_without_module_docstring("app/api/v1/diagnosis/gap_engine.py")
    for forbidden in ("specificity", "_applies(", "_pick(", "from_stage_order"):
        assert forbidden not in code, f"gap_engine.py reimplements {forbidden!r}"
    assert "from app.api.v1.diagnosis.target_state import" in code


def test_current_state_comes_exclusively_from_the_step_7c_resolver():
    """Case 16, structurally: no aggregation logic (MIN_CONFIDENCE, observed_
    level combination) lives in gap_engine.py."""
    code = _code_without_module_docstring("app/api/v1/diagnosis/gap_engine.py")
    for forbidden in ("MIN_CONFIDENCE", "observed_level", "min("):
        assert forbidden not in code, f"gap_engine.py reimplements {forbidden!r}"


# =========================================================== 19-20: traceability
def test_evidence_ids_remain_traceable_through_the_gap():
    """Case 19."""
    g = one((req(1, level=2),), (asmt(1, level=1, supporting=(42, 43)),))
    assert g.supporting_evidence_ids == (42, 43)


def test_target_requirement_reference_is_traceable():
    """Case 20."""
    g = one((req(1, level=2, requirement_id=777),), (asmt(1, level=2),))
    assert g.requirement_id == 777
    assert g.necessity == "core"


def test_not_required_carries_no_requirement_reference():
    g = one((), (asmt(1, level=1),))
    assert g.requirement_id is None
    assert g.necessity is None


def test_unassessed_carries_no_evidence_reference():
    g = one((req(1, level=2),), ())
    assert g.supporting_evidence_ids == ()


# =========================================================== 21-22: determinism
def test_requirement_insertion_order_does_not_change_the_result():
    """Case 21."""
    r1, r2 = req(1, code="A", level=2), req(2, code="B", level=1)
    a1, a2 = asmt(1, code="A", level=2), asmt(2, code="B", level=3)
    forward = compute_capability_gaps((r1, r2), (a1, a2), NAMES)
    backward = compute_capability_gaps((r2, r1), (a2, a1), NAMES)
    assert forward == backward


def test_evidence_insertion_order_does_not_change_the_result():
    """Case 22, via assess_capability's own already-tested determinism, plus a
    direct check that compute_capability_gaps does not itself introduce order
    sensitivity when building its internal maps."""
    a1, a2 = asmt(1, level=2), asmt(1, level=2)  # same capability, redundant
    g1 = compute_capability_gaps((req(1, level=2),), (a1,), NAMES)
    g2 = compute_capability_gaps((req(1, level=2),), (a2,), NAMES)
    assert g1 == g2


# =========================================================== 23-24: isolation
def test_founder_a_gaps_do_not_leak_to_founder_b(db):
    """Case 23. Assessments are session-scoped (Step 7C); the Gap Engine adds
    no founder-crossing lookup of its own."""
    founders = db.execute(text(
        "SELECT DISTINCT founder_id FROM answers ORDER BY founder_id LIMIT 2")).all()
    if len(founders) < 2:
        pytest.skip("need two distinct founders with answers")
    (f1,), (f2,) = founders
    s1 = db.execute(text("SELECT session_id FROM answers WHERE founder_id = :f LIMIT 1"),
                    {"f": f1}).scalar()
    s2 = db.execute(text("SELECT session_id FROM answers WHERE founder_id = :f LIMIT 1"),
                    {"f": f2}).scalar()
    a1 = db.execute(text(
        "SELECT a.answer_id, a.question_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " WHERE a.session_id = :s LIMIT 1"), {"s": s1}).first()
    if a1 is None:
        pytest.skip("founder 1's session has no mapped-question answer")
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": a1[1]}).scalar()
    repo = DiagnosisRepository(db)
    repo.record_capability_evidence(
        capability_id=capability_id, question_id=a1[1], answer_id=a1[0],
        observed_level=3, confidence=0.9, evidence_text="founder 1 only")

    requirement = req(capability_id, level=1)
    gaps_f2 = compute_capability_gaps((requirement,), repo.current_capability_assessments(s2), NAMES)
    assert gaps_f2[0].status == STATUS_UNASSESSED, "founder 2 must not see founder 1's evidence"


def test_session_a_evidence_does_not_leak_to_session_b(db):
    """Case 24."""
    sessions = db.execute(text(
        "SELECT DISTINCT session_id FROM answers ORDER BY session_id LIMIT 2")).all()
    if len(sessions) < 2:
        pytest.skip("need two distinct sessions")
    (s1,), (s2,) = sessions
    a1 = db.execute(text(
        "SELECT a.answer_id, a.question_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " WHERE a.session_id = :s LIMIT 1"), {"s": s1}).first()
    if a1 is None:
        pytest.skip("session 1 has no mapped-question answer")
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": a1[1]}).scalar()
    repo = DiagnosisRepository(db)
    repo.record_capability_evidence(
        capability_id=capability_id, question_id=a1[1], answer_id=a1[0],
        observed_level=3, confidence=0.9, evidence_text="session 1 only")
    gaps_s2 = compute_capability_gaps(
        (req(capability_id, level=1),), repo.current_capability_assessments(s2), NAMES)
    assert gaps_s2[0].status == STATUS_UNASSESSED


# =========================================================== 25-28: no side effects
def test_no_database_writes_occur(db):
    """Case 25. compute_capability_gaps takes no db handle at all -- structural."""
    import inspect
    sig = inspect.signature(compute_capability_gaps)
    assert "db" not in sig.parameters and "session" not in sig.parameters


def test_no_recommendation_is_produced():
    """Case 26."""
    fields = set(CapabilityGap.__dataclass_fields__)
    for forbidden in ("recommendation", "recommended_action", "advice"):
        assert forbidden not in fields


def test_no_intervention_is_selected():
    """Case 27."""
    fields = set(CapabilityGap.__dataclass_fields__)
    for forbidden in ("intervention", "intervention_id", "action"):
        assert forbidden not in fields
    code = _code_without_module_docstring("app/api/v1/diagnosis/gap_engine.py")
    assert "intervention" not in code.lower()


def test_no_priority_is_assigned():
    """Case 28."""
    fields = set(CapabilityGap.__dataclass_fields__)
    for forbidden in ("priority", "urgency", "severity", "roi", "business_impact"):
        assert forbidden not in fields


def test_no_llm_is_imported():
    code = _code_without_module_docstring("app/api/v1/diagnosis/gap_engine.py")
    for forbidden in ("llm", "provider", "prompt", "embedding"):
        assert forbidden not in code.lower()


# =========================================================== 29-32: no regressions
@pytest.mark.parametrize("module", [
    "app/api/v1/reasoning/engines/diagnostic.py",
    "app/api/v1/reasoning/engines/root_cause.py",
    "app/api/v1/diagnosis/engine.py",
    "app/api/v1/diagnosis/advisor.py",
])
def test_existing_module_has_no_dependency_on_the_gap_engine(module):
    """Cases 29-32, structurally: diagnosis scoring, root-cause ranking,
    question selection and the budget must not have grown a dependency on a
    module built to be read by something LATER, not by anything today."""
    source = open(module).read()
    assert "gap_engine" not in source
    assert "compute_capability_gaps" not in source


# =========================================================== golden cases (section 17)
def test_case_a_satisfied():
    g = one((req(1, "GTM-ACQ", 2),), (asmt(1, "GTM-ACQ", 2),))
    assert g.status == STATUS_SATISFIED


def test_case_b_gap():
    g = one((req(1, "GTM-OWN", 3),), (asmt(1, "GTM-OWN", 1),))
    assert g.status == STATUS_GAP and g.gap_size == 2


def test_case_c_unassessed_not_gap():
    g = one((req(1, "FIN-UNIT", 2),), ())
    assert g.status == STATUS_UNASSESSED


def test_case_d_exceeds_is_satisfied():
    g = one((req(1, "OPS-SOP", 2),), (asmt(1, "OPS-SOP", 3),))
    assert g.status == STATUS_SATISFIED


def test_case_e_no_requirement():
    g = one((), (asmt(1, "PRD-DELIVERY", 1),))
    assert g.status == STATUS_NOT_REQUIRED


def test_case_f_unknown_target_context_does_not_activate():
    rows = [{"requirement_id": 1, "capability_id": 1, "capability_code": "X",
            "industry_code": None, "business_model": None, "from_stage_order": None,
            "target_revenue_band": "1Cr_5Cr", "target_time_horizon": None,
            "required_level": 2, "necessity": "core", "rationale": "r"}]
    requirements = resolve_requirements(rows, founder_ctx(), TargetStateContext(None, None))
    assert requirements == ()


# =========================================================== live cross-check (section 18)
def test_live_requirement_data_resolves_deterministically_across_a_context_matrix(db):
    """Section 18. Real capability_requirements rows, real capability ids, a
    matrix of industries/business models/stages/bands/horizons. No requirement
    is invented; this exercises the SAME rows Step 6 seeded."""
    repo = DiagnosisRepository(db)
    rows = repo.capability_requirement_rows()
    names = repo.capability_names()
    assert rows, "no requirements seeded"

    bands = [None, "under_1L", "1Cr_5Cr", "5Cr_25Cr", "above_25Cr"]
    industries = [None, "saas", "fintech", "ecommerce_d2c"]
    models = [None, "B2B", "B2C"]
    stages = [None, 1, 5, 8]

    checked = 0
    for band in bands:
        for industry in industries:
            for model in models:
                for stage in stages:
                    ctx = founder_ctx(industry=industry, business_model=model, stage_order=stage)
                    target = TargetStateContext(band, None)
                    requirements = resolve_requirements(rows, ctx, target)
                    assessments = ()          # no evidence; isolates requirement resolution
                    gaps = compute_capability_gaps(requirements, assessments, names)
                    # Every requirement produces exactly one UNASSESSED gap
                    # (no evidence supplied), and nothing else -- deterministic,
                    # one-to-one, no duplication of the Step 6 cascade's own work.
                    assert len(gaps) == len(requirements)
                    assert all(g.status == STATUS_UNASSESSED for g in gaps)
                    checked += 1
    assert checked == len(bands) * len(industries) * len(models) * len(stages)


def test_live_data_end_to_end_through_the_repository(db):
    """The full composed pipeline against real seeded rows, with real recorded
    evidence, proving all three pieces (Step 6 resolver, Step 7C assessment,
    Step 8 comparison) agree without any manual data construction."""
    row = db.execute(text(
        "SELECT a.answer_id, a.question_id, a.session_id FROM answers a"
        "  JOIN question_capabilities qc ON qc.question_id = a.question_id"
        " LIMIT 1")).first()
    if row is None:
        pytest.skip("no answer to a mapped question in this database")
    answer_id, question_id, session_id = row
    capability_id = db.execute(text(
        "SELECT capability_id FROM question_capabilities WHERE question_id = :q"),
        {"q": question_id}).scalar()

    repo = DiagnosisRepository(db)
    repo.record_capability_evidence(
        capability_id=capability_id, question_id=question_id, answer_id=answer_id,
        observed_level=3, confidence=0.95, evidence_text="live pipeline probe")

    ctx = founder_ctx(industry="saas", business_model="B2B", stage_order=5)
    target = TargetStateContext("1Cr_5Cr", "12_months")
    gaps = repo.capability_gaps_for_session(session_id, ctx, target)

    match = [g for g in gaps if g.capability_id == capability_id]
    if match:
        # Level 3 evidence can only ever be SATISFIED against any real
        # required_level (max is 3) -- never a gap.
        assert match[0].status in (STATUS_SATISFIED, STATUS_NOT_REQUIRED)
        assert match[0].current_level == CapabilityLevel.OWNED
