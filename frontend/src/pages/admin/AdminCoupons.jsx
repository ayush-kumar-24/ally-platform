/**
 * Coupons — create discount codes, watch them being claimed, switch them off.
 *
 * Two shapes of code, and the difference matters when you create one:
 *
 *   "First 100 customers"  ONE code, max redemptions 100. Everyone types the
 *                          same thing and it stops working at 100.
 *   Partner codes          N unique single-use codes under a prefix, from the
 *                          Generate batch form. One recipient, one code.
 *
 * Reading is view_users, because "how many of the 100 are left" is a question
 * support gets asked. Creating decides what founders pay, so it is Super Admin
 * only server-side; the forms are hidden for other roles as a convenience and
 * the backend rejects the request either way.
 *
 * There is no delete. A redeemed coupon is a financial record: deactivating
 * stops further use and keeps the history that explains a discounted payment.
 */

import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  bulkCoupons,
  can,
  couponRedemptions,
  createCoupon,
  listCoupons,
  updateCoupon,
} from '../../services/admin';
import { ConfirmDialog, EmptyState, ErrorState, Flash, Loading, useFlash } from './AdminUI';

const TIERS = [
  { id: 'basic', label: 'Basic' },
  { id: 'starter', label: 'Plus' },
  { id: 'pro', label: 'Pro' },
];

function fmt(iso) {
  return iso ? new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }) : '—';
}

/** `datetime-local` gives "2026-09-30T18:00" with no zone. The admin means
 *  their own clock, so let the browser resolve it and send a real instant —
 *  a coupon that expires "at 6pm" in an unstated zone expires twice. */
function toInstant(local) {
  if (!local) return null;
  const d = new Date(local);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

/** Two weeks out, rounded to the hour: a sane default that still forces the
 *  admin to look at it, since every coupon must carry an expiry. */
function defaultExpiry() {
  const d = new Date(Date.now() + 14 * 86400000);
  d.setMinutes(0, 0, 0);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
    + `T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function describeDiscount(c) {
  return c.discount_type === 'percent'
    ? `${c.discount_value}% off`
    : `₹${c.discount_value.toLocaleString('en-IN')} off`;
}

function describeScope(c) {
  if (!c.applies_to || c.applies_to.length === 0) return 'All paid plans';
  return c.applies_to
    .map(t => TIERS.find(x => x.id === t)?.label || t)
    .join(', ');
}

export default function AdminCoupons() {
  const { me } = useOutletContext();
  const mayManage = can(me, 'modify_subscription');

  const [coupons, setCoupons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useFlash();
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [redemptions, setRedemptions] = useState({});
  const inFlight = useRef(false);

  // Single code
  const [code, setCode] = useState('');
  const [description, setDescription] = useState('');
  const [discountType, setDiscountType] = useState('percent');
  const [discountValue, setDiscountValue] = useState('');
  const [maxRedemptions, setMaxRedemptions] = useState('');
  const [scope, setScope] = useState([]);
  const [validUntil, setValidUntil] = useState(defaultExpiry);

  // Batch
  const [prefix, setPrefix] = useState('');
  const [count, setCount] = useState('');
  const [batchType, setBatchType] = useState('percent');
  const [batchValue, setBatchValue] = useState('');
  const [batchUntil, setBatchUntil] = useState(defaultExpiry);

  const load = useCallback(() => {
    if (inFlight.current) return;
    inFlight.current = true;
    setError(null);
    listCoupons()
      .then(d => setCoupons(d.coupons || []))
      .catch(setError)
      .finally(() => { inFlight.current = false; setLoading(false); });
  }, []);

  useEffect(() => { load(); }, [load]);

  const run = async (fn, message) => {
    setBusy(true);
    try {
      const result = await fn();
      setFlash({ kind: 'ok', message });
      load();
      return result;
    } catch (err) {
      setFlash({ kind: 'err', message: err?.detail || err?.message || 'That did not work.' });
      throw err;
    } finally {
      setBusy(false);
    }
  };

  const toggleRedemptions = async (couponId) => {
    if (expanded === couponId) { setExpanded(null); return; }
    setExpanded(couponId);
    if (redemptions[couponId]) return;
    try {
      const d = await couponRedemptions(couponId);
      setRedemptions(r => ({ ...r, [couponId]: d.redemptions || [] }));
    } catch (err) {
      setFlash({ kind: 'err', message: err?.detail || 'Could not load redemptions.' });
    }
  };

  const submitSingle = (e) => {
    e.preventDefault();
    const until = toInstant(validUntil);
    if (!code.trim() || !discountValue || !until) return;
    run(() => createCoupon({
      code: code.trim().toUpperCase(),
      description: description.trim() || null,
      discount_type: discountType,
      discount_value: Number(discountValue),
      applies_to: scope.length ? scope : null,
      max_redemptions: maxRedemptions ? Number(maxRedemptions) : null,
      max_per_founder: 1,
      valid_until: until,
    }), `Coupon ${code.trim().toUpperCase()} created.`)
      .then(() => {
        setCode(''); setDescription(''); setDiscountValue('');
        setMaxRedemptions(''); setScope([]);
      })
      .catch(() => {});
  };

  const submitBatch = (e) => {
    e.preventDefault();
    const until = toInstant(batchUntil);
    if (!prefix.trim() || !count || !batchValue || !until) return;
    setDialog({
      title: `Generate ${count} codes?`,
      body: <>Each is single-use and expires {fmt(until)}. They cannot be edited afterwards.</>,
      confirmLabel: 'Generate',
      run: () => run(() => bulkCoupons({
        prefix: prefix.trim().toUpperCase(),
        count: Number(count),
        discount_type: batchType,
        discount_value: Number(batchValue),
        valid_until: until,
      }), `${count} codes generated.`)
        .then(() => { setPrefix(''); setCount(''); setBatchValue(''); })
        .catch(() => {}),
    });
  };

  if (loading) return <Loading label="Loading coupons…" />;
  if (error) return <ErrorState error={error} onRetry={load} />;

  return (
    <>
      <h1 className="adm-h1">Coupons</h1>
      <p className="adm-sub">
        Discount codes for paid plans. One code with a cap is how you run
        &ldquo;first 100 customers&rdquo;; a batch is one code per recipient.
      </p>
      <Flash flash={flash} />

      {mayManage && (
        <div className="adm-panel">
          <h2>New coupon</h2>
          <form onSubmit={submitSingle}>
            <div className="adm-filters">
              <input className="adm-input" placeholder="FOUNDER100" value={code}
                     onChange={e => setCode(e.target.value.toUpperCase())}
                     aria-label="Coupon code" maxLength={40} />
              <select className="adm-input" value={discountType}
                      onChange={e => setDiscountType(e.target.value)}
                      aria-label="Discount type">
                <option value="percent">Percent off</option>
                <option value="fixed">Rupees off</option>
              </select>
              <input className="adm-input" type="number" min="1"
                     max={discountType === 'percent' ? 99 : undefined}
                     placeholder={discountType === 'percent' ? '50' : '200'}
                     value={discountValue}
                     onChange={e => setDiscountValue(e.target.value)}
                     aria-label="Discount value" />
              <input className="adm-input" type="number" min="1" placeholder="Max uses (blank = ∞)"
                     value={maxRedemptions}
                     onChange={e => setMaxRedemptions(e.target.value)}
                     aria-label="Maximum redemptions" />
            </div>
            <div className="adm-filters">
              <input className="adm-input adm-search" placeholder="What is this for?"
                     value={description} onChange={e => setDescription(e.target.value)}
                     aria-label="Description" />
              <label className="adm-inline-label">
                Expires
                <input className="adm-input" type="datetime-local" value={validUntil}
                       onChange={e => setValidUntil(e.target.value)}
                       aria-label="Expires at" required />
              </label>
            </div>
            <div className="adm-filters adm-coupon-scope">
              <span className="adm-muted">Applies to:</span>
              {TIERS.map(t => (
                <label key={t.id} className="adm-inline-label">
                  <input type="checkbox" checked={scope.includes(t.id)}
                         onChange={() => setScope(s => s.includes(t.id)
                           ? s.filter(x => x !== t.id) : [...s, t.id])} />
                  {t.label}
                </label>
              ))}
              <span className="adm-muted">
                {scope.length === 0 ? '(none ticked = every paid plan)' : ''}
              </span>
            </div>
            <button className="adm-btn adm-btn--primary" type="submit" disabled={busy}>
              Create coupon
            </button>
            {discountType === 'percent' && (
              <p className="adm-hint">
                Maximum 99%. Razorpay cannot charge an order of ₹0, so a fully
                free coupon is not possible.
              </p>
            )}
          </form>
        </div>
      )}

      {mayManage && (
        <div className="adm-panel">
          <h2>Generate a batch</h2>
          <p className="adm-sub">
            Unique single-use codes, one per recipient. Use this for partners,
            not for a shared launch offer.
          </p>
          <form onSubmit={submitBatch}>
            <div className="adm-filters">
              <input className="adm-input" placeholder="PARTNER" value={prefix}
                     onChange={e => setPrefix(e.target.value.toUpperCase())}
                     aria-label="Code prefix" maxLength={20} />
              <input className="adm-input" type="number" min="1" max="200" placeholder="How many"
                     value={count} onChange={e => setCount(e.target.value)}
                     aria-label="How many codes" />
              <select className="adm-input" value={batchType}
                      onChange={e => setBatchType(e.target.value)}
                      aria-label="Batch discount type">
                <option value="percent">Percent off</option>
                <option value="fixed">Rupees off</option>
              </select>
              <input className="adm-input" type="number" min="1"
                     max={batchType === 'percent' ? 99 : undefined}
                     placeholder="Value" value={batchValue}
                     onChange={e => setBatchValue(e.target.value)}
                     aria-label="Batch discount value" />
              <label className="adm-inline-label">
                Expires
                <input className="adm-input" type="datetime-local" value={batchUntil}
                       onChange={e => setBatchUntil(e.target.value)}
                       aria-label="Batch expires at" required />
              </label>
            </div>
            <button className="adm-btn" type="submit" disabled={busy}>Generate codes</button>
          </form>
        </div>
      )}

      <div className="adm-panel">
        <h2>All coupons</h2>
        {coupons.length === 0 ? (
          <EmptyState title="No coupons yet"
                      hint="Create one above to start discounting a plan." />
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th scope="col" className="adm-nosort">Code</th>
                  <th scope="col" className="adm-nosort">Discount</th>
                  <th scope="col" className="adm-nosort">Applies to</th>
                  <th scope="col" className="adm-nosort">Used</th>
                  <th scope="col" className="adm-nosort">Given away</th>
                  <th scope="col" className="adm-nosort">Expires</th>
                  <th scope="col" className="adm-nosort">State</th>
                  <th scope="col" className="adm-nosort">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {coupons.map(c => {
                  const expired = c.valid_until && new Date(c.valid_until) <= new Date();
                  return (
                    <Fragment key={c.coupon_id}>
                      <tr>
                        <td className="adm-mono">{c.code}</td>
                        <td>{describeDiscount(c)}</td>
                        <td className="adm-muted">{describeScope(c)}</td>
                        <td>
                          {c.confirmed_count}
                          {c.max_redemptions ? ` / ${c.max_redemptions}` : ''}
                          {/* In-flight checkouts, held separately so "3 of 100
                              used" and "2 people are paying now" are not the
                              same number. */}
                          {c.pending_count > 0 && (
                            <span className="adm-muted"> (+{c.pending_count} in progress)</span>
                          )}
                        </td>
                        <td>₹{c.discount_given_inr.toLocaleString('en-IN')}</td>
                        <td className="adm-muted">{fmt(c.valid_until)}</td>
                        <td>
                          <span className={`adm-pill ${c.is_active && !expired ? 'active' : 'inactive'}`}>
                            {!c.is_active ? 'off' : expired ? 'expired' : 'live'}
                          </span>
                        </td>
                        <td>
                          <button className="adm-btn adm-btn--sm" type="button"
                                  onClick={() => toggleRedemptions(c.coupon_id)}>
                            {expanded === c.coupon_id ? 'Hide' : 'Who used it'}
                          </button>
                          {mayManage && c.is_active && (
                            <button className="adm-btn adm-btn--sm" type="button" disabled={busy}
                                    onClick={() => setDialog({
                                      title: `Turn off ${c.code}?`,
                                      body: <>Nobody new can redeem it. Payments already
                                             discounted by it are untouched.</>,
                                      confirmLabel: 'Turn off',
                                      run: () => run(
                                        () => updateCoupon(c.coupon_id, { is_active: false }),
                                        `${c.code} turned off.`).catch(() => {}),
                                    })}>
                              Turn off
                            </button>
                          )}
                        </td>
                      </tr>
                      {expanded === c.coupon_id && (
                        <tr>
                          <td colSpan={8}>
                            {!redemptions[c.coupon_id] ? (
                              <Loading label="Loading redemptions…" />
                            ) : redemptions[c.coupon_id].length === 0 ? (
                              <p className="adm-muted">Nobody has used this code yet.</p>
                            ) : (
                              <table className="adm-table">
                                <thead>
                                  <tr>
                                    <th scope="col" className="adm-nosort">Founder</th>
                                    <th scope="col" className="adm-nosort">Saved</th>
                                    <th scope="col" className="adm-nosort">Status</th>
                                    <th scope="col" className="adm-nosort">When</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {redemptions[c.coupon_id].map(r => (
                                    <tr key={r.redemption_id}>
                                      <td>{r.full_name || r.email || `#${r.founder_id}`}</td>
                                      <td>₹{r.discount_inr.toLocaleString('en-IN')}</td>
                                      <td>
                                        <span className={`adm-pill ${r.status === 'confirmed' ? 'active' : 'inactive'}`}>
                                          {r.status}
                                        </span>
                                      </td>
                                      <td className="adm-muted">
                                        {fmt(r.confirmed_at || r.created_at)}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog dialog={dialog} onClose={() => setDialog(null)} busy={busy} />
    </>
  );
}
