import { useApp } from '../context/AppContext';
import { useNavigate } from 'react-router-dom';

const ACTIONS = [
  {
    num: '1',
    text: 'Fix the 30-day churn cliff before adding a rupee of spend. Map the exact step users drop off in week two.',
    tag: 'high',
    tagLabel: 'High Impact'
  },
  {
    num: '2',
    text: 'Re-segment around your 3 highest-LTV customer types and redesign the first 7 days for them specifically.',
    tag: 'high',
    tagLabel: 'High Impact'
  },
  {
    num: '3',
    text: 'Tie one core metric to retention — not acquisition — and review it weekly as your growth north star.',
    tag: 'medium',
    tagLabel: 'Medium Impact'
  }
];

const ROADMAP = [
  {
    kicker: 'NOW',
    days: '0–30 days',
    items: [
      'Instrument the week-two drop-off',
      'Interview 10 churned users',
      'Ship one first-value fix'
    ]
  },
  {
    kicker: 'NEXT',
    days: '30–60 days',
    items: [
      'Redesign onboarding for top-LTV segment',
      'Set retention as the weekly north star',
      'Re-baseline CAC against retained users'
    ]
  },
  {
    kicker: 'LATER',
    days: '60–90 days',
    items: [
      'Scale spend only after leak is sealed',
      'Build a lifecycle ownership model',
      'Review clarity score with your advisor'
    ]
  }
];

export default function NextSteps() {
  const navigate = useNavigate();
  const { user } = useApp();

  return (
    <div className="fd-container">
      {/* Dark Forest Hero Banner */}
      <div className="fd-hero stagger d1">
        <div className="fd-hero-content">
          <div className="fd-hero-kicker">Next steps</div>
          <h2 className="fd-hero-title">Three moves, sequenced to compound.</h2>
          <p className="fd-hero-desc">
            Not a to-do list. The first move unlocks the second. Work top to
            bottom — Ally tracks momentum as you go.
          </p>
        </div>
      </div>

      {/* Priority Actions */}
      <div className="fd-section-head stagger d2" style={{ marginTop: 32 }}>
        <h3 className="fd-section-title">Priority actions</h3>
      </div>

      <div className="rep-act-list stagger d2">
        {ACTIONS.map((act) => (
          <div key={act.num} className="rep-act-card" style={{ padding: '24px' }}>
            <div className="rep-act-num">{act.num}</div>
            <div className="rep-act-content">
              <p className="rep-act-text" style={{ fontSize: '14.5px', fontWeight: 500 }}>{act.text}</p>
              <span className={`rep-act-tag ${act.tag}`} style={{ marginTop: 8 }}>{act.tagLabel}</span>
            </div>
          </div>
        ))}
      </div>

      {/* 90-day roadmap */}
      <div className="fd-section-head stagger d3" style={{ marginTop: 32 }}>
        <h3 className="fd-section-title">90-day roadmap</h3>
      </div>

      <div className="rep-rm-grid stagger d3" style={{ marginBottom: 24 }}>
        {ROADMAP.map((phase, idx) => (
          <div key={idx} className="rep-rm-card">
            <div className="rep-rm-kicker">{phase.kicker}</div>
            <div className="rep-rm-days">{phase.days}</div>
            <ul className="rep-rm-list">
              {phase.items.map((item, idy) => (
                <li key={idy} className="rep-rm-item">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* Book a session button at the bottom */}
      <div className="stagger d4" style={{ marginTop: 24 }}>
        <button
          onClick={() => navigate('/app/billing')}
          className="btn btn-primary"
          style={{
            background: '#10B981',
            color: '#06231a',
            fontWeight: 750,
            padding: '12px 20px',
            borderRadius: '10px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            boxShadow: '0 10px 24px -8px rgba(16, 185, 129, 0.4)'
          }}
          type="button"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            style={{ width: 16, height: 16 }}
          >
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          Book a session to pressure-test this plan
        </button>
      </div>
    </div>
  );
}
