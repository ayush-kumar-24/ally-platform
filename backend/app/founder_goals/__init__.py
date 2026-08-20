"""Founder Goals -- longer-horizon founder/business/life outcomes.

Public surface (import from here, not from submodules):

    FounderGoal               frozen domain DTO -- one goal
    FounderGoalService        business rules; build_founder_goal_service() to construct
    FounderGoalRepository     persistence seam (InMemory / SqlAlchemy)
    errors                    FounderGoalError and friends -> precise HTTP statuses

Deliberately separate from app.planning's nested Plan -> Goal -> Task
hierarchy (paid, near-term action items) -- see models.py's docstring for
why the two "Goal" concepts do not share a table or a domain class.
"""

from app.founder_goals.errors import (
    FounderGoalError,
    FounderGoalNotFoundError,
    InvalidFounderGoalInputError,
)
from app.founder_goals.models import FounderGoal
from app.founder_goals.repository import FounderGoalRepository, InMemoryFounderGoalRepository
from app.founder_goals.service import FounderGoalService, build_founder_goal_service

__all__ = [
    "FounderGoal",
    "FounderGoalError",
    "FounderGoalNotFoundError",
    "FounderGoalRepository",
    "FounderGoalService",
    "InMemoryFounderGoalRepository",
    "InvalidFounderGoalInputError",
    "build_founder_goal_service",
]
