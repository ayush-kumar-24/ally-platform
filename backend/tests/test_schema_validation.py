"""Pydantic edge cases -- validated directly against the schemas (no DB)."""

import pytest
from pydantic import ValidationError

from app.schemas.founder import FounderUpdate
from app.schemas.sections import BusinessInfoUpdate, FounderInfoUpdate

# founder_motivation/support_preferences/emotional_state were retired from
# FounderInfoUpdate by the 2026-08-17 onboarding redesign -- no longer asked,
# so no longer accepted on this section's PATCH (see sections.py's own
# docstring). The tests below that used to exercise trim/dedupe/cap/omit-vs-
# null behaviour through those fields now use fields that still exist:
# BusinessInfoUpdate.current_challenges/problem_statement for the generic
# CleanStrList/string behaviour, and FounderUpdate (the *generic* whole-
# profile schema, which still carries emotional_state/support_preferences
# for the separate settings page) for the enum-constrained Feelings type.


# --- whitespace / blank handling -------------------------------------------

def test_whitespace_only_full_name_rejected():
    with pytest.raises(ValidationError):
        FounderInfoUpdate(full_name="   ")  # trimmed to "" -> under min_length


def test_strings_are_trimmed():
    m = FounderInfoUpdate(full_name="  Ayush  ")
    assert m.full_name == "Ayush"
    m2 = BusinessInfoUpdate(problem_statement="  fix churn  ")
    assert m2.problem_statement == "fix churn"


# --- multi-select cleaning --------------------------------------------------

def test_current_challenges_deduped_and_cleaned():
    m = BusinessInfoUpdate(current_challenges=["Sales", " sales ", "", "Hiring", "hiring"])
    assert m.current_challenges == ["Sales", "Hiring"]


def test_emotional_state_deduped():
    # emotional_state now lives only on the generic FounderUpdate (the
    # settings-page schema) -- FounderInfoUpdate (onboarding) dropped it.
    m = FounderUpdate(emotional_state=["excited", "excited", "hopeful"])
    assert m.emotional_state == ["excited", "hopeful"]


def test_emotional_state_rejects_unknown_value():
    with pytest.raises(ValidationError):
        FounderUpdate(emotional_state=["angry"])


def test_multi_select_length_capped():
    with pytest.raises(ValidationError):
        BusinessInfoUpdate(current_challenges=[f"x{i}" for i in range(40)])  # over max_length=30


# --- extra fields / cross-section ------------------------------------------

def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        FounderInfoUpdate(goal_90_day="belongs to /goals")


def test_experience_level_enum_enforced():
    FounderInfoUpdate(experience_level="serial")  # ok
    with pytest.raises(ValidationError):
        FounderInfoUpdate(experience_level="wizard")


# --- length limits ----------------------------------------------------------

def test_oversized_text_rejected():
    with pytest.raises(ValidationError):
        FounderUpdate(building_summary="x" * 5001)


def test_business_stage_blank_rejected():
    with pytest.raises(ValidationError):
        BusinessInfoUpdate(stage="   ")  # trimmed -> "" under min_length


# --- PATCH semantics: unset vs explicit null --------------------------------

def test_exclude_unset_distinguishes_omitted_from_null():
    # omitted -> not in dump; explicit None -> in dump (clears the column)
    assert FounderInfoUpdate().model_dump(exclude_unset=True) == {}
    assert FounderInfoUpdate(experience_level=None).model_dump(exclude_unset=True) == {"experience_level": None}
