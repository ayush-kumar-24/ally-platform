"""Session-completion notification port.

The diagnosis module owns this interface because it is the one that *needs* to
announce "a session completed" -- it does not, and must not, know that reasoning
listens. A concrete listener (the reasoning trigger) is bound at application
composition (main.py) via dependency override, so the diagnosis router depends
only on this abstraction and never imports reasoning.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.models.diagnosis import Founder


@runtime_checkable
class SessionCompletionNotifier(Protocol):
    """Notified once a diagnosis session has transitioned to COMPLETED."""

    def notify_session_completed(
        self, db: Session, founder: Founder, session_id: int
    ) -> None: ...


class NullSessionCompletionNotifier:
    """Default no-op notifier: diagnosis runs standalone with no listener bound."""

    def notify_session_completed(
        self, db: Session, founder: Founder, session_id: int
    ) -> None:
        return None


def get_session_completion_notifier() -> SessionCompletionNotifier:
    """Dependency for the completion notifier.

    Returns the no-op notifier by default; the application composition root
    overrides this dependency to bind the reasoning trigger.
    """
    return NullSessionCompletionNotifier()
