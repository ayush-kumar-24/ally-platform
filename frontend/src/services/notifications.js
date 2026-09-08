/**
 * services/notifications.js — the notification bell.
 *
 * The list is server-owned so it is the same on every device and survives a
 * reload. Before this existed the bell rendered a fixed mock array, which meant
 * a founder saw three notifications that were not about them and could never be
 * cleared.
 */

import { get, post } from './api';

/** Newest first. Returns `{ items, unread_count }`. */
export function listNotifications() {
  return get('/notifications');
}

export function markRead(notificationId) {
  return post(`/notifications/${notificationId}/read`, {});
}

export function markAllRead() {
  return post('/notifications/read-all', {});
}

/**
 * Clear the panel. Hides every notification; it does not delete them.
 *
 * The server keeps the rows because the feed is regenerated from standing
 * conditions on every bell open, and only the existing row's dedup key stops a
 * cleared notification coming straight back.
 */
export function dismissAll() {
  return post('/notifications/dismiss-all', {});
}

/**
 * How long ago, in words. "2h ago" beats a raw ISO timestamp, which is what
 * this rendered before.
 */
function timeAgo(iso) {
  if (!iso) return '';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const mins = Math.floor((Date.now() - then.getTime()) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  return then.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

/**
 * Map a server notification onto the shape the bell renders.
 *
 * WHAT THIS USED TO DROP, and why it mattered. The server sends a `title`, a
 * `body` explaining it, and an `action_url` -- the whole point of "6 tasks are
 * overdue" being the click through to Plan Your Day. The old mapper kept the
 * title alone, so the explanation was invisible and the rows went nowhere. It
 * also passed `created_at` through raw, printing an ISO timestamp at a founder.
 *
 * Kept here rather than in the component so the wire format can change without
 * touching the UI.
 */
export function toDisplay(n) {
  return {
    id: n.notification_id ?? n.id,
    type: n.type ?? n.category ?? 'insight',
    unread: !(n.is_read ?? Boolean(n.read_at)),
    time: timeAgo(n.created_at),
    title: n.title ?? n.message ?? '',
    // The sentence under the title. Empty is fine -- the row just shows a title.
    body: n.body ?? '',
    // Where the row goes when clicked. Null means the row is not clickable,
    // which is correct for something purely informational.
    href: n.action_url ?? null,
    from: n.source ?? 'Ally',
  };
}
