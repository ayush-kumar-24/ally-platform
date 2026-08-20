"""Domain tests for the Vision module. In-memory, deterministic, offline."""

from datetime import datetime, timedelta, timezone

import pytest

from app.vision import (
    TERRITORY_KEYS,
    InMemoryVisionRepository,
    InvalidVisionInputError,
    InvalidVisionTerritoryError,
    build_vision_service,
)

T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)


class StepClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def __call__(self):
        v = self._now
        self._now += self._step
        return v


def svc():
    return build_vision_service(InMemoryVisionRepository(), clock=StepClock())


# --- territories -----------------------------------------------------------


def test_all_six_territory_keys_present_even_when_none_written():
    s = svc()
    territories = s.get_territories(1)
    assert set(territories.keys()) == set(TERRITORY_KEYS)
    assert all(v is None for v in territories.values())


def test_upsert_territory_stores_fields():
    s = svc()
    t = s.upsert_territory(1, "business", statement="A company that runs without me.", tag1="4-day week", tag2="Mar 2027")
    assert t.founder_id == 1
    assert t.territory == "business"
    assert t.statement == "A company that runs without me."
    assert t.tag1 == "4-day week" and t.tag2 == "Mar 2027"
    assert t.updated_at == T0


def test_upsert_territory_appears_in_get_territories():
    s = svc()
    s.upsert_territory(1, "legacy", statement="Something that outlasts me.")
    territories = s.get_territories(1)
    assert territories["legacy"].statement == "Something that outlasts me."
    assert territories["life"] is None  # untouched territory stays empty


def test_upsert_unknown_territory_rejected():
    with pytest.raises(InvalidVisionTerritoryError):
        svc().upsert_territory(1, "not-a-real-territory", statement="x")


@pytest.mark.parametrize("bad_statement", ["", "   ", "\t\n"])
def test_empty_statement_rejected(bad_statement):
    with pytest.raises(InvalidVisionInputError):
        svc().upsert_territory(1, "life", statement=bad_statement)


def test_overlong_statement_rejected():
    with pytest.raises(InvalidVisionInputError):
        svc().upsert_territory(1, "life", statement="x" * 1001)


def test_overlong_tag_rejected():
    with pytest.raises(InvalidVisionInputError):
        svc().upsert_territory(1, "life", statement="ok", tag1="x" * 101)


def test_statement_and_tags_are_trimmed():
    s = svc()
    t = s.upsert_territory(1, "life", statement="  hi  ", tag1=" a ", tag2=" b ")
    assert t.statement == "hi" and t.tag1 == "a" and t.tag2 == "b"


def test_re_upsert_replaces_not_duplicates():
    s = svc()
    s.upsert_territory(1, "life", statement="first draft")
    s.upsert_territory(1, "life", statement="second draft")
    territories = s.get_territories(1)
    assert territories["life"].statement == "second draft"


def test_founder_isolation():
    s = svc()
    s.upsert_territory(1, "life", statement="founder 1's vision")
    territories = s.get_territories(2)
    assert territories["life"] is None


# --- summary -----------------------------------------------------------


def test_summary_none_when_never_written():
    assert svc().get_summary(1) is None


def test_upsert_summary_stores_all_fields():
    s = svc()
    summary = s.upsert_summary(1, target="₹100Cr", current="₹3.4Cr", unit="ARR by 2030")
    assert summary.founder_id == 1
    assert summary.target == "₹100Cr" and summary.current == "₹3.4Cr" and summary.unit == "ARR by 2030"
    assert summary.updated_at == T0


def test_upsert_summary_partial_update_keeps_other_fields():
    s = svc()
    s.upsert_summary(1, target="₹100Cr", current="₹3.4Cr", unit="ARR")
    updated = s.upsert_summary(1, current="₹5Cr")
    assert updated.target == "₹100Cr" and updated.unit == "ARR"
    assert updated.current == "₹5Cr"


def test_upsert_summary_explicit_empty_string_clears_field():
    s = svc()
    s.upsert_summary(1, target="₹100Cr")
    cleared = s.upsert_summary(1, target="")
    assert cleared.target == ""


def test_upsert_summary_overlong_field_rejected():
    with pytest.raises(InvalidVisionInputError):
        svc().upsert_summary(1, target="x" * 101)


def test_summary_founder_isolation():
    s = svc()
    s.upsert_summary(1, target="founder 1's target")
    assert s.get_summary(2) is None


# --- determinism --------------------------------------------------------


def test_deterministic_execution():
    def run():
        s = svc()
        s.upsert_territory(1, "life", statement="a")
        s.upsert_summary(1, target="b")
        return (s.get_territories(1)["life"].updated_at, s.get_summary(1).updated_at)
    assert run() == run()
