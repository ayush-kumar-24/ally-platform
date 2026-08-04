/**
 * services/auth.js — Google/LinkedIn sign-in via Supabase, then handoff to our
 * own backend.
 *
 * Flow (matches backend/app/api/v1/auth/routes.py's own docstring):
 *   1. signInWithGoogle()/signInWithLinkedIn() redirects the whole page to the
 *      provider, then back here.
 *   2. On return, Supabase's client parses the token from the URL automatically
 *      (detectSessionInUrl) -- consumeOAuthRedirect() reads that session.
 *   3. Its access_token is exchanged at POST /auth/session for OUR OWN backend
 *      tokens (setTokens stores those) -- from here on, nothing about Supabase
 *      matters; services/api.js's normal Bearer-token flow takes over.
 *
 * consumeOAuthRedirect() itself is provider-agnostic -- it just reads back
 * whatever session Supabase parsed from the URL, so both providers share it.
 */

import { clearTokens, getRefreshToken, post, setTokens } from './api';
import { supabase, supabaseConfigured } from './supabaseClient';

export class AuthNotConfiguredError extends Error {
  constructor() {
    super('Social login is not configured (missing Supabase env vars).');
    this.name = 'AuthNotConfiguredError';
  }
}

async function signInWithProvider(provider) {
  if (!supabaseConfigured) throw new AuthNotConfiguredError();
  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: window.location.origin + '/guided/login' },
  });
  if (error) throw error;
}

/** Redirects the page to Google's consent screen. Never returns (full navigation). */
export function signInWithGoogle() {
  return signInWithProvider('google');
}

/**
 * Redirects to LinkedIn's consent screen. Never returns (full navigation).
 * Uses Supabase's "linkedin_oidc" provider id -- the current OIDC-based
 * LinkedIn integration; the older "linkedin" provider is deprecated on
 * Supabase's side and won't be enabled by a fresh LinkedIn provider setup.
 */
export function signInWithLinkedIn() {
  return signInWithProvider('linkedin_oidc');
}

/**
 * End the session, properly.
 *
 * The refresh token is revoked server-side (it lives 30 days, so simply
 * dropping it client-side would leave a working credential in the wild), then
 * every local trace of the founder is cleared. The button that used to sit here
 * only showed a "Signing out..." toast -- it made no request, cleared no token,
 * and left you signed in.
 *
 * Never throws: a founder pressing sign out must end up signed out even if the
 * revoke call fails, so the local clear happens either way.
 */
export async function logout() {
  const refresh_token = getRefreshToken();
  try {
    if (refresh_token) await post('/auth/logout', { refresh_token });
  } catch {
    // Offline, or the token was already revoked. Clearing locally still matters.
  } finally {
    clearTokens();
    localStorage.removeItem('ally_founder');
    if (supabaseConfigured) {
      try { await supabase.auth.signOut(); } catch { /* nothing left to do */ }
    }
  }
}

/**
 * Local-development sign-in, used only when Supabase is not configured.
 *
 * There is no provider token to exchange, so the backend's dev auth provider
 * takes a founder's `user_id` as the bearer instead (AUTH_PROVIDER=dev, which
 * factory.py refuses outright when ENVIRONMENT=production). Set the founder in
 * VITE_DEV_FOUNDER_TOKEN.
 *
 * Without this the local app runs with no token at all, so every write 401s --
 * onboarding appears to work and then silently fails to save a single answer.
 * Returns null when no dev token is configured.
 */
export async function startDevSession() {
  const token = import.meta.env.VITE_DEV_FOUNDER_TOKEN;
  if (!token) return null;
  clearTokens();
  const result = await post('/auth/session', {}, {
    headers: { Authorization: `Bearer ${token}` },
  });
  setTokens(result);
  return result.founder;
}

/**
 * Call once on the login page's mount. If the URL carries a fresh OAuth
 * session (i.e. we just got redirected back from Google), exchanges it for a
 * backend session and returns the founder identity; otherwise returns null.
 */
export async function consumeOAuthRedirect() {
  if (!supabaseConfigured) return null;

  const { data, error } = await supabase.auth.getSession();
  if (error || !data?.session?.access_token) return null;

  const supabaseToken = data.session.access_token;
  // Done with the Supabase client session either way -- our own tokens take
  // over next, and persistSession is already off, but this also clears the
  // in-memory session so a stale one can't be read again on re-render.
  await supabase.auth.signOut();

  // api.js's request interceptor overwrites the Authorization header with
  // whatever's in localStorage on every call -- clear any leftover backend
  // token first, or the explicit Supabase bearer below would be silently
  // replaced (or, worse, an unrelated stale session reused).
  clearTokens();
  const result = await post('/auth/session', {}, {
    headers: { Authorization: `Bearer ${supabaseToken}` },
  });
  setTokens(result);
  return result.founder; // { id, email, provider }
}
