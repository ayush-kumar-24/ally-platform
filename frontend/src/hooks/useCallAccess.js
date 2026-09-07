/**
 * hooks/useCallAccess.js — what a discovery call costs this founder.
 *
 * THIS HOOK USED TO BE A GATE, AND THE GATE CLOSED ON EVERYONE. It returned
 * `canBook: free_remaining > 0`, and `free_calls_per_month` is 0 on every tier
 * in the catalog -- free, starter, pro, all of them. So `canBook` was false for
 * every founder alive, and the six places that asked it hid the discovery call
 * entirely: the sidebar item, the dashboard card, the Help & Support link, and
 * the page's own scheduler. The feature did not break; it was gated to nobody.
 *
 * The premise was true when it was written. Booking then consumed an allowance
 * and the server answered 402 without one. Booking is now a REQUEST: POST
 * /discovery/book writes a `pending` row, charges nothing, consumes no
 * allowance and carries no entitlement gate, and CALL_BOOKING sits in the
 * catalog's _BASE set precisely because "booking is open to everyone and every
 * call is paid at CALL_PRICE_INR. It is sold beside the plans, not inside one."
 * Nobody can be refused, so there is nothing left to gate on.
 *
 * What the quote is still good for is the price -- GET /plans/me/call-quote
 * returns {is_free, price_inr, free_remaining} -- so a founder is told what a
 * call costs before they ask for one. A price that fails to load hides the
 * price, never the booking.
 *
 * Fetched once per session and shared: six entry points ask this question, and
 * six identical requests on every dashboard load is not a courtesy.
 */

import { useEffect, useState } from 'react';
import { getCallQuote } from '../services/plans';

let cached;             // undefined = never fetched; null = fetched and failed
let inflight = null;    // dedupes concurrent first-mounts

/** Drop the cached quote so the next mount refetches. */
export function refreshCallAccess() {
  cached = undefined;
  inflight = null;
}

export function useCallAccess() {
  const [quote, setQuote] = useState(() => (cached === undefined ? undefined : cached));

  useEffect(() => {
    if (cached !== undefined) return undefined;

    let cancelled = false;
    // A failed quote resolves to null rather than rejecting: this hook supplies
    // a price, and a network blip should not surface as an unhandled rejection
    // on six pages at once.
    inflight = inflight ?? getCallQuote().then((q) => q ?? null).catch(() => null);
    inflight.then((q) => {
      cached = q;
      inflight = null;
      if (!cancelled) setQuote(q);
    });

    return () => { cancelled = true; };
  }, []);

  return {
    loading: quote === undefined,
    quote: quote ?? null,
    /** Rupees for one call, or null if the quote could not be read. Callers
     *  render the price when it is known and stay quiet when it is not --
     *  never hide the booking itself, which is open to every founder. */
    price: quote?.price_inr ?? null,
  };
}
