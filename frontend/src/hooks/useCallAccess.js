/**
 * hooks/useCallAccess.js — can this founder actually complete a call booking?
 *
 * WHY NOT PlanGate/FEATURES.CALL_BOOKING: call_booking lives in the backend's
 * _UNIVERSAL feature set (app/plans/catalog.py: "everyone may book; only the
 * free allowance differs"). Every tier has it, so gating on the feature flag
 * lets free founders straight through to a booking the server will refuse.
 * It would look like it works and would not.
 *
 * The honest signal is the quote: GET /plans/me/call-quote returns
 * {is_free, price_inr, free_remaining}. free_remaining is how many calls this
 * founder can book at no cost right now -- 0 for free tier, and also 0 for a
 * starter who has already used this month's one. Since no payment flow exists
 * in the frontend yet, 0 means "cannot complete a booking", whatever the tier.
 *
 * Fetched once per session and shared: eleven entry points ask this question,
 * and eleven identical requests on every dashboard load is not a courtesy.
 */

import { useEffect, useState } from 'react';
import { getCallQuote } from '../services/plans';

let cached;             // undefined = never fetched; null = fetched and failed
let inflight = null;    // dedupes concurrent first-mounts

/** Drop the cached quote so the next mount refetches -- call after a booking. */
export function refreshCallAccess() {
  cached = undefined;
  inflight = null;
}

export function useCallAccess() {
  const [quote, setQuote] = useState(() => (cached === undefined ? undefined : cached));

  useEffect(() => {
    if (cached !== undefined) return undefined;

    let cancelled = false;
    // A failed quote resolves to null rather than rejecting: this hook decides
    // whether to show a link, and a network blip should not surface as an
    // unhandled rejection on six pages at once.
    inflight = inflight ?? getCallQuote().then((q) => q ?? null).catch(() => null);
    inflight.then((q) => {
      cached = q;
      inflight = null;
      if (!cancelled) setQuote(q);
    });

    return () => { cancelled = true; };
  }, []);

  const loading = quote === undefined;
  const freeRemaining = quote?.free_remaining ?? null;

  return {
    loading,
    quote: quote ?? null,
    /* Fails CLOSED. If the quote could not be read we hide the booking path
       rather than show one we cannot stand behind -- offering a founder a
       button that 402s is the exact failure this hook exists to prevent, and
       it is the one that costs trust. Hidden-but-available is recoverable;
       advertised-but-broken is not. */
    canBook: freeRemaining != null && freeRemaining > 0,
  };
}
