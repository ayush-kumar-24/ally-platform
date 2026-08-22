/**
 * services/calendar.js — connecting a Google Calendar to Plan Your Day.
 *
 * Deliberately unrelated to signing in. Ally's login is email-only, so the app
 * never holds a Google token by default; connecting a calendar is its own
 * explicit step, and the Google account involved need not be the one used for
 * Ally. A founder can use Plan Your Day forever without connecting anything.
 */

import { del, get, post } from './api';

/**
 * Whether a calendar is connected, and to which account.
 *
 * `available` is separate from `connected`: it reports whether this deployment
 * can offer calendar sync at all (OAuth client configured, encryption key set).
 * Without it the UI would show a Connect button that can only ever 503.
 */
export function getCalendarStatus() {
  return get('/calendar/status');
}

/**
 * Begin the Google consent flow.
 *
 * A full-page navigation, not a popup: popups are blocked by default in enough
 * browsers that the flow would silently do nothing, and Google's consent screen
 * refuses to render inside an iframe. The founder comes back to
 * /app/plan?calendar=connected when they are done.
 */
export async function startCalendarConnect() {
  const { authorization_url } = await post('/calendar/connect', {});
  window.location.assign(authorization_url);
}

/**
 * Disconnect. Events Ally already created stay on the founder's calendar —
 * the API says so in its message, and the UI repeats it, because silently
 * leaving them would be just as surprising as silently deleting them.
 */
export function disconnectCalendar() {
  return del('/calendar/connection');
}

/**
 * The browser's IANA zone, e.g. "Asia/Kolkata".
 *
 * Sent with every task write so a 9am reminder means 9am where the founder is.
 * Falls back to UTC rather than guessing: wrong by a known amount is easier to
 * reason about than wrong by an unknowable one.
 */
export function browserTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/** How a task's sync state should read to a founder. */
export const SYNC_LABELS = {
  synced: { label: 'On your calendar', tone: 'ok' },
  failed: { label: "Didn't reach your calendar", tone: 'bad' },
  pending: { label: 'Syncing…', tone: 'muted' },
  // 'skipped' is the normal state for a task with no date, or when no calendar
  // is connected. It is deliberately not shown as a problem, because it isn't.
  skipped: null,
};
