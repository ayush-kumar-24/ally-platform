"""Session-completion notification port.

The diagnosis module owns this interface because it is the one that *needs* to
announce "a session completed" -- it does not, and must not, know that reasoning
listens. A concrete listener (the reasoning trigger) is bound at application
composition (main.py) via dependency override, so the diagnosis router depends
only on this abstraction and never imports reasoning.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SessionCompletionNotifier(Protocol):
    """Notified once a diagnosis session has transitioned to COMPLETED.

    Takes ids, not a Session and a Founder row, and that is load-bearing rather
    than stylistic. Listeners no longer run inside the request that completed the
    session -- the reasoning listener is scheduled as a background task, by which
    point FastAPI's `get_db` dependency has already closed the request's session
    in its `finally`. A Founder handed across that boundary is a detached
    instance, and the first attribute access on it raises DetachedInstanceError.
    Passing ids forces every listener to open its own session and re-load what it
    needs, which is the only thing that is correct once the work outlives the
    request.

    `founder_uuid` is `founders.user_id`, and it is here for row-level security
    rather than identification -- `founder_id` already identifies the founder.
    A listener's own session starts with no RLS context, and the founder-isolation
    policies resolve through `get_founder_id()`, which reads
    `app.current_founder_uuid`. Without it the listener sees zero rows on every
    table it needs and silently does nothing. Carrying the uuid lets the listener
    scope itself to exactly this founder instead of escalating to the policies'
    admin bypass, which is what a system-wide job would have to do.
    """

    def notify_session_completed(
        self, founder_id: int, session_id: int, founder_uuid: str
    ) -> None: ...


class NullSessionCompletionNotifier:
    """Default no-op notifier: diagnosis runs standalone with no listener bound."""

    def notify_session_completed(
        self, founder_id: int, session_id: int, founder_uuid: str
    ) -> None:
        return None


def get_session_completion_notifier() -> SessionCompletionNotifier:
    """Dependency for the completion notifier.

    Returns the no-op notifier by default; the application composition root
    overrides this dependency to bind the reasoning trigger.
    """
    return NullSessionCompletionNotifier()
