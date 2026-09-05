/**
 * Whether sign-in is configured — the env check ONLY, deliberately split out
 * of supabaseClient.js so that asking the question does not drag in the
 * Supabase SDK.
 *
 * App.jsx and Login.jsx both need this boolean on first paint. While it lived
 * alongside `createClient`, importing it pulled the whole SDK into the initial
 * bundle for every visitor — including the ones who only ever read the landing
 * page and never sign in. The SDK is now fetched on demand by services/auth.js
 * at the moment a provider button is actually pressed.
 */
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

/** Real Supabase credentials are present. */
export const supabaseEnvPresent = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

/**
 * Local-development stand-in for the whole email-code flow, so sign-in can be
 * clicked through with no Supabase project and no backend. services/auth.js
 * answers every call itself: no email is sent, the "code" is DEV_MOCK_CODE,
 * and the session is a placeholder token that satisfies the route guards.
 *
 * `import.meta.env.DEV` is a literal `false` in a production build, so Vite
 * deletes every branch behind this constant at build time. No server-side
 * variable can switch it on in production: by then it is not a variable.
 */
export const devMockAuth = import.meta.env.DEV && import.meta.env.VITE_DEV_MOCK_OTP === '1';
export const DEV_MOCK_CODE = '00000000';

/** Where founders without access are sent -- the waitlist site, which is now
 *  the public face of Ally on www. This app lives on app.goxlally.ai. */
export const WAITLIST_URL = import.meta.env.VITE_WAITLIST_URL || 'https://www.goxlally.ai';

export const supabaseConfigured = supabaseEnvPresent || devMockAuth;

if (!supabaseConfigured) {
  // eslint-disable-next-line no-console
  console.warn(
    'VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set — sign-in is disabled.'
  );
}

if (devMockAuth) {
  // eslint-disable-next-line no-console
  console.warn(
    `VITE_DEV_MOCK_OTP=1 — sign-in is MOCKED. No email is sent; the code is ${DEV_MOCK_CODE}.`
  );
}
