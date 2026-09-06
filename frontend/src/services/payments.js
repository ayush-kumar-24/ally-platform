/**
 * services/payments.js — Razorpay Checkout, browser side.
 *
 * The division of authority here is the whole point of the file:
 *
 *  - This module may ASK for an order. `POST /payments/checkout` creates a
 *    *pending* payment server-side and returns the order to open the widget
 *    with. It grants nothing.
 *  - This module may NOT decide that a payment succeeded. Razorpay's success
 *    callback runs in the founder's own tab, so anything it reports is a claim
 *    made by the client — treating it as proof would let anyone with devtools
 *    hand themselves a plan. The plan is granted only by the signed
 *    `payment.captured` webhook Razorpay sends server-to-server (see
 *    app/payments/service.py). All the callback is used for here is knowing
 *    when to start asking the backend whether the plan has actually changed.
 *  - The key SECRET and the webhook secret never appear in the browser and
 *    must never be added to it. Only `key_id` — public by design — reaches the
 *    client, and it arrives in the checkout response rather than from a
 *    frontend env var, so the live/test key can never disagree with the key
 *    the order was created under.
 *
 * The amount likewise comes back from the order rather than being recomputed
 * here: the number shown to the founder and the number Razorpay will charge
 * are then the same number, and the frontend cannot invent a tax or a discount
 * the backend order does not carry.
 */

import { post } from './api';
import { getMyPlan } from './plans';

const CHECKOUT_JS_URL = 'https://checkout.razorpay.com/v1/checkout.js';

/**
 * Create a Razorpay order for a paid tier.
 *
 * @param {'basic'|'starter'|'pro'} tier  Starter / Plus / Pro respectively.
 * @returns {Promise<{payment_id:number, order_id:string, amount_paise:number,
 *                    currency:string, key_id:string}>}
 */
export function startCheckout(tier, couponCode = null) {
  // A code, never a price. The backend prices the plan from its own catalog;
  // anything the browser sent would be a number a founder could edit.
  return post('/payments/checkout',
    couponCode ? { tier, coupon_code: couponCode } : { tier });
}

/**
 * Price a code without claiming it. Reserves nothing, so a founder can try a
 * code, think, and try again — but a capped code can still be gone by the time
 * they press Pay, and checkout re-checks it then.
 */
export function validateCoupon(tier, code) {
  return post('/payments/coupons/validate', { tier, code });
}

// Checkout.js is loaded on demand rather than from index.html: it is a
// third-party script most sessions never need, and a billing page that is
// never opened should not cost every visitor the request.
let scriptPromise = null;

/** Load Razorpay's Checkout.js once per page, resolving with the constructor. */
export function loadCheckoutScript() {
  if (typeof window !== 'undefined' && window.Razorpay) {
    return Promise.resolve(window.Razorpay);
  }
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise((resolve, reject) => {
    const el = document.createElement('script');
    el.src = CHECKOUT_JS_URL;
    el.async = true;
    el.onload = () => {
      if (window.Razorpay) resolve(window.Razorpay);
      else reject(new Error('Razorpay Checkout loaded but did not initialise.'));
    };
    el.onerror = () => {
      // Cleared so a later attempt can retry: a blocked or flaky first load
      // must not permanently poison every subsequent payment in the session.
      scriptPromise = null;
      el.remove();
      reject(new Error('Could not reach Razorpay Checkout. Check your connection or ad blocker.'));
    };
    document.body.appendChild(el);
  });
  return scriptPromise;
}

/**
 * Open Razorpay Checkout for an order and resolve once with what happened.
 *
 * Resolves — never rejects for a payment outcome — with one of:
 *   { status: 'paid',      response }  the widget reported a captured payment
 *   { status: 'failed',    error }     Razorpay reported a failure
 *   { status: 'dismissed' }            the founder closed the popup
 *
 * `payment.failed` deliberately does NOT settle on its own: Razorpay keeps the
 * widget open after a declined attempt so the founder can try another method,
 * and settling there would rip a live popup out from under them. The failure
 * is remembered and reported when the popup actually closes.
 *
 * `status: 'paid'` means "Razorpay's client script said so", NOT "the plan is
 * active". The caller must confirm with the backend — see
 * `waitForPlanActivation` below.
 */
export function openCheckout({ order, planName, prefill = {} }) {
  return loadCheckoutScript().then(Razorpay => new Promise((resolve) => {
    let settled = false;
    let lastError = null;
    const settle = (outcome) => {
      if (settled) return;
      settled = true;
      resolve(outcome);
    };

    const rzp = new Razorpay({
      // Public key, straight from the order response. Never the secret.
      key: order.key_id,
      order_id: order.order_id,
      // Sent for display only; the order on Razorpay's side is what is
      // actually charged, and it was created and priced by the backend.
      amount: order.amount_paise,
      currency: order.currency,
      name: 'GoXL Ally',
      description: `${planName} plan`,
      image: '/ally-logo.png',
      prefill: {
        name: prefill.name || '',
        email: prefill.email || '',
        contact: prefill.contact || '',
      },
      notes: { plan_name: planName },
      theme: { color: '#1B4332' },
      handler: (response) => settle({ status: 'paid', response }),
      modal: {
        ondismiss: () => settle(
          lastError ? { status: 'failed', error: lastError } : { status: 'dismissed' },
        ),
      },
    });

    rzp.on('payment.failed', (e) => { lastError = e?.error ?? null; });
    rzp.open();
  }));
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

/**
 * Poll `GET /plans/me` until the webhook has actually moved the founder onto
 * the tier they paid for.
 *
 * This is the step that makes the browser callback non-authoritative: the UI
 * says "activated" only once the backend — which was told by a signed webhook,
 * not by this tab — reports the new tier itself.
 *
 * Transient errors are swallowed and retried rather than failing the wait: a
 * dropped request while the payment is settling is not evidence the payment
 * failed, and the founder has already been charged by this point.
 *
 * Note the one benign quirk: buying a tier the founder is somehow already on
 * resolves immediately. That is a state the plan cards do not offer (the
 * current plan's button is disabled), and "you are on the plan you just paid
 * for" is the right answer for it anyway.
 *
 * @returns {Promise<{activated:boolean, entitlements?:object, timedOut?:boolean}>}
 */
export async function waitForPlanActivation(tier, {
  attempts = 45,
  intervalMs = 2000,
  isCancelled = () => false,
} = {}) {
  for (let i = 0; i < attempts; i += 1) {
    if (isCancelled()) return { activated: false, cancelled: true };
    try {
      const me = await getMyPlan();
      if (me?.tier === tier) return { activated: true, entitlements: me };
    } catch {
      // Keep waiting — see above.
    }
    await sleep(intervalMs);
  }
  return { activated: false, timedOut: true };
}
