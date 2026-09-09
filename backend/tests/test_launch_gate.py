"""The launch gate -- the one-time go-live moment.

The rules worth protecting here are the ones that only matter on the single
day this code runs in anger, which is exactly when nobody will be reading it:
the platform stays open until somebody deliberately closes it, the countdown
is a real gate rather than an animation, and a launch cannot be replayed.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.launch import (
    AlreadyLaunchedError,
    CountdownRunningError,
    InMemoryLaunchRepository,
    LaunchNotArmedError,
    LaunchState,
    LaunchStatus,
    build_launch_service,
)
from app.middleware.error_handler import AppError

T0 = datetime(2026, 9, 9, 18, 0, tzinfo=timezone.utc)


class Clock:
    """A hand-wound clock. The whole feature is about time, so no test here
    may depend on how long it took to run."""

    def __init__(self, now: datetime = T0) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def service(clock: Clock | None = None, status: LaunchStatus | None = None):
    return build_launch_service(InMemoryLaunchRepository(status), clock=clock or Clock())


# ── the default: no gate ────────────────────────────────────────────────────


def test_default_is_open():
    """Deploying the gate must not close the platform. This is the single most
    important assertion in the file: the alternative is a migration signing
    every founder out of a product that was working a second earlier."""
    s = service()
    assert s.status().state is LaunchState.OPEN
    assert s.is_open() is True


def test_missing_state_reads_as_open():
    """The gate FAILS OPEN, unlike feature flags next door. A repository that
    cannot answer (table not migrated yet, database unreachable) must leave a
    live platform serving, not put a holding screen in front of it."""

    class Unreadable(InMemoryLaunchRepository):
        def read(self):
            return None

    s = build_launch_service(Unreadable(), clock=Clock())
    assert s.is_open() is True
    assert s.status().state is LaunchState.OPEN


# ── arming ──────────────────────────────────────────────────────────────────


def test_arm_closes_the_platform():
    s = service()
    status = s.arm(admin_id=1)
    assert status.state is LaunchState.ARMED
    assert s.is_open() is False


def test_arm_is_idempotent_and_resets_the_countdown_length():
    """Pressing arm twice is how the agreed countdown length gets changed, so
    it restates rather than complains."""
    s = service()
    s.arm(admin_id=1, countdown_seconds=10)
    assert s.arm(admin_id=1, countdown_seconds=30).countdown_seconds == 30


@pytest.mark.parametrize("seconds", [0, 2, 301, -5])
def test_countdown_length_is_bounded(seconds):
    with pytest.raises(AppError):
        service().arm(admin_id=1, countdown_seconds=seconds)


# ── the countdown ───────────────────────────────────────────────────────────


def test_countdown_runs_on_the_server_clock():
    clock = Clock()
    s = service(clock)
    s.arm(admin_id=1, countdown_seconds=10)

    started = s.start_countdown(admin_id=1)
    assert started.state is LaunchState.COUNTING
    assert started.seconds_remaining == pytest.approx(10.0)
    assert started.countdown_ends_at == T0 + timedelta(seconds=10)

    clock.advance(4)
    assert s.status().seconds_remaining == pytest.approx(6.0)


def test_countdown_keeps_the_platform_closed():
    s = service()
    s.arm(admin_id=1)
    s.start_countdown(admin_id=1)
    assert s.is_open() is False


def test_seconds_remaining_is_clamped_at_zero():
    """Never negative: the holding screen shows this number to a room, and
    "-3" is not a countdown."""
    clock = Clock()
    s = service(clock)
    s.arm(admin_id=1, countdown_seconds=10)
    s.start_countdown(admin_id=1)
    clock.advance(45)
    assert s.status().seconds_remaining == 0.0


def test_second_press_does_not_restart_the_clock():
    """A double-click in front of a room must not put the countdown everybody
    is reading aloud back to ten."""
    clock = Clock()
    s = service(clock)
    s.arm(admin_id=1, countdown_seconds=10)
    s.start_countdown(admin_id=1)
    clock.advance(7)

    again = s.start_countdown(admin_id=1)
    assert again.seconds_remaining == pytest.approx(3.0)
    assert again.countdown_ends_at == T0 + timedelta(seconds=10)


def test_countdown_can_start_from_open_without_arming_first():
    """Arming is a convenience for staging the event, not a required step --
    the countdown is what actually closes the doors."""
    s = service()
    assert s.start_countdown(admin_id=1).state is LaunchState.COUNTING


def test_start_countdown_honours_an_explicit_length_over_the_armed_one():
    s = service()
    s.arm(admin_id=1, countdown_seconds=10)
    assert s.start_countdown(admin_id=1, countdown_seconds=20).seconds_remaining == \
        pytest.approx(20.0)


# ── abort ───────────────────────────────────────────────────────────────────


def test_abort_stops_the_clock_and_keeps_the_doors_shut():
    clock = Clock()
    s = service(clock)
    s.arm(admin_id=1)
    s.start_countdown(admin_id=1)
    clock.advance(3)

    aborted = s.abort(admin_id=1)
    assert aborted.state is LaunchState.ARMED
    assert aborted.seconds_remaining is None
    assert s.is_open() is False


def test_abort_then_restart_gives_a_full_countdown():
    clock = Clock()
    s = service(clock)
    s.arm(admin_id=1, countdown_seconds=10)
    s.start_countdown(admin_id=1)
    clock.advance(8)
    s.abort(admin_id=1)

    assert s.start_countdown(admin_id=1).seconds_remaining == pytest.approx(10.0)


def test_abort_requires_a_running_countdown():
    with pytest.raises(LaunchNotArmedError):
        service().abort(admin_id=1)


# ── launching ───────────────────────────────────────────────────────────────


def test_launch_is_refused_while_the_countdown_runs():
    """The abort window is the reason the countdown exists. This is the
    assertion that makes it a gate rather than an animation."""
    clock = Clock()
    s = service(clock)
    s.arm(admin_id=1, countdown_seconds=10)
    s.start_countdown(admin_id=1)
    clock.advance(9)

    with pytest.raises(CountdownRunningError):
        s.launch(admin_id=1)
    assert s.is_open() is False


def test_launch_is_refused_without_a_countdown():
    s = service()
    s.arm(admin_id=1)
    with pytest.raises(LaunchNotArmedError):
        s.launch(admin_id=1)


def test_launch_opens_the_platform_once_the_countdown_elapses():
    clock = Clock()
    s = service(clock)
    s.arm(admin_id=1, countdown_seconds=10)
    s.start_countdown(admin_id=1)
    clock.advance(10)

    launched = s.launch(admin_id=42)
    assert launched.state is LaunchState.LAUNCHED
    assert launched.launched_at == T0 + timedelta(seconds=10)
    assert launched.launched_by == 42
    assert s.is_open() is True


def _launched(clock: Clock):
    s = service(clock)
    s.arm(admin_id=1, countdown_seconds=10)
    s.start_countdown(admin_id=1)
    clock.advance(10)
    s.launch(admin_id=42)
    return s


def test_launching_twice_does_not_rewrite_who_launched_or_when():
    """Idempotent, not repeatable -- a double-click cannot take credit for
    somebody else's launch, or move its timestamp."""
    clock = Clock()
    s = _launched(clock)
    clock.advance(600)

    again = s.launch(admin_id=99)
    assert again.launched_by == 42
    assert again.launched_at == T0 + timedelta(seconds=10)


@pytest.mark.parametrize("action", ["arm", "start_countdown", "abort"])
def test_nothing_reopens_the_gate_after_launch(action):
    """`launched` is terminal. Putting a live platform back behind a countdown
    would sign founders out of something they are mid-way through, and the
    holding screen would be a lie -- there is nothing left to wait for."""
    s = _launched(Clock())
    with pytest.raises(AlreadyLaunchedError):
        getattr(s, action)(admin_id=1)


def test_launch_survives_a_naive_stored_deadline():
    """Postgres returns tz-aware datetimes for this column and SQLite returns
    naive ones. Everything here is written in UTC, so a naive deadline must be
    read as UTC rather than raising mid-countdown."""
    clock = Clock()
    naive_deadline = (T0 - timedelta(seconds=1)).replace(tzinfo=None)
    s = service(clock, LaunchStatus(state=LaunchState.COUNTING, countdown_seconds=10,
                                    countdown_ends_at=naive_deadline))
    assert s.status().seconds_remaining == 0.0
    assert s.launch(admin_id=7).state is LaunchState.LAUNCHED
