"""Go-live gate -- the moment the platform opens to everyone, rehearsable.

Four states, one row:

    armed  --start_countdown-->  counting  --launch-->  launched
      ^                              |                      |
      +---------abort----------------+                      |
      +--------- reset (spends one launch) -----------------+

`launched` is NOT terminal until the allowance runs out. The platform may be
launched a small, fixed number of times -- two rehearsals and the real thing
by default -- and `reset` is the only way back out. Once the last launch is
spent, `reset` is refused and the state is final after all.

That budget is the safety property. An un-launch with no limit is a toggle,
and a toggle eventually gets pressed on a platform full of founders
mid-diagnosis. A bounded allowance buys the practice runs and still
guarantees the launch everybody remembers cannot be taken back, because by
then there is nothing left to spend. See LaunchService.reset.

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
    LaunchAllowanceSpentError,
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
    "LaunchAllowanceSpentError",
    "LaunchNotArmedError",
    "LaunchRepository",
    "LaunchService",
    "LaunchStateRow",
    "LaunchStatus",
    "LaunchState",
    "SqlAlchemyLaunchRepository",
    "build_launch_service",
]
