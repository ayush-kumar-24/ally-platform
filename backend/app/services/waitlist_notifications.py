"""The email a founder gets when their waitlist registration is approved.

One email, sent once, at the moment access actually exists. It is deliberately
not sent at "approved" but at "approved AND the identity was created" -- see
services/waitlist.py -- because the whole content of this message is an
instruction to go and sign in, and an instruction that cannot be followed is
worse than silence.

Plain text is written first and the HTML mirrors it, not the other way round:
a founder reading this in a client that strips HTML should get the same
message, including the link, rather than a stub telling them to view it
elsewhere.
"""

from __future__ import annotations

from html import escape

from app.core.config import settings
from app.services.email import send_email


def _sign_in_url() -> str:
    """Where the founder goes next.

    SHARE_LINK_BASE_URL first, PUBLIC_APP_URL only as a fallback, and this
    order is not arbitrary: config.py records that production has
    PUBLIC_APP_URL pointing at the marketing site, which has no /guided/*
    route, so preferring it would send every approved founder to a 404 in the
    one email whose entire job is "go here and sign in". SHARE_LINK_BASE_URL is
    the setting documented to hold https://app.goxlally.ai.

    Empty when neither is set. The caller drops the link rather than emitting a
    broken one -- a founder told to "sign in at our site" can find it; a
    founder given a dead link assumes we are broken.
    """
    base = (settings.SHARE_LINK_BASE_URL or settings.PUBLIC_APP_URL or "").rstrip("/")
    return f"{base}/guided/login" if base else ""


def send_approval_email(to: str, name: str) -> bool:
    """Tell a founder they are in. Returns True only if the mail actually left.

    Never raises: an approval that has already created the identity must not be
    rolled back because the mail server was briefly unreachable. The caller
    records whether this returned True, so an unsent one can be chased.
    """
    first = (name or "").strip().split(" ")[0] or "there"
    url = _sign_in_url()
    subject = "You're on the founder's list — your Ally access is open"

    text = (
        f"Hi {first},\n\n"
        "You're in.\n\n"
        "Your registration has been reviewed and approved, and your place on "
        "the founder's list is confirmed. Ally is open to a small first group "
        "of founders, and you are one of them.\n\n"
    )
    if url:
        text += f"Sign in here with this email address:\n{url}\n\n"
    else:
        text += "Sign in with this email address at the link on our site.\n\n"
    text += (
        "The first time, enter your email and we'll send you a 6-digit code. "
        "Once you're in, you'll choose a password for next time.\n\n"
        "What happens next: Ally starts by understanding you — how you decide, "
        "where you get stuck — then your business, then where the two meet. "
        "Give the first session a quiet half hour; it is the part everything "
        "else is built on.\n\n"
        "If anything gets in your way, just reply to this email.\n\n"
        "— The GoXL Ally team\n"
    )

    safe_first = escape(first)
    link_html = (
        f'<p style="margin:24px 0"><a href="{escape(url, quote=True)}" '
        'style="background:#10B981;color:#06140d;text-decoration:none;'
        'padding:12px 22px;border-radius:10px;font-weight:700;display:inline-block">'
        "Sign in to Ally</a></p>"
        if url
        else "<p>Sign in with this email address at the link on our site.</p>"
    )

    html = (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;'
        'font-size:15px;line-height:1.6;color:#16241c;max-width:560px">'
        f"<p>Hi {safe_first},</p>"
        '<p style="font-size:19px;font-weight:700;color:#1B4332;margin:18px 0 8px">'
        "You're in.</p>"
        "<p>Your registration has been reviewed and approved, and your place on "
        "the founder's list is confirmed. Ally is open to a small first group of "
        "founders, and you are one of them.</p>"
        f"{link_html}"
        "<p>The first time, enter this email address and we'll send you a "
        "6-digit code. Once you're in, you'll choose a password for next time.</p>"
        '<p style="margin-top:20px"><strong>What happens next.</strong> Ally '
        "starts by understanding you — how you decide, where you get stuck — "
        "then your business, then where the two meet. Give the first session a "
        "quiet half hour; it is the part everything else is built on.</p>"
        "<p>If anything gets in your way, just reply to this email.</p>"
        '<p style="color:#556458;margin-top:24px">— The GoXL Ally team</p>'
        "</div>"
    )

    return send_email(to, subject, text, html)


def send_direct_signup_overflow_email(to: str, name: str) -> bool:
    """Tell a founder who tried to sign in past capacity that they are queued.

    Only path that reaches this: someone with no waitlist history opened the
    sign-in page directly (not the "Register" button, which would not have
    been showing) at the exact moment direct capacity was zero. Their address
    is already in the queue (see services/provisioning.py, which inserts the
    row before this is sent) -- this only has to say so, since the page they
    were just on gave them no confirmation of anything.

    Same never-raises contract as send_approval_email: the queue entry is
    already committed, so a mail failure here must not become a 500 on
    someone's sign-in attempt.
    """
    first = (name or "").strip().split(" ")[0] or "there"
    subject = "You're on the founder's list — we'll email you when it's your turn"

    text = (
        f"Hi {first},\n\n"
        "You tried to sign in just as our current group filled up, so instead "
        "of an account you've been added to the founder's list -- the same "
        "queue everyone else joins from the registration page.\n\n"
        "You do not need to do anything else. We review it in the order "
        "people arrive, and you'll get another email the moment your place "
        "opens, with a link to sign in.\n\n"
        "— The GoXL Ally team\n"
    )

    safe_first = escape(first)
    html = (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;'
        'font-size:15px;line-height:1.6;color:#16241c;max-width:560px">'
        f"<p>Hi {safe_first},</p>"
        "<p>You tried to sign in just as our current group filled up, so "
        "instead of an account you've been added to the founder's list -- the "
        "same queue everyone else joins from the registration page.</p>"
        "<p>You do not need to do anything else. We review it in the order "
        "people arrive, and you'll get another email the moment your place "
        "opens, with a link to sign in.</p>"
        '<p style="color:#556458;margin-top:24px">— The GoXL Ally team</p>'
        "</div>"
    )

    return send_email(to, subject, text, html)
