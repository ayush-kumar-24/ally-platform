/**
 * services/privacy.js — Privacy Center (data-subject rights).
 *
 * Wraps the /privacy endpoints. Pages import from here, never from api.js
 * directly, so the wire format lives in one place.
 *
 * Note the deliberate split between withdraw and delete: withdrawing consent
 * pauses processing but keeps the account; deleting schedules erasure. They are
 * different rights with different consequences, so they are different calls and
 * must stay separate in the UI too.
 */

import { del, get, post } from './api';

/** GDPR Art 15 + 20 — everything we hold, served immediately. */
export function exportData() {
  return get('/privacy/export');
}

/** GDPR Art 17 — schedules erasure after a recovery window. Requires confirmation. */
export function deleteAccount() {
  return del('/privacy/account', { data: { confirm: true } });
}

/** GDPR Art 7(3) — revoke consent, pause processing, keep the account. */
export function withdrawConsent() {
  return post('/privacy/withdraw', { confirm: true });
}

/** GDPR Art 18 — pause or resume processing. Reversible by design. */
export function restrictProcessing(restricted = true) {
  return post('/privacy/restrict', { restricted });
}

/** Current standing + the request history. */
export function getPrivacyStatus() {
  return get('/privacy/status');
}

/**
 * Turn an export payload into a downloaded file. Kept here rather than in the
 * page so the "what does download mean" detail isn't duplicated per caller.
 */
export function downloadExport(bundle, filename = 'ally-data-export.json') {
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoke on the next tick — revoking synchronously can cancel the download in
  // some browsers before it has started reading the blob.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
