"""New-device sign-in emails -- the consumer for `login_notifications`.

The setting existed, defaulted to on, and nothing anywhere read it. No sign-in
email was ever sent. That gap is why help answer 253 tells founders an email
claiming "someone signed in" is NOT from us and is probably phishing -- true
while it lasted, and dangerous the moment anyone switched this on without
noticing that answer. This closes it properly instead.

WHY NEW DEVICES ONLY. An email on every sign-in is noise, and noise is worse
than nothing: people learn to delete it unread, so the one that matters gets
deleted too. An email that fires only when the account is opened from somewhere
it has not been opened before is the one that catches a real problem, and most
founders will see it once or twice a year.

WHAT COUNTS AS A DEVICE. A coarse fingerprint -- the browser/OS family from the
User-Agent, plus the /24 of the IP -- deliberately NOT the exact user agent or
the full address. Exact strings change constantly (every browser update is a new
"device", and a phone changes IP walking down the street), so a stricter
fingerprint would email a founder several times a week and be ignored inside a
month. The /24 keeps a house or an office looking like one place while a
different city does not.

WHERE HISTORY LIVES. `audit_logs`, which already has founder_id, ip_address,
browser and created_at, and is already partitioned by month. No new table and no
migration. It also means the sign-in history is visible to the same admin tools
and included in a founder's data export, which is where they would expect it.

BEST EFFORT, ALWAYS. Nothing here may break a sign-in. A founder who cannot get
in because our mail server is unhappy is a far worse outcome than a missed
notification, so every failure is swallowed and logged.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import logger
from app.models import Founder
from app.models.partitioned import AuditLog
from app.services.email import send_email

#: The action written to audit_logs for a sign-in.
SIGN_IN_ACTION = "sign_in"

#: How far back we look before calling a device "new". A year, so an annual
#: laptop refresh or a long gap between sign-ins does not fire a scary email --
#: and so the partitioned table is never scanned unbounded.
_HISTORY_WINDOW_DAYS = 365

#: Browser and OS families we bother to name. Order matters: Edge and Chrome
#: both contain "Chrome", and Safari's UA contains "Safari" for Chrome too.
_BROWSERS = (
    ("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"), ("Safari/", "Safari"),
)
_PLATFORMS = (
    ("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"),
    ("Windows", "Windows"), ("Mac OS X", "Mac"), ("Macintosh", "Mac"),
    ("Linux", "Linux"),
)


def device_label(user_agent: str | None) -> str:
    """A short, human-readable device name -- "Chrome on Windows".

    This is what a founder reads in the email, so it is written for them and not
    for us. An unrecognised agent becomes "an unrecognised browser" rather than
    a wall of version numbers nobody can act on.
    """
    ua = user_agent or ""
    browser = next((name for token, name in _BROWSERS if token in ua), None)
    platform = next((name for token, name in _PLATFORMS if token in ua), None)
    if browser and platform:
        return f"{browser} on {platform}"
    if browser:
        return browser
    if platform:
        return platform
    return "an unrecognised browser"


def _ip_prefix(ip: str | None) -> str:
    """The /24 of an IPv4 address, or the first four groups of an IPv6 one.

    Coarse on purpose -- see the module docstring. A founder's home broadband
    changing its last octet must not read as a new device.
    """
    raw = (ip or "").strip()
    if not raw:
        return ""
    if ":" in raw:                                    # IPv6
        return ":".join(raw.split(":")[:4])
    if re.fullmatch(r"[\d.]+", raw) and raw.count(".") == 3:
        return ".".join(raw.split(".")[:3])
    return raw


def fingerprint(user_agent: str | None, ip: str | None) -> str:
    """The value compared against history. Never shown to anyone."""
    return f"{device_label(user_agent)}|{_ip_prefix(ip)}"


def _wants_login_notifications(db: Session, founder: Founder) -> bool:
    """The founder's `login_notifications` preference, defaulting to on.

    Lives in the settings module, so it is read through the repository rather
    than assumed off a column here.
    """
    try:
        from app.settings.repository import SqlAlchemySettingsRepository
        snapshot = SqlAlchemySettingsRepository(db).get(founder.founder_id)
        return bool(snapshot.security.login_notifications) if snapshot else True
    except Exception:
        return True     # a preference we cannot read is not a reason to go quiet


def _seen_before(db: Session, founder_id: int, fp: str) -> bool:
    since = datetime.now(timezone.utc) - timedelta(days=_HISTORY_WINDOW_DAYS)
    stmt = (
        select(AuditLog.log_id)
        .where(
            AuditLog.founder_id == founder_id,
            AuditLog.action == SIGN_IN_ACTION,
            AuditLog.browser == fp,
            AuditLog.created_at >= since,
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def _record(db: Session, founder_id: int, fp: str, ip: str, label: str) -> None:
    db.add(AuditLog(
        founder_id=founder_id, action=SIGN_IN_ACTION, entity_type="founder",
        entity_id=founder_id, ip_address=(ip or "0.0.0.0")[:45], browser=fp,
        action_details={"device": label},
    ))
    db.flush()


def _send(to: str, name: str, label: str, when: datetime) -> bool:
    stamp = when.astimezone(timezone.utc).strftime("%d %B %Y at %H:%M UTC")
    subject = "New sign-in to your Ally account"
    # Deliberately contains NO link. A security email that asks you to click
    # something teaches founders to click links in security emails, which is
    # exactly how the phishing this is meant to catch works. It tells them where
    # to go instead, and they get there the way they normally do.
    text = (
        f"Hi {name},\n\n"
        f"Your Ally account was just opened from a device we have not seen before.\n\n"
        f"  Device: {label}\n"
        f"  When:   {stamp}\n\n"
        "If that was you, there is nothing to do.\n\n"
        "If it was not, please change your password. Open Ally the way you normally "
        "do -- by typing the address into your browser -- and use 'forgot password' "
        "on the sign-in screen. We have deliberately not put a link in this email.\n\n"
        "You can turn these emails off in Profile.\n\n"
        "The GoXL Team"
    )
    html = (
        f"<p>Hi {escape(name)},</p>"
        f"<p>Your Ally account was just opened from a device we have not seen before.</p>"
        f"<p><strong>Device:</strong> {escape(label)}<br>"
        f"<strong>When:</strong> {escape(stamp)}</p>"
        "<p>If that was you, there is nothing to do.</p>"
        "<p>If it was not, please change your password. Open Ally the way you normally "
        "do &mdash; by typing the address into your browser &mdash; and use "
        "&lsquo;forgot password&rsquo; on the sign-in screen. We have deliberately not "
        "put a link in this email.</p>"
        "<p>You can turn these emails off in Profile.</p>"
        "<p>The GoXL Team</p>"
    )
    return send_email(to, subject, text, html)


def note_sign_in(db: Session, founder: Founder | None, *,
                 ip: str | None, user_agent: str | None) -> dict:
    """Record this sign-in, and email the founder if the device is new.

    Returns a small dict for logging and tests. Never raises: a sign-in must
    succeed whatever happens in here.
    """
    if founder is None:
        return {"recorded": False, "reason": "no founder"}

    try:
        fp = fingerprint(user_agent, ip)
        label = device_label(user_agent)
        known = _seen_before(db, founder.founder_id, fp)
        _record(db, founder.founder_id, fp, ip or "0.0.0.0", label)

        if known:
            return {"recorded": True, "new_device": False, "emailed": False}

        # A founder's FIRST ever sign-in is by definition from an unseen device.
        # Emailing them about it seconds after they signed up is alarming and
        # tells them nothing, so the first recorded device is learned silently.
        first_ever = not db.execute(
            select(AuditLog.log_id).where(
                AuditLog.founder_id == founder.founder_id,
                AuditLog.action == SIGN_IN_ACTION,
                AuditLog.browser != fp,
            ).limit(1)
        ).first()
        if first_ever:
            return {"recorded": True, "new_device": True, "emailed": False,
                    "reason": "first device learned silently"}

        if not settings.email_enabled:
            return {"recorded": True, "new_device": True, "emailed": False,
                    "reason": "email not configured"}
        if not founder.email:
            return {"recorded": True, "new_device": True, "emailed": False,
                    "reason": "no address"}
        if not _wants_login_notifications(db, founder):
            return {"recorded": True, "new_device": True, "emailed": False,
                    "reason": "founder opted out"}

        sent = _send(founder.email, founder.full_name or "there", label,
                     datetime.now(timezone.utc))

        # The bell too. The email deliberately carries no link (see _send), and
        # a founder who is worried enough to check will already be looking at
        # Ally -- this is where they can act on it.
        #
        # Keyed on the fingerprint, so the same device does not notify twice
        # even if the audit row is somehow written again.
        from app.notifications import notify
        notify(
            db, founder_id=founder.founder_id, type="new_device_signin",
            title="New sign-in to your account",
            body=(f"Your account was opened from {label}, a device we have not "
                  "seen before. If that was you, there is nothing to do."),
            action_url="/app/profile",
            dedup_key=f"new_device_signin:{fp}",
            founder=founder,
        )
        return {"recorded": True, "new_device": True, "emailed": sent}
    except Exception as exc:
        # Swallowed on purpose -- see the module docstring.
        logger.warning("sign-in notification failed",
                       extra={"founder_id": getattr(founder, "founder_id", None)},
                       exc_info=exc)
        return {"recorded": False, "reason": "error"}
