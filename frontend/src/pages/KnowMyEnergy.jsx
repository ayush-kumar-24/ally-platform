/**
 * Know My Energy — Pro-only.
 *
 * PLACEHOLDER. The plan gate, the pricing entry and the route are real; the
 * feature itself is not built yet because its behaviour hasn't been defined.
 * Rendering a deliberate "coming soon" is honest — inventing a founder-facing
 * feature to fill the space would be worse than an empty room with a sign on it.
 *
 * When the real thing lands, replace the body below. Nothing else needs changing:
 * gating, routing and the Pro plan entry already point here.
 */

import PlanGate from '../components/PlanGate';
import { FEATURES } from '../services/plans';

function ComingSoon() {
  return (
    <div className="dc-container">
      <div className="pr-sec-head stagger d1">
        <h3 className="pr-sec-title">Know My Energy</h3>
        <span className="pr-sec-sub">Understand how your energy moves through the week.</span>
      </div>

      <div className="pr-card stagger d2" style={{ textAlign: 'center', padding: '40px 26px' }}>
        <div style={{ fontSize: 30, marginBottom: 12 }} aria-hidden="true">⚡</div>
        <h2 style={{ margin: '0 0 10px', fontSize: 20, color: 'var(--ink, #16241c)' }}>
          Coming soon
        </h2>
        <p style={{
          margin: '0 auto', maxWidth: 460, color: 'var(--muted, #556458)',
          fontSize: 14, lineHeight: 1.65,
        }}>
          This is part of your Pro plan and is being built now. You&apos;ll find it here
          as soon as it&apos;s ready — nothing to do in the meantime.
        </p>
      </div>
    </div>
  );
}

export default function KnowMyEnergy() {
  return (
    <PlanGate
      feature={FEATURES.KNOW_MY_ENERGY}
      requiredPlan="Pro"
      title="Know My Energy is a Pro feature"
      message="Upgrade to Pro to see how your energy patterns shape the decisions you make."
    >
      <ComingSoon />
    </PlanGate>
  );
}
