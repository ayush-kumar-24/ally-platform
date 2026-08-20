"""Framework Usage domain model.

Backs the "last used" date and personal note shown on the Frameworks page
and each framework's detail page. The framework CONTENT itself (title,
tagline, diagrams, how-to-apply text -- frontend/src/data/frameworks.js)
stays static on the frontend by design; only what's true about THIS
founder's relationship to a framework (have they opened it, when, and any
note they wrote) is real, per-founder data, and that's what this module
tracks. framework_id is therefore an opaque string here, not a foreign key
or an enum against the frontend's list -- the backend has no reason to know
what frameworks exist, only to remember what a founder did with whichever
id the frontend sent.

Immutable frozen dataclass -- same reasoning as every other domain model in
this codebase (see app/consents/models.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FrameworkUsage:
    founder_id: int
    framework_id: str
    last_used_at: datetime
    note: str
