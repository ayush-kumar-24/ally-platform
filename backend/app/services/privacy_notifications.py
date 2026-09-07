"""Tell the team a Privacy Center request is waiting.

THE SILENCE THIS ENDS. `privacy_requests` rows were written and nothing was
sent anywhere -- no email, no alert. A request sat `pending` until somebody
happened to open the admin panel and look. For a data correction that is slow.
For an email change it is the whole failure: that founder is locked out of an
account addressed to an inbox they do not own, cannot receive anything we send,
and their one route back to us is a row nobody is watching.

WHY EMAIL AND NOT A DASHBOARD BADGE. A badge is only seen by someone who
already opened the panel, which is the thing that was not happening.

WHY IT NEVER RAISES. This runs after the request has been written. A founder
whose request was recorded must not be told it failed because our mail server
was unhappy -- they would submit it again, and the duplicate guard would then
tell them they already had one pending, which reads as the product lying to
them. Every failure is swallowed and logged, the same rule as
login_notifications.

WHY THE RECIPIENT FALLS BACK. `PRIVACY_ALERT_EMAILS` unset would mean silence
-- exactly the defect this module exists to remove -- so it falls back to
EMAIL_REPLY_TO, which is by definition a mailbox a person reads. Wrong inbox
beats no inbox.
"""

from __future__ import annotations

from html import escape

from app.core.config import settings
from app.core.logger import logger
from app.services.email import send_email

#: Human wording for the queue. Mirrors the founder-facing labels so the team
#: and the founder are talking about the same thing when they speak.
_TYPE_LABELS = {
    "correct_data": "Data correction",
    "email_change": "Email change",
    "view_data": "View data summary",
    "download_data": "Download data",
    "portability": "Data portability export",
    "restrict_processing": "Restrict processing",
    "withdraw_consent": "Withdraw consent",
}

#: Types where waiting is itself the harm, called out in the subject line so it
#: is visible in a notification without opening the mail.
_URGENT = {"email_change"}


def _admin_link() -> str | None:
    """Deep link to the review queue, or None if we cannot build an honest one.

    SHARE_LINK_BASE_URL first: it is the setting that was actually verified to
    point at the app. PUBLIC_APP_URL is documented in config.py as set wrong in
    production, so it is the fallback, not the default. If neither is set the
    email says "open the admin panel" rather than carrying a link to nowhere --
    a broken link in an internal alert teaches people to ignore the alert.
    """
    base = (settings.SHARE_LINK_BASE_URL or settings.PUBLIC_APP_URL or "").strip().rstrip("/")
    return f"{base}/admin/privacy" if base else None


def _recipients() -> list[str]:
    if settings.privacy_alert_emails:
        return settings.privacy_alert_emails
    fallback = (settings.EMAIL_REPLY_TO or "").strip()
    return [fallback] if fallback else []


def notify_team_of_request(
    *,
    request_type: str,
    founder_id: int,
    founder_email: str | None = None,
    request_details: str | None = None,
) -> bool:
    """Email whoever handles the queue. True only if a message actually went."""
    try:
        if not settings.email_enabled:
            return False
        recipients = _recipients()
        if not recipients:
            logger.warning(
                "privacy request queued but nobody is configured to be told",
                extra={"path": f"type={request_type} founder_id={founder_id}"},
            )
            return False

        label = _TYPE_LABELS.get(request_type, request_type)
        urgent = request_type in _URGENT
        subject = f"[Ally] {'ACTION NEEDED: ' if urgent else ''}{label} request from founder {founder_id}"

        link = _admin_link()
        lines = [
            f"A {label.lower()} request is waiting in the Privacy Center queue.",
            "",
            f"  Founder ID:  {founder_id}",
            f"  Current email: {founder_email or 'unknown'}",
            f"  Request type: {request_type}",
        ]
        if request_details:
            # For email_change this IS the new address, validated on the way in.
            lines.append(f"  They said:   {request_details}")
        lines.append("")

        if urgent:
            # Says why it cannot wait, because the reason is not obvious and the
            # person reading this may not know the feature exists.
            lines += [
                "This one is time-sensitive. A founder asking to change their email",
                "usually cannot receive anything we send to the address on the",
                "account -- so they cannot be emailed to confirm, chase us, or be",
                "told it is in hand. Until someone actions this, they are locked",
                "out of every message we send.",
                "",
                "BEFORE CHANGING IT: verify who is asking. Changing the address on",
                "an account is an account-takeover primitive -- whoever controls",
                "the new inbox can then use password reset to own the account.",
                "Do not action this on the request alone.",
                "",
            ]

        lines += [
            f"Review it here: {link}" if link else "Open the admin panel to review it.",
            "",
            "-- Ally",
        ]
        text = "\n".join(lines)

        detail_html = (
            f"<p><strong>They said:</strong> {escape(request_details)}</p>"
            if request_details else ""
        )
        urgent_html = (
            "<p style='background:#fff7ed;border-left:3px solid #ea580c;padding:10px 12px'>"
            "<strong>Time-sensitive.</strong> A founder asking to change their email "
            "usually cannot receive anything we send to the address on the account, so "
            "they cannot be emailed to confirm or chase. "
            "<br><br><strong>Verify who is asking before changing it</strong> -- changing "
            "the address on an account is an account-takeover primitive.</p>"
            if urgent else ""
        )
        link_html = (
            f'<p><a href="{escape(link, quote=True)}">Review it in the admin panel</a></p>'
            if link else "<p>Open the admin panel to review it.</p>"
        )
        html = (
            f"<p>A {escape(label.lower())} request is waiting in the Privacy Center queue.</p>"
            f"<p><strong>Founder ID:</strong> {founder_id}<br>"
            f"<strong>Current email:</strong> {escape(founder_email or 'unknown')}<br>"
            f"<strong>Request type:</strong> {escape(request_type)}</p>"
            f"{detail_html}{urgent_html}{link_html}"
        )

        sent = False
        for to in recipients:
            sent = send_email(to, subject, text, html) or sent
        return sent
    except Exception as exc:
        # Swallowed on purpose -- see the module docstring.
        logger.warning(
            "privacy request notification failed",
            extra={"path": f"type={request_type} founder_id={founder_id}"},
            exc_info=exc,
        )
        return False
