/**
 * services/presenceHint.js — a cross-site hint for the waitlist site.
 *
 * join.goxlally.ai is the front door for everyone, and it wants to greet a
 * founder who already has an account with "Go to my dashboard" or "Log in"
 * rather than the waitlist form. It cannot see this app's session -- different
 * origin -- so this app leaves one word in a cookie on the shared parent
 * domain, goxlally.ai, which both sites can read:
 *
 *   in   a sign-in just succeeded here
 *   out  a founder signed out, or their session could not be resumed
 *
 * The cookie carries nothing else: no token, no email, no name. Forging or
 * editing it changes which button the waitlist site shows, and nothing more --
 * every button lands on this app, which checks the real session as always.
 * It is deliberately not HttpOnly (this file sets it from JS) and is a plain
 * courtesy: with cookies blocked, the waitlist site simply shows the form.
 *
 * On localhost there is no domain attribute -- a host-only cookie -- and since
 * cookies ignore the port, the landing dev server on :3000 reads it too.
 */

const NAME = 'ally_hint';
const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

function domainAttribute() {
  const host = window.location.hostname;
  if (host === 'goxlally.ai' || host.endsWith('.goxlally.ai')) return '; domain=goxlally.ai';
  return '';
}

/** @param {'in' | 'out'} state */
export function setPresenceHint(state) {
  if (state !== 'in' && state !== 'out') return;
  try {
    const secure = window.location.protocol === 'https:' ? '; secure' : '';
    document.cookie = `${NAME}=${state}; path=/; max-age=${ONE_YEAR_SECONDS}${domainAttribute()}; samesite=lax${secure}`;
  } catch {
    // Cookies blocked. Nothing depends on the hint.
  }
}
