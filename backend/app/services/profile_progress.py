"""Profile completeness -- progress + validation.

The onboarding profile is the 4-section, path-branching flow described in
data/onboardingQuestions.js on the frontend, mapped to founders columns. Both
the progress bar and the "is this ready to submit" check read from one
definition here, so they can never disagree.

Rewritten 2026-08-17 for that redesign. The previous static field list marked
founder_motivation/support_preferences/emotional_state as required forever --
none of them are asked by onboarding any more, so no founder going through the
new flow could ever satisfy them and `valid` could never become true. It also
had no notion of path: vision_1_year (Path 2 only) and goal_90_day (Path 1
only) cannot both be "required" without making the other path permanently
incomplete. Required-ness is now computed per founder from their actual stage.
"""

from app.api.v1.diagnosis.engine import stage_groups_for
from app.models import Founder
from app.models.enums import StageGroup

# (column, label, section) -- always required, on every path. order = display
# order. full_name is deliberately absent: it's guaranteed NOT NULL from
# signup (OTP/password or the settings page), not something onboarding alone
# gates completion on.
ALWAYS_REQUIRED: list[tuple[str, str, str]] = [
    ("stage_id", "Stage", "personal"),
    ("experience_level", "Experience", "personal"),
    ("problem_statement", "Problem", "where_you_are"),
    # Path 2's "What are you building?" and Path 1's "What would you call
    # this idea?" write the same column -- whichever path a founder is on,
    # this ends up filled by the end of Section 2.
    ("building_summary", "What you're building", "where_you_are"),
    ("customer_segment", "Who you serve", "what_you_know"),
    ("industry", "Industry", "what_you_know"),
    ("founder_reality_signals", "Founder Reality", "what_you_know"),
    ("invisible_gaps", "Invisible Gaps", "what_you_know"),
    ("current_challenges", "Biggest Challenge", "final"),
]

# Path 2 (beyond Stage 0) only.
PATH_2_REQUIRED: list[tuple[str, str, str]] = [
    ("current_revenue", "Monthly Revenue", "personal"),
    ("product_description", "What It Is", "where_you_are"),
    ("business_reality_signals", "Business Reality", "what_you_know"),
    ("vision_1_year", "One-Year Vision", "final"),
]

# Path 1 (Stage 0 / Ideation) only.
PATH_1_REQUIRED: list[tuple[str, str, str]] = [
    ("goal_90_day", "90-Day Goal", "final"),
]

# Never required -- shown in the progress list, never blocks completion.
OPTIONAL_FIELDS: list[tuple[str, str, str]] = [
    ("linkedin_url", "Social Handle", "personal"),
]


def _is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _path_required(founder: Founder) -> list[tuple[str, str, str]]:
    """PATH_2_REQUIRED, PATH_1_REQUIRED, or neither when the stage isn't
    known yet -- fails open the same way stage_groups_for itself does: a
    founder who hasn't answered the stage question yet is not held to either
    path's extra requirements until it's actually known which one applies."""
    groups = stage_groups_for(getattr(founder, "stage", None))
    if groups == [StageGroup.STAGE_1_TO_10_PLUS.value] or groups == [StageGroup.STAGE_0_TO_1.value]:
        return PATH_2_REQUIRED
    if groups == [StageGroup.STAGE_0.value]:
        return PATH_1_REQUIRED
    return []  # stage unknown -- every group returned, fail open


def _all_fields(founder: Founder) -> list[tuple[str, str, str, bool]]:
    """(column, label, section, required) for this founder specifically --
    required varies by path, so this is computed per founder, not a static
    module-level list the way it used to be."""
    path_required = _path_required(founder)
    return (
        [(c, l, s, True) for c, l, s in ALWAYS_REQUIRED]
        + [(c, l, s, True) for c, l, s in path_required]
        + [(c, l, s, False) for c, l, s in OPTIONAL_FIELDS]
    )


def compute_progress(founder: Founder) -> dict:
    fields = []
    for attr, label, section, required in _all_fields(founder):
        fields.append({
            "field": attr,
            "label": label,
            "section": section,
            "required": required,
            "filled": _is_filled(getattr(founder, attr, None)),
        })

    total = len(fields)
    filled = sum(1 for f in fields if f["filled"])
    required = [f for f in fields if f["required"]]
    required_filled = sum(1 for f in required if f["filled"])

    return {
        "fields": fields,
        "filled": filled,
        "total": total,
        "percent": round(filled / total * 100) if total else 0,
        "required_filled": required_filled,
        "required_total": len(required),
        "profile_completed": bool(founder.profile_completed),
    }


def validate_profile(founder: Founder) -> dict:
    """List the required fields still missing. `valid` is True when none are."""
    missing = [
        {"field": attr, "label": label, "section": section}
        for attr, label, section, required in _all_fields(founder)
        if required and not _is_filled(getattr(founder, attr, None))
    ]
    return {"valid": not missing, "missing": missing}
