"""Step 10A: PRIORITIZED GAPS + ELIGIBLE INTERVENTIONS -> ONE 20-DAY TARGET.

THE RULES THIS FILE PROTECTS: nothing is fabricated (every action traces to a
library row, every success criterion to a Step 5 evidence criterion); a
higher-priority gap that cannot be acted on is PRESERVED, never deleted or
invented around; completing a target never upgrades a capability; and the
optional narrator is structurally incapable of changing what was selected.

The golden case reads REAL reference data end to end -- a real gap, a real
mapped intervention, real evidence criteria -- and asserts the whole chain.
"""

from dataclasses import fields
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
from app.api.v1.diagnosis.gap_intervention import select_interventions_for_gaps
from app.api.v1.diagnosis.gap_priority import (
    PrioritizedCapabilityGap,
    prioritize_capability_gaps,
)
from app.api.v1.diagnosis.repository import DiagnosisRepository
from app.api.v1.diagnosis.target_state import TargetStateContext
from app.api.v1.diagnosis.twenty_day_target import (
    HORIZON_DAYS,
    NO_ACTIONABLE_TARGET,
    TARGET_SELECTED,
    TargetNarration,
    TwentyDayTarget,
    TwentyDayTargetResult,
    build_twenty_day_target,
    narrate_target,
)
from app.db.session import engine as db_engine

ENGINE = "app/api/v1/diagnosis/twenty_day_target.py"


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


def pgap(cid, code="X", rank=1, current=1, required=3, necessity="core", evidence=(11,)):
    return PrioritizedCapabilityGap(
        capability_id=cid, capability_code=code, capability_name=f"Capability {cid}",
        current_level=CapabilityLevel(current), required_level=CapabilityLevel(required),
        gap_size=required - current, necessity=necessity,
        priority_key=(0, -(required - current), cid), priority_reasons=(), rank=rank,
        requirement_id=900 + cid, supporting_evidence_ids=evidence,
    )


def irow(intervention_id, code=None, section="Ops", stages=(5,), industries=("all",)):
    return {"intervention_id": intervention_id,
            "intervention_code": code or f"INT-{intervention_id:03d}",
            "section": section, "stage_relevance": list(stages),
            "industry_relevance": list(industries)}


DETAIL = {cid: {"capability_id": cid, "capability_code": "X",
                "capability_name": f"Outcome {cid}",
                "description": f"The described outcome for {cid}."}
          for cid in range(1, 20)}
#: Criterion text is deliberately digit-free, mirroring the real library --
#: all 136 seeded criteria are qualitative observable statements, which is
#: what `test_real_evidence_criteria_carry_no_numeric_kpi` asserts directly.
CRITERIA = {cid: [{"capability_id": cid, "criterion_id": cid * 10 + n,
                   "criterion_order": n,
                   "criterion_text": f"Observable thing {'abcd'[n - 1]}"}
                  for n in (1, 2, 3, 4)]
            for cid in range(1, 20)}
STEPS = {i: [f"Step one for {i}", f"Step two for {i}"] for i in range(1, 400)}


def build(gaps, by_capability, stage_id=5, industry_code="saas"):
    selection = select_interventions_for_gaps(
        gaps, by_capability, stage_id=stage_id, industry_code=industry_code)
    return build_twenty_day_target(gaps, selection, DETAIL, CRITERIA, STEPS)


def _code_without_module_docstring(path):
    """The file's EXECUTABLE code only -- every docstring (module, class and
    function) and every comment removed.

    Earlier steps stripped just the module docstring, which was not enough: a
    `#:` field comment or a method docstring legitimately explaining, in
    negation, what the module does NOT do ("no 30/60/90-day variant", "copied
    from capability_evidence_criteria") would otherwise trip a guard looking
    for real usage. Re-parsing and unparsing keeps identifiers and string
    literals while dropping all prose, which is exactly the distinction these
    guards are trying to draw.
    """
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


# =========================================================== 1-3: primary selection
def test_highest_priority_actionable_gap_becomes_the_target():
    """Case 1."""
    result = build([pgap(1, "A", rank=1), pgap(2, "B", rank=2)],
                   {1: [irow(10)], 2: [irow(20)]})
    assert result.status == TARGET_SELECTED
    assert result.target.primary_capability_id == 1
    assert result.skipped_gaps == ()


def test_priority_one_without_an_intervention_falls_through_to_priority_two():
    """Case 2. The step brief's own example: GTM-OWN has nothing eligible, so
    the target is built on the next actionable gap -- never fabricated."""
    result = build([pgap(1, "GTM-OWN", rank=1), pgap(2, "GTM-SALES", rank=2)],
                   {2: [irow(20)]})
    assert result.status == TARGET_SELECTED
    assert result.target.primary_capability_code == "GTM-SALES"


def test_the_skipped_higher_priority_gap_is_preserved_with_its_reason():
    """Case 3. GTM-OWN must not silently disappear."""
    result = build([pgap(1, "GTM-OWN", rank=1), pgap(2, "GTM-SALES", rank=2)],
                   {2: [irow(20)]})
    assert len(result.skipped_gaps) == 1
    skipped = result.skipped_gaps[0]
    assert skipped.capability_code == "GTM-OWN"
    assert skipped.gap_rank == 1
    assert skipped.reason == "no_mapped_intervention"


def test_a_skipped_gap_filtered_by_eligibility_records_the_excluded_ids():
    result = build([pgap(1, "A", rank=1), pgap(2, "B", rank=2)],
                   {1: [irow(10, stages=(7,))], 2: [irow(20, stages=(2,))]}, stage_id=2)
    assert result.target.primary_capability_id == 2
    assert result.skipped_gaps[0].reason == "all_candidates_filtered"
    assert result.skipped_gaps[0].excluded_intervention_ids == (10,)


def test_lower_priority_gaps_after_the_selected_one_are_not_listed_as_skipped():
    """Only gaps that OUTRANKED the target were passed over. Everything below
    it simply was not reached -- 20 days holds one target."""
    result = build([pgap(1, "A", rank=1), pgap(2, "B", rank=2)],
                   {1: [irow(10)], 2: [irow(20)]})
    assert [s.capability_code for s in result.skipped_gaps] == []


# =========================================================== 4-7: only GAP rows
def _raw(cid, status):
    return CapabilityGap(
        capability_id=cid, capability_code="X", capability_name="X", status=status,
        required_level=CapabilityLevel(3),
        current_level=None if status == STATUS_UNASSESSED else CapabilityLevel(3),
        gap_size=None,
        necessity="core" if status != STATUS_NOT_REQUIRED else None,
        requirement_id=None if status == STATUS_NOT_REQUIRED else 1,
    )


@pytest.mark.parametrize("status", [STATUS_UNASSESSED, STATUS_SATISFIED, STATUS_NOT_REQUIRED])
def test_non_gap_statuses_can_never_become_a_target(status):
    """Cases 4, 5, 6, 7. Composed through the real Step 9A filter."""
    prioritized = prioritize_capability_gaps((_raw(1, status),))
    assert prioritized == ()
    result = build(prioritized, {1: [irow(10)]})
    assert result.status == NO_ACTIONABLE_TARGET
    assert result.target is None


def test_only_gap_rows_reach_the_engine_at_all():
    """Case 4, positively: a GAP alongside the other three yields exactly one
    considered gap."""
    raw = (_raw(1, STATUS_GAP_WITH := STATUS_UNASSESSED), )
    assert raw  # keeps the parametrized cases above honest about what varies
    gap = CapabilityGap(
        capability_id=1, capability_code="A", capability_name="A", status=STATUS_GAP,
        required_level=CapabilityLevel(3), current_level=CapabilityLevel(1),
        gap_size=2, necessity="core", requirement_id=1)
    prioritized = prioritize_capability_gaps((gap, _raw(2, STATUS_SATISFIED),
                                              _raw(3, STATUS_UNASSESSED),
                                              _raw(4, STATUS_NOT_REQUIRED)))
    result = build(prioritized, {1: [irow(10)]})
    assert result.considered_gap_count == 1
    assert result.target.primary_capability_id == 1


# =========================================================== 8-9: nothing fabricated
def test_a_gap_with_no_intervention_produces_no_target_and_no_invented_action():
    """Case 8."""
    result = build([pgap(1, "A", rank=1)], {})
    assert result.status == NO_ACTIONABLE_TARGET
    assert result.target is None


def test_no_actionable_gaps_returns_the_structured_no_target_state():
    """Case 9. Section 14: gaps considered, and why nothing was available."""
    result = build([pgap(1, "A", rank=1), pgap(2, "B", rank=2)], {})
    assert result.status == NO_ACTIONABLE_TARGET
    assert result.considered_gap_count == 2
    assert [s.capability_code for s in result.skipped_gaps] == ["A", "B"]
    assert all(s.reason == "no_mapped_intervention" for s in result.skipped_gaps)


# =========================================================== 10-15: context preserved
def test_selected_intervention_is_preserved():
    """Case 10."""
    result = build([pgap(1, "A")], {1: [irow(42, code="INT-042", section="Sales")]})
    assert result.target.source_intervention_id == 42
    assert result.target.source_intervention_code == "INT-042"
    assert result.target.source_section == "Sales"


def test_primary_capability_is_preserved():
    """Case 11."""
    result = build([pgap(7, "FIN-UNIT")], {7: [irow(10)]})
    assert result.target.primary_capability_id == 7
    assert result.target.primary_capability_code == "FIN-UNIT"


def test_gap_size_necessity_and_levels_are_preserved():
    """Cases 12, 13, 14, 15."""
    result = build([pgap(1, "A", current=1, required=3, necessity="contextual")],
                   {1: [irow(10)]})
    target = result.target
    assert target.gap_size == 2
    assert target.necessity == "contextual"
    assert target.current_level == CapabilityLevel(1)
    assert target.required_level == CapabilityLevel(3)


# =========================================================== 16-18: the horizon
def test_the_horizon_is_exactly_twenty_days():
    """Case 16."""
    assert HORIZON_DAYS == 20
    result = build([pgap(1, "A")], {1: [irow(10)]})
    assert result.target.horizon_days == 20


def test_no_ninety_day_or_multi_year_output_exists():
    """Cases 17, 18. Structural: no other horizon is representable."""
    code = _code_without_module_docstring(ENGINE)
    for forbidden in ("90", "ninety", "roadmap", "milestone", "3_year", "three_year",
                      "year", "quarter", "month"):
        assert forbidden not in code.lower(), f"twenty_day_target.py mentions {forbidden!r}"
    target_fields = set(TwentyDayTarget.__dataclass_fields__)
    for forbidden in ("roadmap", "milestones", "phases", "quarters", "direction",
                      "strategic_direction", "deadline", "due_date"):
        assert forbidden not in target_fields


def test_the_horizon_is_not_configurable():
    """Section 7: fixed, because no plan object in this codebase carries a
    duration field for it to follow."""
    horizon = TwentyDayTarget.__dataclass_fields__["horizon_days"]
    assert horizon.default == 20
    code = _code_without_module_docstring(ENGINE)
    assert "settings." not in code, "the horizon must not come from configuration"


# =========================================================== 19: no billing
def test_no_plan_or_price_logic_lives_in_the_engine():
    """Case 19. Entitlement is a router concern in this codebase."""
    code = _code_without_module_docstring(ENGINE)
    for forbidden in ("199", "499", "999", "plan_tier", "plantier", "entitlement",
                      "subscription", "feature.", "price", "billing", "tier"):
        assert forbidden not in code.lower(), f"engine references {forbidden!r}"


# =========================================================== 20-21: determinism
def test_target_selection_is_deterministic():
    """Case 20."""
    gaps = [pgap(1, "A", rank=1), pgap(2, "B", rank=2)]
    rows = {1: [irow(10)], 2: [irow(20)]}
    first, second = build(gaps, rows), build(gaps, rows)
    assert first.target.primary_capability_id == second.target.primary_capability_id
    assert first.target.source_intervention_id == second.target.source_intervention_id


def test_insertion_order_cannot_change_the_selected_target():
    """Case 21. Rank decides, not the order the gaps arrived in."""
    a, b, c = pgap(1, "A", rank=3), pgap(2, "B", rank=1), pgap(3, "C", rank=2)
    rows = {1: [irow(10)], 2: [irow(20)], 3: [irow(30)]}
    for ordering in ((a, b, c), (c, b, a), (b, a, c)):
        result = build(list(ordering), rows)
        assert result.target.primary_capability_code == "B"


def test_several_interventions_for_one_capability_pick_a_stable_one():
    """No new ordering signal is invented: Step 9B's existing order decides."""
    rows = {1: [irow(30), irow(10), irow(20)]}
    assert build([pgap(1, "A")], rows).target.source_intervention_id == 10


# =========================================================== 22-23: multi-capability
def test_a_multi_capability_intervention_retains_both_supporting_capabilities():
    """Case 22. Section 15: the real relationship is kept, with ONE primary."""
    shared = irow(60)
    result = build([pgap(1, "A", rank=1), pgap(2, "B", rank=2)],
                   {1: [shared], 2: [shared]})
    target = result.target
    assert target.primary_capability_id == 1               # one primary rationale
    assert set(target.supporting_capability_ids) == {1, 2}
    assert target.is_joint


def test_unrelated_gaps_are_never_bundled_into_one_target():
    """Case 23. Two gaps served by two DIFFERENT interventions yield a target
    on one of them only -- breadth is never manufactured."""
    result = build([pgap(1, "A", rank=1), pgap(2, "B", rank=2)],
                   {1: [irow(10)], 2: [irow(20)]})
    target = result.target
    assert target.supporting_capability_ids == (1,)
    assert not target.is_joint
    assert target.source_intervention_id == 10


# =========================================================== 24-27: no mutation
def test_the_engine_cannot_mutate_a_capability_assessment():
    """Cases 24, 25. Completion is not evidence: there is no writable path
    from this module to current_level or capability_evidence."""
    code = _code_without_module_docstring(ENGINE)
    for forbidden in ("capability_evidence", "record_capability_evidence",
                      "assess_capabilit", "current_level =", "insert", "update ",
                      "delete", "commit", "flush", "execute("):
        assert forbidden not in code.lower(), f"engine may write: {forbidden!r}"


def test_the_engine_creates_no_gap_and_no_intervention():
    """Cases 26, 27. It consumes Step 8/9A/9B output; it never constructs one."""
    code = _code_without_module_docstring(ENGINE)
    for forbidden in ("CapabilityGap(", "compute_capability_gaps",
                      "InterventionCandidate(", "prioritize_capability_gaps"):
        assert forbidden not in code


def test_building_a_target_leaves_the_input_gap_untouched():
    """Case 24, behaviourally: the frozen input is not rewritten in place."""
    gap = pgap(1, "A", current=1, required=3)
    build([gap], {1: [irow(10)]})
    assert gap.current_level == CapabilityLevel(1)
    assert gap.rank == 1


# =========================================================== 28-30: traceability
def test_the_source_intervention_gap_and_evidence_are_all_traceable():
    """Cases 28, 29, 30. Target -> Intervention -> Gap -> Assessment -> Evidence,
    and Target -> Gap -> Target Requirement."""
    result = build([pgap(3, "A", rank=1, evidence=(77, 78))], {3: [irow(42)]})
    target = result.target
    assert target.source_intervention_id == 42                  # -> intervention
    assert target.primary_capability_id == 3 and target.gap_rank == 1   # -> gap
    assert target.supporting_evidence_ids == (77, 78)           # -> evidence
    assert target.requirement_id == 903                         # -> requirement


# =========================================================== 31: no invented KPI
def test_success_criteria_contain_no_fabricated_numeric_kpi():
    """Case 31. Criteria are Step 5's observable statements, copied verbatim --
    there is no path by which a number could be introduced here."""
    result = build([pgap(1, "A")], {1: [irow(10)]})
    for criterion in result.target.success_criteria:
        assert not any(ch.isdigit() for ch in criterion.criterion_text)
    code = _code_without_module_docstring(ENGINE)
    for forbidden in ("%", "increase", "revenue by", "kpi", "target_metric"):
        assert forbidden not in code.lower()


def test_real_evidence_criteria_carry_no_numeric_kpi(db):
    """Case 31, against the whole library: all 136 seeded criteria are
    qualitative observable statements, so a target built from them cannot
    promise "increase revenue by 30%" even in principle. If a numeric
    criterion is ever authored, this fails and the promise semantics get
    revisited deliberately."""
    numeric = db.execute(text(
        "SELECT criterion_id, criterion_text FROM capability_evidence_criteria"
        " WHERE criterion_text ~ '[0-9]'")).all()
    assert not numeric, f"numeric evidence criteria appeared: {numeric}"


def test_success_criteria_are_the_step_5_evidence_criteria_not_a_second_taxonomy():
    """Section 10: criterion_ids are carried so the NEXT diagnosis's Step 7B
    extractor can cite the same criteria. One vocabulary, not two."""
    result = build([pgap(1, "A")], {1: [irow(10)]})
    criteria = result.target.success_criteria
    assert [c.criterion_id for c in criteria] == [11, 12, 13, 14]
    assert [c.criterion_order for c in criteria] == [1, 2, 3, 4]


def test_every_action_is_copied_from_the_selected_intervention():
    """Section 13: no generic startup advice can appear -- each action is a
    library step, tagged with the intervention it came from."""
    result = build([pgap(1, "A")], {1: [irow(42)]})
    assert [a.action for a in result.target.actions] == STEPS[42]
    assert all(a.source_intervention_id == 42 for a in result.target.actions)
    assert [a.sequence for a in result.target.actions] == [1, 2]


def test_the_outcome_is_read_off_the_capability_not_the_intervention():
    """Section 8: target and action stay separate concepts."""
    result = build([pgap(5, "A")], {5: [irow(10, section="Sales Execution")]})
    target = result.target
    assert target.primary_capability_name == "Outcome 5"
    assert target.target_outcome == "The described outcome for 5."
    assert target.source_section == "Sales Execution"     # the means, kept apart


# =========================================================== 32-34: the narrator
class _Rewriter:
    """A narrator that tries to change everything it can reach."""

    def narrate(self, target):
        return TargetNarration(focus="different focus", why_now="different reason",
                               actions=tuple(f"rewritten {i}" for i in
                                             range(len(target.actions))),
                               success="different success")


class _Exploder:
    def narrate(self, target):
        raise RuntimeError("provider down")


class _DropsActions:
    def narrate(self, target):
        return TargetNarration(focus="f", why_now="w", actions=("only one",), success="s")


def test_the_narrator_cannot_change_the_selected_capability_or_intervention():
    """Cases 32, 33. Structural: TargetNarration carries no identifier at all,
    so there is nothing in it capable of redirecting the target."""
    narration_fields = {f.name for f in fields(TargetNarration)}
    for forbidden in ("capability_id", "intervention_id", "criterion_id",
                      "current_level", "required_level", "gap_size", "rank"):
        assert forbidden not in narration_fields

    result = build([pgap(1, "A")], {1: [irow(42)]})
    narrated = narrate_target(result, _Rewriter())
    assert narrated.target.primary_capability_id == 1
    assert narrated.target.source_intervention_id == 42
    assert narrated.target.current_level == result.target.current_level
    assert narrated.target.required_level == result.target.required_level
    assert [a.action for a in narrated.target.actions] == STEPS[42]   # untouched
    assert narrated.target.narration.focus == "different focus"        # wording only


def test_narrator_failure_leaves_the_structured_target_intact():
    """Case 34."""
    result = build([pgap(1, "A")], {1: [irow(42)]})
    narrated = narrate_target(result, _Exploder())
    assert narrated.target == result.target
    assert narrated.target.narration is None


def test_a_narrator_that_drops_actions_is_discarded():
    """A narrator changing the action count is rewriting the intervention,
    which is Layer A's decision and not its to make."""
    result = build([pgap(1, "A")], {1: [irow(42)]})
    narrated = narrate_target(result, _DropsActions())
    assert narrated.target.narration is None
    assert len(narrated.target.actions) == 2


def test_no_narrator_is_the_default_and_the_target_is_already_usable():
    """Layer A alone produces a complete target -- generation is optional."""
    result = build([pgap(1, "A")], {1: [irow(42)]})
    assert narrate_target(result, None) is result
    assert result.target.narration is None
    assert result.target.actions and result.target.success_criteria
    assert result.target.target_outcome


def test_narration_of_a_no_actionable_target_is_a_no_op():
    result = build([pgap(1, "A")], {})
    assert narrate_target(result, _Rewriter()) is result


# =========================================================== 35: no writes
def test_the_engine_module_has_no_database_access(db):
    """Case 35. Inspection established no persistence requirement, so this is
    a pure read model like Steps 7C, 8, 9A and 9B."""
    code = _code_without_module_docstring(ENGINE)
    for forbidden in ("session", "sqlalchemy", "self.db", "text("):
        assert forbidden not in code.lower()


def test_building_a_target_writes_nothing(db):
    """Case 35, live."""
    repo = DiagnosisRepository(db)
    before = {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar()
              for t in ("capability_evidence", "interventions",
                        "capability_evidence_criteria", "capabilities")}
    session_id = db.execute(text("SELECT session_id FROM sessions LIMIT 1")).scalar()
    if session_id is None:
        pytest.skip("no session")
    ctx = SimpleNamespace(industry_code="saas", business_model="B2B", stage_order=5)
    repo.twenty_day_target_for_session(session_id, ctx, TargetStateContext(None, None))
    after = {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in before}
    assert before == after


# =========================================================== 36-39: isolation
@pytest.mark.parametrize("module", [
    "app/api/v1/reasoning/engines/diagnostic.py",
    "app/api/v1/reasoning/engines/root_cause.py",
    "app/api/v1/reasoning/engines/recommendation.py",
    "app/api/v1/reasoning/reporting/generator.py",
    "app/api/v1/reports/generator.py",
    "app/api/v1/diagnosis/engine.py",
    "app/api/v1/diagnosis/advisor.py",
    "app/api/v1/diagnosis/gap_engine.py",
    "app/api/v1/diagnosis/gap_priority.py",
    "app/api/v1/diagnosis/gap_intervention.py",
])
def test_existing_module_has_no_dependency_on_the_target_engine(module):
    """Cases 36-39: the existing diagnosis, Step 8, Step 9A and Step 9B are all
    unchanged, and no report generator was touched. The dependency runs one
    way only."""
    source = open(module).read()
    for forbidden in ("twenty_day_target", "TwentyDayTarget", "build_twenty_day_target"):
        assert forbidden not in source


def test_the_engine_consumes_step_9a_and_9b_without_reimplementing_them():
    code = _code_without_module_docstring(ENGINE)
    assert "PrioritizedCapabilityGap" in code
    assert "GapInterventionSelection" in code
    for reimplemented in ("necessity_rank", "is_relevant", "stage_relevance",
                          "industry_relevance", "required_level -"):
        assert reimplemented not in code


# =========================================================== golden case (section 20)
def test_golden_case_full_trace_on_real_reference_data(db, capsys):
    """Section 20. A real gap, a real mapped intervention, real evidence
    criteria -- and the brief's own fallback scenario: GTM-OWN outranks
    GTM-SALES but its only two interventions are stage-restricted, so an
    early-stage founder's target is built on GTM-SALES while GTM-OWN is kept
    on the record."""
    repo = DiagnosisRepository(db)
    def cap(code):
        return db.execute(text(
            "SELECT capability_id FROM capabilities WHERE capability_code = :c"),
            {"c": code}).scalar()
    gtm_own, gtm_sales = cap("GTM-OWN"), cap("GTM-SALES")

    gaps = [pgap(gtm_own, "GTM-OWN", rank=1, current=1, required=3),
            pgap(gtm_sales, "GTM-SALES", rank=2, current=1, required=3)]
    ids = (gtm_own, gtm_sales)
    selection = select_interventions_for_gaps(
        gaps, repo.interventions_for_capabilities(ids),
        stage_id=3, industry_code="saas")
    result = build_twenty_day_target(
        gaps, selection, repo.capability_detail(ids), repo.capability_criteria(ids),
        repo.intervention_steps([c.intervention_id for c in selection.candidates]))

    assert result.status == TARGET_SELECTED
    target = result.target

    # The skipped higher-priority gap is on the record, with its real reason.
    assert [s.capability_code for s in result.skipped_gaps] == ["GTM-OWN"]
    assert result.skipped_gaps[0].gap_rank == 1
    assert result.skipped_gaps[0].excluded_intervention_ids

    # The outcome is the real capability, in the library's own words.
    assert target.primary_capability_code == "GTM-SALES"
    assert target.primary_capability_name == "Repeatable Sales System"
    assert target.target_outcome == (
        "A defined, teachable sales process rather than a series of improvisations.")
    assert target.horizon_days == 20

    # The intervention and its steps are real and copied verbatim.
    real_steps = repo.intervention_steps([target.source_intervention_id])[
        target.source_intervention_id]
    assert [a.action for a in target.actions] == real_steps
    assert target.source_intervention_id in {
        r[0] for r in db.execute(text(
            "SELECT intervention_id FROM intervention_capabilities"
            " WHERE capability_id = :c"), {"c": gtm_sales}).all()}

    # Success criteria are the real Step 5 criteria for this capability.
    real_criteria = db.execute(text(
        "SELECT criterion_id, criterion_text FROM capability_evidence_criteria"
        " WHERE capability_id = :c ORDER BY criterion_order"), {"c": gtm_sales}).all()
    assert [c.criterion_id for c in target.success_criteria] == [r[0] for r in real_criteria]
    assert [c.criterion_text for c in target.success_criteria] == [r[1] for r in real_criteria]
    assert len(target.success_criteria) == 4

    with capsys.disabled():
        print(f"\n    20-DAY TARGET ({target.horizon_days} days)")
        print(f"    focus     : {target.primary_capability_name}")
        print(f"    outcome   : {target.target_outcome}")
        print(f"    level     : {int(target.current_level)} -> "
              f"{int(target.required_level)} ({target.necessity}, gap {target.gap_size})")
        print(f"    via       : {target.source_intervention_code} / {target.source_section}")
        for action in target.actions:
            print(f"      {action.sequence}. {action.action}")
        print("    success   :")
        for criterion in target.success_criteria:
            print(f"      [{criterion.criterion_id}] {criterion.criterion_text}")
        print(f"    skipped   : {[(s.capability_code, s.reason) for s in result.skipped_gaps]}")


def test_live_end_to_end_through_the_repository(db):
    """The whole composed pipeline: Steps 6, 7B, 7C, 8, 9A, 9B, 10A."""
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
        observed_level=0, confidence=0.95, evidence_text="live 10A probe")

    ctx = SimpleNamespace(industry_code="saas", business_model="B2B", stage_order=5)
    target_ctx = TargetStateContext("1Cr_5Cr", "12_months")
    result = repo.twenty_day_target_for_session(session_id, ctx, target_ctx)
    assert isinstance(result, TwentyDayTargetResult)
    assert result.status in (TARGET_SELECTED, NO_ACTIONABLE_TARGET)

    if result.has_target:
        target = result.target
        gaps = repo.prioritized_capability_gaps_for_session(session_id, ctx, target_ctx)
        assert target.primary_capability_id in {g.capability_id for g in gaps}
        assert target.horizon_days == 20
        assert target.actions, "a selected target must carry real library actions"

    again = repo.twenty_day_target_for_session(session_id, ctx, target_ctx)
    assert again.status == result.status
    if result.has_target:
        assert again.target.source_intervention_id == result.target.source_intervention_id
