"""Error surface for the settings-preferences endpoints.

The domain errors are AppError subclasses, so the app's global handler already maps
them to consistent JSON (422 invalid setting, 404 not found). Re-exported here for
discoverability; the router raises nothing itself and lets them propagate."""

from app.settings.errors import InvalidSettingError, SettingsError, SettingsNotFoundError

__all__ = ["SettingsError", "InvalidSettingError", "SettingsNotFoundError"]
