import { useApp } from '../context/AppContext';

const DIMENSIONS = [
  {
    key: 'leadership',
    title: 'Leadership style',
    subtitle: 'Energy-led, present',
    score: 68,
    desc: 'Your team follows your conviction. Direction is clear; ownership of outcomes still centres on you.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    )
  },
  {
    key: 'decision',
    title: 'Decision pattern',
    subtitle: 'Intuitive, fast',
    score: 64,
    desc: 'You decide quickly from instinct. Under pressure you reach for familiar levers — spend — over unfamiliar ones like retention.',
    icon: (
      <svg viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="6" x2="12" y2="18" />
        <line x1="6" y1="12" x2="18" y2="12" />
      </svg>
    )
  },
  {
    key: 'execution',
    title: 'Execution behaviour',
    subtitle: 'Top-of-funnel biased',
    score: 59,
    desc: 'Follow-through is real but concentrated on acquisition. Lifecycle work quietly gets less of your attention.',
    icon: (
      <svg viewBox="0 0 24 24">
        <polyline points="9 11 12 14 22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    )
  },
  {
    key: 'communication',
    title: 'Communication style',
    subtitle: 'Direct, momentum-first',
    score: 72,
    desc: "Clear and fast — you rally people around a goal well. The 'why' sometimes trails the pace you set.",
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    )
  },
  {
    key: 'risk',
    title: 'Risk appetite',
    subtitle: 'High, growth-tilted',
    score: 66,
    desc: 'Comfortable betting on upside. The instinct to double down can outrun the evidence in front of you.',
    icon: (
      <svg viewBox="0 0 24 24">
        <polygon points="12 2 2 7 12 12 22 7 12 2" />
        <polyline points="2 17 12 22 22 17" />
        <polyline points="2 12 12 17 22 12" />
      </svg>
    )
  },
  {
    key: 'blindspot',
    title: 'Founder blind spot',
    subtitle: 'Downstream of the sale',
    score: 51,
    desc: 'Sharp visibility up to conversion, thinner after it. What happens post-activation is your least-watched surface.',
    icon: (
      <svg viewBox="0 0 24 24">
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
        <line x1="1" y1="1" x2="23" y2="23" />
      </svg>
    )
  },
  {
    key: 'stress',
    title: 'Stress signal',
    subtitle: 'Adds effort, not questions',
    score: 57,
    desc: 'When numbers wobble you add inputs — spend, hours — before pausing to re-diagnose. A tell worth watching.',
    icon: (
      <svg viewBox="0 0 24 24">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    )
  }
];

export default function FounderDNA() {
  const { user } = useApp();

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
          <div className="fd-hero-kicker">Founder First - Your Archetype</div>
          <h2 className="fd-hero-title">
            You lead like <em>The Momentum Builder.</em>
          </h2>
          <p className="fd-hero-desc">
            You create velocity better than almost anyone — and your growth is
            now limited by what you watch least, not what you do most. Below is
            how Ally reads the person behind the decisions.
          </p>
        </div>
        <div className="fd-hero-score-wrap">
          <div className="fd-hero-score">71</div>
          <div className="fd-hero-label">Founder</div>
        </div>
      </div>

      {/* Section Head */}
      <div className="fd-section-head stagger d2">
        <h3 className="fd-section-title">Founder dimensions</h3>
        <span className="fd-section-meta">
          Observed across your conversations with Ally
        </span>
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
                  <span className="fd-card-subtitle">{dim.subtitle}</span>
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
