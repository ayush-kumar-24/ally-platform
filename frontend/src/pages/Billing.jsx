import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MOCK_PLANS, MOCK_FOUNDER } from '../data/mockData';
import { getCatalog } from '../services/plans';

/* ─── Static data ─── */
/** Keys must match the plan tiers (free / starter / pro) served by GET /plans. */
const COMPARE_ROWS = [
  { label: 'Credits', free: '120 (once)', starter: '180 / month', pro: '240 / month' },
  { label: 'Tokens per day', free: '4,000', starter: '6,000', pro: '8,000' },
  { label: 'First diagnosis', free: 'Free', starter: 'Free', pro: 'Free' },
  { label: 'Founder DNA', free: true, starter: true, pro: true },
  { label: 'Business DNA', free: true, starter: true, pro: true },
  { label: 'Clarity Reports', free: true, starter: true, pro: true },
  { label: 'Voice in Diagnosis', free: true, starter: true, pro: true },
  { label: 'Voice in Ally Chat', free: false, starter: true, pro: true },
  { label: 'Plan Your Day', free: false, starter: true, pro: true },
  { label: 'Know My Energy', free: false, starter: false, pro: true },
  { label: 'Free calls / month', free: '—', starter: '1', pro: '2' },
  { label: 'Extra calls', free: '₹300 / 30 min', starter: '₹300 / 30 min', pro: '₹300 / 30 min' },
];

const MOCK_INVOICES = [
  { id: 'INV-2026-007', date: 'Jul 1, 2026', plan: 'Pro', amount: '₹999', status: 'Paid' },
  { id: 'INV-2026-006', date: 'Jun 1, 2026', plan: 'Pro', amount: '₹999', status: 'Paid' },
  { id: 'INV-2026-005', date: 'May 1, 2026', plan: 'Starter', amount: '₹450', status: 'Paid' },
  { id: 'INV-2026-004', date: 'Apr 1, 2026', plan: 'Starter', amount: '₹450', status: 'Paid' },
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

function UsageBar({ used, total, color = '#10B981' }) {
  const pct = Math.min(100, Math.round((used / total) * 100));
  const barColor = pct >= 90 ? '#f59e0b' : color;
  return (
    <div className="bl-usage-bar-wrap">
      <div className="bl-usage-bar-track">
        <div
          className="bl-usage-bar-fill"
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>
      <span className="bl-usage-bar-label">{used}/{total}</span>
    </div>
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
        setPlans(catalog.plans.map((p) => ({
          id: p.tier,
          name: p.name,
          price: p.price_inr,
          period: p.price_inr ? '/mo' : '',
          tag: p.tagline,
          popular: p.tier === 'starter',
          cta: p.price_inr ? `Start ${p.name}` : 'Current',
          features: [
            p.monthly_credits
              ? `${p.monthly_credits} credits every month`
              : `1 month free · ${p.signup_credits} credits`,
            `${p.daily_token_limit.toLocaleString('en-IN')} tokens per day`,
            'Full diagnosis — free, uses no credits',
            p.features.includes('voice_chat') ? 'Voice in Ally Chat' : 'Voice in Diagnosis',
            ...(p.features.includes('plan_your_day') ? ['Plan Your Day'] : []),
            ...(p.features.includes('know_my_energy') ? ['Know My Energy'] : []),
            p.free_calls_per_month
              ? `${p.free_calls_per_month} free call${p.free_calls_per_month > 1 ? 's' : ''} each month, then ₹300`
              : 'Book a call · ₹300 / 30 min',
          ],
        })));
        setLive(true);
      })
      .catch(() => { /* keep the fallback — a pricing page must always render */ });
    return () => { cancelled = true; };
  }, []);

  return { plans, live };
}

function PlansView({ annual, setAnnual, onSelectPlan, currentPlan }) {
  const { plans: PLANS } = useCatalog();
  return (
    <>
      {/* Hero */}
      <div className="pr-hero stagger d1">
        <div className="pr-eye">
          <span className="lv" />
          Transparent Pricing
        </div>
        <h1>Simple plans, <em>powerful</em> clarity</h1>
        <p>Start free. Upgrade when you need more diagnoses, deeper insights, or team features.</p>
      </div>

      {/* Toggle */}
      <div style={{ textAlign: 'center' }}>
        <div className="bill-toggle stagger d1">
          <button className={`bt-opt${!annual ? ' on' : ''}`} onClick={() => setAnnual(false)}>Monthly</button>
          <button className={`bt-opt${annual ? ' on' : ''}`} onClick={() => setAnnual(true)}>
            Annual <span className="bt-save">Save 20%</span>
          </button>
          <div className="bt-slider" style={{
            left: annual ? 'calc(50% + 2px)' : '4px',
            width: annual ? 'calc(50% - 6px)' : 'calc(50% - 6px)',
          }} />
        </div>
      </div>

      {/* Plan cards */}
      <div className="plans stagger d2">
        {PLANS.map(plan => {
          const price = annual ? Math.floor(plan.price * 0.8) : plan.price;
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
                    <span className="cur">₹</span>
                    <span className="amt">{price.toLocaleString()}</span>
                    <span className="per">/mo</span>
                  </>
                )}
              </div>
              {plan.price > 0 && <div className="pc-sub">{annual ? 'billed annually' : 'billed monthly'}</div>}
              <button
                id={`plan-cta-${plan.id}`}
                className={`pc-cta${isCurrent ? '' : ' primary'}`}
                onClick={() => {
                  if (!isCurrent && plan.id !== 'max') {
                    onSelectPlan({ ...plan, displayPrice: price, annual });
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
          <svg viewBox="0 0 24 24"><polyline points="9 11 12 14 22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" /></svg>
          Cancel anytime
        </span>
        <span>
          <svg viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 11-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
          100% data privacy
        </span>
        <span>
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
          14-day free trial
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
              <th style={{ textAlign: 'left', padding: '16px' }}>Feature</th>
              {PLANS.map(p => (
                <th key={p.id} className={p.popular ? 'cmp-col-pop' : ''}>
                  <div className="cmp-pn">{p.name}</div>
                  <div className="cmp-pp">{p.price === 0 ? 'Free' : `₹${(annual ? Math.floor(p.price * 0.8) : p.price).toLocaleString()}/mo`}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COMPARE_ROWS.map((row, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(6,20,13,.02)' }}>
                <td style={{ fontWeight: 600, color: '#16241c', fontSize: 13 }}>{row.label}</td>
                <td><CmpCell val={row.free} /></td>
                <td className="cmp-col-pop"><CmpCell val={row.pro} /></td>
                
                
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* ═══════════════════════════════════════════
   VIEW 2 — Checkout
═══════════════════════════════════════════ */
const PAYMENT_METHODS = [
  { id: 'card', label: 'Credit / Debit Card' },
  { id: 'upi', label: 'UPI' },
  { id: 'netbanking', label: 'Net Banking' },
];

function CheckoutView({ plan, annual, onBack, onSuccess }) {
  const [method, setMethod] = useState('card');
  const [form, setForm] = useState({
    name: MOCK_FOUNDER.name,
    email: MOCK_FOUNDER.email,
    card: '',
    expiry: '',
    cvv: '',
    upi: '',
    bank: '',
  });
  const [errors, setErrors] = useState({});
  const [processing, setProcessing] = useState(false);

  const price = annual ? Math.floor(plan.price * 0.8) : plan.price;
  const gst = Math.round(price * 0.18);
  const total = price + gst;
  const annualTotal = annual ? total * 12 : null;

  const formatCard = v => v.replace(/\D/g, '').replace(/(.{4})/g, '$1 ').trim().slice(0, 19);
  const formatExpiry = v => {
    const d = v.replace(/\D/g, '');
    if (d.length >= 3) return `${d.slice(0, 2)}/${d.slice(2, 4)}`;
    return d;
  };

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Required';
    if (!form.email.trim()) e.email = 'Required';
    if (method === 'card') {
      if (form.card.replace(/\s/g, '').length < 16) e.card = 'Enter valid 16-digit card number';
      if (form.expiry.length < 5) e.expiry = 'Enter valid expiry';
      if (form.cvv.length < 3) e.cvv = 'Enter 3-digit CVV';
    }
    if (method === 'upi' && !form.upi.includes('@')) e.upi = 'Enter valid UPI ID (e.g. name@upi)';
    if (method === 'netbanking' && !form.bank) e.bank = 'Select a bank';
    return e;
  };

  const handleSubmit = e => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setProcessing(true);
    setTimeout(() => {
      setProcessing(false);
      onSuccess(plan);
    }, 2200);
  };

  const set = (k, v) => {
    setForm(f => ({ ...f, [k]: v }));
    setErrors(ex => { const n = { ...ex }; delete n[k]; return n; });
  };

  return (
    <div className="bl-checkout-wrap stagger d1">
      {/* Back */}
      <button id="checkout-back-btn" className="bl-back-btn" onClick={onBack}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        Back to Plans
      </button>

      <div className="bl-checkout-grid">
        {/* ── Left: Form ── */}
        <div className="bl-checkout-form-col">
          <div className="bl-section-label">Payment Details</div>

          {/* Payment method tabs */}
          <div className="bl-method-tabs">
            {PAYMENT_METHODS.map(m => (
              <button
                key={m.id}
                id={`method-tab-${m.id}`}
                className={`bl-method-tab${method === m.id ? ' active' : ''}`}
                onClick={() => { setMethod(m.id); setErrors({}); }}
                type="button"
              >
                {m.label}
              </button>
            ))}
          </div>

          <form id="checkout-form" className="bl-form" onSubmit={handleSubmit} noValidate>
            {/* Cardholder / Contact */}
            <div className="bl-field-row">
              <div className={`bl-field${errors.name ? ' err' : ''}`}>
                <label htmlFor="co-name">Full Name</label>
                <input id="co-name" type="text" value={form.name}
                  onChange={e => set('name', e.target.value)} placeholder="Rahul Varma" />
                {errors.name && <span className="bl-err-msg">{errors.name}</span>}
              </div>
              <div className={`bl-field${errors.email ? ' err' : ''}`}>
                <label htmlFor="co-email">Email</label>
                <input id="co-email" type="email" value={form.email}
                  onChange={e => set('email', e.target.value)} placeholder="you@example.com" />
                {errors.email && <span className="bl-err-msg">{errors.email}</span>}
              </div>
            </div>

            {/* Card fields */}
            {method === 'card' && (
              <>
                <div className={`bl-field${errors.card ? ' err' : ''}`}>
                  <label htmlFor="co-card">Card Number</label>
                  <div className="bl-input-icon-wrap">
                    <svg className="bl-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <rect x="1" y="4" width="22" height="16" rx="3" ry="3" />
                      <line x1="1" y1="10" x2="23" y2="10" />
                    </svg>
                    <input id="co-card" type="text" inputMode="numeric" value={form.card}
                      onChange={e => set('card', formatCard(e.target.value))}
                      placeholder="1234 5678 9012 3456" maxLength={19} />
                  </div>
                  {errors.card && <span className="bl-err-msg">{errors.card}</span>}
                </div>
                <div className="bl-field-row">
                  <div className={`bl-field${errors.expiry ? ' err' : ''}`}>
                    <label htmlFor="co-expiry">Expiry</label>
                    <input id="co-expiry" type="text" inputMode="numeric" value={form.expiry}
                      onChange={e => set('expiry', formatExpiry(e.target.value))}
                      placeholder="MM/YY" maxLength={5} />
                    {errors.expiry && <span className="bl-err-msg">{errors.expiry}</span>}
                  </div>
                  <div className={`bl-field${errors.cvv ? ' err' : ''}`}>
                    <label htmlFor="co-cvv">CVV</label>
                    <input id="co-cvv" type="text" inputMode="numeric" value={form.cvv}
                      onChange={e => set('cvv', e.target.value.replace(/\D/g, '').slice(0, 3))}
                      placeholder="•••" maxLength={3} />
                    {errors.cvv && <span className="bl-err-msg">{errors.cvv}</span>}
                  </div>
                </div>
              </>
            )}

            {/* UPI field */}
            {method === 'upi' && (
              <div className={`bl-field${errors.upi ? ' err' : ''}`}>
                <label htmlFor="co-upi">UPI ID</label>
                <div className="bl-input-icon-wrap">
                  <svg className="bl-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
                  </svg>
                  <input id="co-upi" type="text" value={form.upi}
                    onChange={e => set('upi', e.target.value)}
                    placeholder="yourname@upi" />
                </div>
                {errors.upi && <span className="bl-err-msg">{errors.upi}</span>}
                <p className="bl-field-hint">Enter your UPI ID linked to your bank account.</p>
              </div>
            )}

            {/* Net banking */}
            {method === 'netbanking' && (
              <div className={`bl-field${errors.bank ? ' err' : ''}`}>
                <label htmlFor="co-bank">Select Bank</label>
                <select id="co-bank" value={form.bank} onChange={e => set('bank', e.target.value)}>
                  <option value="">-- Choose your bank --</option>
                  <option>HDFC Bank</option>
                  <option>ICICI Bank</option>
                  <option>SBI</option>
                  <option>Axis Bank</option>
                  <option>Kotak Mahindra Bank</option>
                  <option>Yes Bank</option>
                  <option>IndusInd Bank</option>
                </select>
                {errors.bank && <span className="bl-err-msg">{errors.bank}</span>}
              </div>
            )}

            {/* Submit */}
            <button
              id="checkout-pay-btn"
              type="submit"
              className={`bl-pay-btn${processing ? ' loading' : ''}`}
              disabled={processing}
            >
              {processing ? (
                <>
                  <span className="bl-spinner" />
                  Processing…
                </>
              ) : (
                <>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                  Pay ₹{total.toLocaleString()} {annual ? '/ year (×12)' : '/ month'}
                </>
              )}
            </button>
            <p className="bl-pay-note">
              🔒 Secured by 256-bit SSL encryption. Your card details are never stored.
            </p>
          </form>
        </div>

        {/* ── Right: Order Summary ── */}
        <div className="bl-order-summary">
          <div className="bl-section-label">Order Summary</div>

          <div className="bl-os-plan-badge">
            <div className="bl-os-plan-name">{plan.name} Plan</div>
            <div className="bl-os-plan-tag">{plan.tag}</div>
            <div className="bl-os-plan-cycle">{annual ? 'Billed Annually' : 'Billed Monthly'}</div>
          </div>

          <ul className="bl-os-feats">
            {plan.features.map((f, i) => (
              <li key={i}>
                <CheckIcon size={14} />
                {f}
              </li>
            ))}
          </ul>

          <div className="bl-os-breakdown">
            <div className="bl-os-line">
              <span>{plan.name} ({annual ? 'Annual' : 'Monthly'})</span>
              <span>₹{price.toLocaleString()}</span>
            </div>
            <div className="bl-os-line">
              <span>GST (18%)</span>
              <span>₹{gst.toLocaleString()}</span>
            </div>
            {annual && (
              <div className="bl-os-line bl-os-saving">
                <span>Annual savings (20% off)</span>
                <span>–₹{Math.round(plan.price * 0.2 * 12).toLocaleString()}</span>
              </div>
            )}
            <div className="bl-os-total">
              <span>Total {annual ? '/ year' : '/ month'}</span>
              <span>₹{(annual ? annualTotal : total).toLocaleString()}</span>
            </div>
          </div>

          <div className="bl-os-trust">
            <span>Cancel anytime, no questions asked</span>
            <span>14-day money-back guarantee</span>
            <span>Instant activation after payment</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   VIEW 3 — Payment Success / Confirmation
═══════════════════════════════════════════ */
function SuccessView({ plan, onViewStatus }) {
  return (
    <div className="bl-success-wrap stagger d1">
      <div className="bl-success-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
      <h2 className="bl-success-title">Payment Successful!</h2>
      <p className="bl-success-sub">
        Welcome to the <strong>{plan.name} Plan</strong>. Your subscription is now active.
        A confirmation receipt has been sent to <strong>{MOCK_FOUNDER.email}</strong>.
      </p>
      <div className="bl-success-details">
        <div className="bl-sd-row"><span>Plan</span><strong>{plan.name}</strong></div>
        <div className="bl-sd-row"><span>Amount charged</span><strong>₹{plan.displayPrice?.toLocaleString()}/mo + GST</strong></div>
        <div className="bl-sd-row"><span>Billing cycle</span><strong>{plan.annual ? 'Annual' : 'Monthly'}</strong></div>
        <div className="bl-sd-row"><span>Next renewal</span><strong>{plan.annual ? 'Jul 2027' : 'Aug 2026'}</strong></div>
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
          <p className="bl-status-renew">Next renewal: <strong>August 1, 2026</strong> · ₹{plan.price.toLocaleString()}/mo</p>
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

      {/* Usage meters */}
      <div className="bl-usage-grid">
        <div className="bl-usage-card">
          <div className="bl-uc-label">Diagnoses this month</div>
          <UsageBar used={8} total={10} />
          <div className="bl-uc-note">2 remaining — resets Aug 1</div>
        </div>
        <div className="bl-usage-card">
          <div className="bl-uc-label">Ally Chat sessions</div>
          <div className="bl-uc-unlimited">
            <CheckIcon size={14} /> Unlimited
          </div>
        </div>
        <div className="bl-usage-card">
          <div className="bl-uc-label">Clarity Reports generated</div>
          <UsageBar used={3} total={10} color="#10B981" />
          <div className="bl-uc-note">7 remaining this month</div>
        </div>
        <div className="bl-usage-card">
          <div className="bl-uc-label">Team members</div>
          <div className="bl-uc-unlimited" style={{ color: '#6c7a70' }}>
            Not available on {plan.name}
          </div>
        </div>
      </div>

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
      <div className="bl-invoice-section">
        <div className="bl-section-label" style={{ marginBottom: 14 }}>Billing History</div>
        <div className="bl-invoice-table-wrap">
          <table className="bl-invoice-table">
            <thead>
              <tr>
                <th>Invoice ID</th>
                <th>Date</th>
                <th>Plan</th>
                <th>Amount</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {MOCK_INVOICES.map(inv => (
                <tr key={inv.id}>
                  <td className="inv-id">{inv.id}</td>
                  <td>{inv.date}</td>
                  <td>{inv.plan}</td>
                  <td className="inv-amount">{inv.amount}</td>
                  <td><span className="inv-status paid">{inv.status}</span></td>
                  <td>
                    <button id={`download-${inv.id}`} className="inv-dl-btn">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      PDF
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   ROOT COMPONENT
═══════════════════════════════════════════ */
export default function Billing() {
  const navigate = useNavigate();
  const [view, setView] = useState('plans'); // 'plans' | 'checkout' | 'success' | 'status'
  const [annual, setAnnual] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const currentPlan = 'starter';

  const handleSelectPlan = plan => {
    setSelectedPlan(plan);
    setView('checkout');
  };

  const handlePaySuccess = plan => {
    setSelectedPlan(plan);
    setView('success');
  };

  return (
    <div className="pad bill-wrap">
      {/* Top nav tabs (when not in plans view) */}
      {view !== 'plans' && view !== 'checkout' && (
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
          annual={annual}
          setAnnual={setAnnual}
          onSelectPlan={handleSelectPlan}
          currentPlan={currentPlan}
        />
      )}

      {view === 'checkout' && selectedPlan && (
        <CheckoutView
          plan={selectedPlan}
          annual={annual}
          onBack={() => setView('plans')}
          onSuccess={handlePaySuccess}
        />
      )}

      {view === 'success' && selectedPlan && (
        <SuccessView
          plan={selectedPlan}
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
