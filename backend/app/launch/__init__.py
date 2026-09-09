"""Go-live gate -- the one-time moment the platform opens to everyone.

Three states, one row, one direction of travel:

    armed  --start_countdown-->  counting  --launch-->  launched
      ^                              |
      +---------abort----------------+

`launched` is terminal. There is deliberately no un-launch: this models a
public go-live, and "we opened, then we closed again" is not a state the
product has. Closing the door after founders are inside is a different
decision (maintenance mode / a feature flag), taken deliberately, not by
reversing a launch. See LaunchService.launch for how that is enforced.

Why a countdown at all, rather than one button: the countdown is the part
everybody watching sees. It gives the room a shared clock, and it gives
whoever is holding the button a bounded window to abort before the thing
becomes irreversible. The clock is authoritative on the server -- every
viewer polls the same `seconds_remaining` rather than running their own
timer from their own wall clock, which would otherwise drift apart across
the room by exactly as much as their laptops disagree.

Launching is gated on the countdown having actually run out. That is the
single reason the countdown is state and not a frontend animation: an
animation can be skipped with a page refresh, a server-side deadline cannot.
"""

from app.launch.service import (
    AlreadyLaunchedError,
    CountdownRunningError,
    InMemoryLaunchRepository,
    LaunchNotArmedError,
    LaunchRepository,
    LaunchService,
    LaunchStateRow,
    LaunchStatus,
    LaunchState,
    SqlAlchemyLaunchRepository,
    build_launch_service,
)

__all__ = [
    "AlreadyLaunchedError",
    "CountdownRunningError",
    "InMemoryLaunchRepository",
    "LaunchNotArmedError",
    "LaunchRepository",
    "LaunchService",
    "LaunchStateRow",
    "LaunchStatus",
    "LaunchState",
    "SqlAlchemyLaunchRepository",
    "build_launch_service",
]
