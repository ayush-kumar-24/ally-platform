"""Step 7A: the question -> capability bridge. Mapping data only.

THIS STEP ADDS NO BEHAVIOUR. `question_capabilities` is read by nothing: no
capability is scored, no gap is computed, no intervention is chosen, and
question selection is untouched. So the tests that matter most are the ones
asserting what is STILL ABSENT -- `test_no_capability_score_is_computed_yet`,
`test_question_selection_does_not_read_the_mapping` -- because a mapping that
quietly started influencing the diagnosis would be the worst outcome of this
step, not the best.

The second group guards the curation itself. A false mapping contaminates every
future capability assessment, and it does so invisibly: the founder simply gets
told something about a capability nobody actually asked them about. Hence
`test_no_rejected_problem_leaked_into_the_mapping` and
`test_every_mapped_question_belongs_to_a_high_confidence_problem`.
"""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import engine as db_engine

MIGRATION = (Path(__file__).resolve().parents[1] / "alembic" / "versions"
             / "2026_09_19_1600-c5e7b1a94f60_question_capability_mapping.py")


def _curation():
    """The migration's own curation lists, loaded as data."""
    spec = importlib.util.spec_from_file_location("qc_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def curation():
    return _curation()


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


# =========================================================== 1-4: integrity
def test_every_mapping_references_a_real_question_and_capability(db):
    """Case 4, from both directions. FKs enforce it; this proves they are on."""
    bad = db.execute(text(
        "SELECT count(*) FROM question_capabilities qc"
        "  LEFT JOIN questions q ON q.question_id = qc.question_id"
        "  LEFT JOIN capabilities c ON c.capability_id = qc.capability_id"
        " WHERE q.question_id IS NULL OR c.capability_id IS NULL")).scalar()
    assert bad == 0


def test_an_invalid_capability_id_is_rejected(db):
    question_id = db.execute(text("SELECT question_id FROM questions LIMIT 1")).scalar()
    with pytest.raises(Exception):
        db.execute(text("INSERT INTO question_capabilities (question_id, capability_id)"
                        " VALUES (:q, 999999)"), {"q": question_id})
        db.flush()


def test_duplicate_mappings_are_impossible(db):
    """Case 3, enforced by the composite primary key rather than by convention."""
    row = db.execute(text(
        "SELECT question_id, capability_id FROM question_capabilities LIMIT 1")).first()
    assert row is not None, "nothing seeded"
    with pytest.raises(Exception):
        db.execute(text("INSERT INTO question_capabilities (question_id, capability_id)"
                        " VALUES (:q, :c)"), {"q": row[0], "c": row[1]})
        db.flush()


def test_a_question_may_have_zero_mappings(db):
    """Case 2. 1,874 of 3,340 do, and that is the designed outcome."""
    unmapped = db.execute(text(
        "SELECT count(*) FROM questions q"
        "  LEFT JOIN question_capabilities qc ON qc.question_id = q.question_id"
        " WHERE qc.question_id IS NULL")).scalar()
    assert unmapped > 0, (
        "every question being mapped would mean the curation forced matches"
    )


# =========================================================== the curation held
def test_no_rejected_problem_leaked_into_the_mapping(db, curation):
    """A trait is not a capability. 20 problems map to nothing, on purpose."""
    leaked = db.execute(text(
        "SELECT DISTINCT p.problem_code FROM question_capabilities qc"
        "  JOIN questions q ON q.question_id = qc.question_id"
        "  JOIN problems p ON p.problem_id = q.problem_id"
        " WHERE p.problem_code = ANY(:codes)"), {"codes": curation.REJECTED}).all()
    assert leaked == [], f"rejected problems were mapped: {leaked}"


def test_no_medium_problem_was_seeded(db, curation):
    """MEDIUM is reported for review, never inserted. A false mapping
    contaminates every future capability assessment, invisibly."""
    codes = [p for p, _cap in curation.MEDIUM_FOR_REVIEW]
    leaked = db.execute(text(
        "SELECT DISTINCT p.problem_code FROM question_capabilities qc"
        "  JOIN questions q ON q.question_id = qc.question_id"
        "  JOIN problems p ON p.problem_id = q.problem_id"
        " WHERE p.problem_code = ANY(:codes)"), {"codes": codes}).all()
    assert leaked == [], f"MEDIUM problems were seeded: {leaked}"


def test_every_mapped_question_belongs_to_a_high_confidence_problem(db, curation):
    allowed = {p for p, _c in curation.HIGH_CONFIDENCE}
    actual = {p for (p,) in db.execute(text(
        "SELECT DISTINCT p.problem_code FROM question_capabilities qc"
        "  JOIN questions q ON q.question_id = qc.question_id"
        "  JOIN problems p ON p.problem_id = q.problem_id")).all()}
    assert actual <= allowed


def test_the_three_confidence_sets_are_disjoint_and_complete(db, curation):
    high = {p for p, _c in curation.HIGH_CONFIDENCE}
    med = {p for p, _c in curation.MEDIUM_FOR_REVIEW}
    rej = set(curation.REJECTED)
    assert not (high & med) and not (high & rej) and not (med & rej)
    live = {p for (p,) in db.execute(text(
        "SELECT DISTINCT p.problem_code FROM problems p"
        "  JOIN questions q ON q.problem_id = p.problem_id")).all()}
    assert live == high | med | rej, (
        "every problem carrying questions must have an explicit verdict; "
        f"unjudged: {sorted(live - (high | med | rej))}"
    )


def test_no_question_maps_to_more_than_one_capability(db):
    """One strong mapping beats several speculative ones (step brief s6)."""
    multi = db.execute(text(
        "SELECT count(*) FROM (SELECT question_id FROM question_capabilities"
        "  GROUP BY question_id HAVING count(*) > 1) t")).scalar()
    assert multi == 0


# =========================================================== 5-8: no regressions
def test_question_selection_does_not_read_the_mapping():
    """Case 5. The engine must not have grown a capability axis in this step."""
    for module in ("app/api/v1/diagnosis/engine.py",
                   "app/api/v1/diagnosis/repository.py",
                   "app/api/v1/diagnosis/service.py",
                   "app/api/v1/diagnosis/advisor.py"):
        source = open(module).read()
        assert "question_capabilities" not in source, (
            f"{module} reads the mapping; Step 7A adds data, not behaviour"
        )


def test_industry_eligibility_is_untouched_by_mapping(db):
    """Case 7. A mapped question keeps exactly the industry_relevance it had."""
    rows = db.execute(text(
        "SELECT count(*) FROM question_capabilities qc"
        "  JOIN questions q ON q.question_id = qc.question_id"
        " WHERE q.industry_relevance IS NULL")).scalar()
    assert rows == 0, "mapping must not have disturbed industry_relevance"


def test_a_universal_question_is_mapped_once_not_once_per_industry(db):
    """Case 8. The mapping is per question, not per (question, industry)."""
    universal = db.execute(text(
        "SELECT qc.question_id, count(*) FROM question_capabilities qc"
        "  JOIN questions q ON q.question_id = qc.question_id"
        " WHERE q.industry_relevance = '[\"all\"]'::jsonb"
        " GROUP BY qc.question_id HAVING count(*) > 1")).all()
    assert universal == []


def test_the_mapping_table_has_no_industry_or_stage_column(db):
    # Those axes belong to the question, and duplicating them here is how two
    # sources of truth start disagreeing.
    cols = {c for (c,) in db.execute(text(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name = 'question_capabilities'")).all()}
    assert cols == {"question_id", "capability_id", "created_at"}


# =========================================================== 9-12: still absent
def test_no_capability_score_is_computed_yet(db):
    """Cases 10 and 11. Evidence and gaps are Steps 7B and 8."""
    present = {t for (t,) in db.execute(text(
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema = 'public'")).all()}
    for premature in ("capability_evidence", "capability_assessments",
                      "detected_gaps", "capability_scores"):
        assert premature not in present, f"{premature} belongs to a later step"


def test_no_module_derives_evidence_from_the_mapping():
    """Case 1, structurally: nothing can turn an answer into capability evidence
    yet, because no code reads the table at all."""
    import subprocess
    hits = subprocess.run(
        ["grep", "-rl", "--include=*.py", "question_capabilities", "app/"],
        capture_output=True, text=True).stdout.split()
    assert hits == ["app/models/capability.py"], (
        f"only the ORM model may reference the mapping in Step 7A; found {hits}"
    )


def test_the_mapping_is_read_only_reference_data(db):
    """Case 9. Seeded by migration and dumped like the question bank; no
    application code writes it."""
    import subprocess
    writes = subprocess.run(
        ["grep", "-rn", "INSERT INTO question_capabilities", "app/"],
        capture_output=True, text=True).stdout
    assert writes == "", f"application code writes the mapping: {writes}"


# =========================================================== coverage reporting
def test_coverage_is_reported(db, capsys):
    total = db.execute(text("SELECT count(*) FROM questions")).scalar()
    mapped = db.execute(text(
        "SELECT count(DISTINCT question_id) FROM question_capabilities")).scalar()
    zero = [c for (c,) in db.execute(text(
        "SELECT c.capability_code FROM capabilities c"
        "  LEFT JOIN question_capabilities qc ON qc.capability_id = c.capability_id"
        " GROUP BY c.capability_code HAVING count(qc.question_id) = 0"
        " ORDER BY c.capability_code")).all()]
    with capsys.disabled():
        print(f"\n    question->capability: {mapped}/{total} mapped "
              f"({mapped / total:.0%}), {len(zero)} capabilities with no questions")
        if zero:
            print(f"    no coverage: {', '.join(zero)}")


def test_capabilities_without_questions_are_known_and_few(db):
    """A capability nobody can ask about can never be assessed, so it can never
    be a gap. Four of 34 are in that state and each is recorded in
    backend/docs/QUESTION-CAPABILITY-MAPPING.md."""
    zero = {c for (c,) in db.execute(text(
        "SELECT c.capability_code FROM capabilities c"
        "  LEFT JOIN question_capabilities qc ON qc.capability_id = c.capability_id"
        " GROUP BY c.capability_code HAVING count(qc.question_id) = 0")).all()}
    assert zero == {"FND-TIME", "OPS-TOOLING", "PRD-DELIVERY", "PRD-ROADMAP"}, (
        f"the set of unaskable capabilities changed: {sorted(zero)}. Update the "
        "doc and this test together, or the gap silently stops being tracked."
    )
