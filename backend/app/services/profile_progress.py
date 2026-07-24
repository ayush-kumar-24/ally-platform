"""Profile completeness -- progress + validation.

The onboarding profile is the 13 questions, mapped to founders columns. Both the
progress bar and the "is this ready to submit" check read from one definition
here, so they can never disagree.
"""

from app.models import Founder

# (column, label, section, required) -- order = display order.
PROFILE_FIELDS: list[tuple[str, str, str, bool]] = [
    ("stage_id", "Stage", "business", True),
    ("building_summary", "What you're building", "business", True),
    ("problem_statement", "Problem", "business", True),
    ("customer_segment", "Customer", "business", True),
    ("industry", "Industry", "business", True),
    ("current_challenges", "Challenges", "business", True),
    ("goal_90_day", "90-day goal", "goals", True),
    ("vision_1_year", "1-year vision", "goals", True),
    ("founder_motivation", "Why you started", "founder", True),
    ("support_preferences", "Support preferences", "founder", True),
    ("experience_level", "Experience", "founder", True),
    ("emotional_state", "Feeling", "founder", True),
    ("adaptive_reflection", "Reflection", "founder", False),
]


def _is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def compute_progress(founder: Founder) -> dict:
    fields = []
    for attr, label, section, required in PROFILE_FIELDS:
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
        for attr, label, section, required in PROFILE_FIELDS
        if required and not _is_filled(getattr(founder, attr, None))
    ]
    return {"valid": not missing, "missing": missing}
