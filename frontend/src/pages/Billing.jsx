import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MOCK_PLANS } from '../data/mockData';

const COMPARE_ROWS = [
  { label: 'Diagnoses / month', free: '2', pro: '10', proplus: '25', max: 'Unlimited' },
  { label: 'Founder DNA assessment', free: true, pro: true, proplus: true, max: true },
  { label: 'Business DNA mapping', free: false, pro: true, proplus: true, max: true },
  { label: 'Ally Chat sessions', free: '1/week', pro: 'Unlimited', proplus: 'Unlimited', max: 'Unlimited' },
  { label: 'Clarity Reports', free: false, pro: true, proplus: true, max: true },
  { label: 'Action Plans', free: false, pro: true, proplus: true, max: true },
  { label: 'Team accounts', free: false, pro: false, proplus: '3 members', max: 'Unlimited' },
  { label: 'Dedicated coach', free: false, pro: false, proplus: true, max: true },
  { label: 'API access', free: false, pro: false, proplus: true, max: true },
  { label: 'White-label reports', free: false, pro: false, proplus: false, max: true },
];

function CmpCell({ val }) {
  if (val === true) return <span className="cmp-yes"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="2 6 5 9 10 3"/></svg></span>;
  if (val === false) return <span className="cmp-no">—</span>;
  return <span style={{ fontSize: 12, color: '#556458', fontWeight: 600 }}>{val}</span>;
}

export default function Billing() {
  const navigate = useNavigate();
  const [annual, setAnnual] = useState(false);
  const currentPlan = 'pro';

  return (
    <div className="pad bill-wrap">
      {/* Hero */}
      <div className="pr-hero stagger d1">
        <div className="pr-eye">
          <span className="lv" />
          Transparent Pricing
        </div>
        <h1>Simple plans, <em>powerful</em> clarity</h1>
        <p>Start free. Upgrade when you need more diagnoses, deeper insights, or team features.</p>
      </div>

      {/* Billing toggle */}
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
        {MOCK_PLANS.map(plan => {
          const price = annual ? Math.floor(plan.price * 0.8) : plan.price;
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
                className={`pc-cta${currentPlan === plan.id ? '' : ' primary'}`}
                onClick={() => plan.id === 'max' ? null : navigate('/app/billing')}
                disabled={currentPlan === plan.id}
              >
                {currentPlan === plan.id ? '✓ Current Plan' : plan.cta}
              </button>
              <ul className="pc-feats">
                {plan.features.map((f, i) => (
                  <li key={i}>
                    <span className="fk">
                      <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="2 6 5 9 10 3"/></svg>
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
        <span><svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>Bank-grade encryption</span>
        <span><svg viewBox="0 0 24 24"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>Cancel anytime</span>
        <span><svg viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>100% data privacy</span>
        <span><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>14-day free trial</span>
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
              {MOCK_PLANS.map(p => (
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
                <td><CmpCell val={row.proplus} /></td>
                <td><CmpCell val={row.max} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
