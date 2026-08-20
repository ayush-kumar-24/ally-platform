"""Achievements domain model.

Founder-authored milestones ("Crossed ₹1Cr ARR", "Hired the first ops
leader") -- there is no backend feature that detects these automatically
yet, so every one is written by the founder themselves. See service.py for
the engagement gate that decides whether this page is even reachable.

Immutable frozen dataclass -- same reasoning as every other domain model in
this codebase (see app/consents/models.py / app/founder_goals/models.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Achievement:
    achievement_id: str
    founder_id: int
    title: str
    description: str
    # Free text, not an enum, mirroring the frontend's own choice for
    # founder_goals.subtitle -- categories are a UI convenience (a select
    # box), not a fixed taxonomy worth a migration every time it changes.
    category: str
    # Free text ("Aug 2026"), not a real date -- a founder describing when
    # something happened rarely means a specific calendar day, and forcing
    # one would either be false precision or block the entry entirely.
    occurred_on: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Engagement:
    """How much the founder has actually talked to Ally -- the real signal
    the Achievements page gates on. `message_count` sums every real
    conversation's message_count (conversations.message_count, maintained
    live by the chat pipeline), never a guess."""

    message_count: int
    threshold: int

    @property
    def unlocked(self) -> bool:
        return self.message_count >= self.threshold
