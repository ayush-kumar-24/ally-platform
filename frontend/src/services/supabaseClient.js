/**
 * services/supabaseClient.js — the ONLY place the Supabase JS client is created.
 *
 * Used exclusively for the OAuth handshake (signInWithOAuth + reading back the
 * resulting session). We never talk to Supabase for anything else — no direct
 * table access, no RLS-dependent queries — the backend's own API is the single
 * source of truth for everything except "who did Google say this is."
 *
 * Importing this module pulls in the Supabase SDK, so it is loaded on demand by
 * services/auth.js rather than statically. Anything that only needs to know
 * *whether* social login is available should import `supabaseConfigured` from
 * ./supabaseConfig, which costs nothing.
 */

import { createClient } from '@supabase/supabase-js';
import { supabaseConfigured } from './supabaseConfig';

export { supabaseConfigured };

// Only construct the client when configured; callers must check
// `supabaseConfigured` first (auth.js does this for every export).
export const supabase = supabaseConfigured
  ? createClient(
      import.meta.env.VITE_SUPABASE_URL,
      import.meta.env.VITE_SUPABASE_ANON_KEY,
      {
        auth: {
          // We read the session once on page load and hand it to our own backend
          // (POST /auth/session) -- Supabase's own session/refresh cycle is not
          // used afterward, so there's nothing to gain from persisting it.
          persistSession: false,
          detectSessionInUrl: true,
        },
      },
    )
  : null;
