"""Fail-closed validation for the settings this module owns.

EMPTY ON PURPOSE, 2026-09-05. This file validated `reminder_time` and
`session_timeout_minutes`. Both settings have been removed -- see
app/settings/schemas.py for why -- so there is nothing left here to check.

Kept as a file rather than deleted because `InvalidSettingError` is part of the
module's public surface and a validator will be wanted again the moment a
setting with a constrained value is added. Add it here.
"""

from __future__ import annotations

from app.settings.errors import InvalidSettingError

__all__ = ["InvalidSettingError"]
