"""The one email that tells a founder they can come in.

Kept out of `panel_service` so the admin service stays about authorization and
audit, and kept best-effort like every other send in this codebase: an approval
that succeeded must not be reported as failed because a mail server was slow.
The founder is approved the moment the column changes; this only tells them so.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logger import logger
from app.services.email import send_email

_SUBJECT = "Your GoXL Ally account is ready"


def _sign_in_url() -> str:
    """Where to send them. Falls back to the marketing domain rather than to a
    relative path: this is an email, so a link with no origin is a dead link."""
    base = (settings.PUBLIC_APP_URL or "https://app.goxlally.ai").rstrip("/")
    return f"{base}/guided/login"


def send_approval_email(*, to: str | None, full_name: str | None = None) -> bool:
    """Tell an approved founder their account is open. Returns whether it sent.

    A missing address is not an error worth raising: some rows genuinely have
    none, and refusing to approve someone because we cannot email them would be
    the wrong trade. It is logged so it is not silent.
    """
    if not to:
        logger.info("approval email skipped: founder has no email address")
        return False

    name = (full_name or "").strip().split(" ")[0] or "there"
    url = _sign_in_url()

    text = (
        f"Hi {name},\n\n"
        "Your GoXL Ally account has been approved. You can sign in now:\n\n"
        f"{url}\n\n"
        "When you sign in you'll finish a short onboarding, then choose the plan "
        "that fits how much you want Ally involved.\n\n"
        "If you have any questions, just reply to this email or write to "
        "info@goxl.in.\n\n"
        "— The GoXL Ally team"
    )

    html = (
        '<div style="font-family:system-ui,-apple-system,sans-serif;line-height:1.6;'
        'color:#16241c;max-width:520px">'
        f"<p>Hi {name},</p>"
        "<p>Your <strong>GoXL Ally</strong> account has been approved. "
        "You can sign in now:</p>"
        f'<p><a href="{url}" style="display:inline-block;padding:11px 20px;'
        'border-radius:10px;background:#1B4332;color:#fff;text-decoration:none;'
        'font-weight:700">Sign in to Ally</a></p>'
        "<p>When you sign in you'll finish a short onboarding, then choose the "
        "plan that fits how much you want Ally involved.</p>"
        "<p style=\"color:#556458;font-size:14px\">Any questions, just reply to "
        'this email or write to <a href="mailto:info@goxl.in">info@goxl.in</a>.</p>'
        '<p style="color:#556458;font-size:14px">— The GoXL Ally team</p>'
        "</div>"
    )

    return send_email(to=to, subject=_SUBJECT, body_text=text, body_html=html)
