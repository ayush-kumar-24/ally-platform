/**
 * services/settings.js — /settings/notifications.
 *
 * Backs the profile page's four "Preferences" toggles (Notifications,
 * Renewal reminder, Reduced motion, Private mode). All four were live React
 * state only until now -- no backend call, not even localStorage -- so every
 * one silently reset to its default on reload. Mapped onto the existing
 * notification_preferences JSONB rather than a new table: it already stores
 * exactly this shape (a handful of named booleans) for the founder.
 */

import { get, patch } from './api';

/** {in_app_all, email_reminders, email_report_ready, reduced_motion, private_mode} */
export function getNotificationPreferences() {
  return get('/settings/notifications');
}

/** Partial update -- only the keys you pass are changed. */
export function updateNotificationPreferences(changes) {
  return patch('/settings/notifications', changes);
}
