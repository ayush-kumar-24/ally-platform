"""No API field may accept more text than its column can hold.

PATCH /profile returned 500 for any founder whose answer landed in the gap
between the two: FounderUpdate advertised max_length=100 for
decision_making_style while `founders.decision_making_style` was varchar(30),
so "gather everything, then decide late" -- 35 characters -- passed validation,
reached Postgres, and raised StringDataRightTruncation. Unhandled, so a 500,
and the founder's whole profile update was discarded.

Seven fields were mismatched that way. This test compares the two declarations
directly so the next one is caught before it reaches a founder.

Deliberately checked against the ORM model rather than a live database: the
column widths are declared in app/models/schema.py, migrations keep the real
table in step with it, and a test that needs a database connection is a test
that gets skipped in CI.
"""

from __future__ import annotations

import pydantic
import pytest

from app import schemas as _schemas  # noqa: F401  (ensures schema modules import)
from app.models.schema import Founders
from app.schemas.founder import FounderUpdate


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
