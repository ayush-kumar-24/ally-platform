import { useCallback, useEffect, useRef, useState } from 'react';
import { MOCK_PLANS } from '../data/mockData';
import { getProfile } from '../services/profile';
import { getCatalog, getMyPlan } from '../services/plans';
import { openCheckout, startCheckout, waitForPlanActivation } from '../services/payments';

/* ─── Static data ─── */
/** Keys must match the plan tiers served by GET /plans, which lists only the
 * tiers actually on sale (basic / starter / pro — shown as Starter, Plus and
 * Pro). EVERY row needs a key for EVERY tier: the table body maps the live plan
 * list and reads row[tier], so a missing key renders an empty cell under a
 * heading that is still there — which is how a column silently shifted one
 * place left once before. */
const COMPARE_ROWS = [
  { label: 'Tokens per day', basic: '—', starter: '3,500', pro: '8,000' },
  // Founder DNA and Business DNA are not rows here: they are sections of the
  // Clarity Report, not things a plan includes or withholds.
  { label: 'Adaptive diagnosis', basic: true, starter: true, pro: true },
  { label: 'Clarity Report', basic: true, starter: true, pro: true },
  { label: 'Download your report', basic: true, starter: true, pro: true },
  { label: 'Speak your answers', basic: true, starter: true, pro: true },
  { label: 'Talk to Ally', basic: false, starter: true, pro: true },
  { label: 'Voice in chat', basic: false, starter: true, pro: true },
  { label: 'Next Critical Steps', basic: 'In report', starter: true, pro: true },
  { label: 'Set your Goals', basic: false, starter: true, pro: true },
  { label: 'Plan Your Day', basic: false, starter: true, pro: true },
  { label: 'Founder Compass', basic: false, starter: 'Basic view', pro: true },
  { label: 'Ally recommends your steps', basic: false, starter: false, pro: true },
  { label: 'Build your Vision Board', basic: false, starter: false, pro: true },
  { label: 'Work a framework with Ally', basic: false, starter: false, pro: true },
  { label: 'Email reminders from Ally', basic: false, starter: false, pro: true },
  { label: 'Book a discovery call', basic: true, starter: true, pro: true },
  { label: 'Call price', basic: '₹300 / 30 min', starter: '₹300 / 30 min', pro: '₹300 / 30 min' },
  { label: 'Priority call booking', basic: false, starter: false, pro: true },
];

/* ─── Helpers ─── */
function CmpCell({ val }) {
  if (val === true)
    return (
      <span className="cmp-yes">
        <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="3">
          <polyline points="2 6 5 9 10 3" />
        </svg>
      </span>
    );
  if (val === false) return <span className="cmp-no">—</span>;
  return <span style={{ fontSize: 12, color: '#556458', fontWeight: 600 }}>{val}</span>;
}

function CheckIcon({ size = 18, color = '#10B981' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.5">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}


/* ═══════════════════════════════════════════
   VIEW 1 — Plans (existing, enhanced)
═══════════════════════════════════════════ */
/**
 * Load the live plan catalog, falling back to MOCK_PLANS until it arrives.
 *
 * The backend is the source of truth: if this page kept its own copy of the tiers
 * it would eventually disagree with the gate that enforces them — and the version
 * the customer read is the one they'd expect to be honoured.
 */
function useCatalog() {
  const [plans, setPlans] = useState(MOCK_PLANS);
  const [live, setLive] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCatalog()
      .then((catalog) => {
        if (cancelled || !catalog?.plans?.length) return;
        const callMins = catalog.call_duration_minutes ?? 15;
        const callPrice = catalog.call_price_inr ?? 300;
        setPlans(catalog.plans.map((p) => {
          // Whether a tier is bought once or subscribed to is the backend's
          // call (`one_time` in the catalog response). The old inference is
          // kept as the fallback because the frontend and backend deploy
          // separately: a frontend that lands before the backend that grew
          // the field must not relabel a one-time purchase as monthly.
          // Both agree on today's catalog -- a paid tier with nothing that
          // renews, no monthly credits and no daily budget, is Starter.
          const oneTime = p.one_time
            ?? (!!p.price_inr && !p.monthly_credits && !p.daily_token_limit);
          return {
            id: p.tier,
            name: p.name,
            price: p.price_inr,
            // Null unless the backend judged it a real saving — the decision is
            // made once, server-side, so no surface can render a crossed-out
            // number that saves the founder nothing.
            mrp: p.mrp_inr ?? null,
            oneTime,
            period: p.price_inr ? (oneTime ? ' once' : '/mo') : '',
            tag: p.tagline,
            popular: p.tier === 'pro',
            cta: p.price_inr ? `Start ${p.name}` : 'Current',
            features: [
              // Tokens, not credits: credits are an internal accounting unit.
              // Rs 199 has no metered surface at all, so it gets what it is.
              ...(p.features.includes('ally_chat')
                ? [`${p.daily_token_limit.toLocaleString('en-IN')} tokens per day`,
                   'Talk to Ally']
                : ['One adaptive diagnosis', 'Your Clarity Report']),
              p.features.includes('voice_chat') ? 'Voice in chat' : 'Speak your answers',
              ...(p.features.includes('next_steps') ? ['Your Next Critical Steps'] : []),
              ...(p.features.includes('goals') ? ['Goals'] : []),
              ...(p.features.includes('plan_your_day') ? ['Plan Your Day'] : []),
              ...(p.features.includes('recommendations') ? ['Ally recommends your steps'] : []),
              ...(p.features.includes('vision') ? ['Vision'] : []),
              ...(p.features.includes('knowledge_chat') ? ['Work a framework with Ally'] : []),
              ...(p.features.includes('email_notifications') ? ['Email reminders from Ally'] : []),
              `Book a call · ₹${callPrice} / ${callMins} min`,
              ...(p.features.includes('priority_call') ? ['Priority call booking'] : []),
            ],
          };
        }));
        setLive(true);
      })
      .catch(() => { /* keep the fallback — a pricing page must always render */ });
    return () => { cancelled = true; };
  }, []);

  return { plans, live };
}

function PlansView({ onSelectPlan, currentPlan }) {
  const { plans: PLANS } = useCatalog();
  return (
    <>
      {/* Hero */}
      <div className="pr-hero stagger d1">
        <div className="pr-eye">
          <span className="lv" />
          Transparent Pricing
        </div>
        {/* Demoted from h1: PlatformLayout's topbar already renders the page h1. */}
        <h2>Simple plans, <em>powerful</em> clarity</h2>
        <p>Pick the plan that matches how much you want Ally involved. Every plan
          includes a full diagnosis and your Clarity Report.</p>
      </div>

      {/* Plan cards */}
      <div className="plans stagger d2">
        {PLANS.map(plan => {
          const price = plan.price;
          const isCurrent = currentPlan === plan.id;
          return (
            <div key={plan.id} className={`plan-card${plan.popular ? ' popular' : ''}`}>
              {plan.popular && <div className="pc-ribbon">⭐ Most Popular</div>}
              <div className="pc-name">{plan.name}</div>
              <div className="pc-tag">{plan.tag}</div>
              <div className="pc-price">
                {plan.price === 0 ? (
                  <span className="amt" style={{ fontSize: 36 }}>Free</span>
                ) : (
                  <>
                    {plan.mrp && (
                      <span className="pc-mrp" aria-label={`Was ₹${plan.mrp.toLocaleString()}`}>
                        ₹{plan.mrp.toLocaleString()}
                      </span>
                    )}
                    <span className="cur">₹</span>
                    <span className="amt">{price.toLocaleString()}</span>
                    <span className="per">{plan.period}</span>
                  </>
                )}
              </div>
              {plan.price > 0 && <div className="pc-sub">{plan.oneTime ? 'one-time payment' : 'billed monthly'}</div>}
              <button
                id={`plan-cta-${plan.id}`}
                className={`pc-cta${isCurrent ? '' : ' primary'}`}
                onClick={() => {
                  if (!isCurrent && plan.id !== 'max') {
                    onSelectPlan({ ...plan, displayPrice: price });
                  }
                }}
                disabled={isCurrent}
              >
                {isCurrent ? '✓ Current Plan' : plan.cta}
              </button>
              <ul className="pc-feats">
                {plan.features.map((f, i) => (
                  <li key={i}>
                    <span className="fk">
                      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="3">
                        <polyline points="2 6 5 9 10 3" />
                      </svg>
                    </span>
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      {/* Trust strip */}
      <div className="pr-trust stagger d3">
        <span>
          <svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
          Bank-grade encryption
        </span>
        <span>
          <svg viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 11-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
          100% data privacy
        </span>
      </div>

      {/* Comparison table */}
      <div className="cmp-head stagger d4">
        <h2>Full feature comparison</h2>
      </div>
      <div className="cmp-scroll stagger d4">
        <table className="cmp">
          <thead>
            <tr>
              <th scope="col" style={{ textAlign: 'left', padding: '16px' }}>Feature</th>
              {PLANS.map(p => (
                <th scope="col" key={p.id} className={p.popular ? 'cmp-col-pop' : ''}>
                  <div className="cmp-pn">{p.name}</div>
                  <div className="cmp-pp">{p.price === 0 ? 'Free' : `₹${p.price.toLocaleString()}${p.period}`}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COMPARE_ROWS.map((row, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(6,20,13,.02)' }}>
                <td style={{ fontWeight: 600, color: '#16241c', fontSize: 13 }}>{row.label}</td>
                {/* The header maps every plan but the body emitted only `free`
                    and `pro`, so Starter had a column heading and no cells and
                    every value under it was shifted one column left. */}
                {PLANS.map(p => (
                  <td key={p.id} className={p.popular ? 'cmp-col-pop' : ''}>
                    <CmpCell val={row[p.id]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════
   VIEW 2 — Checkout (Razorpay)
═══════════════════════════════════════════ */

/** Paise → a rupee string, without inventing precision the order lacks. */
function rupeesFromPaise(paise) {
  const rupees = (paise ?? 0) / 100;
  return rupees.toLocaleString('en-IN', {
    minimumFractionDigits: Number.isInteger(rupees) ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Payment happens in Razorpay's own hosted widget, so this screen collects no
 * card, UPI or netbanking details at all. What used to be here was a mock form
 * behind a 2.2-second timer that charged nothing and then declared success —
 * and a real form in its place would have put card data in our DOM for no
 * reason, since Razorpay's widget is what must handle it.
 *
 * The order is created when the screen opens rather than on the Pay click, so
 * every amount rendered below is read straight off the order Razorpay will
 * charge against. The frontend adds nothing to it — no GST line, no rounding —
 * because the backend order carries no such line either (payments/service.py:
 * `amount_paise = plan.price_inr * 100`). A total here that disagreed with the
 * widget would be a broken promise about a price.
 */
function CheckoutView({ plan, onBack, onPaid }) {
  const [order, setOrder] = useState(null);
  const [orderError, setOrderError] = useState(null);
  const [payState, setPayState] = useState('idle'); // 'idle' | 'opening' | 'paid'
  const [payError, setPayError] = useState(null);
  const [prefill, setPrefill] = useState({ name: '', email: '' });

  /* Nothing started here may touch state after unmount: both the order request
     and the Razorpay popup outlive a "Back to Plans" click. */
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  const createOrder = useCallback(() => {
    setOrder(null);
    setOrderError(null);
    setPayError(null);
    return startCheckout(plan.id)
      .then((o) => { if (alive.current) setOrder(o); })
      .catch((err) => { if (alive.current) setOrderError(err); });
  }, [plan.id]);

  useEffect(() => { createOrder(); }, [createOrder]);

  /* Prefill only. Razorpay asks for anything we cannot supply, so a failed
     profile fetch costs the founder a field, not the payment. */
  useEffect(() => {
    let cancelled = false;
    getProfile()
      .then((p) => {
        if (cancelled || !p) return;
        setPrefill({ name: p.full_name || '', email: p.email || '' });
      })
      .catch(() => { /* leave it to the widget */ });
    return () => { cancelled = true; };
  }, []);

  const handlePay = async () => {
    if (!order || payState !== 'idle') return;
    setPayError(null);
    setPayState('opening');
    let outcome;
    try {
      outcome = await openCheckout({ order, planName: plan.name, prefill });
    } catch (err) {
      // Checkout.js itself never loaded — nothing was charged.
      if (alive.current) {
        setPayState('idle');
        setPayError(err?.message || 'Could not open the payment window. Please try again.');
      }
      return;
    }
    if (!alive.current) return;

    if (outcome.status === 'paid') {
      /* Deliberately NOT "your plan is active". This callback is the founder's
         own browser telling us what it saw; the plan is granted by the signed
         payment.captured webhook, and the next screen is what waits for it. */
      setPayState('paid');
      onPaid({ plan, order, razorpayPaymentId: outcome.response?.razorpay_payment_id ?? null });
      return;
    }

    setPayState('idle');
    if (outcome.status === 'failed') {
      setPayError(outcome.error?.description
        || 'The payment did not go through. No money has been taken — you can try again.');
    } else {
      setPayError('Payment cancelled. You have not been charged.');
    }
  };

  const amountLabel = order ? `₹${rupeesFromPaise(order.amount_paise)}` : null;
  const busy = payState !== 'idle';

  return (
    <div className="bl-checkout-wrap stagger d1">
      {/* Back */}
      <button id="checkout-back-btn" className="bl-back-btn" onClick={onBack} disabled={busy}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        Back to Plans
      </button>

      <div className="bl-checkout-grid">
        {/* ── Left: Pay ── */}
        <div className="bl-checkout-form-col">
          <div className="bl-section-label">Secure Payment</div>

          <h3 className="bl-pay-heading">Pay for {plan.name}</h3>
          <p className="bl-pay-lede">
            You&apos;ll complete payment in Razorpay&apos;s secure window — card, UPI,
            net banking and wallets are all available there. Your payment details
            are entered on Razorpay and never touch GoXL Ally.
          </p>

          {orderError && (
            <div className="bl-pay-alert err" role="alert">
              <strong>We couldn&apos;t start this payment.</strong>
              <span>{orderError.detail || orderError.message || 'Please try again in a moment.'}</span>
              <button type="button" className="bl-link-btn" onClick={createOrder}>
                Try again
              </button>
              {/* The backend logs every failed checkout under this id, so a
                  founder who emails "it didn't work" can quote the one thing
                  that finds the exact log line -- without which the message
                  above is all anyone has to go on. */}
              {orderError.data?.request_id && (
                <small className="bl-pay-ref">Reference: {orderError.data.request_id}</small>
              )}
            </div>
          )}

          {payError && (
            <div className="bl-pay-alert warn" role="alert">
              <span>{payError}</span>
            </div>
          )}

          <button
            id="checkout-pay-btn"
            type="button"
            className={`bl-pay-btn${busy ? ' loading' : ''}`}
            onClick={handlePay}
            disabled={!order || busy}
          >
            {busy ? (
              <>
                <span className="bl-spinner" />
                {payState === 'paid' ? 'Payment received…' : 'Opening Razorpay…'}
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
                {order ? `Pay ${amountLabel}` : 'Preparing secure checkout…'}
              </>
            )}
          </button>

          <p className="bl-pay-note">
            🔒 Payments are processed by Razorpay. GoXL Ally never sees or stores
            your card details.
          </p>

          {order && (
            <p className="bl-pay-order-ref">Order reference: {order.order_id}</p>
          )}
        </div>

        {/* ── Right: Order Summary ── */}
        <div className="bl-order-summary">
          <div className="bl-section-label">Order Summary</div>

          <div className="bl-os-plan-badge">
            <div className="bl-os-plan-name">{plan.name} Plan</div>
            <div className="bl-os-plan-tag">{plan.tag}</div>
            <div className="bl-os-plan-cycle">{plan.oneTime ? 'One-time payment' : 'Billed Monthly'}</div>
          </div>

          <ul className="bl-os-feats">
            {plan.features.map((f, i) => (
              <li key={i}>
                <CheckIcon size={14} />
                {f}
              </li>
            ))}
          </ul>

          {/* Every figure here comes from the order the backend created, so what
              the founder reads is exactly what Razorpay will charge. */}
          <div className="bl-os-breakdown">
            <div className="bl-os-line">
              <span>{plan.name} ({plan.oneTime ? 'One-time' : 'Monthly'})</span>
              <span>{amountLabel ?? '—'}</span>
            </div>
            <div className="bl-os-total">
              <span>Total payable</span>
              <span>{amountLabel ?? '—'}</span>
            </div>
          </div>

          <div className="bl-os-trust">
            <span>Payments secured by Razorpay</span>
            <span>Your plan activates as soon as payment is confirmed</span>
            <span>No card details are stored by GoXL Ally</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   VIEW 2b — Activating (waiting on the webhook)
═══════════════════════════════════════════ */
/**
 * The gap between "Razorpay says paid" and "the founder is on the plan".
 *
 * Razorpay's success callback runs in the founder's own tab, so it grants
 * nothing here — the plan is granted server-side when Razorpay's signed
 * payment.captured webhook reaches the backend. This screen simply asks
 * GET /plans/me until that has happened, which is why it can honestly say
 * "activating" rather than "active".
 */
function ActivatingView({ plan, order, onActivated, onViewStatus }) {
  const [timedOut, setTimedOut] = useState(false);
  const [attempt, setAttempt] = useState(0);
  // Bumped by "Check again", which restarts the wait rather than reloading the
  // page -- a founder who has already paid should never have to guess whether
  // refreshing costs them the payment.
  const [round, setRound] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setTimedOut(false);
    const ticker = setInterval(() => { if (!cancelled) setAttempt(a => a + 1); }, 1000);

    waitForPlanActivation(plan.id, { isCancelled: () => cancelled })
      .then((result) => {
        if (cancelled) return;
        if (result.activated) onActivated(result.entitlements);
        else if (result.timedOut) setTimedOut(true);
      });

    return () => { cancelled = true; clearInterval(ticker); };
    // `attempt` is display-only and must not restart the wait.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan.id, round]);

  return (
    <div className="bl-success-wrap stagger d1">
      <div className={`bl-activating-icon${timedOut ? ' slow' : ''}`}>
        {timedOut ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
          </svg>
        ) : (
          <span className="bl-spinner dark" />
        )}
      </div>

      {timedOut ? (
        <>
          <h2 className="bl-success-title">Payment received — activation is taking longer than usual</h2>
          <p className="bl-success-sub">
            Your payment went through and nothing is lost. {plan.name} is activated
            by our payment provider&apos;s confirmation, which is running late.
            It usually lands within a few minutes.
          </p>
        </>
      ) : (
        <>
          <h2 className="bl-success-title">Payment received. Activating your plan…</h2>
          <p className="bl-success-sub">
            We&apos;re confirming your payment with Razorpay and switching you to
            {' '}{plan.name}. This usually takes a few seconds — please keep this
            page open.
          </p>
        </>
      )}

      <div className="bl-success-details">
        <div className="bl-sd-row"><span>Plan</span><strong>{plan.name}</strong></div>
        {order && (
          <>
            <div className="bl-sd-row">
              <span>Amount paid</span>
              <strong>₹{rupeesFromPaise(order.amount_paise)}</strong>
            </div>
            <div className="bl-sd-row"><span>Order reference</span><strong>{order.order_id}</strong></div>
          </>
        )}
        <div className="bl-sd-row">
          <span>Status</span>
          <strong className={`bl-status-badge ${timedOut ? 'pending' : 'active'}`}>
            {timedOut ? 'Awaiting confirmation' : `Activating${'.'.repeat(attempt % 4)}`}
          </strong>
        </div>
      </div>

      {timedOut && (
        <>
          <button id="activation-recheck-btn" className="bl-pay-btn"
                  onClick={() => setRound(r => r + 1)}>
            Check again
          </button>
          <p className="bl-pay-note">
            Still not showing?{' '}
            <button type="button" className="bl-link-btn" onClick={onViewStatus}>
              Go to My Subscription
            </button>
            {' '}or email info@goxl.in with the order reference above.
          </p>
        </>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════
   VIEW 3 — Payment Success / Confirmation
═══════════════════════════════════════════ */
function SuccessView({ plan, order, onViewStatus }) {
  const [founder, setFounder] = useState(null);
  useEffect(() => { getProfile().then(setFounder).catch(() => setFounder(null)); }, []);
  return (
    <div className="bl-success-wrap stagger d1">
      <div className="bl-success-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
      <h2 className="bl-success-title">Payment Successful!</h2>
      <p className="bl-success-sub">
        Welcome to the <strong>{plan.name} Plan</strong>. Your {plan.oneTime ? 'plan' : 'subscription'} is now active.
        A payment receipt has been sent to <strong>{founder?.email ?? 'your email'}</strong>.
      </p>
      <div className="bl-success-details">
        <div className="bl-sd-row"><span>Plan</span><strong>{plan.name}</strong></div>
        {/* The order's own amount, not a recomputed one: this is the figure
            Razorpay charged, so it cannot drift from the receipt. */}
        <div className="bl-sd-row">
          <span>Amount charged</span>
          <strong>₹{rupeesFromPaise(order?.amount_paise)}{plan.oneTime ? '' : '/mo'}</strong>
        </div>
        <div className="bl-sd-row"><span>Billing cycle</span><strong>{plan.oneTime ? 'One-time' : 'Monthly'}</strong></div>
        {!plan.oneTime && <div className="bl-sd-row"><span>Next renewal</span><strong>Aug 2026</strong></div>}
        {order && (
          <div className="bl-sd-row"><span>Order reference</span><strong>{order.order_id}</strong></div>
        )}
        <div className="bl-sd-row"><span>Status</span><strong className="bl-status-badge active">Active</strong></div>
      </div>
      <button id="view-subscription-btn" className="bl-pay-btn" onClick={onViewStatus}>
        View My Subscription
      </button>
    </div>
  );
}

/* ═══════════════════════════════════════════
   VIEW 4 — Subscription Status
═══════════════════════════════════════════ */
function StatusView({ onUpgrade, currentPlan }) {
  const [cancelModal, setCancelModal] = useState(false);
  const plan = MOCK_PLANS.find(p => p.id === currentPlan) || MOCK_PLANS[1];

  return (
    <div className="bl-status-wrap stagger d1">
      {/* Cancel modal */}
      {cancelModal && (
        <div className="bl-modal-overlay" onClick={() => setCancelModal(false)}>
          <div className="bl-modal" onClick={e => e.stopPropagation()}>
            <div className="bl-modal-icon warn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>
            <h3>Cancel Subscription?</h3>
            <p>Your access to {plan.name} features will continue until your current billing period ends (Aug 1, 2026). After that, your account reverts to the Free plan.</p>
            <div className="bl-modal-actions">
              <button id="cancel-confirm-btn" className="bl-modal-btn danger" onClick={() => setCancelModal(false)}>
                Yes, Cancel Plan
              </button>
              <button id="cancel-dismiss-btn" className="bl-modal-btn ghost" onClick={() => setCancelModal(false)}>
                Keep My Plan
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bl-status-header">
        <div>
          <div className="bl-section-label">Current Subscription</div>
          <h2 className="bl-status-plan-name">
            {plan.name} Plan
            <span className="bl-status-badge active">Active</span>
          </h2>
          {plan.oneTime
            ? <p className="bl-status-renew">One-time purchase · ₹{plan.price.toLocaleString()}</p>
            : <p className="bl-status-renew">Next renewal: <strong>August 1, 2026</strong> · ₹{plan.price.toLocaleString()}/mo</p>}
        </div>
        <div className="bl-status-actions">
          <button id="upgrade-plan-btn" className="bl-action-btn primary" onClick={onUpgrade}>
            Upgrade Plan
          </button>
          <button id="cancel-plan-btn" className="bl-action-btn ghost" onClick={() => setCancelModal(true)}>
            Cancel Plan
          </button>
        </div>
      </div>

      {/* The usage meters that stood here were mock numbers (8 of 10 diagnoses,
          unlimited chat) that no plan matches: every plan is one diagnosis per
          account and chat is metered by tokens. Real meters need real usage
          data from the API; until then nothing is better than fiction. */}

      {/* Plan features included */}
      <div className="bl-incl-section">
        <div className="bl-section-label" style={{ marginBottom: 14 }}>What's included in {plan.name}</div>
        <div className="bl-incl-grid">
          {plan.features.map((f, i) => (
            <div key={i} className="bl-incl-item">
              <CheckIcon size={15} />
              {f}
            </div>
          ))}
        </div>
      </div>

      {/* Invoice history */}
      {/* This table listed four invoices -- INV-2026-007 at ₹999 "Paid", and
          three more -- for every founder who opened the page, with a PDF button
          that did nothing. They were invented: there is no invoice endpoint in
          the API at all. Fabricated payment records are not a placeholder, so
          the section says what is true until billing history actually exists. */}
      <div className="bl-invoice-section">
        <div className="bl-section-label" style={{ marginBottom: 14 }}>Billing History</div>
        <p className="dash-empty">
          No invoices yet. Once billing is live, your receipts will appear here.
        </p>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   ROOT COMPONENT
═══════════════════════════════════════════ */
export default function Billing() {
  // 'plans' | 'checkout' | 'activating' | 'success' | 'status'
  const [view, setView] = useState('plans');
  const [selectedPlan, setSelectedPlan] = useState(null);
  // The order the founder actually paid against, kept so the activating and
  // success screens can quote the charged amount and order reference rather
  // than a price recomputed from the catalog.
  const [paidOrder, setPaidOrder] = useState(null);
  // Was hardcoded to 'starter' -- every founder, on any plan, saw Starter marked
  // "Current Plan" here regardless of what they actually pay for.
  const [currentPlan, setCurrentPlan] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getMyPlan()
      .then((p) => { if (!cancelled) setCurrentPlan(p?.tier || 'free'); })
      .catch(() => { if (!cancelled) setCurrentPlan('free'); });
    return () => { cancelled = true; };
  }, []);

  const handleSelectPlan = plan => {
    setSelectedPlan(plan);
    setPaidOrder(null);
    setView('checkout');
  };

  /* Razorpay reported a captured payment. That is NOT authority to show the
     plan as active: the grant happens when the signed payment.captured webhook
     reaches the backend, so this only moves to the screen that waits for it. */
  const handlePaid = ({ plan, order }) => {
    setSelectedPlan(plan);
    setPaidOrder(order);
    setView('activating');
  };

  /* The backend itself now reports the new tier — the webhook has landed. */
  const handleActivated = (entitlements) => {
    if (entitlements?.tier) setCurrentPlan(entitlements.tier);
    setView('success');
  };

  return (
    <div className="pad bill-wrap">
      {/* Top nav tabs (when not in plans view) */}
      {view !== 'plans' && view !== 'checkout' && view !== 'activating' && (
        <div className="bl-top-tabs">
          <button
            id="tab-plans"
            className={`bl-top-tab${view === 'plans' ? ' active' : ''}`}
            onClick={() => setView('plans')}
          >
            Plans & Pricing
          </button>
          <button
            id="tab-status"
            className={`bl-top-tab${view === 'status' || view === 'success' ? ' active' : ''}`}
            onClick={() => setView('status')}
          >
            My Subscription
          </button>
        </div>
      )}

      {view === 'plans' && (
        <PlansView
          onSelectPlan={handleSelectPlan}
          currentPlan={currentPlan}
        />
      )}

      {view === 'checkout' && selectedPlan && (
        <CheckoutView
          plan={selectedPlan}
          onBack={() => setView('plans')}
          onPaid={handlePaid}
        />
      )}

      {view === 'activating' && selectedPlan && (
        <ActivatingView
          plan={selectedPlan}
          order={paidOrder}
          onActivated={handleActivated}
          onViewStatus={() => setView('status')}
        />
      )}

      {view === 'success' && selectedPlan && (
        <SuccessView
          plan={selectedPlan}
          order={paidOrder}
          onViewStatus={() => setView('status')}
        />
      )}

      {view === 'status' && (
        <StatusView
          currentPlan={currentPlan}
          onUpgrade={() => setView('plans')}
        />
      )}

      {/* Persistent tab switcher at bottom when on plans */}
      {view === 'plans' && (
        <div className="bl-manage-link stagger d5">
          Already subscribed?{' '}
          <button id="manage-sub-btn" className="bl-link-btn" onClick={() => setView('status')}>
            Manage your subscription →
          </button>
        </div>
      )}
    </div>
  );
}
