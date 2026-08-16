"""ReasoningRepository.get_blind_spot_ids_by_root_cause_codes /
get_behaviour_pattern_ids_by_root_cause_codes -- live conformance, read-only.

Live-confirmed gap: blind_spots (20 seeded rows) and behaviour_patterns (27
seeded rows) were never queried anywhere in the pipeline -- not because they
had no data, but because internal_intelligence_reports.blind_spot_ids and
.behaviour_pattern_ids were always written as `[]` unconditionally. These two
methods are the fix; this locks the @> containment query in against real data
rather than a fixture, matching the read-only pattern in
test_sql_knowledge_graph_repository.py (inserting fixture rows here would
mean fighting the same NOT NULL/embedding columns that file avoids).
"""

import pytest
from sqlalchemy import text

from app.api.v1.reasoning.repository import ReasoningRepository
from app.db.session import SessionLocal


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def repo(db):
    return ReasoningRepository(db)


@pytest.fixture
def blind_spot_case(db):
    """A real (root_cause_code, blind_spot_id) pair straight off live data,
    not hardcoded -- stays valid as the seed data evolves."""
    row = db.execute(text(
        "select bs.blind_spot_id, jsonb_array_elements_text(bs.linked_root_cause_ids) as code "
        "from blind_spots bs limit 1"
    )).first()
    if row is None:
        pytest.skip("no seeded blind_spots row to test against")
    return row.blind_spot_id, row.code


@pytest.fixture
def behaviour_pattern_case(db):
    row = db.execute(text(
        "select bp.pattern_id, jsonb_array_elements_text(bp.linked_root_cause_ids) as code "
        "from behaviour_patterns bp limit 1"
    )).first()
    if row is None:
        pytest.skip("no seeded behaviour_patterns row to test against")
    return row.pattern_id, row.code


def test_blind_spot_lookup_matches_real_seeded_row(repo, blind_spot_case):
    blind_spot_id, code = blind_spot_case
    assert blind_spot_id in repo.get_blind_spot_ids_by_root_cause_codes([code])


def test_blind_spot_lookup_empty_for_unknown_code(repo):
    assert repo.get_blind_spot_ids_by_root_cause_codes(["RC-does-not-exist"]) == []


def test_blind_spot_lookup_empty_for_no_codes(repo):
    assert repo.get_blind_spot_ids_by_root_cause_codes([]) == []


def test_behaviour_pattern_lookup_matches_real_seeded_row(repo, behaviour_pattern_case):
    pattern_id, code = behaviour_pattern_case
    assert pattern_id in repo.get_behaviour_pattern_ids_by_root_cause_codes([code])


def test_behaviour_pattern_lookup_empty_for_unknown_code(repo):
    assert repo.get_behaviour_pattern_ids_by_root_cause_codes(["RC-does-not-exist"]) == []
