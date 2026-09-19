"""Step 9A: CAPABILITY GAPS -> PRIORITY ORDER.

THE ONE RULE THIS FILE PROTECTS ABOVE ALL OTHERS, same spirit as
test_gap_engine.py's: UNASSESSED is never promoted into a priority merely
because it is unknown. Only `status == STATUS_GAP` rows may ever appear in
`prioritize_capability_gaps`'s output -- every other status is filtered out
before the sort ever runs.

No golden case in this file asserts "X is more important than Y" beyond what
the documented algorithm -- necessity, then gap_size, then capability_id --
actually establishes. A gap is never called "high severity," and no fabricated
business-impact number ever appears on `PrioritizedCapabilityGap`.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.api.v1.diagnosis.gap_engine import (
    STATUS_GAP,
    STATUS_NOT_REQUIRED,
    STATUS_SATISFIED,
    STATUS_UNASSESSED,
    CapabilityGap,
)
from app.api.v1.diagnosis.gap_priority import (
    PrioritizedCapabilityGap,
    prioritize_capability_gaps,
)
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.api.v1.diagnosis.target_state import TargetStateContext, resolve_requirements
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


def gap(cid, code="X", status=STATUS_GAP, required=3, current=1, gap_size=None,
        necessity="core", requirement_id=None, supporting=(1,)):
    """A CapabilityGap built directly, matching test_gap_engine.py's own
    `req`/`asmt` helper style -- these tests are about the comparison-to-
    priority step, not about re-deriving a CapabilityGap from scratch."""
    required_level = None if required is None else CapabilityLevel(required)
    current_level = None if current is None else CapabilityLevel(current)
    if gap_size is None and status == STATUS_GAP and required is not None and current is not None:
        gap_size = required - current
    return CapabilityGap(
        capability_id=cid, capability_code=code, capability_name=f"Capability {cid}",
        status=status, required_level=required_level, current_level=current_level,
        gap_size=gap_size, necessity=necessity,
        requirement_id=requirement_id or (100 + cid) if status != STATUS_NOT_REQUIRED else None,
        supporting_evidence_ids=supporting if status in (STATUS_GAP, STATUS_SATISFIED) else (),
    )


def _code_without_module_docstring(path):
    """See test_gap_engine.py's identical helper -- strips the module's own
    leading docstring so a structural guard test is not tripped by prose that
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


# =========================================================== 1-4: status filtering
def test_only_gap_status_enters_prioritization():
    """Case 1."""
    g = gap(1, status=STATUS_GAP)
    result = prioritize_capability_gaps((g,))
    assert len(result) == 1
    assert result[0].capability_id == 1


def test_unassessed_is_excluded():
    """Case 2. THE test: unknown must never be promoted into a priority."""
    g = gap(1, status=STATUS_UNASSESSED, current=None, gap_size=None)
    result = prioritize_capability_gaps((g,))
    assert result == ()


def test_satisfied_is_excluded():
    """Case 3."""
    g = gap(1, status=STATUS_SATISFIED, required=2, current=3, gap_size=None)
    result = prioritize_capability_gaps((g,))
    assert result == ()


def test_not_required_is_excluded():
    """Case 4."""
    g = gap(1, status=STATUS_NOT_REQUIRED, required=None, current=1, gap_size=None)
    result = prioritize_capability_gaps((g,))
    assert result == ()


def test_mixed_statuses_keep_only_the_gap_rows():
    gaps = (
        gap(1, status=STATUS_GAP, required=3, current=1),
        gap(2, status=STATUS_UNASSESSED, current=None, gap_size=None),
        gap(3, status=STATUS_SATISFIED, required=1, current=2, gap_size=None),
        gap(4, status=STATUS_NOT_REQUIRED, required=None, gap_size=None),
    )
    result = prioritize_capability_gaps(gaps)
    assert {p.capability_id for p in result} == {1}


# =========================================================== 5: gap_size correctness
def test_gap_size_is_carried_through_unchanged():
    """Case 5. This module never recomputes gap_size -- it reads the value
    Step 8 already produced (required_level - current_level)."""
    g = gap(1, required=3, current=1, gap_size=2)
    result = prioritize_capability_gaps((g,))
    assert result[0].gap_size == 2


# =========================================================== 6: necessity ordering
def test_core_outranks_contextual_regardless_of_gap_size():
    """Case 6. The step brief's own Case A: necessity is the PRIMARY factor.
    A small core gap still outranks a larger contextual one."""
    core_small = gap(1, code="GTM-OWN", necessity="core", required=2, current=1)       # gap_size 1
    contextual_large = gap(2, code="FIN-UNIT", necessity="contextual", required=3, current=0)  # gap_size 3
    result = prioritize_capability_gaps((core_small, contextual_large))
    assert [p.capability_code for p in result] == ["GTM-OWN", "FIN-UNIT"]


def test_within_the_same_necessity_larger_gap_size_sorts_first():
    core_1, core_3 = gap(1, necessity="core", required=2, current=1), gap(2, necessity="core", required=3, current=0)
    result = prioritize_capability_gaps((core_1, core_3))
    assert [p.capability_id for p in result] == [2, 1]


# =========================================================== 7: no fabricated signal
def test_missing_business_impact_signal_produces_no_fabricated_field():
    """Case 7 / step brief Case B. There is no business-impact field on
    PrioritizedCapabilityGap at all -- verified structurally, not just by
    absence of a particular value, so a future accidental addition is caught."""
    fields = set(PrioritizedCapabilityGap.__dataclass_fields__)
    for forbidden in ("business_impact", "impact_score", "founder_score", "severity"):
        assert forbidden not in fields


# =========================================================== 8-11: determinism
def test_ordering_is_deterministic_across_repeated_calls():
    """Case 8/9."""
    gaps = (gap(1, necessity="core", required=3, current=1), gap(2, necessity="contextual", required=2, current=0))
    first = prioritize_capability_gaps(gaps)
    second = prioritize_capability_gaps(gaps)
    assert [p.capability_id for p in first] == [p.capability_id for p in second]


def test_insertion_order_does_not_change_the_result():
    """Case 10."""
    a = gap(1, code="A", necessity="core", required=3, current=0)
    b = gap(2, code="B", necessity="core", required=3, current=1)
    c = gap(3, code="C", necessity="contextual", required=2, current=1)
    forward = prioritize_capability_gaps((a, b, c))
    backward = prioritize_capability_gaps((c, b, a))
    shuffled = prioritize_capability_gaps((b, a, c))
    codes = [p.capability_code for p in forward]
    assert [p.capability_code for p in backward] == codes
    assert [p.capability_code for p in shuffled] == codes


def test_ties_use_stable_capability_id_tie_break():
    """Case 11. Three gaps with identical necessity and gap_size -- only
    capability_id breaks the tie, ascending."""
    g30 = gap(30, necessity="core", required=3, current=1)
    g10 = gap(10, necessity="core", required=3, current=1)
    g20 = gap(20, necessity="core", required=3, current=1)
    result = prioritize_capability_gaps((g30, g10, g20))
    assert [p.capability_id for p in result] == [10, 20, 30]


# =========================================================== 12-15: no scope creep
def test_no_llm_is_imported():
    """Case 12."""
    code = _code_without_module_docstring("app/api/v1/diagnosis/gap_priority.py")
    for forbidden in ("llm", "provider", "prompt", "embedding"):
        assert forbidden not in code.lower()


def test_no_intervention_is_selected():
    """Case 13. No intervention field, and this module never even imports
    anything named InterventionCapability / intervention_capabilities."""
    fields = set(PrioritizedCapabilityGap.__dataclass_fields__)
    for forbidden in ("intervention", "intervention_id", "action"):
        assert forbidden not in fields
    code = _code_without_module_docstring("app/api/v1/diagnosis/gap_priority.py")
    assert "intervention_capabilities" not in code
    assert "InterventionCapability" not in code


def test_no_recommendation_prose_is_generated():
    """Case 14. No free-text advice field, no "you should" anywhere in the
    dataclass or the reasons it emits."""
    fields = set(PrioritizedCapabilityGap.__dataclass_fields__)
    for forbidden in ("recommendation", "advice", "next_step", "message"):
        assert forbidden not in fields
    g = gap(1, necessity="core", required=3, current=1)
    result = prioritize_capability_gaps((g,))
    for reason in result[0].priority_reasons:
        assert "should" not in reason.lower()


def test_no_roadmap_is_generated():
    """Case 15."""
    fields = set(PrioritizedCapabilityGap.__dataclass_fields__)
    for forbidden in ("roadmap", "milestone", "deadline", "task", "sequence"):
        assert forbidden not in fields


# =========================================================== 16-19: existing-system isolation
@pytest.mark.parametrize("module", [
    "app/api/v1/reasoning/engines/diagnostic.py",
    "app/api/v1/reasoning/engines/root_cause.py",
    "app/api/v1/reasoning/engines/recommendation.py",
    "app/api/v1/reasoning/engines/business_health.py",
    "app/api/v1/diagnosis/engine.py",
    "app/api/v1/diagnosis/advisor.py",
])
def test_existing_module_has_no_dependency_on_gap_priority(module):
    """Cases 16-19, structurally: diagnosis scoring, root-cause ranking,
    the recommendation engine, business health, question selection, and the
    adaptive advisor must not have grown a dependency on a module built to be
    read by something LATER, not by anything today."""
    source = open(module).read()
    assert "gap_priority" not in source
    assert "prioritize_capability_gaps" not in source
    assert "PrioritizedCapabilityGap" not in source


def test_existing_gap_engine_unchanged_by_this_step():
    """Case 16 (Gap Engine specifically): gap_priority.py imports from
    gap_engine.py, never the other way around."""
    code = _code_without_module_docstring("app/api/v1/diagnosis/gap_engine.py")
    assert "gap_priority" not in code
    assert "prioritize_capability_gaps" not in code


def test_gap_priority_reimplements_neither_upstream_resolver():
    """Structural: this module reads only CapabilityGap's own fields -- no
    specificity cascade, no evidence aggregation logic of its own."""
    code = _code_without_module_docstring("app/api/v1/diagnosis/gap_priority.py")
    for forbidden in ("specificity", "_applies(", "MIN_CONFIDENCE", "observed_level"):
        assert forbidden not in code, f"gap_priority.py reimplements {forbidden!r}"


# =========================================================== 20: founder/session isolation
def test_founder_session_isolation_is_the_callers_job_not_this_modules(db):
    """Case 20. This module takes a plain tuple of CapabilityGap and knows
    nothing about sessions or founders -- isolation is guaranteed upstream, by
    Step 8's own session-scoped `capability_gaps_for_session`, exactly as it
    already is for Step 7C. Verified here by confirming the function's only
    parameter is the gaps tuple itself (no session_id, no founder_id anywhere
    in its signature)."""
    import inspect
    sig = inspect.signature(prioritize_capability_gaps)
    assert list(sig.parameters) == ["gaps"]


# =========================================================== golden cases (section 17)
def test_case_a_priority_follows_only_the_documented_algorithm():
    """Case A. GTM-OWN (core, current=1, required=3, gap_size=2) vs FIN-UNIT
    (contextual, current=2, required=3, gap_size=1). GTM-OWN outranks
    FIN-UNIT -- but because necessity says so, not because "GTM-OWN feels more
    important." Swap the necessities and the order swaps too (proved below)."""
    gtm_own = gap(1, code="GTM-OWN", necessity="core", required=3, current=1)
    fin_unit = gap(2, code="FIN-UNIT", necessity="contextual", required=3, current=2)
    result = prioritize_capability_gaps((gtm_own, fin_unit))
    assert [p.capability_code for p in result] == ["GTM-OWN", "FIN-UNIT"]

    # Swap necessity only -- the ranking swaps too, proving the algorithm (not
    # a hardcoded opinion about which capability "matters more") drives this.
    gtm_own_ctx = gap(1, code="GTM-OWN", necessity="contextual", required=3, current=1)
    fin_unit_core = gap(2, code="FIN-UNIT", necessity="core", required=3, current=2)
    swapped = prioritize_capability_gaps((gtm_own_ctx, fin_unit_core))
    assert [p.capability_code for p in swapped] == ["FIN-UNIT", "GTM-OWN"]


def test_case_b_unavailable_business_impact_signal_fabricates_nothing():
    """Case B. Same two gaps as Case A; there is no business-impact input to
    this function at all, so there is nothing to fabricate -- verified by the
    absence of any such field (see test_missing_business_impact_signal_..)
    and by confirming ordering is unaffected by anything not in the documented
    algorithm."""
    gtm_own = gap(1, code="GTM-OWN", necessity="core", required=3, current=1)
    fin_unit = gap(2, code="FIN-UNIT", necessity="contextual", required=3, current=2)
    result = prioritize_capability_gaps((gtm_own, fin_unit))
    for p in result:
        assert not hasattr(p, "business_impact")
        assert not hasattr(p, "impact_score")


def test_case_c_three_identical_gaps_use_stable_capability_id_tiebreak():
    """Case C."""
    g100 = gap(100, necessity="core", required=3, current=1)
    g5 = gap(5, necessity="core", required=3, current=1)
    g50 = gap(50, necessity="core", required=3, current=1)
    result = prioritize_capability_gaps((g100, g5, g50))
    assert [p.capability_id for p in result] == [5, 50, 100]


def test_case_d_unassessed_alongside_a_real_gap_is_excluded():
    """Case D."""
    real_gap = gap(1, code="GTM-OWN", status=STATUS_GAP, necessity="core", required=3, current=1)
    unassessed = gap(2, code="OPS-X", status=STATUS_UNASSESSED, required=2, current=None, gap_size=None)
    result = prioritize_capability_gaps((real_gap, unassessed))
    assert [p.capability_id for p in result] == [1]


def test_case_e_gap_size_difference_is_used_but_never_labeled_severity():
    """Case E. gap_size=1 vs gap_size=3, same necessity -- the larger gap
    sorts first (the documented secondary factor), and nothing anywhere calls
    either one "high severity" or "low severity"."""
    small = gap(1, code="A", necessity="core", required=2, current=1)   # gap_size 1
    large = gap(2, code="B", necessity="core", required=3, current=0)   # gap_size 3
    result = prioritize_capability_gaps((small, large))
    assert [p.capability_code for p in result] == ["B", "A"]
    for p in result:
        for reason in p.priority_reasons:
            assert "severity" not in reason.lower()
            assert "high" not in reason.lower() and "low" not in reason.lower()
    fields = set(PrioritizedCapabilityGap.__dataclass_fields__)
    assert "severity" not in fields


# =========================================================== priority_key / reasons shape
def test_priority_key_is_a_plain_tuple_not_a_numeric_score():
    """Section 14: prefer a deterministic tuple over an arbitrary 0-100
    score. Verified structurally: there is no `priority_score` field, and
    `priority_key` is a 3-tuple of small integers, not a blended float."""
    fields = set(PrioritizedCapabilityGap.__dataclass_fields__)
    assert "priority_score" not in fields
    assert "priority_key" in fields
    g = gap(1, necessity="core", required=3, current=1)
    result = prioritize_capability_gaps((g,))
    assert isinstance(result[0].priority_key, tuple)
    assert len(result[0].priority_key) == 3
    assert all(isinstance(part, int) for part in result[0].priority_key)


def test_priority_reasons_explain_every_factor_in_the_key():
    g = gap(1, necessity="contextual", required=3, current=1)
    result = prioritize_capability_gaps((g,))
    reasons = " ".join(result[0].priority_reasons)
    assert "necessity=contextual" in reasons
    assert "gap_size=2" in reasons
    assert "capability_id=1" in reasons


def test_rank_is_one_based_and_sequential():
    a = gap(1, necessity="core", required=3, current=0)
    b = gap(2, necessity="core", required=2, current=1)
    result = prioritize_capability_gaps((a, b))
    assert [p.rank for p in result] == [1, 2]


def test_traceability_fields_pass_through_unchanged():
    g = gap(1, necessity="core", required=3, current=1, requirement_id=555, supporting=(7, 8))
    result = prioritize_capability_gaps((g,))
    assert result[0].requirement_id == 555
    assert result[0].supporting_evidence_ids == (7, 8)


def test_empty_input_produces_empty_output():
    assert prioritize_capability_gaps(()) == ()


# =========================================================== live cross-check (section 18)
def test_live_data_prioritizes_only_gap_status_from_a_real_session(db):
    """Real Step 6 requirement rows, real Step 7B/7C pipeline: record one
    confident low-level observation against a real mapped question, resolve a
    real target context, and confirm the prioritized output is a subset of
    the raw gaps restricted to status == GAP, in the algorithm's own order."""
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
        observed_level=0, confidence=0.95, evidence_text="live priority probe")

    ctx = SimpleNamespace(industry_code="saas", business_model="B2B", stage_order=5)
    target = TargetStateContext("1Cr_5Cr", "12_months")
    gaps = repo.capability_gaps_for_session(session_id, ctx, target)
    prioritized = repo.prioritized_capability_gaps_for_session(session_id, ctx, target)

    assert {p.capability_id for p in prioritized} <= {g.capability_id for g in gaps if g.status == STATUS_GAP}
    assert all(p.necessity in ("core", "contextual") for p in prioritized)
    # deterministic re-run
    again = repo.prioritized_capability_gaps_for_session(session_id, ctx, target)
    assert [p.capability_id for p in prioritized] == [p.capability_id for p in again]
