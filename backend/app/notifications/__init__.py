"""In-app notifications: the bell.

`writer.notify()` is the only way a notification is created. `rules` decides
which ones a founder should have right now, and is run both by a scheduled
sweep and whenever a founder opens the bell -- so the feed is fresh when they
actually look, not just when a cron happened to fire.
"""

from app.notifications.writer import notify, reset_type_cache

__all__ = ["notify", "reset_type_cache"]
