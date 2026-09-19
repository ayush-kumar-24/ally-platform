"""Step 5: the capability taxonomy -- the shared semantic layer.

WHAT THESE TESTS ARE DEFENDING is the taxonomy's usefulness as a JOIN, not its
contents. A capability is only worth having if a question, a target requirement
and an intervention can all point at the same row. So the structural tests
(unique codes, real foreign keys, no duplicate mappings) matter more than any
particular capability name, and the ones that would catch the taxonomy going
wrong are:

  test_no_capability_exists_only_because_an_intervention_has_a_label
      the failure mode of deriving a taxonomy from 390 free-text labels.
  test_the_taxonomy_is_industry_neutral
      the failure mode of a SaaS Sales Capability beside an Agri Sales
      Capability, which would move contextualisation into the wrong table.
  test_unassessed_cannot_be_compared_with_a_level
      the failure mode the whole Future-State design turns on: a founder told a
      capability is missing when nobody ever asked them about it.

Counts are reported, not pinned, wherever a legitimate curation pass would
change them.
"""

import re

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.diagnosis.capability_levels import (
    UNASSESSED,
    CapabilityLevel,
    is_assessed,
)
from app.db.session import engine as db_engine
from app.models import Capability, CapabilityDomain


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


# =========================================================== 1-3: the taxonomy
def test_capability_codes_are_unique(db):
    codes = [c for (c,) in db.execute(text("SELECT capability_code FROM capabilities")).all()]
    assert codes, "the taxonomy is empty"
    assert len(codes) == len(set(codes))


def test_capability_codes_follow_one_convention(db):
    # DOMAIN-SLUG, uppercase. A code is the stable identifier a migration, a
    # curation spreadsheet and a report all write by hand.
    for (code,) in db.execute(text("SELECT capability_code FROM capabilities")).all():
        assert re.fullmatch(r"[A-Z]{3,4}-[A-Z]+", code), code


def test_domain_codes_are_unique_and_ordered(db):
    rows = db.execute(text(
        "SELECT domain_code, domain_order FROM capability_domains ORDER BY domain_order")).all()
    codes = [r[0] for r in rows]
    orders = [r[1] for r in rows]
    assert len(codes) == len(set(codes))
    assert orders == sorted(orders)
    assert len(set(orders)) == len(orders), "domain_order must be unambiguous"


def test_every_capability_belongs_to_a_real_domain(db):
    orphans = db.execute(text(
        "SELECT c.capability_code FROM capabilities c"
        "  LEFT JOIN capability_domains d ON d.domain_id = c.domain_id"
        " WHERE d.domain_id IS NULL")).all()
    assert orphans == []


def test_every_domain_has_capabilities(db):
    empty = db.execute(text(
        "SELECT d.domain_code FROM capability_domains d"
        "  LEFT JOIN capabilities c ON c.domain_id = d.domain_id"
        " GROUP BY d.domain_code HAVING count(c.capability_id) = 0")).all()
    assert empty == [], f"domains with no capabilities: {empty}"


def test_pillar_references_are_real_or_null(db):
    # Contextual metadata: nullable, but never dangling.
    bad = db.execute(text(
        "SELECT c.capability_code FROM capabilities c"
        "  LEFT JOIN readiness_pillars p ON p.pillar_id = c.pillar_id"
        " WHERE c.pillar_id IS NOT NULL AND p.pillar_id IS NULL")).all()
    assert bad == []


def test_every_capability_has_evidence_criteria(db):
    """A capability nobody can observe cannot be assessed, so it cannot be required."""
    bare = db.execute(text(
        "SELECT c.capability_code FROM capabilities c"
        "  LEFT JOIN capability_evidence_criteria e ON e.capability_id = c.capability_id"
        " GROUP BY c.capability_code HAVING count(e.criterion_id) = 0")).all()
    assert bare == [], f"capabilities with no evidence criteria: {bare}"


def test_criteria_are_statements_not_advice(db):
    """Criteria describe the business; they never tell the founder what to do.

    A criterion that reads as an instruction has become an intervention, and the
    taxonomy would be doing two jobs.
    """
    imperatives = ("you should", "you must", "start ", "build a ", "create a ",
                   "implement ", "consider ")
    rows = db.execute(text("SELECT criterion_text FROM capability_evidence_criteria")).all()
    offenders = [t for (t,) in rows if any(t.lower().startswith(i) for i in imperatives)]
    assert offenders == [], offenders


# =========================================================== 4-7: the mappings
def test_intervention_mappings_reference_real_rows(db):
    bad = db.execute(text(
        "SELECT count(*) FROM intervention_capabilities ic"
        "  LEFT JOIN capabilities c ON c.capability_id = ic.capability_id"
        "  LEFT JOIN interventions i ON i.intervention_id = ic.intervention_id"
        " WHERE c.capability_id IS NULL OR i.intervention_id IS NULL")).scalar()
    assert bad == 0


def test_duplicate_intervention_capability_pairs_are_impossible(db):
    """Case 5, enforced by the composite primary key rather than by convention."""
    row = db.execute(text(
        "SELECT intervention_id, capability_id FROM intervention_capabilities LIMIT 1")).first()
    assert row is not None, "no mappings seeded"
    with pytest.raises(Exception):
        db.execute(
            text("INSERT INTO intervention_capabilities (intervention_id, capability_id)"
                 " VALUES (:i, :c)"),
            {"i": row[0], "c": row[1]},
        )
        db.flush()


def test_an_intervention_may_build_several_capabilities(db):
    """Case 6. Supported on purpose -- "Channel Testing Infrastructure" is both
    acquisition and tooling, and forcing one would lose information."""
    multi = db.execute(text(
        "SELECT count(*) FROM ("
        "  SELECT intervention_id FROM intervention_capabilities"
        "   GROUP BY intervention_id HAVING count(*) > 1) t")).scalar()
    assert multi > 0


def test_unmapped_interventions_are_detectable(db, capsys):
    """Case 7. Reported, never forced -- an ambiguous mapping is worse than none."""
    unmapped = db.execute(text(
        "SELECT count(*) FROM interventions i"
        "  LEFT JOIN intervention_capabilities ic ON ic.intervention_id = i.intervention_id"
        " WHERE ic.intervention_id IS NULL")).scalar()
    total = db.execute(text("SELECT count(*) FROM interventions")).scalar()
    assert unmapped < total, "nothing was mapped at all"
    with capsys.disabled():
        print(f"\n    interventions: {total - unmapped}/{total} mapped, "
              f"{unmapped} unmapped (founder-psychology + ambiguous)")


def test_no_capability_exists_only_because_an_intervention_has_a_label(db):
    """The failure mode of deriving a taxonomy from 390 free-text labels.

    If capabilities had been generated per intervention label, the taxonomy
    would be roughly the size of the library and almost every capability would
    have exactly one intervention. Both are asserted against.
    """
    capabilities = db.execute(text("SELECT count(*) FROM capabilities")).scalar()
    interventions = db.execute(text("SELECT count(*) FROM interventions")).scalar()
    assert capabilities < interventions / 5, (
        f"{capabilities} capabilities for {interventions} interventions looks "
        "like one capability per intervention"
    )
    singletons = db.execute(text(
        "SELECT count(*) FROM ("
        "  SELECT capability_id FROM intervention_capabilities"
        "   GROUP BY capability_id HAVING count(*) = 1) t")).scalar()
    mapped_caps = db.execute(text(
        "SELECT count(DISTINCT capability_id) FROM intervention_capabilities")).scalar()
    assert singletons < mapped_caps / 2, (
        "most capabilities map to a single intervention, which is what a "
        "label-derived taxonomy looks like"
    )


# =========================================================== 8: industry neutrality
INDUSTRY_WORDS = (
    "saas", "fintech", "agritech", "healthtech", "edtech", "ecommerce", "d2c",
    "logistics", "proptech", "manufactur", "retail", "automotive", "agri",
    "food", "b2b", "b2c", "marketplace",
)


def test_the_taxonomy_is_industry_neutral(db):
    """Case 8. No SaaS Sales Capability beside an Agriculture Sales Capability.

    Industry belongs on the REQUIREMENT (Step 6), never on the capability --
    otherwise every new vertical becomes a taxonomy change, which is the thing
    Steps 2-4 were spent removing from the engine.
    """
    rows = db.execute(text(
        "SELECT capability_code, capability_name, description FROM capabilities")).all()
    for code, name, description in rows:
        blob = f"{code} {name} {description}".lower()
        hits = [w for w in INDUSTRY_WORDS if w in blob]
        assert not hits, f"{code} names an industry or business model: {hits}"


def test_domains_are_industry_neutral_too(db):
    rows = db.execute(text(
        "SELECT domain_code, domain_name, description FROM capability_domains")).all()
    for code, name, description in rows:
        blob = f"{code} {name} {description}".lower()
        assert not [w for w in INDUSTRY_WORDS if w in blob], code


def test_one_shared_capability_serves_every_industry(db):
    """The positive form: a generic sales capability exists and there is exactly
    one of it."""
    sales = db.execute(text(
        "SELECT capability_code FROM capabilities"
        " WHERE lower(capability_name) LIKE '%sales%'")).all()
    assert sales, "no sales capability at all"
    assert len(sales) <= 2, f"sales appears to be split per context: {sales}"


# =========================================================== 10: referenceable
def test_a_future_requirement_can_reference_a_capability_without_target_logic(db):
    """Case 10. Capabilities are addressable by a stable code, today.

    Step 6 will add capability_requirements keyed on this. Nothing about that is
    implemented here; what is asserted is that the join it needs will work.
    """
    row = db.execute(text(
        "SELECT capability_id, capability_code FROM capabilities"
        " WHERE capability_code = 'GTM-SALES'")).first()
    assert row is not None, "the code Step 6's worked example uses is missing"
    capability_id, _code = row
    criteria = db.execute(text(
        "SELECT count(*) FROM capability_evidence_criteria WHERE capability_id = :c"),
        {"c": capability_id}).scalar()
    assert criteria >= 3, "a requirement needs criteria to be judged against"


def test_question_capability_mapping_is_partial_by_design(db, capsys):
    """Step 7A curated this; Step 5 shipped it empty.

    The assertion that matters is that it is STILL PARTIAL. A fabricated mapping
    would produce confident evidence about capabilities nobody checked, so the
    1,874 unmapped questions are the designed outcome, not a backlog to burn
    down. Full coverage here would mean the curation forced matches.
    """
    mapped = db.execute(text(
        "SELECT count(DISTINCT question_id) FROM question_capabilities")).scalar()
    total = db.execute(text("SELECT count(*) FROM questions")).scalar()
    assert 0 < mapped < total, (
        "the mapping must be seeded and partial; see "
        "backend/docs/QUESTION-CAPABILITY-MAPPING.md"
    )
    with capsys.disabled():
        print(f"\n    questions: {mapped}/{total} mapped to capabilities "
              f"({mapped / total:.0%}) -- see QUESTION-CAPABILITY-MAPPING.md")


# =========================================================== 11: no gap states yet
def test_there_is_no_gap_table_yet(db):
    """The boundary, moved forward exactly one step again.

    Step 6 added `capability_requirements` (what a DESTINATION needs) and Step
    7B added `capability_evidence` (what one ANSWER observably showed). Neither
    is a verdict: the comparison between them -- the Gap Engine -- is Step 8,
    and its tables must still be absent. This is what stops a gap being
    computed before there is a mechanism to compute it: you cannot join to a
    table that does not exist.
    """
    present = {t for (t,) in db.execute(text(
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema = 'public'")).all()}
    assert "capability_requirements" in present, "Step 6 should have added this"
    assert "capability_evidence" in present, "Step 7B should have added this"
    for premature in ("detected_gaps", "target_state_profiles", "capability_assessments"):
        assert premature not in present, f"{premature} belongs to a later step"


def test_unassessed_is_not_a_level():
    assert not isinstance(UNASSESSED, CapabilityLevel)
    assert is_assessed(UNASSESSED) is False
    assert is_assessed(CapabilityLevel.ABSENT) is True
    assert is_assessed(None) is False


def test_unassessed_cannot_be_compared_with_a_level():
    """The rule the whole Future-State design turns on, enforced by the type.

    If UNASSESSED were a fifth enum member, `observed < required` would silently
    evaluate and a founder would be told a capability is missing when nobody
    ever asked them about it. It is a string precisely so that comparison is a
    TypeError.
    """
    with pytest.raises(TypeError):
        UNASSESSED < CapabilityLevel.DOCUMENTED       # noqa: B015
    with pytest.raises(TypeError):
        CapabilityLevel.DOCUMENTED > UNASSESSED       # noqa: B015


def test_absent_is_a_claim_and_unassessed_is_not():
    # Level 0 says the thing is not there. UNASSESSED says nobody looked.
    assert CapabilityLevel.ABSENT == 0
    assert CapabilityLevel.ABSENT.is_founder_dependent is True
    assert UNASSESSED != 0


def test_the_level_scale_measures_founder_dependence():
    assert CapabilityLevel.PERSONAL.is_founder_dependent is True
    assert CapabilityLevel.DOCUMENTED.is_founder_dependent is False
    assert CapabilityLevel.OWNED > CapabilityLevel.DOCUMENTED > CapabilityLevel.PERSONAL


# =========================================================== reporting
def test_taxonomy_shape_is_reported(db, capsys):
    rows = db.execute(text(
        "SELECT d.domain_code, count(c.capability_id)"
        "  FROM capability_domains d"
        "  LEFT JOIN capabilities c ON c.domain_id = d.domain_id"
        " GROUP BY d.domain_code, d.domain_order ORDER BY d.domain_order")).all()
    with capsys.disabled():
        shape = "  ".join(f"{code}:{n}" for code, n in rows)
        print(f"\n    taxonomy: {shape}")
