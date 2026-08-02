"""Input validation for the Consents module. Fails closed -- anything that is not
provably a valid document version is rejected rather than stored."""

from __future__ import annotations

import re

from app.consents.errors import InvalidConsentInputError

MAX_VERSION_LENGTH = 20

# Dotted numeric versions only: "1", "1.0", "2.1.3". Deliberately strict -- a
# version string is legal evidence of *which document* was agreed to, so free text
# ("latest", "v2-draft") would make the record unfalsifiable.
_VERSION_RE = re.compile(r"^\d+(\.\d+){0,2}$")


def validate_version(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise InvalidConsentInputError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise InvalidConsentInputError(f"{field} is required")
    if len(cleaned) > MAX_VERSION_LENGTH:
        raise InvalidConsentInputError(f"{field} may not exceed {MAX_VERSION_LENGTH} characters")
    if not _VERSION_RE.match(cleaned):
        raise InvalidConsentInputError(
            f"{field} must be a dotted numeric version such as '1.0' (got {value!r})")
    return cleaned
