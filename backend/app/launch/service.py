"""Launch gate -- state, storage and the rules that move between states.

Transport lives in app/api/v1/launch/ and app/api/v1/admin/launch_router.py.
Every rule that decides whether the platform is open is here, and nowhere
else: the frontend's countdown screen is a rendering of this state, never a
second opinion about it.

THE FOUR STATES

    open       no gate at all -- the platform behaves exactly as it did
               before this module existed. This is the seeded default, so
               deploying the launch gate changes nothing until somebody
               deliberately arms it.
    armed      the doors are shut. Everyone but an admin sees the holding
               screen. Nothing is counting yet.
    counting   the shared clock is running towards `countdown_ends_at`.
    launched   open to everyone, and recorded as the one-time event it was.

`open` and `launched` both mean "anybody may come in" -- is_open() treats
them identically. They are kept apart because only one of them is a fact
about a thing that happened, and `launched_at` is the record of it.

WHY `launched` IS TERMINAL
"It opened, then it closed again" is not a state a public go-live has. Once
founders are inside, taking the platform back behind a countdown would sign
them out of something they are mid-way through, and the countdown screen
would be a lie -- there is nothing left to wait for. Shutting the platform
after launch is a different decision with a different tool (maintenance
mode, or a feature flag on the specific thing being withdrawn), taken
deliberately rather than by rewinding history. So there is no transition out
of `launched`, and `launch()` is idempotent rather than repeatable: pressing
the button twice tells you about the first launch, it does not stage a
second one.

WHY THE COUNTDOWN IS SERVER STATE
Two reasons, both of which a frontend animation fails:

  1. Everybody watching gets the same clock. Viewers poll `seconds_remaining`
     off one deadline rather than each running a local timer from their own
     wall clock, which across a room of laptops disagree by seconds -- enough
     that the countdown people are reading aloud together does not match.
  2. It is a real gate on the button. `launch()` refuses while the countdown
     is still running, so the irreversible action cannot happen before the
     window everybody was given to abort in. An animation can be skipped
     with a page refresh; a server-side deadline cannot.
"""

from __future__ import annotations

import abc
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.logger import logger
from app.db.session import Base
from app.middleware.error_handler import AppError

# The ceremony's countdown. Ten seconds is short enough to hold a room's
# attention and long enough to notice a mistake and abort. Overridable per
# call (the admin endpoint accepts 3-300) so a rehearsal or a longer public
# countdown does not need a code change.
DEFAULT_COUNTDOWN_SECONDS = 10
MIN_COUNTDOWN_SECONDS = 3
MAX_COUNTDOWN_SECONDS = 300

# The singleton row. There is one launch, so there is one row, and its id is
# a constant rather than something a caller passes in -- an endpoint that
# could address "launch state 2" would be an endpoint that could launch the
# wrong thing.
STATE_ID = 1


class LaunchState(str, Enum):
    OPEN = "open"
    ARMED = "armed"
    COUNTING = "counting"
    LAUNCHED = "launched"


# --- errors -----------------------------------------------------------------

class AlreadyLaunchedError(AppError):
    """Any attempt to move out of the terminal state. 409, not 400: the
    request was well-formed, the world had simply already moved on."""

    def __init__(self) -> None:
        super().__init__(
            "The platform has already launched. A launch happens once and "
            "cannot be replayed or undone.", status_code=409)


class LaunchNotArmedError(AppError):
    def __init__(self, state: LaunchState, needed: str) -> None:
        super().__init__(
            f"The launch is {state.value}; {needed} first.", status_code=409)


class CountdownRunningError(AppError):
    """The abort window is the whole point of the countdown -- launching
    before it elapses would skip the one chance anyone has to stop it."""

    def __init__(self, seconds_remaining: float) -> None:
        super().__init__(
            f"The countdown still has {seconds_remaining:.1f}s to run. "
            f"Wait for it to reach zero, or abort.", status_code=409)


# --- storage ----------------------------------------------------------------

class LaunchStateRow(Base):
    __tablename__ = "launch_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False,
                                       server_default=LaunchState.OPEN.value)
    countdown_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=str(DEFAULT_COUNTDOWN_SECONDS))
    countdown_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    countdown_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    launched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    launched_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


@dataclass(frozen=True)
class LaunchStatus:
    """One immutable answer to "may people in, and what should they see?"."""

    state: LaunchState
    countdown_seconds: int = DEFAULT_COUNTDOWN_SECONDS
    countdown_ends_at: datetime | None = None
    launched_at: datetime | None = None
    launched_by: int | None = None
    # Server-computed, never derived by the client from countdown_ends_at
    # against its own clock -- see the module docstring. None unless counting.
    seconds_remaining: float | None = None

    @property
    def is_open(self) -> bool:
        return self.state in (LaunchState.OPEN, LaunchState.LAUNCHED)

    @property
    def countdown_elapsed(self) -> bool:
        return self.state is LaunchState.COUNTING and (self.seconds_remaining or 0) <= 0


class LaunchRepository(abc.ABC):
    @abc.abstractmethod
    def read(self) -> LaunchStatus | None:
        """Current state, or None when the gate is not installed -- see
        SqlAlchemyLaunchRepository.read for what that means."""

    @abc.abstractmethod
    def write(self, status: LaunchStatus, *, admin_id: int | None,
              at: datetime) -> LaunchStatus: ...


class InMemoryLaunchRepository(LaunchRepository):
    def __init__(self, status: LaunchStatus | None = None) -> None:
        self._status = status or LaunchStatus(state=LaunchState.OPEN)
        self._lock = threading.RLock()

    def read(self) -> LaunchStatus:
        with self._lock:
            return self._status

    def write(self, status, *, admin_id, at) -> LaunchStatus:
        with self._lock:
            self._status = status
            return status


class SqlAlchemyLaunchRepository(LaunchRepository):
    def __init__(self, db):
        self.db = db

    def read(self) -> LaunchStatus | None:
        """None means "no gate installed", and the service turns that into an
        OPEN platform -- it FAILS OPEN, on purpose, unlike feature flags next
        door which fail closed.

        A flag that fails closed withholds one feature. This gate failing
        closed would put a holding screen in front of a platform that is
        already live and full of founders mid-diagnosis, and it would do it
        for the most ordinary reason there is: this code deployed a few
        minutes before its migration did. The blast radius of the two
        failures is not comparable, so neither is the safe direction.

        The cost of failing open is that a launch-day database problem opens
        the doors early. That is loud and immediately visible (the countdown
        screen everybody is watching simply vanishes), and recoverable. A
        silent, total lockout of a live platform is neither.
        """
        try:
            row = self.db.get(LaunchStateRow, STATE_ID)
        except Exception:
            self.db.rollback()
            logger.error("launch_state_unreadable",
                         extra={"impact": "launch gate open -- platform serving normally"})
            return None
        if row is None:
            # The table is there but the seeded row is not. Distinct from the
            # case above: the migration ran, so the gate IS installed, and
            # something removed its row. Treat as ungated for the same reason
            # -- the row says nothing, so it cannot be saying "keep people
            # out" -- but say so, because it should not happen.
            logger.error("launch_state_row_missing", extra={"id": STATE_ID})
            return None
        return _status(row)

    def write(self, status, *, admin_id, at) -> LaunchStatus:
        row = self.db.get(LaunchStateRow, STATE_ID)
        if row is None:
            # The migration seeds the row, and production grants ally_app
            # SELECT and UPDATE but not INSERT -- so this branch is for tests
            # and for a local database created straight from the metadata. If
            # it is ever reached in production the insert is refused and the
            # press fails loudly, which is the right outcome: a launch whose
            # state could not be written is a launch that did not happen, and
            # silently reporting success would be far worse.
            row = LaunchStateRow(id=STATE_ID)
            self.db.add(row)
        row.state = status.state.value
        row.countdown_seconds = status.countdown_seconds
        row.countdown_ends_at = status.countdown_ends_at
        row.countdown_started_at = (
            at if status.state is LaunchState.COUNTING else row.countdown_started_at)
        row.launched_at = status.launched_at
        row.launched_by = status.launched_by
        row.updated_by, row.updated_at = admin_id, at
        self.db.commit()
        self.db.refresh(row)
        return _status(row)


def _status(row: LaunchStateRow) -> LaunchStatus:
    try:
        state = LaunchState(row.state)
    except ValueError:
        # An unrecognised value is not a reason to hold the doors shut, for
        # the same reason read() fails open. Recorded, then ignored.
        logger.error("launch_state_unknown", extra={"state": row.state})
        state = LaunchState.OPEN
    return LaunchStatus(
        state=state,
        countdown_seconds=row.countdown_seconds or DEFAULT_COUNTDOWN_SECONDS,
        countdown_ends_at=row.countdown_ends_at,
        launched_at=row.launched_at,
        launched_by=row.launched_by,
    )


# --- service ----------------------------------------------------------------

class LaunchService:
    def __init__(self, repository: LaunchRepository, *, clock=None) -> None:
        self.repository = repository
        self._now = clock or (lambda: datetime.now(timezone.utc))

    # -- read ----------------------------------------------------------------

    def status(self) -> LaunchStatus:
        """What every caller -- the public endpoint, the admin panel, the gate
        itself -- reads. `seconds_remaining` is filled in here so there is one
        clock and it is this one."""
        stored = self.repository.read()
        if stored is None:
            return LaunchStatus(state=LaunchState.OPEN)
        if stored.state is not LaunchState.COUNTING or stored.countdown_ends_at is None:
            return stored
        remaining = (_aware(stored.countdown_ends_at) - self._now()).total_seconds()
        # Clamped at zero: a countdown that ran out reads "0.0", never a
        # negative number the UI would have to interpret. "Elapsed" is
        # countdown_elapsed's job, not the sign of this field's.
        return _replace(stored, seconds_remaining=max(0.0, remaining))

    def is_open(self) -> bool:
        return self.status().is_open

    # -- transitions ---------------------------------------------------------

    def arm(self, *, admin_id: int | None = None,
            countdown_seconds: int = DEFAULT_COUNTDOWN_SECONDS) -> LaunchStatus:
        """Shut the doors ahead of the event, from `open` or from a countdown
        being aborted. Idempotent: arming an already-armed gate re-states the
        countdown length rather than complaining, because the only reason to
        press it twice is to change that number."""
        current = self.status()
        if current.state is LaunchState.LAUNCHED:
            raise AlreadyLaunchedError()
        seconds = _validate_seconds(countdown_seconds)
        return self._write(LaunchStatus(state=LaunchState.ARMED,
                                        countdown_seconds=seconds), admin_id)

    def start_countdown(self, *, admin_id: int | None = None,
                        countdown_seconds: int | None = None) -> LaunchStatus:
        """Start the shared clock.

        A second press while it is already running is deliberately NOT a
        restart -- it returns the countdown in flight untouched. On the day,
        the button is pressed by somebody in front of a room, and a
        double-click (or two people pressing at once, or a retried request on
        a flaky connection) putting the clock back to ten would be visible to
        everybody watching and impossible to explain. Restarting is what
        abort-then-start is for, and that is two deliberate presses.
        """
        current = self.status()
        if current.state is LaunchState.LAUNCHED:
            raise AlreadyLaunchedError()
        if current.state is LaunchState.COUNTING:
            return current
        seconds = _validate_seconds(
            current.countdown_seconds if countdown_seconds is None else countdown_seconds)
        now = self._now()
        return self._write(
            LaunchStatus(state=LaunchState.COUNTING, countdown_seconds=seconds,
                         countdown_ends_at=now + timedelta(seconds=seconds)), admin_id)

    def abort(self, *, admin_id: int | None = None) -> LaunchStatus:
        """Stop the clock, doors still shut. The abort window is the reason
        the countdown exists; this is what it is for."""
        current = self.status()
        if current.state is LaunchState.LAUNCHED:
            raise AlreadyLaunchedError()
        if current.state is not LaunchState.COUNTING:
            raise LaunchNotArmedError(current.state, "start a countdown")
        return self._write(LaunchStatus(state=LaunchState.ARMED,
                                        countdown_seconds=current.countdown_seconds),
                           admin_id)

    def launch(self, *, admin_id: int | None = None) -> LaunchStatus:
        """Open the platform to everyone. The irreversible one.

        Idempotent rather than repeatable: a second call returns the first
        launch unchanged, so a double-click cannot rewrite who launched or
        when. The audit trail's `launched_by` names the person who actually
        did it.
        """
        current = self.status()
        if current.state is LaunchState.LAUNCHED:
            return current
        if current.state is not LaunchState.COUNTING:
            raise LaunchNotArmedError(current.state, "start the countdown")
        if not current.countdown_elapsed:
            raise CountdownRunningError(current.seconds_remaining or 0.0)
        now = self._now()
        return self._write(
            LaunchStatus(state=LaunchState.LAUNCHED,
                         countdown_seconds=current.countdown_seconds,
                         launched_at=now, launched_by=admin_id), admin_id)

    def _write(self, status: LaunchStatus, admin_id: int | None) -> LaunchStatus:
        written = self.repository.write(status, admin_id=admin_id, at=self._now())
        logger.info("launch_state_changed",
                    extra={"state": written.state.value, "admin_id": admin_id})
        # Re-read through status() so a countdown comes back with its
        # seconds_remaining already filled in, exactly as a poll would see it.
        return self.status()


def _replace(status: LaunchStatus, **changes) -> LaunchStatus:
    from dataclasses import replace
    return replace(status, **changes)


def _aware(value: datetime) -> datetime:
    """Postgres hands back tz-aware datetimes; SQLite (tests) hands back naive
    ones for the same column. Arithmetic against a tz-aware `now` raises on
    the naive case, so naive values are read as UTC -- which is what they are,
    everything here is written in UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _validate_seconds(seconds: int) -> int:
    if not MIN_COUNTDOWN_SECONDS <= seconds <= MAX_COUNTDOWN_SECONDS:
        raise AppError(
            f"Countdown must be between {MIN_COUNTDOWN_SECONDS} and "
            f"{MAX_COUNTDOWN_SECONDS} seconds.", status_code=422)
    return seconds


def build_launch_service(repository: LaunchRepository | None = None, *,
                         clock=None) -> LaunchService:
    return LaunchService(repository or InMemoryLaunchRepository(), clock=clock)
