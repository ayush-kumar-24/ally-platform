/**
 * services/discovery.js — discovery call booking.
 *
 * Booking is entitlement-gated server-side: the founder's plan decides whether the
 * call is free or ₹300. `getCallQuote()` (services/plans.js) tells the UI which,
 * so the button can say the true price before anyone clicks it.
 */

import { get, post, prune } from './api';

export function getSlots(days = 7) {
  return get('/discovery/slots', { params: { days } });
}

export function listCalls() {
  return get('/discovery/calls');
}

export function getCall(callId) {
  return get(`/discovery/calls/${callId}`);
}

/**
 * Book a call.
 *
 * A 402 means the free allowance is used up and payment is required — the server
 * refuses rather than booking something unpaid. `paymentReference` is how a paid
 * booking is asserted once the gateway is live.
 */
export function bookCall({ scheduledAt, timezone, notes, paymentReference }) {
  return post('/discovery/book', prune({
    scheduled_at: scheduledAt,
    timezone,
    notes_pre_call: notes,
    payment_reference: paymentReference,
  }));
}
