"""Pydantic edge cases -- validated directly against the schemas (no DB)."""

import pytest
from pydantic import ValidationError

from app.schemas.founder import FounderUpdate
from app.schemas.sections import BusinessInfoUpdate, FounderInfoUpdate


# --- whitespace / blank handling -------------------------------------------

def test_whitespace_only_full_name_rejected():
    with pytest.raises(ValidationError):
        FounderInfoUpdate(full_name="   ")  # trimmed to "" -> under min_length


def test_strings_are_trimmed():
    m = FounderInfoUpdate(full_name="  Ayush  ", founder_motivation="  fix churn  ")
    assert m.full_name == "Ayush"
    assert m.founder_motivation == "fix churn"


# --- multi-select cleaning --------------------------------------------------

def test_support_preferences_deduped_and_cleaned():
    m = FounderInfoUpdate(support_preferences=["Sales", " sales ", "", "Hiring", "hiring"])
    assert m.support_preferences == ["Sales", "Hiring"]


def test_emotional_state_deduped():
    m = FounderInfoUpdate(emotional_state=["excited", "excited", "hopeful"])
    assert m.emotional_state == ["excited", "hopeful"]


def test_emotional_state_rejects_unknown_value():
    with pytest.raises(ValidationError):
        FounderInfoUpdate(emotional_state=["angry"])


def test_multi_select_length_capped():
    with pytest.raises(ValidationError):
        FounderInfoUpdate(support_preferences=[f"x{i}" for i in range(40)])  # over max_length=30


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
    assert FounderInfoUpdate(founder_motivation=None).model_dump(exclude_unset=True) == {"founder_motivation": None}
