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

/** Put a founder on a plan by hand. `reason` is required by the API. */
export function setPlan(id, tier, reason) {
  return post(`/admin/users/${id}/plan`, { tier, reason });
}

export function changeStatus(id, status, reason) {
  return post(`/admin/users/${id}/status`, { status, reason });
}

export function resetDiagnosis(id) {
  return post(`/admin/users/${id}/reset-diagnosis`, { confirm: true });
}

export function resetOnboarding(id) {
  return post(`/admin/users/${id}/reset-onboarding`, { confirm: true });
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

/**
 * Re-run report generation for a founder.
 *
 * Five minutes, not api.js's 20s default: this runs the reasoning pipeline
 * synchronously (trigger.py's regenerate_report_for_founder -> analyze_session),
 * which is a 203s job live-measured. On the default timeout the browser gave up
 * roughly three minutes before the server finished, so a regeneration that
 * actually succeeded was reported to the admin as a failure -- and clicking
 * again just started a second one.
 *
 * The endpoint answers 200 even when the pipeline fails; the real outcome is
 * `result.status` in the body, so callers must read it rather than trust the
 * status code.
 */
export function regenerateReport(id, reason) {
  return post(`/admin/users/${id}/regenerate-report`, { confirm: true, reason },
              { timeout: 300_000 });
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

// --- coupons ---------------------------------------------------------------
// Reading is view_users (support gets asked "how many of the 100 are left");
// creating decides what founders pay, so it is Super Admin only.

export function listCoupons({ includeInactive = true, limit = 100 } = {}) {
  return get('/admin/coupons', { params: { include_inactive: includeInactive, limit } });
}

export function createCoupon(payload) {
  return post('/admin/coupons', payload);
}

/** N unique single-use codes under one prefix — the partner/influencer shape.
 *  "First 100 customers" is the opposite: ONE code with max_redemptions: 100. */
export function bulkCoupons(payload) {
  return post('/admin/coupons/bulk', payload);
}

/** Only the fields it is safe to change after issue: description, caps, expiry,
 *  active. The code and its value are fixed once anyone could have seen it. */
export function updateCoupon(couponId, payload) {
  return patch(`/admin/coupons/${couponId}`, payload);
}

export function couponRedemptions(couponId, { limit = 200 } = {}) {
  return get(`/admin/coupons/${couponId}/redemptions`, { params: { limit } });
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

// --- founder feedback + support -------------------------------------------
//
// Everything a founder writes to us lands in `founder_feedback`: the Feedback
// page, star ratings, and — tagged `[Support request]` — anything sent from
// Help & Support or the help widget.
//
// These endpoints existed with no UI calling them, so every bug report and
// support message was stored correctly and read by nobody, while the product
// told the founder "our team will get back to you by email".

/** Ratings and written notes, newest first. `type` filters; omit for all. */
export function listFounderFeedback({ type = null, limit = 100 } = {}) {
  return get('/admin/founder-feedback', {
    params: type ? { feedback_type: type, limit } : { limit },
  });
}

/** Counts and average rating, for the summary strip. */
export function founderFeedbackStats({ type = null } = {}) {
  return get('/admin/founder-feedback/stats', {
    params: type ? { feedback_type: type } : {},
  });
}

/**
 * Questions the help bot could not answer, grouped by question, most-asked
 * first. This is the list of help answers worth writing next.
 */
export function listSupportMisses({ limit = 100 } = {}) {
  return get('/admin/support-misses', { params: { limit } });
}

// --- waitlist -------------------------------------------------------------
// Access to Ally is granted by approval, never by signing up: sign-ups are off
// at the Supabase project level, so an address with no identity cannot even
// receive a login code. Approving here is what creates that identity and emails
// the founder -- it is the only door in.

/**
 * The queue. `status` is one of pending | approved | rejected | all; pending is
 * the only view with work in it, so it is the default on the server too.
 *
 * Returns { registrations, counts, cap } -- `cap` carries the 300-place budget
 * and whether access can be granted at all right now (it cannot without the
 * service role key, and the screen says so rather than failing at the click).
 */
export function listWaitlist({ status = 'pending', limit = 100, offset = 0 } = {}) {
  return get('/admin/waitlist', { params: { status, limit, offset } });
}

/** Approve: creates the founder's login and emails them. Not undoable. */
export function approveRegistration(registrationId) {
  return post(`/admin/waitlist/${registrationId}/approve`, {});
}

/** Reject, with a reason. Recorded, never emailed to the person. */
export function rejectRegistration(registrationId, reason) {
  return post(`/admin/waitlist/${registrationId}/reject`, { reason });
}

/**
 * Who opening `slots` places would let in — the front of the queue, oldest
 * first, in the order they would be approved. Changes nothing.
 *
 * Its own call rather than a flag on openWaitlistSlots: the screen shows this
 * list and waits for a person to read it, because the act it precedes mints
 * that many logins and sends that many emails.
 */
export function previewWaitlistSlots(slots) {
  return get('/admin/waitlist/slots/preview', { params: { slots } });
}

/**
 * Open `slots` places and let the front of the queue into them. Super admin
 * only, and not idempotent — two calls open twice as many places.
 *
 * Returns { slots, approved, failures, cap }. `failures` is per person and is
 * not an error: one identity call failing does not deny the rest their place,
 * and those rows stay pending at the front of the queue.
 */
export function openWaitlistSlots(slots) {
  return post('/admin/waitlist/slots/open', { slots });
}
