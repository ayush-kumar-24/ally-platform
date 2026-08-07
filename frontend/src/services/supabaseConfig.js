/**
 * Whether social login is configured — the env check ONLY, deliberately split
 * out of supabaseClient.js so that asking the question does not drag in the
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

export const supabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

if (!supabaseConfigured) {
  // eslint-disable-next-line no-console
  console.warn(
    'VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set — social login is disabled.'
  );
}
