"""Time source for the memory layer.

Every timestamp (created_at, updated_at, accessed_at, archived_at) and every
expiration check goes through an injected Clock rather than a bare
`datetime.now()`. That makes the whole subsystem deterministic and testable: tests
inject a fixed/advanceable clock, production uses SystemClock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Real, timezone-aware wall clock. The default in production."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
