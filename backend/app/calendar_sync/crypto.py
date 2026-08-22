"""Encryption for stored OAuth tokens.

A Google refresh token is a long-lived, silent grant to read and write someone's
personal calendar. Unlike a password it is not hashed-and-compared -- we have to
be able to read it back -- so the protection has to be encryption at rest, and
the key has to live somewhere the database does not.

Fernet (AES-128-CBC + HMAC-SHA256, from `cryptography`) rather than anything
hand-rolled: it authenticates as well as encrypts, so a tampered ciphertext
fails loudly instead of decrypting to garbage that then gets sent to Google.

The key comes from CALENDAR_TOKEN_KEY. There is deliberately NO default and no
fallback to plaintext: a misconfigured deploy must fail closed at the point of
use, because the alternative is silently writing refresh tokens to the database
in the clear and nobody noticing until the table leaks.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings


class TokenEncryptionUnavailableError(RuntimeError):
    """CALENDAR_TOKEN_KEY is missing or unusable.

    Raised at the point a token would be written or read, not at import: the
    rest of the app -- and Plan Your Day itself -- must keep working on a deploy
    that has no calendar key set. Only the calendar feature is unavailable.
    """


@lru_cache(maxsize=1)
def _fernet():
    from cryptography.fernet import Fernet

    key = (settings.CALENDAR_TOKEN_KEY or "").strip()
    if not key:
        raise TokenEncryptionUnavailableError(
            "CALENDAR_TOKEN_KEY is not set, so calendar tokens cannot be stored "
            "safely. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode())
    except Exception as exc:  # malformed key -- wrong length, not base64, ...
        raise TokenEncryptionUnavailableError(
            "CALENDAR_TOKEN_KEY is not a valid Fernet key (needs 32 url-safe "
            "base64-encoded bytes)."
        ) from exc


def is_available() -> bool:
    """Can tokens be encrypted right now?

    Lets the connect endpoint refuse cleanly with "calendar sync isn't
    configured" instead of starting an OAuth flow that can only fail after the
    founder has already granted Google access -- the worst possible moment to
    discover a missing env var.
    """
    try:
        _fernet()
        return True
    except TokenEncryptionUnavailableError:
        return False


def encrypt(plaintext: str) -> str:
    """Encrypt a token for storage. Empty in, empty out.

    The empty case is real: Google omits refresh_token on re-consent when the
    user has already granted offline access, and storing an encrypted empty
    string would be indistinguishable from a genuine token until it failed.
    """
    if not plaintext:
        return ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Read a stored token back.

    Returns "" for an empty column rather than raising, so callers can treat
    "no refresh token stored" as a normal state. A ciphertext that fails to
    authenticate DOES raise -- that means the key changed or the row was
    tampered with, and quietly returning "" would turn a security event into a
    confusing reconnect prompt.
    """
    if not ciphertext:
        return ""
    return _fernet().decrypt(ciphertext.encode()).decode()
