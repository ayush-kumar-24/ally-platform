"""Email sending -- generic SMTP, with a stub fallback.

Works with any SMTP provider (Gmail, SendGrid, SES, Postmark...). Until
EMAIL_HOST is configured, `send_email` runs in stub mode: it logs the message
and returns False instead of sending, so dev and tests never send real mail.

Callers should treat email as best-effort -- a failure to send must never break
the action that triggered it (e.g. a booking still succeeds if the confirmation
email fails).
"""

import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.logger import logger


def send_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> bool:
    """Send one email. Returns True if actually sent, False in stub mode / on error."""
    if not settings.email_enabled:
        logger.info("Email (stub, not sent)", extra={"path": f"to={to} subject={subject!r}"})
        return False

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=15) as server:
            if settings.EMAIL_USE_TLS:
                server.starttls()
            if settings.EMAIL_USER:
                server.login(settings.EMAIL_USER, settings.EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        # Never let an email failure bubble up into the caller's request.
        logger.warning("Email send failed", extra={"path": f"to={to} subject={subject!r}"})
        return False
