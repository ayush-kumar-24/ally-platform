/**
 * services/consents.js — consent persistence.
 *
 * Wraps POST/GET /consents. Pages import from here, never from api.js directly,
 * so the wire format and the "what version is current" rule live in one place.
 *
 * The versions below MUST match app/consents/defaults.py on the backend and the
 * version tag rendered next to the checkbox. Bump all three together when the
 * Terms or Privacy Policy materially changes — the backend then reports
 * `needs_reconsent: true` for everyone who agreed to the older text.
 */

import { get, post } from './api';

export const CURRENT_VERSIONS = {
  terms: '1.0',
  privacy: '1.0',
};

/** Consent captured before an authenticated identity exists, awaiting flush. */
const PENDING_KEY = 'ally.pending_consent';

/**
 * Persist a consent record for the signed-in founder.
 *
 * @param {{ agreeTerms: boolean, agreeDiagnosis: boolean }} choices
 * @returns {Promise<object>} the stored consent record
 * @throws {ApiError} 422 if terms weren't accepted or a version is malformed
 */
export function recordConsent({ agreeTerms, agreeDiagnosis }) {
  return post('/consents', {
    terms_version: CURRENT_VERSIONS.terms,
    privacy_version: CURRENT_VERSIONS.privacy,
    agree_terms: agreeTerms,
    agree_diagnosis: agreeDiagnosis,
  });
}

/** Current consent + full history + whether re-consent is due. */
export function getConsents() {
  return get('/consents');
}

// ── Deferred capture ─────────────────────────────────────────────────────────
// Consent is collected on the login screen — i.e. potentially before the backend
// knows who the founder is. Rather than drop it, we hold it locally and flush it
// once a session exists. This keeps the moment of consent truthful: what the user
// actually ticked, at the time they ticked it.

export function savePendingConsent(choices) {
  localStorage.setItem(PENDING_KEY, JSON.stringify({ ...choices, capturedAt: new Date().toISOString() }));
}

export function getPendingConsent() {
  try {
    return JSON.parse(localStorage.getItem(PENDING_KEY) || 'null');
  } catch {
    return null;
  }
}

export function clearPendingConsent() {
  localStorage.removeItem(PENDING_KEY);
}

/**
 * Send any locally-held consent to the backend. Safe to call on every app start
 * and after sign-in: it no-ops when there is nothing pending, and the backend is
 * idempotent, so a re-send can't create a duplicate ledger entry.
 *
 * @returns {Promise<object|null>} the stored record, or null if nothing to flush
 */
export async function flushPendingConsent() {
  const pending = getPendingConsent();
  if (!pending) return null;
  const record = await recordConsent(pending); // throws → keep it pending, retry later
  clearPendingConsent();
  return record;
}
