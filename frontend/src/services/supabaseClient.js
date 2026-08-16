/**
 * services/supabaseClient.js — the ONLY place the Supabase JS client is created.
 *
 * Used exclusively for authentication: mailing the OTP, verifying it, setting a
 * password, and signing in with one. We never talk to Supabase for anything
 * else — no direct table access, no RLS-dependent queries — the backend's own
 * API is the single source of truth for everything except "is this really the
 * owner of that email address."
 *
 * Importing this module pulls in the Supabase SDK, so it is loaded on demand by
 * services/auth.js rather than statically. Anything that only needs to know
 * *whether* sign-in is available should import `supabaseConfigured` from
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
          // The Supabase session exists only long enough to hand its access
          // token to our own backend (POST /auth/session), which then issues the
          // tokens the app actually runs on -- so there is nothing worth
          // persisting, and Supabase's own refresh cycle is never used.
          persistSession: false,
          autoRefreshToken: false,
          // Nothing arrives by redirect any more: the email/OTP/password flow
          // completes on the login page without ever leaving it, so there is no
          // token in the URL to detect.
          detectSessionInUrl: false,
        },
      },
    )
  : null;
