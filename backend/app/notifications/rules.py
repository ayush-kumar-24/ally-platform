"""What a founder should be told, worked out from the state they are in.

TWO KINDS OF NOTIFICATION, AND ONLY ONE LIVES HERE.

  ONE-OFF events -- your report is ready, your payment failed, your call was
  confirmed -- are written at the moment they happen, by the code that made them
  happen. Those calls live next to the event, not here. Discovering "a payment
  failed four hours ago" by polling would be a worse product.

  STANDING conditions -- credits expiring, a task overdue, a profile still
  missing a field, an account deletion counting down -- have no moment. They are
  simply true today and were not true last week. Nothing fires when they become
  true, so something has to look. That is this file.

EVERY RULE IS IDEMPOTENT. Each returns a dedup key that says when it may repeat:
per day for "tasks due today", per expiry date for "credits expiring", once ever
for "your first impression is ready". Running the sweep twice in a minute writes
nothing the second time, which is what makes it safe to run this both on a timer
AND every time a founder opens the bell.

EVERY RULE IS DEFENSIVE. A rule reads tables that may be absent on a given
target (support_bot_misses on an un-migrated database, last_active_at on an old
one). One rule that raises must not stop the other twenty from running, so the
runner catches per rule.

WRITTEN IN RAW SQL, deliberately. These are narrow reads across a dozen tables
that mostly do not have ORM models in this codebase (planning_tasks, credits,
daily_actions are separate modules), and a rule is easier to check for
correctness when the query it runs is sitting there in the file.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Candidate:
    """One notification a rule thinks should exist."""
    type: str
    title: str
    body: str
    dedup_key: str
    action_url: str | None = None


def _today() -> str:
    return date.today().isoformat()


def _one(db: Session, sql: str, **params):
    return db.execute(text(sql), params).first()


# --- credits and usage ------------------------------------------------------

def credits_expiring(db: Session, founder_id: int) -> list[Candidate]:
    """Monthly credits that vanish on a date, while there are still some left.

    Keyed on the expiry date, so it fires once per cycle rather than once per
    sweep -- and fires again next month, which is correct.
    """
    row = _one(db, """
        select monthly_credits, credits_expires_at
          from founders
         where founder_id = :fid
           and coalesce(monthly_credits, 0) > 0
           and credits_expires_at is not null
           and credits_expires_at between now() and now() + interval '5 days'
    """, fid=founder_id)
    if not row:
        return []
    credits, expires = row
    when = expires.date().isoformat()
    days = (expires.date() - date.today()).days
    when_words = "today" if days <= 0 else "tomorrow" if days == 1 else f"in {days} days"
    plural = "s" if credits != 1 else ""
    return [Candidate(
        type="credits_expiring",
        title=f"{credits} credit{plural} expire{'' if credits != 1 else 's'} {when_words}",
        body=(f"You have {credits} credit{plural} left this cycle and they expire {when_words}. "
              "They do not roll over, so it is worth using them."),
        dedup_key=f"credits_expiring:{when}",
        action_url="/app/ally-chat",
    )]


def credits_low(db: Session, founder_id: int) -> list[Candidate]:
    row = _one(db, """
        select credits_balance
          from founders
         where founder_id = :fid
           and credits_balance is not null
           and credits_balance > 0
           and credits_balance <= 10
    """, fid=founder_id)
    if not row:
        return []
    # Keyed to the week, not the day: a balance sitting at 4 for a fortnight
    # should say so once, not fourteen times.
    week = date.today().strftime("%G-W%V")
    n = row[0]
    return [Candidate(
        type="credits_low",
        title=f"{n} credit{'s' if n != 1 else ''} left",
        body="Your credit balance is running low. You can top up from Billing.",
        dedup_key=f"credits_low:{week}",
        action_url="/app/billing",
    )]


# --- plan and payment -------------------------------------------------------

def subscription_expiring(db: Session, founder_id: int) -> list[Candidate]:
    row = _one(db, """
        select plan_type, expires_at
          from subscriptions
         where founder_id = :fid
           and status = 'active'
           and expires_at between now() and now() + interval '7 days'
         order by expires_at asc
         limit 1
    """, fid=founder_id)
    if not row:
        return []
    plan, expires = row
    days = (expires.date() - date.today()).days
    when = "today" if days <= 0 else "tomorrow" if days == 1 else f"in {days} days"
    return [Candidate(
        type="subscription_expiring",
        title=f"Your {plan} plan renews {when}",
        body=f"Your {plan} plan renews {when}. Nothing to do unless you want to change it.",
        dedup_key=f"subscription_expiring:{expires.date().isoformat()}",
        action_url="/app/billing",
    )]


# --- account deletion -- the highest-stakes one -----------------------------

def deletion_grace_ending(db: Session, founder_id: int) -> list[Candidate]:
    """The account deletes soon and can still be stopped.

    Repeats DAILY on purpose, unlike everything else here. This is the one
    notification where being ignored is irreversible, so a founder who changed
    their mind gets a fresh chance every day rather than one easily-missed row.
    """
    row = _one(db, """
        select grace_period_ends_at
          from data_deletion_requests
         where founder_id = :fid
           and status = 'grace_period'
           and grace_period_ends_at > now()
         order by grace_period_ends_at asc
         limit 1
    """, fid=founder_id)
    if not row:
        return []
    ends = row[0]
    days = (ends.date() - date.today()).days
    when = "today" if days <= 0 else "tomorrow" if days == 1 else f"in {days} days"
    return [Candidate(
        type="account_deletion_grace",
        title=f"Your account is deleted {when}",
        body=("You asked us to delete your account. Everything goes permanently "
              f"{when} and cannot be recovered afterwards. If you have changed your "
              "mind, you can still cancel."),
        dedup_key=f"account_deletion_grace:{_today()}",
        action_url="/app/profile",
    )]


# --- tasks and daily actions ------------------------------------------------

def tasks_due_today(db: Session, founder_id: int) -> list[Candidate]:
    row = _one(db, """
        select count(*)
          from planning_tasks
         where founder_id = :fid
           and due_date = current_date
           and coalesce(status, '') <> 'done'
           and completed_at is null
    """, fid=founder_id)
    n = row[0] if row else 0
    if not n:
        return []
    return [Candidate(
        type="task_due_today",
        title=f"{n} task{'s' if n > 1 else ''} due today",
        body="Open Plan Your Day to see what you set for yourself.",
        dedup_key=f"task_due_today:{_today()}",
        action_url="/app/plan",
    )]


def tasks_overdue(db: Session, founder_id: int) -> list[Candidate]:
    row = _one(db, """
        select count(*)
          from planning_tasks
         where founder_id = :fid
           and due_date < current_date
           and coalesce(status, '') <> 'done'
           and completed_at is null
    """, fid=founder_id)
    n = row[0] if row else 0
    if not n:
        return []
    # Weekly, not daily. An overdue pile is usually a sign the plan was wrong,
    # and telling someone about it every morning is nagging, not helping.
    week = date.today().strftime("%G-W%V")
    return [Candidate(
        type="task_overdue",
        title=f"{n} task{'s are' if n > 1 else ' is'} overdue",
        body=("Worth a look -- either they still matter and need a new date, or "
              "they do not and can go."),
        dedup_key=f"task_overdue:{week}",
        action_url="/app/plan",
    )]


def goal_deadline_near(db: Session, founder_id: int) -> list[Candidate]:
    row = _one(db, """
        select title, target_date
          from planning_goals
         where founder_id = :fid
           and target_date between current_date and current_date + 7
           and completed_at is null
           and coalesce(status, '') <> 'done'
         order by target_date asc
         limit 1
    """, fid=founder_id)
    if not row:
        return []
    title, target = row
    days = (target - date.today()).days
    when = "today" if days <= 0 else "tomorrow" if days == 1 else f"in {days} days"
    return [Candidate(
        type="goal_deadline_near",
        title=f"Goal due {when}",
        body=f"“{title}” is due {when}.",
        dedup_key=f"goal_deadline_near:{target.isoformat()}",
        action_url="/app/goals",
    )]


# --- diagnosis and profile --------------------------------------------------

def diagnosis_unfinished(db: Session, founder_id: int) -> list[Candidate]:
    """Started, answered something, then stopped for a day or more."""
    row = _one(db, """
        select session_id, last_activity_at
          from sessions
         where founder_id = :fid
           and status = 'in_progress'
           and coalesce(questions_answered_count, 0) > 0
           and last_activity_at < now() - interval '24 hours'
         order by last_activity_at desc
         limit 1
    """, fid=founder_id)
    if not row:
        return []
    # Weekly: someone who put it down deliberately should not be asked daily.
    week = date.today().strftime("%G-W%V")
    return [Candidate(
        type="diagnosis_incomplete",
        title="Your diagnosis is waiting",
        body=("You started your diagnosis and stopped partway. Your answers are "
              "saved -- you can pick up exactly where you left off."),
        dedup_key=f"diagnosis_incomplete:{week}",
        action_url="/app/diagnosis",
    )]


def profile_incomplete(db: Session, founder_id: int) -> list[Candidate]:
    """Names the exact thing that is missing.

    "Complete your profile" is ignorable; "we still need your industry" is a
    thirty-second job. `profile_progress` already works out which fields are
    outstanding, so this reuses it rather than duplicating the rules.
    """
    row = _one(db, """
        select profile_completed, current_problem_completed_at
          from founders where founder_id = :fid
    """, fid=founder_id)
    if not row or row[0]:
        return []

    missing_label = "a few details"
    try:
        from app.services.profile_progress import missing_required_fields
        missing = missing_required_fields(db, founder_id)          # type: ignore[misc]
        if missing:
            missing_label = missing[0] if len(missing) == 1 else f"{len(missing)} details"
    except Exception:
        # profile_progress may not expose that helper; the generic wording is
        # still true and this rule is not worth breaking over.
        pass

    week = date.today().strftime("%G-W%V")
    return [Candidate(
        type="profile_incomplete",
        title="Your profile needs finishing",
        body=(f"Ally still needs {missing_label} before it can tailor your "
              "diagnosis properly."),
        dedup_key=f"profile_incomplete:{week}",
        action_url="/app/profile",
    )]


# --- recommendations --------------------------------------------------------

def suggestions_unread(db: Session, founder_id: int) -> list[Candidate]:
    row = _one(db, """
        select count(*)
          from suggestions
         where founder_id = :fid
           and status = 'active'
           and feedback = 'pending'
           and priority in ('high', 'critical')
    """, fid=founder_id)
    n = row[0] if row else 0
    if not n:
        return []
    week = date.today().strftime("%G-W%V")
    return [Candidate(
        type="suggestions_unread",
        title=f"{n} suggestion{'s' if n > 1 else ''} waiting",
        body="Ally raised something it thinks matters. Worth two minutes.",
        dedup_key=f"suggestions_unread:{week}",
        action_url="/app/recommendations",
    )]


# --- calendar ---------------------------------------------------------------

def calendar_sync_broken(db: Session, founder_id: int) -> list[Candidate]:
    """Only for `revoked` -- a real disconnection needing the founder to act.

    `error` is transient and usually fixes itself on the next sync; telling a
    founder about it would be reporting our own retry to them.
    """
    row = _one(db, """
        select status from calendar_connections
         where founder_id = :fid and status = 'revoked'
         limit 1
    """, fid=founder_id)
    if not row:
        return []
    week = date.today().strftime("%G-W%V")
    return [Candidate(
        type="calendar_sync_broken",
        title="Calendar disconnected",
        body="Ally can no longer reach your calendar, so tasks are not syncing. Reconnect it in Settings.",
        dedup_key=f"calendar_sync_broken:{week}",
        action_url="/app/profile",
    )]


# --- report -----------------------------------------------------------------

def report_ready(db: Session, founder_id: int) -> list[Candidate]:
    """A report exists that the founder has not been told about.

    DETECTED RATHER THAN FIRED AT GENERATION TIME, unlike the other one-off
    events. Reports are written from several paths -- the normal diagnosis flow,
    an admin regeneration, a backfill -- and a rule keyed on `report_id` covers
    all of them and can never fire twice, where a hook would have to be added to
    each path and would be forgotten on the next one.

    The cost is a short delay: it appears on the next sweep or the next time the
    founder opens the bell, not the same millisecond. That is fine -- a founder
    watching their report generate is already looking at it, and this is for the
    one who walked away.

    Only recent reports, so switching this on does not fill every long-standing
    founder's bell with news about a report they read months ago.
    """
    row = _one(db, """
        select report_id
          from founder_reports
         where founder_id = :fid
           and is_active = true
           and generated_at > now() - interval '14 days'
         order by generated_at desc
         limit 1
    """, fid=founder_id)
    if not row:
        return []
    return [Candidate(
        type="report_ready",
        title="Your report is ready",
        body="Ally has finished your diagnosis report -- the root cause it found, and what to do about it.",
        dedup_key=f"report_ready:{row[0]}",
        action_url="/app/report",
    )]


def report_pdf_ready(db: Session, founder_id: int) -> list[Candidate]:
    row = _one(db, """
        select report_id
          from founder_reports
         where founder_id = :fid
           and pdf_storage_key is not null
           and pdf_requested_at is not null
           and pdf_requested_at > now() - interval '14 days'
         order by pdf_requested_at desc
         limit 1
    """, fid=founder_id)
    if not row:
        return []
    return [Candidate(
        type="report_pdf_ready",
        title="Your report PDF is ready",
        body="The PDF you asked for has finished and can be downloaded.",
        dedup_key=f"report_pdf_ready:{row[0]}",
        action_url="/app/report",
    )]


#: Every standing-condition rule. Order is the order they appear in the bell on
#: a first sweep, so the consequential ones come first.
ALL_RULES = (
    deletion_grace_ending,
    report_ready,
    report_pdf_ready,
    subscription_expiring,
    credits_expiring,
    credits_low,
    tasks_due_today,
    tasks_overdue,
    goal_deadline_near,
    diagnosis_unfinished,
    profile_incomplete,
    suggestions_unread,
    calendar_sync_broken,
)
