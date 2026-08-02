/**
 * PlanGate — hides a feature the founder's plan does not include and offers the
 * upgrade instead.
 *
 * This is presentation only. The backend refuses the same action regardless of
 * what renders here, so a founder who bypasses the UI gains nothing. The point is
 * to explain rather than to protect: showing a button that 403s is worse than
 * showing why it isn't available.
 *
 * While entitlements are loading it renders `children`, not a spinner — the common
 * case is that the founder DOES have access, and flashing a paywall at a paying
 * customer for half a second is the worse failure.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { can, getMyPlan } from '../services/plans';

export function usePlan() {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getMyPlan()
      .then(p => { if (!cancelled) setPlan(p); })
      .catch(() => { /* not signed in, or plans not live yet */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return { plan, loading };
}

export function UpgradeCard({ title, message, requiredPlan = 'Starter' }) {
  return (
    <div className="pg-lock" role="status" style={{
      maxWidth: 520, margin: '48px auto', padding: '28px 26px', textAlign: 'center',
      background: 'var(--ivory-2, #fbf7f2)', border: '1px solid var(--bd, #e7e0d6)',
      borderRadius: 14,
    }}>
      <div style={{ fontSize: 26, marginBottom: 10 }} aria-hidden="true">🔒</div>
      <h2 style={{ margin: '0 0 8px', fontSize: 19, color: 'var(--ink, #16241c)' }}>{title}</h2>
      <p style={{ margin: '0 0 18px', color: 'var(--muted, #556458)', fontSize: 14, lineHeight: 1.6 }}>
        {message}
      </p>
      <Link to="/app/billing" className="btn-primary" style={{
        display: 'inline-block', padding: '10px 18px', borderRadius: 9,
        background: 'var(--emerald, #10B981)', color: '#fff', fontWeight: 700,
        textDecoration: 'none', fontSize: 14,
      }}>
        Upgrade to {requiredPlan}
      </Link>
    </div>
  );
}

/**
 * Wrap a page or section. `feature` is a value from services/plans.js FEATURES.
 */
export default function PlanGate({ feature, requiredPlan = 'Starter', title, message, children }) {
  const { plan, loading } = usePlan();

  // Optimistic while loading, and permissive if entitlements can't be fetched:
  // the server is still the authority, so a UI failure must not lock out a
  // customer who has actually paid.
  if (loading || !plan) return children;

  if (can(plan, feature)) return children;

  return (
    <UpgradeCard
      title={title || 'Not on your plan'}
      message={message || `This feature is part of the ${requiredPlan} plan.`}
      requiredPlan={requiredPlan}
    />
  );
}
