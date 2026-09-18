"""Every field onboarding collects must have an endpoint that accepts it.

THE BUG THIS REPLACES. `saveProfileEdits` routed each field to a section
endpoint through an OWNER map and silently dropped anything the map did not
know: no call, no error, no log. A question could be added to onboarding, be
answered by a founder, and never reach the server -- which is how `team_size`
and `business_model` could be "collected" and still be NULL on every row. The
founder-facing symptom is "Ally does not capture my context", and nothing in the
UI or the network tab shows it.

`saveProfileEdits` now throws on an unowned field. That throw cannot be
unit-tested here: the frontend has no test runner (no vitest, no jest, no test
files anywhere under `frontend/`), and adding one is a separate change. So this
test covers the same invariant from the side that DOES run in CI -- every
`field:` declared in the onboarding source is accepted by a real request schema.
A question added without a home fails here instead of in production.
"""

import re
from pathlib import Path

import pytest

from app.schemas.founder import FounderUpdate
from app.schemas.sections import BusinessInfoUpdate, FounderInfoUpdate, GoalsUpdate

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
ONBOARDING_QUESTIONS = FRONTEND / "data" / "onboardingQuestions.js"
PROFILE_SERVICE = FRONTEND / "services" / "profile.js"

#: Written by the route rather than the payload: the client sends a stage NAME
#: as `stage` and `update_business_info` resolves it to `stage_id`.
_RESOLVED_BY_THE_ROUTE = {"stage"}


def _declared_fields() -> set[str]:
    """Every `field:` / `otherField:` in the onboarding question bank."""
    source = ONBOARDING_QUESTIONS.read_text()
    return set(re.findall(r"(?:field|otherField):\s*'([a-zA-Z_0-9]+)'", source))


def _accepting_schemas():
    return (BusinessInfoUpdate, FounderInfoUpdate, GoalsUpdate, FounderUpdate)


def test_every_onboarding_field_is_accepted_by_some_update_schema():
    declared = _declared_fields()
    assert declared, "parsed no fields out of onboardingQuestions.js"

    accepted: set[str] = set()
    for schema in _accepting_schemas():
        accepted |= set(schema.model_fields)
    accepted |= _RESOLVED_BY_THE_ROUTE

    orphans = sorted(declared - accepted)
    assert not orphans, (
        f"onboarding collects fields no update schema accepts: {orphans}. "
        f"Every one of these is silently discarded on save. Add it to the "
        f"matching schema in app/schemas/sections.py and to the OWNER map in "
        f"frontend/src/services/profile.js."
    )


def test_the_two_new_context_fields_are_among_them():
    # Guards the specific regression: these were declared by neither side.
    declared = _declared_fields()
    assert "team_size" in declared
    assert "business_model" in declared
    assert "team_size" in BusinessInfoUpdate.model_fields
    assert "business_model" in BusinessInfoUpdate.model_fields


def test_every_onboarding_field_has_an_owner_in_the_frontend_map():
    """The other half of the round trip: the OWNER map must know the field too.

    A field can be accepted by a schema and still never be sent, because
    `saveProfileEdits` only forwards what the OWNER map claims. Both halves have
    to agree or the save is a no-op for that field.
    """
    service = PROFILE_SERVICE.read_text()
    # The four OWNER groups are object literals of `key: 'api_field',`.
    owned = set(re.findall(r"^\s+\w+:\s*'([a-z_0-9]+)',", service, re.M))
    orphans = sorted(_declared_fields() - owned - _RESOLVED_BY_THE_ROUTE)
    assert not orphans, (
        f"onboarding collects fields the OWNER map in profile.js does not "
        f"route: {orphans}. saveProfileEdits would now throw on these rather "
        f"than drop them, but they still never reach the server."
    )


def test_save_profile_edits_refuses_an_unowned_field():
    """The throw itself, asserted against the source.

    A source assertion rather than a behavioural one, for the reason in the
    module docstring: there is no JavaScript test runner in this repository. It
    is deliberately narrow -- it checks the guard exists and names the offending
    field -- so it fails if the guard is removed, and does not pretend to be a
    substitute for running the function.
    """
    service = PROFILE_SERVICE.read_text()
    assert "no section endpoint owns" in service, (
        "saveProfileEdits no longer refuses unowned fields; they would be "
        "silently dropped again."
    )
    assert "orphans.join" in service, (
        "the error should name the offending field(s), or the next person hits "
        "the same silent-drop bug with a louder message and no clue which field."
    )


@pytest.mark.parametrize("schema", [BusinessInfoUpdate, FounderInfoUpdate, GoalsUpdate])
def test_section_schemas_still_forbid_unknown_fields(schema):
    # extra="forbid" is what makes an orphaned field a 422 rather than a silent
    # server-side drop. Losing it would hide the same bug one layer deeper.
    assert schema.model_config.get("extra") == "forbid"
