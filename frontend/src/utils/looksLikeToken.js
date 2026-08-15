/**
 * Guards against ever displaying a raw token as a person's name or email.
 *
 * Live-reproduced: with the local backend in dev-auth mode, a real Supabase
 * OAuth JWT handed back after Google/LinkedIn login is treated as an opaque
 * identity string rather than verified -- the backend then synthesizes
 * `"<the whole JWT>@ally.local"` as a placeholder email for a founder who
 * hasn't provisioned yet. Login.jsx's fallback chain (profile.full_name ||
 * founder.email || ...) had no reason to distrust that value, so a 250+
 * character JWT ended up rendered as the founder's name on their very first
 * screen. This is a defensive backstop at the display layer, independent of
 * whatever upstream cause produces a bad value -- a real name or email is
 * never this long or this shaped, regardless of why a bad one showed up.
 */

// A JWT is three base64url segments joined by '.'; the header segment always
// starts with the base64 of '{"' (alg/typ), i.e. "eyJ". Matches any of our
// own tokens or a raw Supabase token uniformly.
const JWT_SHAPE = /^eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}/;
const MAX_PLAUSIBLE_LENGTH = 120; // a real name or email address is well under this

export function looksLikeToken(value) {
  if (!value || typeof value !== 'string') return false;
  return value.length > MAX_PLAUSIBLE_LENGTH || JWT_SHAPE.test(value);
}

/** First candidate that is truthy and does not look like a token, else the fallback. */
export function firstSafe(candidates, fallback = '') {
  for (const c of candidates) {
    if (c && !looksLikeToken(c)) return c;
  }
  return fallback;
}
