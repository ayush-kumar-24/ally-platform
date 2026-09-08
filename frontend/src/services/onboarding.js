/**
 * services/onboarding.js — is the founder's onboarding profile finished?
 *
 * WHY A SEPARATE SERVICE. `/profile/validate` is the same computation the API
 * runs in `require_profile_complete`, which is what actually refuses
 * /diagnosis/start, /founder-dna/start and /current-problem/start with a 409.
 * Reading the same endpoint means the UI and the server can only ever disagree
 * about timing, never about the answer.
 *
 * THE SERVER IS STILL THE AUTHORITY. Everything here is so a founder is sent
 * somewhere useful instead of into a page that 409s. Somebody who edits the
 * bundle gains nothing.
 *
 * CACHED FOR THE SESSION, because the guard runs on every navigation into the
 * diagnosis and the answer only changes when the profile is written. Any write
 * clears it (see services/profile.js), so finishing onboarding takes effect
 * immediately rather than after a reload.
 *
 * A FAILED CHECK IS NOT CACHED. Caching a rejected promise would make one
 * dropped request look like a permanent verdict for the rest of the session.
 */

import { get } from './api';

let pending = null;

/** `{ valid, missing: [{field, label, section}] }`. */
export function checkProfileComplete({ force = false } = {}) {
  if (force || !pending) {
    pending = get('/profile/validate').catch((err) => {
      pending = null;          // let the next caller try again
      throw err;
    });
  }
  return pending;
}

/** Called after any profile write, so the next check re-reads. */
export function forgetProfileComplete() {
  pending = null;
}
