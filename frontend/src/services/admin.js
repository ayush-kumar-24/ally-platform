/**
 * services/admin.js — Admin Panel API.
 *
 * Internal-only. Pages import from here, never from api.js directly.
 *
 * Note on `can()`: it exists to hide controls the caller cannot use, which is a
 * usability nicety only. Every one of these endpoints is authorized server-side —
 * hiding a button is not a security control and nothing here relies on it.
 */

import { del, get, patch, post, put } from './api';

export const ROLES = { SUPER_ADMIN: 'super_admin', ADMIN: 'admin', SUPPORT: 'support' };

export const CREDIT_OPS = [
  { value: 'add', label: 'Add credits' },
  { value: 'remove', label: 'Remove credits' },
  { value: 'set', label: 'Set balance to' },
  { value: 'bonus', label: 'Transfer bonus' },
];

export const USER_STATUSES = ['active', 'inactive', 'suspended', 'banned'];

/** Caller's role + capabilities. */
export function getMe() {
  return get('/admin/me');
}

/** True if the signed-in admin holds a capability. */
export function can(me, capability) {
  return Boolean(me?.capabilities?.includes(capability));
}

/** Paged, filtered user list. Undefined/empty params are dropped. */
export function listUsers(params = {}) {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  );
  return get('/admin/users', { params: clean });
}

export function getUser(id) {
  return get(`/admin/users/${id}`);
}

export function updateUser(id, changes) {
  return patch(`/admin/users/${id}`, changes);
}

export function changeStatus(id, status, reason) {
  return post(`/admin/users/${id}/status`, { status, reason });
}

export function resetDiagnosis(id) {
  return post(`/admin/users/${id}/reset-diagnosis`, { confirm: true });
}

export function resetConversations(id) {
  return post(`/admin/users/${id}/reset-conversations`, { confirm: true });
}

export function deleteUser(id, reason) {
  return del(`/admin/users/${id}`, { data: { confirm: true, reason } });
}

export function getCredits(id, { limit = 50, offset = 0 } = {}) {
  return get(`/admin/users/${id}/credits`, { params: { limit, offset } });
}

export function adjustCredits(id, { operation, amount, reason }) {
  return post(`/admin/users/${id}/credits`, { operation, amount: Number(amount), reason });
}

export function updateSubscription(id, payload) {
  return patch(`/admin/users/${id}/subscription`, payload);
}

export function getAuditLog(params = {}) {
  return get('/admin/audit-log', { params });
}

// ── Second wave ──────────────────────────────────────────────────────────────

/** Dashboard cards. A card with `available: false` could not be measured. */
export function getMetrics() {
  return get('/admin/metrics');
}

export function getTimeline(id, limit = 200) {
  return get(`/admin/users/${id}/timeline`, { params: { limit } });
}

export function listUserConversations(id, params = {}) {
  return get(`/admin/users/${id}/conversations`, { params });
}

export function viewConversation(conversationId) {
  return get(`/admin/conversations/${conversationId}`);
}

export function regenerateReport(id, reason) {
  return post(`/admin/users/${id}/regenerate-report`, { confirm: true, reason });
}

/**
 * Cohort credit operation. Pass `dry_run: true` first — it resolves the cohort
 * and returns the count without writing, so a 500-user grant can be checked
 * before it becomes irreversible.
 */
export function bulkCredits(payload) {
  return post('/admin/credits/bulk', payload);
}

export function listFlags() {
  return get('/admin/flags');
}

export function setFlag(key, enabled, description = '') {
  return put(`/admin/flags/${key}`, { enabled, description });
}

export function setFlagOverride(key, founderId, enabled) {
  return put(`/admin/flags/${key}/users/${founderId}`, { enabled });
}

export function listBroadcasts() {
  return get('/admin/broadcasts');
}

export function createBroadcast(payload) {
  return post('/admin/broadcasts', payload);
}

export function deactivateBroadcast(id) {
  return del(`/admin/broadcasts/${id}`);
}

/** System-wide token usage, estimated cost and the unbilled backlog. */
export function getUsage(days = 30) {
  return get('/admin/usage', { params: { days } });
}

/** One founder's usage and remaining credits. */
export function getUserUsage(id, days = 30) {
  return get(`/admin/users/${id}/usage`, { params: { days } });
}

/** Replay unbilled usage against the ledger. Super Admin only. */
export function reconcileUsage() {
  return post('/admin/usage/reconcile', {});
}


// --- discovery calls -------------------------------------------------------
//
// A founder requests a slot from the team's real availability and it lands here
// as `pending`. Nothing is charged and no calendar event exists until somebody
// confirms it -- confirming is what creates the meeting and emails the founder.

/** The request queue: priority first, then soonest slot. */
export function listCallRequests({ onlyPending = true, limit = 50 } = {}) {
  return get('/admin/discovery-calls', {
    params: { only_pending: onlyPending, limit },
  });
}

/** Accept a request: creates the meeting and emails the founder. */
export function confirmCallRequest(callId) {
  return post(`/admin/discovery-calls/${callId}/confirm`, {});
}

/** Turn a request down. A reason is required -- the founder is owed one. */
export function declineCallRequest(callId, reason) {
  return post(`/admin/discovery-calls/${callId}/decline`, { reason });
}

// --- privacy center review queue -------------------------------------------
//
// Every Privacy Center action that needs a person lands here: data corrections,
// and email changes from founders who mistyped their address at signup and can
// no longer receive anything we send.
//
// These endpoints existed on the backend with NOTHING in the UI calling them,
// so the queue was invisible: rows accumulated `pending` and could only be seen
// by querying the database directly.

/** The review queue. `status` filters; omit it to see everything. */
export function listPrivacyRequests({ status = 'pending', limit = 50 } = {}) {
  return get('/admin/privacy-requests', {
    params: status ? { status, limit } : { limit },
  });
}

/**
 * Move a request on: 'in_progress', 'completed' or 'rejected'.
 *
 * `rejection_reason` is required by the API when rejecting — the founder is
 * owed a reason, and the endpoint refuses without one.
 */
export function resolvePrivacyRequest(requestId, { status, processingNotes, rejectionReason } = {}) {
  return patch(`/admin/privacy-requests/${requestId}`, {
    status,
    ...(processingNotes ? { processing_notes: processingNotes } : {}),
    ...(rejectionReason ? { rejection_reason: rejectionReason } : {}),
  });
}
