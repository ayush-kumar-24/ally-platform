"""Check that email and the discovery-call calendar are actually configured.

    python -m app.jobs.verify_notifications
    python -m app.jobs.verify_notifications --send-to you@example.com

Run this the moment Resend and Google Workspace credentials are added. It answers
one question -- "will a founder who books a call actually get an email with a
working link?" -- without booking a call or emailing a founder to find out.

WHY THIS EXISTS. Every piece of this is designed to degrade quietly, which is
correct at runtime and useless when you are trying to find out whether it works:

  * send_email() returns False and logs in stub mode, so nothing raises
  * the calendar falls back to a shared Meet room, so bookings still succeed
  * reminders report cheerful zero counts when mail is off

All of that means a completely unconfigured deployment looks healthy. This is the
one place that says plainly what is missing.

It NEVER emails a founder. --send-to takes an explicit address and nothing else
sends.

EXIT CODES:
    0  everything needed for a working discovery call is configured
    1  something is missing or broken -- the report says which
"""

from __future__ import annotations

import argparse
import smtplib
import sys
from datetime import datetime, timedelta, timezone

from app.core.config import settings

OK, WARN, BAD = "PASS", "WARN", "FAIL"


class Report:
    """Collects results so the whole picture prints at once.

    Deliberately not fail-fast: someone adding credentials wants the full list of
    what is still missing, not the first thing that broke.
    """

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, state: str, name: str, detail: str = "") -> None:
        self.rows.append((state, name, detail))

    @property
    def failed(self) -> bool:
        return any(s == BAD for s, _, _ in self.rows)

    def render(self) -> None:
        width = max(len(n) for _, n, _ in self.rows) + 2
        for state, name, detail in self.rows:
            print(f"  [{state}] {name.ljust(width)} {detail}")


# --- email -------------------------------------------------------------------

def check_email(r: Report, send_to: str | None) -> None:
    print("\nEMAIL")
    if not settings.email_enabled:
        r.add(BAD, "EMAIL_HOST", "not set -- every email silently no-ops")
        return

    r.add(OK, "EMAIL_HOST", f"{settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
    r.add(OK if settings.EMAIL_FROM else BAD, "EMAIL_FROM", settings.EMAIL_FROM or "not set")

    if not settings.EMAIL_USER:
        r.add(WARN, "EMAIL_USER", "empty -- fine for an open relay, wrong for Resend/Gmail")
    else:
        r.add(OK, "EMAIL_USER", settings.EMAIL_USER)

    if not settings.EMAIL_PASSWORD:
        r.add(WARN, "EMAIL_PASSWORD", "empty")

    # Connect and authenticate for real. Config being present says nothing about
    # whether the credentials work, and a wrong API key looks identical to a
    # right one until something tries to send.
    try:
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=15) as s:
            if settings.EMAIL_USE_TLS:
                s.starttls()
            if settings.EMAIL_USER:
                s.login(settings.EMAIL_USER, settings.EMAIL_PASSWORD)
        r.add(OK, "SMTP connect + auth", "credentials accepted")
    except smtplib.SMTPAuthenticationError as exc:
        r.add(BAD, "SMTP connect + auth", f"rejected: {exc}")
        return
    except Exception as exc:  # noqa: BLE001 -- any failure here is a real failure
        r.add(BAD, "SMTP connect + auth", f"{type(exc).__name__}: {exc}")
        return

    if send_to:
        from app.services.email import send_email
        sent = send_email(
            send_to,
            "Ally: notification check",
            "If you are reading this, outbound email is working.\n\n"
            "Sent by python -m app.jobs.verify_notifications.",
        )
        r.add(OK if sent else BAD, "test send", f"to {send_to}" if sent else "send returned False")


# --- calendar ----------------------------------------------------------------

def check_calendar(r: Report) -> None:
    print("\nDISCOVERY CALL CALENDAR")
    if not settings.google_calendar_enabled:
        r.add(WARN, "Google Calendar", "not configured -- bookings use a stub meeting link")
        return

    r.add(OK, "GOOGLE_CALENDAR_ID", settings.GOOGLE_CALENDAR_ID)

    delegated = (settings.GOOGLE_CALENDAR_DELEGATED_USER or "").strip()
    if delegated:
        r.add(OK, "Delegated user", delegated)
    else:
        r.add(WARN, "Delegated user",
              "unset -- no per-call Meet links, no attendee invites")

    # The two Workspace-only features, and whether the config is self-consistent.
    if settings.GOOGLE_CALENDAR_CREATE_MEET and not delegated:
        r.add(BAD, "Per-call Meet links",
              "CREATE_MEET=true but no delegated user -- Google will refuse")
    elif settings.GOOGLE_CALENDAR_CREATE_MEET:
        r.add(OK, "Per-call Meet links", "enabled")
    else:
        shared = settings.GOXL_MEETING_URL
        r.add(WARN if shared else BAD, "Per-call Meet links",
              f"off -- every call shares {shared}" if shared
              else "off AND GOXL_MEETING_URL unset: calls would have NO link")

    if settings.GOOGLE_CALENDAR_INVITE_ATTENDEES and not delegated:
        r.add(BAD, "Attendee invites",
              "INVITE_ATTENDEES=true but no delegated user -- Google will refuse")
    elif settings.GOOGLE_CALENDAR_INVITE_ATTENDEES:
        r.add(OK, "Attendee invites", "enabled -- Google emails the founder directly")
    else:
        r.add(WARN, "Attendee invites", "off -- the app must deliver the link itself")

    # Talk to Google for real. Free/busy is read-only, so this proves credentials,
    # delegation and calendar access without creating anything.
    try:
        from app.services.calendar import _service
        now = datetime.now(timezone.utc)
        resp = _service().freebusy().query(body={
            "timeMin": now.isoformat(),
            "timeMax": (now + timedelta(days=1)).isoformat(),
            "items": [{"id": settings.GOOGLE_CALENDAR_ID}],
        }).execute()
        cal = resp.get("calendars", {}).get(settings.GOOGLE_CALENDAR_ID, {})
        if cal.get("errors"):
            r.add(BAD, "Calendar API call", f"{cal['errors']}")
        else:
            busy = len(cal.get("busy", []))
            r.add(OK, "Calendar API call", f"reachable, {busy} busy block(s) in the next 24h")
    except Exception as exc:  # noqa: BLE001
        r.add(BAD, "Calendar API call", f"{type(exc).__name__}: {exc}")


# --- what a founder ends up with ---------------------------------------------

def summarise(r: Report) -> None:
    print("\nWHAT A FOUNDER GETS TODAY")
    mail = settings.email_enabled
    invites = settings.GOOGLE_CALENDAR_INVITE_ATTENDEES and settings.GOOGLE_CALENDAR_DELEGATED_USER
    per_call = settings.GOOGLE_CALENDAR_CREATE_MEET and settings.GOOGLE_CALENDAR_DELEGATED_USER

    if mail:
        print("  - a booking confirmation email with the joining link")
        print("  - 24h and 1h reminders, IF a scheduler runs app.jobs.discovery_reminders")
    else:
        print("  - NO email of any kind. The link is only visible on the")
        print("    Discovery call page inside the app.")
    print(f"  - a calendar invite from Google: {'yes' if invites else 'no'}")
    print(f"  - their own Meet room: {'yes' if per_call else 'no, the shared room'}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--send-to", metavar="ADDRESS",
                   help="also send one real test email to this address")
    args = p.parse_args()

    print("=" * 66)
    print("  Ally -- discovery call and email readiness")
    print("=" * 66)

    r = Report()
    check_email(r, args.send_to)
    check_calendar(r)

    print("\nRESULTS")
    r.render()
    summarise(r)

    if r.failed:
        print("\n  FAIL -- something above is missing or wrong.\n")
        return 1
    print("\n  PASS -- a booked call will reach the founder.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
