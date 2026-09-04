"""Beta-access emails: "you're in" and "you're next in line".

Two messages, and the second one matters more than it looks. Telling 100 founders
they were selected is easy; the 100 who were not are the ones who decide whether
your waitlist is a queue or a lottery. So the deferral email says the specific,
checkable thing -- you were not picked this round, you are now ahead of the people
who joined after you, and here is which round you are waiting for -- rather than
the "we'll be in touch" that means nothing.

Everything is best-effort by construction: `send_email` returns False rather than
raising, and this module's senders return (sent, error) so a failure is recorded
against the founder's waitlist row instead of aborting a release halfway through.
"""

from __future__ import annotations

import html

from app.admin.beta import Cohort, EmailKind, WaitlistEntry
from app.core.config import settings
from app.services.email import send_email

PRODUCT = "Ally"
TEAM = "The GoXL Team"


def _site() -> str:
    return (settings.PUBLIC_APP_URL or "").strip().rstrip("/")


def _greeting(entry: WaitlistEntry) -> str:
    name = (entry.full_name or "").strip().split(" ")[0]
    return f"Hi {name}," if name else "Hi,"


def _coupon_lines(code: str | None, label: str) -> tuple[str, str]:
    """(plain, html) for the coupon paragraph. Empty strings when there is none."""
    if not code:
        return "", ""
    offer = f" ({label})" if label else ""
    text = f"\nYour code: {code}{offer}. Apply it when you pick a plan.\n"
    markup = (f"<p>Your code: <strong>{html.escape(code)}</strong>{html.escape(offer)}. "
              f"Apply it when you pick a plan.</p>")
    return text, markup


def send_invite(entry: WaitlistEntry, cohort: Cohort | None = None, *,
                coupon_label: str = "") -> tuple[bool, str | None]:
    """Selected. Returns (sent, error); (False, None) means email is not configured."""
    site = _site()
    link = f"{site}/login" if site else ""
    coupon_text, coupon_html = _coupon_lines(entry.coupon_code, coupon_label)
    round_name = f" ({cohort.name})" if cohort else ""

    subject = f"You're in -- your {PRODUCT} beta access is open"
    text = (
        f"{_greeting(entry)}\n\n"
        f"You've been selected for the {PRODUCT} beta{round_name}. Your access is "
        f"open now.\n"
        f"{coupon_text}"
        + (f"\nStart here: {link}\n" if link else "")
        + f"\nWe read every piece of feedback in this phase, so tell us what breaks.\n\n"
        f"{TEAM}"
    )
    markup = (
        f"<p>{html.escape(_greeting(entry))}</p>"
        f"<p>You've been selected for the {PRODUCT} beta{html.escape(round_name)}. "
        f"Your access is open now.</p>"
        f"{coupon_html}"
        + (f'<p><a href="{html.escape(link)}">Start here</a></p>' if link else "")
        + f"<p>We read every piece of feedback in this phase, so tell us what breaks.</p>"
        f"<p>{TEAM}</p>"
    )
    return _send(entry.email, subject, text, markup)


def send_deferred(entry: WaitlistEntry, cohort: Cohort | None = None) -> tuple[bool, str | None]:
    """Not selected this round -- and moved to the front of the queue for the next.

    The number is included deliberately: `times_deferred` is the mechanism that
    actually promotes them, so quoting it makes the promise falsifiable rather
    than decorative.
    """
    round_name = f" ({cohort.name})" if cohort else ""
    times = entry.times_deferred
    standing = (
        "You're now at the front of the queue for the next round."
        if times <= 1 else
        f"You've been ahead of new signups for {times} rounds now, and you stay ahead "
        f"until you're in."
    )

    subject = f"You're next in line for the {PRODUCT} beta"
    text = (
        f"{_greeting(entry)}\n\n"
        f"We've just opened this round of the {PRODUCT} beta{round_name} and your name "
        f"wasn't in it. Places are limited, so this is about batch size, not about you.\n\n"
        f"{standing} We invite from the top of that queue, oldest first, so you don't "
        f"have to do anything to keep your place.\n\n"
        f"You'll hear from us when the next slot opens.\n\n"
        f"{TEAM}"
    )
    markup = (
        f"<p>{html.escape(_greeting(entry))}</p>"
        f"<p>We've just opened this round of the {PRODUCT} beta{html.escape(round_name)} "
        f"and your name wasn't in it. Places are limited, so this is about batch size, "
        f"not about you.</p>"
        f"<p>{html.escape(standing)} We invite from the top of that queue, oldest first, "
        f"so you don't have to do anything to keep your place.</p>"
        f"<p>You'll hear from us when the next slot opens.</p>"
        f"<p>{TEAM}</p>"
    )
    return _send(entry.email, subject, text, markup)


def _send(to: str, subject: str, text: str, markup: str) -> tuple[bool, str | None]:
    """Map `send_email`'s boolean onto (sent, error).

    `send_email` returns False for two very different situations -- "no SMTP is
    configured" and "the send failed" -- and swallows the exception in both. Only
    the second is worth retrying, so the configured-ness is checked here rather
    than inferred from the False.
    """
    if not settings.email_enabled:
        return False, None
    sent = send_email(to, subject, text, markup)
    return (True, None) if sent else (False, "the mail server rejected or dropped the message")


def build_sender(coupon_service=None):
    """A `(entry, kind, cohort) -> (sent, error)` callable for BetaAccessService.

    The coupon service is optional and read-only here: it is used purely to put a
    human-readable "20% off" next to the code in the invite, never to reserve or
    redeem it. Redemption happens when the founder actually uses the code.
    """

    def send(entry: WaitlistEntry, kind: EmailKind, cohort: Cohort | None):
        if kind is EmailKind.INVITE:
            label = ""
            if coupon_service is not None and entry.coupon_code:
                coupon = coupon_service.get(entry.coupon_code)
                if coupon is not None:
                    from app.admin.coupons import describe_discount
                    label = describe_discount(coupon.discount_type, coupon.discount_value)
            return send_invite(entry, cohort, coupon_label=label)
        return send_deferred(entry, cohort)

    return send
