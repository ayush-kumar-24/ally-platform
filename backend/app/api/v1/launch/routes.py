"""The launch gate's public read -- the only endpoint every visitor polls.

    GET /launch/status

Unauthenticated by design, like the waitlist form next door: the people who
most need this answer are the ones who cannot get in yet, and they have no
token to present. It discloses nothing but whether the platform is open and
how many seconds are left on a clock that is about to be shown to a room.

Deliberately cheap: one indexed primary-key read, no founder context, no
plan lookup. Every open browser hits it on a short poll for the length of
the countdown, and launch day is exactly when that traffic peaks.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.container import container
from app.db.session import get_db

router = APIRouter(prefix="/launch", tags=["launch"])


class LaunchStatusResponse(BaseModel):
    # What the gate actually decides on. Everything else in this body is for
    # the holding screen to render; a client that only understands this field
    # still behaves correctly.
    is_open: bool
    state: str
    countdown_seconds: int
    seconds_remaining: float | None = None
    countdown_ends_at: datetime | None = None
    launched_at: datetime | None = None


@router.get("/status", response_model=LaunchStatusResponse,
            summary="Whether the platform is open, and the countdown if one is running")
def launch_status(response: Response, db: Session = Depends(get_db)) -> LaunchStatusResponse:
    # No-store, not a short max-age: a CDN or browser holding this for even a
    # few seconds is a room full of people whose countdowns disagree, and a
    # founder still looking at a holding screen after the platform opened.
    response.headers["Cache-Control"] = "no-store"
    status = container.launch_service(db).status()
    return LaunchStatusResponse(
        is_open=status.is_open,
        state=status.state.value,
        countdown_seconds=status.countdown_seconds,
        seconds_remaining=status.seconds_remaining,
        countdown_ends_at=status.countdown_ends_at,
        launched_at=status.launched_at,
    )
