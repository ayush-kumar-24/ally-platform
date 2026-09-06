"""A process-local TTL cache, for data that is the same for every founder.

Deliberately not Redis. There is none in this codebase (see
middleware/rate_limit.py and webhooks/internal_jobs.py, which both say so), and
the things worth caching here -- the eight founder stages, the industry list,
the business pillars -- are small, identical for everybody, and change only
when a migration changes them. A dictionary in the process is the right size of
tool for that, and it costs nothing to run.

What must NOT go through this: anything scoped to one founder. Two instances
would disagree, and a founder who has just finished a diagnosis would be shown
the state they had before it. Founder-specific staleness is exactly the class
of lie the dashboard's placeholder states exist to avoid.
"""

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Long enough that a page load never pays for the same list twice, short enough
# that a migration's effects appear without a redeploy. A deploy replaces the
# process and empties this anyway.
DEFAULT_TTL_SECONDS = 600

_lock = threading.Lock()
_entries: dict[str, tuple[float, Any]] = {}


def cached(key: str, produce: Callable[[], T], *, ttl: int = DEFAULT_TTL_SECONDS) -> T:
    """Return the cached value for `key`, or produce and store it.

    `produce` may run more than once under a race -- two threads arriving on a
    cold key both compute it. That is deliberate: holding the lock across a
    database query would serialise every request behind the slowest one, which
    is the exact problem the rest of this work is undoing. Computing a small
    list twice is cheaper than that.
    """
    now = time.monotonic()

    with _lock:
        entry = _entries.get(key)
        if entry is not None and entry[0] > now:
            return entry[1]

    value = produce()

    with _lock:
        _entries[key] = (now + ttl, value)
    return value


def clear() -> None:
    """Drop everything. For tests, and for anything that knowingly invalidates."""
    with _lock:
        _entries.clear()
