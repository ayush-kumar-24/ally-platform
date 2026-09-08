/**
 * services/billing.js — the founder's own subscription, receipts and billing
 * identity.
 *
 * Split from payments.js on purpose. That module is about GETTING PAID: it
 * opens Razorpay, and its whole design is about which side is allowed to
 * decide that money arrived. This one is about what the founder can SEE and
 * CHANGE afterwards — what they are on, when it renews, what they were
 * charged, and how to stop it. Nothing here grants anything or moves money.
 *
 * One rule worth stating because the page depends on it: `entitlement` in the
 * subscription response is the authority on access, not `status`. A cancelled
 * subscription can still be entitled — the founder paid for the rest of the
 * month — and a page that inferred "cancelled means gone" would tell them
 * they had lost something they still have.
 */

import { get, post, put } from './api';

/**
 * My current subscription and entitlement.
 *
 * Returns `{ has_subscription, tier, plan_name, status, current_period_end,
 * next_charge_at, cancel_at_period_end, entitlement: { plan, plan_name,
 * is_paid, access_until, access_start } }`.
 *
 * `has_subscription: false` is a normal answer — a founder on Free, or one who
 * bought Starter (a one-time purchase, which is not a subscription).
 */
export function getSubscription() {
  return get('/payments/subscription');
}

/**
 * Start a monthly subscription for a recurring tier.
 *
 * Sends a TIER, never a price and never a Razorpay plan id: the amount is
 * fixed on the plan at Razorpay and the plan is chosen server-side. Nothing is
 * charged by this call — it creates the mandate the founder is about to
 * authorise in Checkout.
 *
 * @param {'starter'|'pro'} tier  Plus / Pro respectively.
 */
export function startSubscription(tier) {
  return post('/payments/subscription', { tier });
}

/**
 * Cancel the subscription.
 *
 * `atPeriodEnd` defaults to true and the UI should keep it that way: the
 * founder has paid for this month, and taking it back the moment they click
 * Cancel is keeping money for a service withdrawn. The response's
 * `access_until` is the date to show them — and it must be shown BEFORE they
 * confirm, not after.
 */
export function cancelSubscription({ atPeriodEnd = true, reason = null } = {}) {
  return post('/payments/subscription/cancel', {
    at_period_end: atPeriodEnd,
    ...(reason ? { reason } : {}),
  });
}

/** Razorpay's invoices for this founder, newest first. `invoice_url` is the
 *  hosted document — we index invoices, we do not render them. */
export function getInvoices() {
  return get('/payments/invoices');
}

/** Every payment, INCLUDING failures. A founder whose renewal did not go
 *  through needs to see that with its reason, on the page where they would fix
 *  it — hiding it is how someone discovers a lapsed card by losing access. */
export function getPaymentHistory() {
  return get('/payments/history');
}

/** Billing name, GSTIN and address. Always resolves — an empty profile is the
 *  normal state for most founders, not a 404. */
export function getBillingProfile() {
  return get('/payments/billing-profile');
}

/** Save them. The backend validates the GSTIN shape and state code and refuses
 *  a bad one with a 422 whose detail is worth showing verbatim: a malformed
 *  GSTIN discovered on an issued invoice is one the customer cannot claim
 *  input credit against. */
export function saveBillingProfile(profile) {
  return put('/payments/billing-profile', profile);
}

/** Indian states and UTs, for the place-of-supply field. GST treatment turns
 *  on this, so it is a fixed list rather than free text. */
export const INDIAN_STATES = [
  'Andaman and Nicobar Islands', 'Andhra Pradesh', 'Arunachal Pradesh', 'Assam',
  'Bihar', 'Chandigarh', 'Chhattisgarh', 'Dadra and Nagar Haveli and Daman and Diu',
  'Delhi', 'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jammu and Kashmir',
  'Jharkhand', 'Karnataka', 'Kerala', 'Ladakh', 'Lakshadweep', 'Madhya Pradesh',
  'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha',
  'Puducherry', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana',
  'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
];

/** `2026-10-08T...` -> `08 October 2026`. Returns null for a null date so the
 *  caller can decide what "no date" reads as, rather than printing "Invalid
 *  Date" — which is what a bare `new Date(null)` renders. */
export function formatDate(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' });
}

/** Rupees with Indian digit grouping. Amounts from these endpoints are already
 *  rupees (the paise/rupee conversion happens once, server-side). */
export function formatINR(amount) {
  const n = Number(amount);
  if (!Number.isFinite(n)) return '—';
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

/**
 * What to tell the founder their subscription is doing, in one line.
 *
 * Centralised because the same state has to read the same way on the status
 * card, the plans page and the cancel dialog — and because two of these are
 * easy to get backwards. A `pending` subscription has NOT lost access (Razorpay
 * is retrying), and a `cancel_at_period_end` one is still active until its date.
 */
export function describeSubscription(sub) {
  if (!sub?.has_subscription) return { tone: 'none', label: 'No subscription', detail: null };

  const until = formatDate(sub.entitlement?.access_until);
  switch (sub.status) {
    case 'created':
    case 'authenticated':
      return { tone: 'pending', label: 'Awaiting first payment',
               detail: 'We will confirm as soon as Razorpay takes the first charge.' };
    case 'pending':
      return { tone: 'warn', label: 'Payment failed',
               detail: until
                 ? `We could not take this month's payment. Razorpay is retrying — your plan stays on until ${until}.`
                 : "We could not take this month's payment. Razorpay is retrying." };
    case 'halted':
      return { tone: 'error', label: 'Payment failed',
               detail: 'We could not take payment after several attempts. Update your card to restart the plan.' };
    case 'cancelled':
      return { tone: 'ended', label: 'Cancelled',
               detail: until ? `Your paid features stay on until ${until}.`
                             : 'Your paid features have ended.' };
    case 'completed':
      return { tone: 'ended', label: 'Completed',
               detail: until ? `Your paid features stay on until ${until}.` : null };
    case 'expired':
      return { tone: 'ended', label: 'Ended', detail: 'You are back on the free plan.' };
    case 'active':
    default:
      if (sub.cancel_at_period_end) {
        return { tone: 'ended', label: 'Cancelling',
                 detail: until ? `Your paid features stay on until ${until}. It will not renew.`
                               : 'This subscription will not renew.' };
      }
      return { tone: 'active', label: 'Active', detail: null };
  }
}
