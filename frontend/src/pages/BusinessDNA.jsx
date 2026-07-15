import { useApp } from '../context/AppContext';
import { useNavigate } from 'react-router-dom';

const DIMENSIONS = [
  {
    key: 'retention',
    title: 'Retention',
    score: 44,
    desc: 'Week two drop confirmed. First value moment not reached.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
        <path d="M3 3v5h5" />
      </svg>
    )
  },
  {
    key: 'acquisition',
    title: 'Acquisition',
    score: 62,
    desc: 'Spend rising, efficiency falling — churn is the tax.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <line x1="19" y1="8" x2="19" y2="14" />
        <line x1="16" y1="11" x2="22" y2="11" />
      </svg>
    )
  },
  {
    key: 'product',
    title: 'Product',
    score: 66,
    desc: 'Core loop works. Onboarding sequence is weak.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
        <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
        <line x1="12" y1="22.08" x2="12" y2="12" />
      </svg>
    )
  },
  {
    key: 'sales',
    title: 'Sales pipeline',
    score: 78,
    desc: 'Strong intent. Qualification gap at demo stage.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" />
      </svg>
    )
  },
  {
    key: 'cash',
    title: 'Cash flow',
    score: 70,
    desc: 'Healthy runway. Timing of collections could tighten.',
    icon: (
      <svg viewBox="0 0 24 24">
        <rect x="2" y="6" width="20" height="12" rx="2" />
        <circle cx="12" cy="12" r="3" />
        <line x1="6" y1="12" x2="6.01" y2="12" />
        <line x1="18" y1="12" x2="18.01" y2="12" />
      </svg>
    )
  },
  {
    key: 'team',
    title: 'Team',
    score: 61,
    desc: 'Capable hires. Ownership of outcomes not yet distributed.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    )
  },
  {
    key: 'strategy',
    title: 'Strategy',
    score: 58,
    desc: 'Ten priorities competing for the same energy.',
    icon: (
      <svg viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="6" />
        <circle cx="12" cy="12" r="2" />
      </svg>
    )
  },
  {
    key: 'pricing',
    title: 'Pricing',
    score: 74,
    desc: 'Competitive and defensible. Not the constraint.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
        <line x1="7" y1="7" x2="7.01" y2="7" />
      </svg>
    )
  }
];

export default function BusinessDNA() {
  const { user } = useApp();
  const navigate = useNavigate();

  const getColorClass = (score) => {
    if (score >= 70) return 'fd-cat-green';
    if (score >= 52) return 'fd-cat-orange';
    return 'fd-cat-red';
  };

  return (
    <div className="fd-container">
      {/* Dark Forest Hero Banner */}
      <div className="fd-hero stagger d1">
        <div className="fd-hero-content">
          <div className="fd-hero-kicker">Business DNA</div>
          <h2 className="fd-hero-title">
            Ten dimensions, weighed together.
          </h2>
          <p className="fd-hero-desc">
            Each dimension read through your founder profile — an advisor
            holding your whole business in their head at once, not a checklist.
          </p>
        </div>
        <div className="fd-hero-score-wrap">
          <div className="fd-hero-score">64</div>
          <div className="fd-hero-label">Business</div>
        </div>
      </div>

      {/* Section Head */}
      <div className="fd-section-head stagger d2">
        <h3 className="fd-section-title">Business dimensions</h3>
        <button
          onClick={() => navigate('/app/thinking')}
          className="fd-section-link"
          type="button"
        >
          See root cause
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            width="13"
            height="13"
          >
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </button>
      </div>

      {/* Dimensions Grid */}
      <div className="fd-grid stagger d3">
        {DIMENSIONS.map((dim) => (
          <div key={dim.key} className={`fd-card ${getColorClass(dim.score)}`}>
            <div className="fd-card-top">
              <div className="fd-card-info">
                <div className="fd-card-icon">{dim.icon}</div>
                <div className="fd-card-title-wrap">
                  <h4 className="fd-card-title">{dim.title}</h4>
                </div>
              </div>
              <div className="fd-card-score">{dim.score}</div>
            </div>

            <div className="fd-progress-track">
              <div
                className="fd-progress-bar"
                style={{ width: `${dim.score}%` }}
              />
            </div>

            <p className="fd-card-desc">{dim.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
