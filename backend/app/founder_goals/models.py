"""Founder Goals domain model.

A DELIBERATELY separate concept from app.planning's Goal: planning's Goal is
nested under a Plan (Plan -> Goal -> Task), scoped to the Plan Your Day paid
feature, and represents near-term actionable work. This module backs the
standalone "Goals" page ("Outcomes you are actively moving. ... Today's tasks
stay in Plan Your Day.") -- longer-horizon founder/business/life outcomes,
free from the start, with no plan/task hierarchy underneath them. The two
concepts intentionally do not share a table or a domain class; naming them
identically ("Goal") in two unrelated modules invites exactly the confusion
the frontend copy above is written to avoid.

Immutable frozen dataclass -- same reasoning as every other domain model in
this codebase (see app/consents/models.py): the service returns these, never
ORM rows, so the persistence layer can be swapped without touching callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FounderGoal:
    goal_id: str
    founder_id: int
    title: str
    # Free-text, founder-written status line ("₹3.4Cr achieved · due 31 Mar
    # 2027"). Deliberately not structured (current/target/unit fields): goals
    # vary too much in shape -- revenue, retention, a focus goal, a life
    # goal -- for one schema to fit without forcing it. Mirrors the frontend's
    # own reasoning in services/goals.js.
    subtitle: str
    created_at: datetime
    updated_at: datetime
