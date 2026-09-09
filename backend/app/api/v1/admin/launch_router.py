"""Launch control -- the four buttons behind the go-live ceremony.

    GET  /admin/launch            current state (any admin may watch)
    POST /admin/launch/arm        close the doors ahead of the event
    POST /admin/launch/countdown  start the shared clock
    POST /admin/launch/abort      stop the clock, doors still shut
    POST /admin/launch/launch     open to everyone -- spends one launch
    POST /admin/launch/reset      close it again, so the ceremony can be rehearsed

Every mutation needs SYSTEM_SETTINGS, which is Super Admin only. That is not
caution for its own sake: launching is the single most public action in the
panel, and the whole product is downstream of it.

Reset is bounded, not free. The platform may be launched a small, fixed
number of times and the last one is final -- see app/launch/__init__.py for
why the budget, and not an unlimited toggle, is what makes the rest safe.
Watching the state is VIEW_USERS, so the rest of the team can follow along
on the day without being able to press anything.

Each press is written to the admin audit trail before the response is
returned, so "who launched the platform, from where, at what second" is
answerable from the same log as every other admin action rather than from
somebody's memory of the room.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.admin.rbac import Capability, require
from app.api.v1.admin.panel_dependencies import (
    PanelAdmin,
    client_ip,
    get_panel_admin,
    get_panel_service,
)
from app.core.container import container
from app.db.session import get_db
from app.launch import LaunchStatus
from app.launch.service import (
    DEFAULT_COUNTDOWN_SECONDS,
    MAX_COUNTDOWN_SECONDS,
    MIN_COUNTDOWN_SECONDS,
)

router = APIRouter(prefix="/admin/launch", tags=["admin-launch"])


class CountdownRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Optional: omitted keeps whatever the gate was armed with, so the number
    # agreed beforehand is not re-decided by whoever happens to press start.
    countdown_seconds: int | None = Field(
        default=None, ge=MIN_COUNTDOWN_SECONDS, le=MAX_COUNTDOWN_SECONDS)


class ArmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    countdown_seconds: int = Field(
        default=DEFAULT_COUNTDOWN_SECONDS, ge=MIN_COUNTDOWN_SECONDS,
        le=MAX_COUNTDOWN_SECONDS)


class LaunchStateResponse(BaseModel):
    is_open: bool
    state: str
    countdown_seconds: int
    seconds_remaining: float | None = None
    countdown_ends_at: datetime | None = None
    launched_at: datetime | None = None
    launched_by: int | None = None
    launch_count: int = 0
    max_launches: int = 0
    launches_remaining: int = 0
    # Whether the launch button is pressable right now. Computed here rather
    # than in the browser so the UI cannot arm its own button: the same rule
    # the service enforces is the one the panel renders.
    can_launch: bool = False
    # Same principle: whether the platform can still be closed again. Goes
    # false for good once the allowance is spent, and the panel reads it
    # rather than doing its own arithmetic on the counters.
    can_reset: bool = False


def _response(status: LaunchStatus) -> LaunchStateResponse:
    return LaunchStateResponse(
        is_open=status.is_open,
        state=status.state.value,
        countdown_seconds=status.countdown_seconds,
        seconds_remaining=status.seconds_remaining,
        countdown_ends_at=status.countdown_ends_at,
        launched_at=status.launched_at,
        launched_by=status.launched_by,
        launch_count=status.launch_count,
        max_launches=status.max_launches,
        launches_remaining=status.launches_remaining,
        can_launch=status.countdown_elapsed,
        can_reset=status.can_reset,
    )


@router.get("", response_model=LaunchStateResponse, summary="Current launch state")
def read_state(admin: PanelAdmin = Depends(get_panel_admin),
               db: Session = Depends(get_db)) -> LaunchStateResponse:
    require(admin.role, Capability.VIEW_USERS)
    return _response(container.launch_service(db).status())


@router.post("/arm", response_model=LaunchStateResponse,
             summary="Close the platform ahead of the launch (Super Admin)")
def arm(payload: ArmRequest, ip: str | None = Depends(client_ip),
        admin: PanelAdmin = Depends(get_panel_admin),
        service=Depends(get_panel_service),
        db: Session = Depends(get_db)) -> LaunchStateResponse:
    require(admin.role, Capability.SYSTEM_SETTINGS)
    launch = container.launch_service(db)
    before = launch.status()
    after = launch.arm(admin_id=admin.admin_id,
                       countdown_seconds=payload.countdown_seconds)
    service.audit.record(admin=admin, action="launch.arm", resource="launch",
                         ip_address=ip, old_value={"state": before.state.value},
                         new_value={"state": after.state.value,
                                    "countdown_seconds": after.countdown_seconds})
    return _response(after)


@router.post("/countdown", response_model=LaunchStateResponse,
             summary="Start the launch countdown (Super Admin)")
def start_countdown(payload: CountdownRequest, ip: str | None = Depends(client_ip),
                    admin: PanelAdmin = Depends(get_panel_admin),
                    service=Depends(get_panel_service),
                    db: Session = Depends(get_db)) -> LaunchStateResponse:
    require(admin.role, Capability.SYSTEM_SETTINGS)
    launch = container.launch_service(db)
    before = launch.status()
    after = launch.start_countdown(admin_id=admin.admin_id,
                                   countdown_seconds=payload.countdown_seconds)
    service.audit.record(admin=admin, action="launch.countdown", resource="launch",
                         ip_address=ip, old_value={"state": before.state.value},
                         new_value={"state": after.state.value,
                                    "ends_at": str(after.countdown_ends_at)})
    return _response(after)


@router.post("/abort", response_model=LaunchStateResponse,
             summary="Stop a running countdown (Super Admin)")
def abort(ip: str | None = Depends(client_ip),
          admin: PanelAdmin = Depends(get_panel_admin),
          service=Depends(get_panel_service),
          db: Session = Depends(get_db)) -> LaunchStateResponse:
    require(admin.role, Capability.SYSTEM_SETTINGS)
    launch = container.launch_service(db)
    before = launch.status()
    after = launch.abort(admin_id=admin.admin_id)
    service.audit.record(admin=admin, action="launch.abort", resource="launch",
                         ip_address=ip, old_value={"state": before.state.value,
                                                   "ends_at": str(before.countdown_ends_at)},
                         new_value={"state": after.state.value})
    return _response(after)


@router.post("/launch", response_model=LaunchStateResponse,
             summary="Open the platform to everyone -- irreversible (Super Admin)")
def launch_now(ip: str | None = Depends(client_ip),
               admin: PanelAdmin = Depends(get_panel_admin),
               service=Depends(get_panel_service),
               db: Session = Depends(get_db)) -> LaunchStateResponse:
    require(admin.role, Capability.SYSTEM_SETTINGS)
    launch = container.launch_service(db)
    before = launch.status()
    after = launch.launch(admin_id=admin.admin_id)
    # Recorded even when the call was a no-op re-press of an already-launched
    # gate: "somebody pressed launch again at 19:04" is exactly the kind of
    # thing the trail should be able to answer afterwards.
    service.audit.record(admin=admin, action="launch.launch", resource="launch",
                         ip_address=ip, old_value={"state": before.state.value},
                         new_value={"state": after.state.value,
                                    "launched_at": str(after.launched_at),
                                    "launched_by": after.launched_by})
    return _response(after)


@router.post("/reset", response_model=LaunchStateResponse,
             summary="Close a launched platform again for another rehearsal (Super Admin)")
def reset(ip: str | None = Depends(client_ip),
          admin: PanelAdmin = Depends(get_panel_admin),
          service=Depends(get_panel_service),
          db: Session = Depends(get_db)) -> LaunchStateResponse:
    """Takes a live platform back behind the gate. Refused once the launch
    allowance is spent, which is what keeps the final launch final.

    Audited with the counters on both sides, because "how many launches are
    left" is the question somebody will ask afterwards and the state itself
    only ever shows the answer now.
    """
    require(admin.role, Capability.SYSTEM_SETTINGS)
    launch = container.launch_service(db)
    before = launch.status()
    after = launch.reset(admin_id=admin.admin_id)
    service.audit.record(admin=admin, action="launch.reset", resource="launch",
                         ip_address=ip,
                         old_value={"state": before.state.value,
                                    "launches_remaining": before.launches_remaining},
                         new_value={"state": after.state.value,
                                    "launches_remaining": after.launches_remaining})
    return _response(after)
