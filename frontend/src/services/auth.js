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

import { clearTokens, post, setTokens } from './api';
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
