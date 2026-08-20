"""No API field may accept a value its column will reject.

Two ways the same failure happened, both a 500 with the founder's whole profile
update lost, and both because validation stopped short of what Postgres
enforces.

PATCH /profile returned 500 for any founder whose answer landed in the gap
between the two: FounderUpdate advertised max_length=100 for
decision_making_style while `founders.decision_making_style` was varchar(30),
so "gather everything, then decide late" -- 35 characters -- passed validation,
reached Postgres, and raised StringDataRightTruncation. Unhandled, so a 500,
and the founder's whole profile update was discarded.

Seven fields were mismatched that way.

Then, with the widths fixed, the same save failed again on CheckViolation: five
of those columns are not free text at all but controlled vocabularies with a
CHECK constraint listing their values, while the schema still typed them as
plain `str`. "D2C e-commerce" is a reasonable thing to type into business_model
and is not on the list.

This module compares both -- declared max_length against column width, and
declared Literal members against the CHECK definition read out of Postgres -- so
the next drift in either direction is caught before it reaches a founder.

The width checks read the ORM model, not a live database: the widths are
declared in app/models/schema.py, migrations keep the real table in step with
it, and a test needing a connection is a test that gets skipped in CI. The
vocabulary check has no such option -- a CHECK definition exists only in
Postgres -- so that one connects, and skips rather than fails when it cannot.
"""

from __future__ import annotations

import re
from typing import get_args

import pydantic
import pytest
from sqlalchemy import text

from app import schemas as _schemas  # noqa: F401  (ensures schema modules import)
from app.models.schema import Founders
from app.schemas.founder import (
    BusinessModel,
    CurrentRevenue,
    ExperienceLevel,
    FounderUpdate,
    TeamSize,
    WorkingRelationship,
)


def _column_lengths() -> dict[str, int]:
    lengths = {}
    for column in Founders.__table__.columns:
        length = getattr(column.type, "length", None)
        if length is not None:
            lengths[column.name] = length
    return lengths


def _declared_max_length(field: pydantic.fields.FieldInfo) -> int | None:
    """Pydantic v2 keeps constraints in `metadata`, not on the field itself."""
    for meta in field.metadata:
        value = getattr(meta, "max_length", None)
        if value is not None:
            return value
    return None


def _mismatches(model: type[pydantic.BaseModel]) -> list[tuple[str, int, int]]:
    columns = _column_lengths()
    found = []
    for name, field in model.model_fields.items():
        api = _declared_max_length(field)
        column = columns.get(name)
        if api is None or column is None:
            continue
        if api > column:
            found.append((name, api, column))
    return found


def test_founder_update_fits_its_columns():
    bad = _mismatches(FounderUpdate)
    assert not bad, "API accepts more than the column holds -> 500 on save: " + ", ".join(
        f"{name} (max_length={api} > varchar({column}))" for name, api, column in bad
    )


@pytest.mark.parametrize(
    "field, expected",
    [
        ("working_relationship", 100),
        ("experience_level", 100),
        ("decision_making_style", 100),
        ("team_size", 50),
        ("current_revenue", 50),
        ("business_model", 100),
        ("website", 500),
    ],
)
def test_widened_columns_stay_widened(field, expected):
    """The specific seven from migration c8a1f47b93de.

    Pinned individually as well as by the general rule above, because the
    general rule also passes if someone "fixes" a future mismatch by narrowing
    the API instead -- which would keep founders from writing a full sentence
    about themselves rather than letting them.
    """
    assert _column_lengths()[field] == expected


# --- controlled vocabularies -----------------------------------------------

_ENUM_FIELDS = {
    "business_model": BusinessModel,
    "current_revenue": CurrentRevenue,
    "experience_level": ExperienceLevel,
    "team_size": TeamSize,
    "working_relationship": WorkingRelationship,
}


def _check_constraint_values(engine, column: str) -> set[str]:
    """The values `founders_<column>_check` actually permits, from Postgres."""
    sql = text(
        "select pg_get_constraintdef(oid) from pg_constraint "
        "where conrelid = 'founders'::regclass and conname = :name"
    )
    with engine.connect() as conn:
        definition = conn.execute(sql, {"name": f"founders_{column}_check"}).scalar()
    assert definition, f"no CHECK constraint found for founders.{column}"
    return set(re.findall(r"'([^']+)'::character varying", definition))


@pytest.mark.parametrize("column, literal", sorted(_ENUM_FIELDS.items()))
def test_literal_members_match_the_database_check(column, literal):
    """The schema's accepted values and the column's CHECK must be the same set.

    Needs a database, unlike the width tests above -- the CHECK definition is
    the authority and it only exists in Postgres. Skipped rather than failed
    when there is no connection, so this file still guards the widths in an
    offline run.
    """
    try:
        from app.db.session import engine
        allowed = _check_constraint_values(engine, column)
    except Exception as exc:  # no database configured for this run
        pytest.skip(f"no database available: {exc}")

    declared = set(get_args(literal))
    assert declared == allowed, (
        f"founders.{column}: schema accepts {sorted(declared)}, "
        f"database allows {sorted(allowed)}"
    )


def test_enum_fields_reject_free_text_with_422_not_500():
    """The actual reported failure: a plausible free-text value must be refused
    by validation, not by Postgres."""
    with pytest.raises(pydantic.ValidationError):
        FounderUpdate(business_model="D2C e-commerce")
    with pytest.raises(pydantic.ValidationError):
        FounderUpdate(team_size="2")
    with pytest.raises(pydantic.ValidationError):
        FounderUpdate(experience_level="first-time founder")


def test_enum_fields_still_accept_their_real_values():
    ok = FounderUpdate(business_model="D2C", team_size="solo",
                       experience_level="first_time", current_revenue="pre_revenue",
                       working_relationship="cofounder")
    assert ok.business_model == "D2C"
    assert ok.team_size == "solo"
