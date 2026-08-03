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
 * Map a server notification onto the shape the bell renders.
 *
 * Kept here rather than in the component so the wire format can change without
 * touching the UI.
 */
export function toDisplay(n) {
  return {
    id: n.notification_id ?? n.id,
    type: n.type ?? n.category ?? 'insight',
    status: n.read_at ? 'read' : (n.status ?? 'upcoming'),
    time: n.created_at ?? '',
    message: n.message ?? n.title ?? '',
    from: n.source ?? 'Ally',
  };
}
