/**
 * Calendar dates as plain `YYYY-MM-DD` strings.
 *
 * Never Date objects across a boundary, and never `toISOString()`: that
 * converts to UTC first, so 26 Aug local becomes "2026-08-25T18:30:00Z" in
 * India and the date silently reads as the 25th. Strings built from local
 * getters compare correctly, sort correctly, and match what the API stores.
 *
 * Lives outside the component file so React Fast Refresh can still hot-reload
 * the calendar -- a module exporting both components and plain functions loses
 * that.
 */

/** Local calendar date as YYYY-MM-DD. */
export function toKey(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

/** Today, in the founder's own timezone. */
export function todayKey() {
  return toKey(new Date());
}
