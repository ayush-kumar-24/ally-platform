"""Injectable clock for deterministic timestamps.

The whole ai_chat layer takes time through this seam and never calls
`datetime.now()` directly, so tests inject a fake clock and get byte-identical,
reproducible timestamps -- the same determinism discipline as Phase 5.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Real wall-clock, always timezone-aware UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
