"""The seam between Plan Your Day and Google Calendar.

Why this lives here and not in PlanningService: that service is pure domain
logic over an injected repository, and the hermetic test suite runs it against
an in-memory implementation with no network and no database. Putting an HTTP
call to Google inside it would make the domain layer untestable without mocking
Google, and would couple "what is a task" to "what is a calendar event".

So the router calls these after the task is already safely written. By the time
anything here runs, the founder's data is committed. That ordering is the whole
safety property, and it is why every function returns rather than raises:

    task = service.add_task(...)        # committed -- cannot be undone by us
    task = hooks.after_task_saved(...)  # best effort; worst case a badge

`db.rollback()` on failure is deliberate and important. A sync attempt can leave
the session dirty (a failed flush while marking a connection errored), and an
exception escaping into the request would roll back the *task* the founder just
created. We own the mess we make and hand back a clean session.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.calendar_sync import sync
from app.core.logger import logger
from app.planning.models import Task
from app.planning.service import PlanningService


def after_task_saved(db: Session, service: PlanningService, task: Task,
                     *, timezone_name: str = "UTC") -> Task:
    """Push a created or edited task to the calendar and record the outcome.

    Returns the task with its sync status filled in -- the same object when
    nothing was attempted, so callers can use the result unconditionally.
    """
    try:
        status, event_id = sync.push_task(
            db, task.founder_id,
            task_id=task.task_id, title=task.title,
            due_date=task.due_date, due_time=task.due_time,
            existing_event_id=task.calendar_event_id,
            timezone_name=timezone_name,
        )
        # Nothing changed -- don't spend a write. The common case by far is a
        # founder with no calendar connected adding a dateless task.
        if status == task.calendar_sync_status and event_id == task.calendar_event_id:
            return task
        return service.record_calendar_sync(
            task.founder_id, task.task_id, status=status, event_id=event_id)

    except Exception as exc:
        # Belt and braces: sync.push_task already swallows its own failures, so
        # reaching here means something unexpected broke -- recording the status
        # itself, most likely. The task is still saved either way.
        logger.warning("calendar sync hook failed after task save",
                       extra={"founder_id": task.founder_id, "task_id": task.task_id},
                       exc_info=exc)
        db.rollback()
        return task


def before_task_deleted(db: Session, task: Task) -> None:
    """Remove the task's calendar event, if it has one.

    Called BEFORE the task row goes away, because the event id lives on it. A
    failure here is logged and ignored: the founder asked to delete a task, and
    refusing because Google is unreachable would make an outage look like a bug
    in Ally. The cost of failing is one orphaned calendar entry, which they can
    delete themselves -- strictly better than a task that will not go away.
    """
    if not task.calendar_event_id:
        return
    try:
        if not sync.delete_event(db, task.founder_id, task.calendar_event_id):
            logger.info("calendar event left behind after task delete",
                        extra={"founder_id": task.founder_id,
                               "event_id": task.calendar_event_id})
    except Exception as exc:
        logger.warning("calendar event delete hook failed",
                       extra={"founder_id": task.founder_id,
                              "event_id": task.calendar_event_id}, exc_info=exc)
        db.rollback()
