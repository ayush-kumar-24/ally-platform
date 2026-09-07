/**
 * Payments — every attempt, not just the ones that worked.
 *
 * The panel had no view of `payments` at all: revenue was summed off
 * `subscriptions`, and the user detail page showed a plan or "No subscription
 * record". So a founder whose card was declined, or whose payment succeeded at
 * Razorpay but whose webhook never arrived, left a complete row in the database
 * that nobody answering their email could see.
 *
 * The failed and pending rows are the reason this page exists. A successful
 * payment is already visible as the plan the founder is on; the ones that need
 * a human are exactly the ones that left no other trace, which is why the
 * default filter is "all statuses" and failures are called out in the summary.
 *
 * Read-only by design. Refunds live in the Razorpay dashboard and granting a
 * plan belongs to the signed webhook — a second "mark this paid" button here is
 * how one payment grants a plan twice.
 *
 * Reading is view_users: "did my payment go through?" is a support question,
 * and the person answering it should be able to see the failed row without
 * being able to change anybody's plan.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { listPayments, PAYMENT_STATUSES, paymentsSummary } from '../../services/admin';
import { useDebounce } from '../../hooks/useDebounce';
import { EmptyState, ErrorState, Loading, Pagination } from './AdminUI';

const PAGE_SIZE = 25;

function fmt(iso) {
  return iso ? new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }) : '—';
}

function rupees(n) {
  return n == null ? '—' : `₹${Number(n).toLocaleString('en-IN')}`;
}

/** A gateway id is what you paste into Razorpay to find the other half of the
 *  story, so it is rendered whole and in mono rather than prettified — a
 *  truncated `pay_…` is worse than useless when the point is to copy it. An
 *  absent one is normal: `gateway_payment_id` is only set once a payment is
 *  captured, so every pending and failed row has a dash there. */
function GatewayId({ value }) {
  if (!value) return <span className="adm-muted">—</span>;
  return <span className="adm-mono" title={value}>{value}</span>;
}

export default function AdminPayments() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);

  const [data, setData] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const debouncedSearch = useDebounce(search, 300);
  // A slower earlier request landing after a newer one would show the wrong
  // rows for the current filters — same guard the Users list uses.
  const seq = useRef(0);

  const load = useCallback(() => {
    const mine = ++seq.current;
    setLoading(true);
    setError(null);
    Promise.all([
      listPayments({
        status: status || undefined,
        q: debouncedSearch || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
      // The summary counts everything, deliberately ignoring the filters: it is
      // the reference the filtered table is read against, and a "3 failed" that
      // moved every time you typed would be useless for that.
      paymentsSummary().catch(() => null),
    ])
      .then(([res, sum]) => {
        if (mine !== seq.current) return;
        setData(res);
        if (sum) setSummary(sum);
      })
      .catch((err) => { if (mine === seq.current) setError(err); })
      .finally(() => { if (mine === seq.current) setLoading(false); });
  }, [debouncedSearch, status, page]);

  useEffect(load, [load]);

  // Staying on page 4 of a result set that now has one page shows an empty table.
  useEffect(() => { setPage(1); }, [debouncedSearch, status]);

  const items = data?.items ?? [];
  const hasFilters = Boolean(debouncedSearch || status);
  const pages = data ? Math.max(1, Math.ceil((data.total || 0) / PAGE_SIZE)) : 1;
  const byStatus = summary?.by_status ?? {};

  return (
    <>
      <h1 className="adm-h1">Payments</h1>
      <p className="adm-sub">
        Every checkout attempt Razorpay was asked for — captured, pending and failed.
        Read-only: refunds are done in Razorpay, and plans are granted by the webhook.
      </p>

      {summary && (
        <div className="adm-grid">
          <div className="adm-panel">
            <h2>Captured</h2>
            <div className="adm-stat">{rupees(summary.captured_inr)}</div>
            <p className="adm-muted" style={{ fontSize: 12 }}>
              {byStatus.success?.count ?? 0} successful payment
              {(byStatus.success?.count ?? 0) === 1 ? '' : 's'}
            </p>
          </div>
          <div className="adm-panel">
            <h2>Failed</h2>
            <div className="adm-stat">{byStatus.failed?.count ?? 0}</div>
            <p className="adm-muted" style={{ fontSize: 12 }}>
              Founders who tried to pay and could not
            </p>
          </div>
          <div className="adm-panel">
            <h2>Pending</h2>
            <div className="adm-stat">{byStatus.pending?.count ?? 0}</div>
            <p className="adm-muted" style={{ fontSize: 12 }}>
              {/* A pending row is an order created and never captured: an
                  abandoned checkout, or a webhook that never arrived. The two
                  look identical here and only the gateway can tell them apart. */}
              Order created, never captured — check Razorpay before assuming abandoned
            </p>
          </div>
          <div className="adm-panel">
            <h2>Discounts given</h2>
            <div className="adm-stat">{rupees(summary.discount_given_inr)}</div>
            <p className="adm-muted" style={{ fontSize: 12 }}>
              Off list price, on captured payments
            </p>
          </div>
        </div>
      )}

      <div className="adm-panel">
        <div className="adm-filters">
          <input
            className="adm-input adm-search"
            type="search"
            placeholder="Email, name, founder ID, or a Razorpay order/payment id…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search payments"
          />
          <select className="adm-select" value={status}
                  onChange={e => setStatus(e.target.value)} aria-label="Filter by status">
            <option value="">All statuses</option>
            {PAYMENT_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {error ? (
          <ErrorState error={error} onRetry={load} />
        ) : loading && !data ? (
          <Loading label="Loading payments…" />
        ) : items.length === 0 ? (
          <EmptyState
            title={hasFilters ? 'No payments match those filters' : 'No payments recorded'}
            hint={hasFilters
              ? 'Try clearing the search or the status filter.'
              : 'Nothing has been written to the payments table yet. If founders '
                + 'are on paid plans, those plans were granted outside checkout — '
                + 'or the Razorpay webhook is not reaching this environment.'}
          />
        ) : (
          <>
            <div className="adm-table-wrap" aria-busy={loading}>
              <table className="adm-table">
                <thead>
                  <tr>
                    <th scope="col" className="adm-nosort">ID</th>
                    <th scope="col" className="adm-nosort">Founder</th>
                    <th scope="col" className="adm-nosort adm-num">Amount</th>
                    <th scope="col" className="adm-nosort">Status</th>
                    <th scope="col" className="adm-nosort">Plan</th>
                    <th scope="col" className="adm-nosort">Coupon</th>
                    <th scope="col" className="adm-nosort">Order id</th>
                    <th scope="col" className="adm-nosort">Payment id</th>
                    <th scope="col" className="adm-nosort">Created</th>
                    <th scope="col" className="adm-nosort">Paid</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(p => (
                    <tr key={p.payment_id}>
                      <td className="adm-mono">{p.payment_id}</td>
                      <td>
                        <Link to={`/admin/users/${p.founder_id}`}>
                          {p.full_name || p.email || `#${p.founder_id}`}
                        </Link>
                        {p.full_name && p.email && (
                          <div className="adm-muted" style={{ fontSize: 12 }}>{p.email}</div>
                        )}
                      </td>
                      <td className="adm-num">
                        {rupees(p.amount_inr)}
                        {/* Only shown when a coupon actually moved the price:
                            list_amount_inr is NULL on an undiscounted payment
                            rather than a copy of the amount. */}
                        {p.discount_inr != null && (
                          <div className="adm-muted" style={{ fontSize: 12 }}>
                            was {rupees(p.list_amount_inr)} · −{rupees(p.discount_inr)}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className={`adm-pill ${p.status}`}>{p.status}</span>
                        {p.failure_reason && (
                          <div className="adm-muted" style={{ fontSize: 12 }}
                               title={p.failure_reason}>
                            {p.failure_reason}
                          </div>
                        )}
                      </td>
                      <td>{p.plan_type || <span className="adm-muted">—</span>}</td>
                      <td className="adm-mono">
                        {p.coupon_code || <span className="adm-muted">—</span>}
                      </td>
                      <td><GatewayId value={p.gateway_order_id} /></td>
                      <td><GatewayId value={p.gateway_payment_id} /></td>
                      <td className="adm-muted">{fmt(p.created_at)}</td>
                      <td className="adm-muted">{fmt(p.paid_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pages={pages} total={data.total}
                        noun="payment" onChange={setPage} busy={loading} />
          </>
        )}
      </div>
    </>
  );
}
