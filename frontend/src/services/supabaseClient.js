/**
 * services/supabaseClient.js — the ONLY place the Supabase JS client is created.
 *
 * Used exclusively for the OAuth handshake (signInWithOAuth + reading back the
 * resulting session). We never talk to Supabase for anything else — no direct
 * table access, no RLS-dependent queries — the backend's own API is the single
 * source of truth for everything except "who did Google say this is."
 */

import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

if (!supabaseConfigured) {
  // eslint-disable-next-line no-console
  console.warn(
    'VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set — social login is disabled.'
  );
}

// Only construct the client when configured; callers must check
// `supabaseConfigured` first (auth.js does this for every export).
export const supabase = supabaseConfigured
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        // We read the session once on page load and hand it to our own backend
        // (POST /auth/session) -- Supabase's own session/refresh cycle is not
        // used afterward, so there's nothing to gain from persisting it.
        persistSession: false,
        detectSessionInUrl: true,
      },
    })
  : null;
