"""Tell the team when a founder writes to us.

THE PROMISE THIS MAKES TRUE. Help & Support and the help widget both toast
"Sent -- our team will get back to you by email", and the Feedback page says
"we read every one of these". Neither was true: the row was written to
`founder_feedback` and nothing anywhere lit up. No email, no alert, and until
now no admin screen either. A founder reporting that they cannot pay, or that
their report is wrong, was told a person would reply and no person ever knew.

ONLY WHEN THERE ARE WORDS. A star rating with no comment does NOT send anything.
Ratings fire automatically after a diagnosis and after a report, so alerting on
them would put several mails a day in front of the team with nothing to act on
-- and a team that learns to skim these will skim the one that says "I have been
charged twice". Silence on ratings is what keeps the alerts worth reading; the
numbers are for the admin page, which shows them all.

SUPPORT REQUESTS ARE MARKED. Anything the founder sent from Help & Support or
the widget is tagged `[Support request]` by the client, and that tag is the
difference between "someone shared an idea" and "someone is stuck right now".
It goes in the subject line.

NEVER RAISES. Same rule as every other notifier here: the feedback is already
saved when this runs, and a founder must not be told their message failed
because our mail server was unhappy -- they would send it again.
"""

from __future__ import annotations

from html import escape

from app.core.config import settings
from app.core.logger import logger
from app.services.email import send_email

#: The tag the frontend puts in front of anything sent from a support box.
#: Kept in step with HelpSupport.jsx and HelpWidget.jsx, which both write it.
SUPPORT_TAG = "[Support request]"


def _recipients() -> list[str]:
    if settings.support_alert_emails:
        return settings.support_alert_emails
    if settings.privacy_alert_emails:
        return settings.privacy_alert_emails
    fallback = (settings.EMAIL_REPLY_TO or "").strip()
    return [fallback] if fallback else []


def _admin_link() -> str | None:
    base = (settings.SHARE_LINK_BASE_URL or settings.PUBLIC_APP_URL or "").strip().rstrip("/")
    return f"{base}/admin/feedback" if base else None


def notify_team_of_feedback(
    *,
    founder_id: int,
    comment: str | None,
    feedback_type: str,
    rating: int | None = None,
    founder_email: str | None = None,
    founder_name: str | None = None,
) -> bool:
    """Email the team about written feedback. True only if something was sent."""
    try:
        text_body = (comment or "").strip()
        if not text_body:
            return False            # a bare rating -- see the module docstring
        if not settings.email_enabled:
            return False
        recipients = _recipients()
        if not recipients:
            logger.warning(
                "founder feedback received but nobody is configured to be told",
                extra={"path": f"founder_id={founder_id} type={feedback_type}"},
            )
            return False

        is_support = text_body.startswith(SUPPORT_TAG)
        who = founder_name or f"founder {founder_id}"
        subject = (
            f"[Ally] Support request from {who}" if is_support
            else f"[Ally] Feedback from {who}"
        )

        link = _admin_link()
        stars = f"{rating}/5" if rating else "not rated"
        lines = [
            f"{who} wrote:",
            "",
            text_body,
            "",
            f"  Founder ID: {founder_id}",
            f"  Reply to:   {founder_email or 'unknown'}",
            f"  Type:       {feedback_type}   Rating: {stars}",
            "",
        ]
        if is_support:
            # The founder was told, in the product, that a person would reply.
            lines += [
                "They were shown \"our team will get back to you by email\", so "
                "this is a reply somebody is expecting -- not a suggestion box.",
                "",
            ]
        lines += [
            f"See all feedback: {link}" if link else "Open the admin panel to see all feedback.",
            "",
            "-- Ally",
        ]

        support_html = (
            "<p style='background:#fff7ed;border-left:3px solid #ea580c;padding:10px 12px'>"
            "They were shown <em>&ldquo;our team will get back to you by email&rdquo;</em>, "
            "so this is a reply somebody is expecting &mdash; not a suggestion box.</p>"
            if is_support else ""
        )
        link_html = (
            f'<p><a href="{escape(link, quote=True)}">See all feedback in the admin panel</a></p>'
            if link else "<p>Open the admin panel to see all feedback.</p>"
        )
        html = (
            f"<p><strong>{escape(who)}</strong> wrote:</p>"
            f"<blockquote style='border-left:3px solid #ddd;margin:0;padding:4px 12px'>"
            f"{escape(text_body)}</blockquote>"
            f"<p><strong>Founder ID:</strong> {founder_id}<br>"
            f"<strong>Reply to:</strong> {escape(founder_email or 'unknown')}<br>"
            f"<strong>Type:</strong> {escape(feedback_type)} &middot; "
            f"<strong>Rating:</strong> {escape(stars)}</p>"
            f"{support_html}{link_html}"
        )

        sent = False
        for to in recipients:
            sent = send_email(to, subject, "\n".join(lines), html) or sent
        return sent
    except Exception as exc:
        logger.warning(
            "feedback notification failed",
            extra={"path": f"founder_id={founder_id}"},
            exc_info=exc,
        )
        return False
