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
 * @param {{ agreeTerms: boolean, agreeDiagnosis: boolean, ageConfirmed: boolean }} choices
 * @returns {Promise<object>} the stored consent record
 * @throws {ApiError} 422 if terms weren't accepted or a version is malformed
 */
export function recordConsent({ agreeTerms, agreeDiagnosis, ageConfirmed }) {
  return post('/consents', {
    terms_version: CURRENT_VERSIONS.terms,
    privacy_version: CURRENT_VERSIONS.privacy,
    agree_terms: agreeTerms,
    agree_diagnosis: agreeDiagnosis,
    // Stored alongside the consent so the attestation carries the same
    // timestamp and document versions as the rest of it.
    age_confirmed: ageConfirmed,
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

// ── Cookie choice ────────────────────────────────────────────────────────────
// The banner ENFORCES the choice immediately and locally -- that part never
// depended on the server and still does not. What this adds is the RECORD:
// localStorage is per-device and vanishes when someone clears site data, so it
// cannot answer "what did this founder choose, and when". DPDP expects a Data
// Fiduciary to be able to demonstrate consent.
//
// Deferred for the same reason the terms consent is: the banner can be answered
// before anyone signs in, and the row is founder-scoped. Held locally, flushed
// when a session exists, with the ORIGINAL timestamp preserved.

const PENDING_COOKIES_KEY = 'ally_pending_cookie_choice';

/** Post one cookie choice. Requires a session. */
export function recordCookieChoice({ analytics, marketing, functional, bannerAction, chosenAt }) {
  return post('/cookie-preferences', {
    analytics: Boolean(analytics),
    marketing: Boolean(marketing),
    functional: Boolean(functional),
    banner_action: bannerAction,
    chosen_at: chosenAt,
  });
}

/**
 * Record the choice if we can, hold it if we cannot.
 *
 * Never throws and never blocks the banner closing: enforcement already
 * happened client-side, and a founder must not be stuck behind a consent
 * dialog because our API had a bad moment.
 */
export async function syncCookieChoice(choice) {
  const payload = { ...choice, chosenAt: choice.chosenAt || new Date().toISOString() };
  try {
    await recordCookieChoice(payload);
    localStorage.removeItem(PENDING_COOKIES_KEY);
  } catch {
    try {
      localStorage.setItem(PENDING_COOKIES_KEY, JSON.stringify(payload));
    } catch { /* private mode, quota -- the local choice still stands */ }
  }
}

/** Send a held cookie choice once a session exists. Safe to call on every start. */
export async function flushPendingCookieChoice() {
  let pending = null;
  try {
    pending = JSON.parse(localStorage.getItem(PENDING_COOKIES_KEY) || 'null');
  } catch { return null; }
  if (!pending) return null;
  try {
    const saved = await recordCookieChoice(pending);
    localStorage.removeItem(PENDING_COOKIES_KEY);
    return saved;
  } catch {
    return null;      // keep it pending, try again next start
  }
}
