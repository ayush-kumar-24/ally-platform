"""A compact, prompt-ready summary of everything already known about a founder.

Onboarding asks around 14 questions specifically to understand someone BEFORE
the diagnosis starts (17 defined in the frontend's onboardingQuestions.js, some
path-conditional so no single founder sees them all), and Founder DNA and
Current Problem ask more on top. None of it
reached question selection: the advisor was handed the last five Q&A pairs, the
question just asked, and a shortlist -- so a compliance-SaaS founder at Rs 1cr
with a churn problem and a pre-revenue solo founder in the same stage group had
their next question chosen on identical grounds.

This module is the missing input. It reads what onboarding already collected and
renders it as a short block the advisor (and the reasoning pipeline) can read.

Why a rendered string rather than a structured object handed to the model:
everything here is free text a founder typed, and the consumer is a prompt. A
dataclass would be converted to text at every call site, differently each time.

BUDGET is the whole design constraint. This is built once per answer, up to 30
times a session, and every character is paid for on every one of those calls --
so fields are truncated hard and anything empty is dropped entirely rather than
rendered as "Not set", which costs tokens to say nothing. Measured at ~420
tokens for a fully-populated founder, and proportionally less for a sparse one
-- roughly 12k extra input tokens across a full 30-question diagnosis.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# Per-field caps. Deliberately uneven: what a founder is building and the
# problem they arrived with are what the next question should respond to, so
# they get room; a motivation essay does not change which question comes next.
_SHORT = 160
_MEDIUM = 240
# Excerpts, not transcripts. These are the bulkiest part of the brief and
# the advisor needs the gist of what the founder is like, not their full
# answers -- which it would anyway see again in `history` for recent turns.
_DNA_ANSWER = 130
_MAX_DNA_TURNS = 3
_MAX_PROBLEM_TURNS = 2


def _clean(value: Any, limit: int) -> str:
    """One line, collapsed and truncated, or "" if there is nothing to say."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v) for v in value if v not in (None, ""))
    elif isinstance(value, dict):
        # JSONB signal blobs: keep the keys that are actually set, not the shape.
        value = ", ".join(f"{k}={v}" for k, v in value.items()
                          if v not in (None, "", [], {}))
    text_value = " ".join(str(value).split())
    if not text_value or text_value.lower() in {"none", "null", "{}", "[]"}:
        return ""
    return text_value[:limit].rstrip() + ("..." if len(text_value) > limit else "")


def _line(label: str, value: str) -> str | None:
    return f"{label}: {value}" if value else None


def build_founder_brief(db: Session, founder: Any, *,
                        include_dna: bool = True,
                        include_problem: bool = True) -> str:
    """The founder in a few hundred tokens, or "" when nothing is known.

    Returns "" rather than a header with empty sections for a founder who
    skipped onboarding entirely -- an empty block in a prompt reads as "we
    looked and there is nothing", which is worse than not raising the subject.
    """
    parts: list[str] = []

    # --- who they are and what they are building -------------------------
    stage = getattr(getattr(founder, "stage", None), "stage_name", None)
    facts = [
        _line("Stage", _clean(stage, 60)),
        _line("Industry", _clean(getattr(founder, "industry", None), 60)),
        _line("Revenue", _clean(getattr(founder, "current_revenue", None), 40)),
        _line("Team size", _clean(getattr(founder, "team_size", None), 40)),
        _line("Business model", _clean(getattr(founder, "business_model", None), 40)),
        _line("Experience", _clean(getattr(founder, "experience_level", None), 40)),
    ]
    facts = [f for f in facts if f]
    if facts:
        parts.append(" | ".join(facts))

    for label, attr, limit in (
        ("Building", "building_summary", _MEDIUM),
        ("Product", "product_description", _SHORT),
        ("Problem they described", "problem_statement", _MEDIUM),
        ("Customers", "customer_segment", _SHORT),
        ("Current challenges", "current_challenges", _MEDIUM),
        ("90-day goal", "goal_90_day", _SHORT),
        ("1-year vision", "vision_1_year", _SHORT),
    ):
        line = _line(label, _clean(getattr(founder, attr, None), limit))
        if line:
            parts.append(line)

    # --- how they operate -------------------------------------------------
    how = [
        _line("motivation", _clean(getattr(founder, "founder_motivation", None), _SHORT)),
        _line("decision style", _clean(getattr(founder, "decision_making_style", None), 40)),
        _line("emotional state", _clean(getattr(founder, "emotional_state", None), 80)),
        _line("wants Ally to be", _clean(getattr(founder, "working_relationship", None), 40)),
    ]
    how = [h for h in how if h]
    if how:
        parts.append("Founder: " + "; ".join(how))

    # Self-reported weak spots. These are the highest-signal fields onboarding
    # collects for a diagnosis -- a founder naming their own blind spot is
    # exactly what the next question should press on.
    for label, attr in (("Reality check (founder)", "founder_reality_signals"),
                        ("Reality check (business)", "business_reality_signals"),
                        ("Self-declared gaps", "invisible_gaps")):
        line = _line(label, _clean(getattr(founder, attr, None), _SHORT))
        if line:
            parts.append(line)

    founder_id = getattr(founder, "founder_id", None)

    # --- what they said in the two phases before this one ----------------
    # Read directly rather than through the phase services: this needs the raw
    # text, not domain objects, and it runs on the answer path where an extra
    # service construction per turn is cost for nothing. Failures degrade to
    # omitting the section -- a missing brief must never break the interview.
    if include_problem and founder_id is not None:
        try:
            rows = db.execute(text("""
                SELECT q.question_text, a.answer_text
                  FROM current_problem_answers a
                  JOIN current_problem_questions q
                    ON q.current_problem_question_id = a.current_problem_question_id
                 WHERE a.founder_id = :f
                 ORDER BY a.answered_at
                 LIMIT :n
            """), {"f": founder_id, "n": _MAX_PROBLEM_TURNS}).fetchall()
            said = [f"- {_clean(r[1], _DNA_ANSWER)}" for r in rows if _clean(r[1], _DNA_ANSWER)]
            if said:
                parts.append("What they said the problem is:\n" + "\n".join(said))
        except Exception:  # noqa: BLE001 -- context is optional, the interview is not
            pass

    if include_dna and founder_id is not None:
        try:
            rows = db.execute(text("""
                SELECT q.dimension_code, a.answer_text
                  FROM founder_dna_answers a
                  JOIN founder_dna_questions q
                    ON q.founder_dna_question_id = a.founder_dna_question_id
                 WHERE a.founder_id = :f
                 ORDER BY a.answered_at DESC
                 LIMIT :n
            """), {"f": founder_id, "n": _MAX_DNA_TURNS}).fetchall()
            dna = [f"- {r[0]}: {_clean(r[1], _DNA_ANSWER)}"
                   for r in rows if _clean(r[1], _DNA_ANSWER)]
            if dna:
                parts.append("Founder DNA (most recent):\n" + "\n".join(dna))
        except Exception:  # noqa: BLE001
            pass

    if not parts:
        return ""
    return "FOUNDER CONTEXT (from onboarding, Founder DNA and Current Problem)\n" \
        + "\n".join(parts)
