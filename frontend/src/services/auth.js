/**
 * services/auth.js — email + OTP + password sign-in via Supabase, then handoff
 * to our own backend.
 *
 * Two ways in, both ending at the same place:
 *
 *   New founder / forgot password
 *     1. sendEmailOtp(email)                 -- Supabase mails a 6-digit code
 *     2. verifyOtpAndSetPassword(email, code, password)
 *          verifyOtp   -> a real Supabase session
 *          updateUser  -> stores the password they just chose
 *          POST /auth/session -> OUR tokens (and, first time, the founder row)
 *
 *   Returning founder
 *     signInWithPassword(email, password) -> POST /auth/session
 *
 * Their email IS their login id -- there is no separate identifier to remember.
 *
 * From the exchange onward nothing about Supabase matters: services/api.js's
 * normal Bearer-token flow takes over, and the backend verifies the token by
 * signature without caring which of these flows produced it (see
 * backend/app/core/auth/supabase_provider.py).
 *
 * No redirects anywhere in here -- unlike the OAuth flow this replaces, the
 * whole thing happens on one page, so there is no "consume the redirect on
 * mount" step and no session parsed out of the URL.
 */

import { clearTokens, post, setTokens } from './api';
import { setPresenceHint } from './presenceHint';
import { DEV_MOCK_CODE, devMockAuth, supabaseConfigured, WAITLIST_URL } from './supabaseConfig';

/**
 * Local development only: a placeholder session so the login flow can be
 * walked with no Supabase and no backend. Compiled out of production builds
 * with `devMockAuth` (see supabaseConfig.js). The token satisfies the route
 * guards; every API call still fails, which is the point -- this is for
 * checking the flow, not for using the product.
 */
function mockSession(email) {
  clearTokens();
  setTokens({ access_token: 'dev-mock-access-token' });
  setPresenceHint('in');
  return { id: 'dev-mock-founder', email: email.trim().toLowerCase(), provider: 'mock' };
}

const WAITLIST_HOST = (() => {
  try { return new URL(WAITLIST_URL).host; } catch { return WAITLIST_URL; }
})();

/**
 * The Supabase SDK is ~40 kB gzipped and is needed only while signing in, so it
 * is fetched at the moment a founder submits the login form rather than shipped
 * to every visitor who loads the landing page. Vite caches the module, so
 * repeat calls do not re-download it.
 */
async function getSupabase() {
  const { supabase } = await import('./supabaseClient');
  return supabase;
}

export class AuthNotConfiguredError extends Error {
  constructor() {
    super('Sign-in is not configured (missing Supabase env vars).');
    this.name = 'AuthNotConfiguredError';
  }
}

/**
 * A sign-in step that failed for a reason the founder can act on -- wrong code,
 * expired code, wrong password, weak password.
 *
 * Supabase's own messages are written for developers ("Token has expired or is
 * invalid"), so they are translated once, here, rather than leaking into the UI
 * or being re-guessed at each call site.
 */
export class AuthStepError extends Error {
  constructor(message) {
    super(message);
    this.name = 'AuthStepError';
  }
}

function translate(error, fallback) {
  const raw = (error?.message || '').toLowerCase();
  if (raw.includes('expired') || (raw.includes('invalid') && raw.includes('token'))) {
    return new AuthStepError('That code is wrong or has expired. Request a new one.');
  }
  if (raw.includes('invalid login credentials')) {
    return new AuthStepError('That email and password do not match. Try again, or reset your password.');
  }
  if (raw.includes('password') && (raw.includes('short') || raw.includes('least') || raw.includes('weak'))) {
    return new AuthStepError('Please choose a longer password.');
  }
  if (raw.includes('rate limit') || raw.includes('too many') || error?.status === 429) {
    return new AuthStepError('Too many attempts. Please wait a minute and try again.');
  }
  // Sign-ups are closed at the Supabase project level and this client never
  // asks to create a user (see sendEmailOtp), so this is exactly one case: an
  // address the waitlist has not approved. Saying so does reveal that the
  // address is not approved -- accepted, because a founder who typed their
  // email and got a vague error would have no idea what to do next.
  if (raw.includes('not authorized') || raw.includes('signups not allowed')) {
    return new AuthStepError(`This email hasn't been approved for Ally yet. Join the waitlist at ${WAITLIST_HOST}.`);
  }
  return new AuthStepError(fallback);
}

/**
 * Trade a verified Supabase access token for OUR backend session.
 *
 * api.js's request interceptor overwrites the Authorization header with
 * whatever's in localStorage on every call -- clear any leftover backend token
 * first, or the explicit Supabase bearer below would be silently replaced (or,
 * worse, an unrelated stale session reused).
 *
 * The Supabase session is signed out afterwards: our own tokens take over, and
 * `persistSession` is already off, but this also clears the in-memory session
 * so a stale one can't be read again on re-render.
 */
async function exchangeForBackendSession(supabaseToken) {
  clearTokens();
  const result = await post('/auth/session', {}, {
    headers: { Authorization: `Bearer ${supabaseToken}` },
  });
  setTokens(result);
  setPresenceHint('in');
  try {
    await (await getSupabase()).auth.signOut();
  } catch {
    // Nothing left to do -- our tokens are already stored.
  }
  return result.founder; // { id, email, provider }
}

/**
 * Mail a sign-in code to `email`.
 *
 * `shouldCreateUser: false`: this call never creates an account. Access to
 * Ally is granted by the waitlist -- approving a registration on
 * join.goxlally.ai creates the founder's auth user (server-side, with the
 * service role), and only then will Supabase mail this address a code. An
 * unapproved address gets "Signups not allowed", which translate() turns into
 * a pointer at the waitlist. The flag is client-side courtesy; the actual
 * gate is the project's "Allow new users to sign up" switch being OFF, which
 * no client code can override.
 *
 * Both journeys still share this one call: a first-time (approved) founder
 * sets their password after verifying, and an existing founder who has
 * forgotten theirs simply gets a code.
 *
 * `emailRedirectTo` is not set: we want a code, not a magic link. The Supabase
 * email template must use {{ .Token }} for this to arrive as digits.
 */
export async function sendEmailOtp(email) {
  if (!supabaseConfigured) throw new AuthNotConfiguredError();
  if (devMockAuth) return;
  const supabase = await getSupabase();
  const { error } = await supabase.auth.signInWithOtp({
    email: email.trim().toLowerCase(),
    options: { shouldCreateUser: false },
  });
  if (error) throw translate(error, "We couldn't send that code. Please try again.");
}

/**
 * Verify the emailed code, save the password and name the founder chose, and
 * start a backend session. Returns their identity, or throws AuthStepError.
 *
 * `fullName` goes into Supabase's `user_metadata.full_name` because that is
 * exactly where the backend already looks: provisioning.py's _display_name()
 * reads it off the token's claims to name the founder row. Google used to fill
 * that field in for us; with email sign-in nobody does, and without this every
 * new founder would be provisioned -- and greeted -- as the local part of their
 * email address.
 *
 * Order matters twice over:
 *
 *   updateUser needs the Supabase session verifyOtp just created, so it must
 *   run BEFORE exchangeForBackendSession signs that session out.
 *
 *   The access token verifyOtp returned was minted before that metadata
 *   existed, so it still carries the old (empty) claims. refreshSession mints a
 *   new one that includes the name -- exchanging the stale token would provision
 *   the founder under the fallback name and quietly waste the field.
 *
 * A password Supabase rejects stops the whole step rather than being waved
 * through: telling a founder their password was saved when it wasn't would lock
 * them out of the password path permanently, and the code they hold is still
 * good for a retry.
 */
export async function verifyOtpAndSetPassword(email, code, password, fullName = '') {
  if (!supabaseConfigured) throw new AuthNotConfiguredError();
  if (devMockAuth) {
    if (code.trim() !== DEV_MOCK_CODE) {
      throw new AuthStepError(`Dev mock: the code is ${DEV_MOCK_CODE}.`);
    }
    return mockSession(email);
  }
  const supabase = await getSupabase();

  const { data, error } = await supabase.auth.verifyOtp({
    email: email.trim().toLowerCase(),
    token: code.trim(),
    type: 'email',
  });
  if (error || !data?.session?.access_token) {
    throw translate(error, 'That code is wrong or has expired. Request a new one.');
  }

  const name = fullName.trim();
  const { error: updateError } = await supabase.auth.updateUser({
    password,
    ...(name ? { data: { full_name: name } } : {}),
  });
  if (updateError) {
    throw translate(updateError, "We couldn't save that password. Please choose another.");
  }

  let accessToken = data.session.access_token;
  if (name) {
    // Best-effort: if the refresh fails we still have a perfectly valid token,
    // and a founder provisioned under the email-derived fallback name can edit
    // it on their profile. Blocking a successful sign-in over a display name
    // would be the worse trade.
    try {
      const { data: refreshed } = await supabase.auth.refreshSession();
      if (refreshed?.session?.access_token) accessToken = refreshed.session.access_token;
    } catch { /* keep the token we already hold */ }
  }

  return exchangeForBackendSession(accessToken);
}

/** Returning founder: email + the password they set. Returns their identity. */
export async function signInWithPassword(email, password) {
  if (!supabaseConfigured) throw new AuthNotConfiguredError();
  if (devMockAuth) return mockSession(email);
  const supabase = await getSupabase();

  const { data, error } = await supabase.auth.signInWithPassword({
    email: email.trim().toLowerCase(),
    password,
  });
  if (error || !data?.session?.access_token) {
    throw translate(error, 'That email and password do not match. Try again, or reset your password.');
  }

  return exchangeForBackendSession(data.session.access_token);
}

/**
 * End the session, properly.
 *
 * The refresh token is revoked server-side (it lives 30 days, so simply
 * dropping it client-side would leave a working credential in the wild), then
 * every local trace of the founder is cleared.
 *
 * The refresh token itself is never read here -- it rides as the HttpOnly
 * cookie (api.js's withCredentials), and the backend clears that cookie as
 * part of this same call. Always attempted (no more "if there's a token"
 * guard): there is no client-side way to know whether the cookie is present,
 * and POSTing with none just means the backend has nothing to revoke.
 *
 * Never throws: a founder pressing sign out must end up signed out even if the
 * revoke call fails, so the local clear happens either way.
 */
export async function logout() {
  try {
    await post('/auth/logout');
  } catch {
    // Offline, or the token was already revoked. Clearing locally still matters.
  } finally {
    clearTokens();
    setPresenceHint('out');
    localStorage.removeItem('ally_founder');
    if (supabaseConfigured && !devMockAuth) {
      try { await (await getSupabase()).auth.signOut(); } catch { /* nothing left to do */ }
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
  setPresenceHint('in');
  return result.founder;
}
