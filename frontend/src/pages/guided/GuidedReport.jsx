import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

const FOUNDER_DIMS = [
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

const BIZ_DIMS = [
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
  }
];

const EVIDENCE = [
  { val: '-38%', desc: 'Retention from week 1 to week 2' },
  { val: '+40%', desc: 'Ad spend, with flat net growth' },
  { val: '11 days', desc: 'Median time before users go silent' },
  { val: '4 of 4', desc: 'Symptoms trace to one mechanism' },
  { val: '0', desc: 'Onboarding steps that teach core value' },
  { val: '92%', desc: 'Diagnosis confidence after full scan' }
];

const ACTIONS = [
  {
    num: '1',
    text: 'Fix the 30-day churn cliff before adding a rupee of spend. Map the exact steps users drop off in week two.',
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
      'Instrument the week-two dropoff',
      'Interview 10 churned users',
      'Ship one first-value fix'
    ]
  },
  {
    kicker: 'NEXT',
    days: '30–60 days',
    items: [
      'Redesign onboarding for high-LTV segment',
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

const WHY_STEPS = [
  { bold: 'What you feel', text: 'spend is up ~40%, yet net growth is flat.' },
  { bold: 'What Ally ruled out', text: 'pricing, positioning and sales effort all scored healthy.' },
  { bold: 'The signal', text: 'a ~38% drop from week one to week two, clustered around day 11.' },
  { bold: 'The link to you', text: 'your growth reflex keeps attention upstream of the leak.' },
  { bold: 'The conclusion', text: 'one mechanism explains all four: a first-value conversion leak. 92% confidence.' }
];

export default function GuidedReport() {
  const navigate = useNavigate();
  const ringRef = useRef(null);
  const rcFillRef = useRef(null);

  useEffect(() => {
    if (ringRef.current) {
      setTimeout(() => {
        if (ringRef.current) ringRef.current.style.strokeDashoffset = '70';
      }, 350);
    }
    if (rcFillRef.current) {
      setTimeout(() => {
        if (rcFillRef.current) rcFillRef.current.style.width = '92%';
      }, 550);
    }
  }, []);

  const getColorClass = (score) => {
    if (score >= 70) return 'fd-cat-green';
    if (score >= 52) return 'fd-cat-orange';
    return 'fd-cat-red';
  };

  return (
    <div style={{ position: 'relative', height: '100%', display: 'flex', flexDirection: 'column', width: '100%' }}>
      {/* Scrollable Report Content */}
      <div className="fd-container" style={{ flex: 1, overflowY: 'auto', paddingBottom: '90px', background: 'var(--ivory-2, #faf5ee)', color: 'var(--ink, #16241c)' }}>
        {/* Dark Forest Hero Banner */}
        <div className="fd-hero stagger d1">
          <div className="fd-hero-content" style={{ textAlign: 'left' }}>
            <div className="fd-hero-kicker">Founder DNA Report - Jul 2026</div>
            <h2 className="fd-hero-title">Growth & retention diagnosis</h2>
            <p className="fd-hero-desc">
              Ally understood the founder, scanned 10 business dimensions, and
              traced that growth to one root cause with 92% confidence.
            </p>
            <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
              <button
                className="btn btn-em"
                style={{ padding: '9px 16px', borderRadius: 10, fontSize: 13 }}
                onClick={() => navigate('/guided/recommend')}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  style={{ width: 14, height: 14 }}
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Download PDF
              </button>
              <button
                className="btn btn-dark-ghost"
                style={{ padding: '9px 16px', borderRadius: 10, fontSize: 13 }}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  style={{ width: 14, height: 14 }}
                >
                  <circle cx="18" cy="5" r="3" />
                  <circle cx="6" cy="12" r="3" />
                  <circle cx="18" cy="19" r="3" />
                  <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                  <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                </svg>
                Share
              </button>
            </div>
          </div>

          <div className="rep-ring">
            <svg viewBox="0 0 100 100">
              <circle className="bg" cx="50" cy="50" r="43" />
              <circle ref={ringRef} className="fg" cx="50" cy="50" r="43" style={{ strokeDasharray: 270, strokeDashoffset: 270 }} />
            </svg>
            <div className="rep-ring-c">
              <b>74</b>
              <span>Score</span>
            </div>
          </div>
        </div>

        {/* 01 Founder Summary */}
        <div className="rep-sec-head stagger d2">
          <span className="num">01</span>
          <h3 className="title">Founder summary</h3>
        </div>
        <p className="rep-summary-text stagger d2">
          Ayush leads with conviction and moves fast — a strength that built early
          traction, and the same reflex that keeps attention on{' '}
          <strong>acquisition</strong> when the real leak is downstream.
          Decisions are made quickly and intuitively; the gap is not ambition or
          effort, but <strong>visibility</strong> into what happens after a user
          arrives.
        </p>

        {/* 02 Founder DNA */}
        <div className="rep-sec-head stagger d3">
          <span className="num">02</span>
          <h3 className="title">Founder DNA</h3>
        </div>
        <p className="rep-intro-text stagger d3">
          Across four founder dimensions, <strong>execution behaviour</strong> is
          the constraint; strong vision and leadership, but follow-through
          concentrates on top-of-funnel motion. This bias shapes where the
          business bleeds.
        </p>

        <div className="fd-grid stagger d3" style={{ marginBottom: 32 }}>
          {FOUNDER_DIMS.map((dim) => (
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

        {/* 03 Business DNA */}
        <div className="rep-sec-head stagger d4">
          <span className="num">03</span>
          <h3 className="title">Business DNA</h3>
        </div>
        <p className="rep-intro-text stagger d4">
          Pricing, positioning and sales intent are healthy. Retention scores
          lowest and drags acquisition efficiency with it — spend rises while each
          new user is worth less.
        </p>

        <div className="fd-grid stagger d4" style={{ marginBottom: 32 }}>
          {BIZ_DIMS.map((dim) => (
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

        {/* 04 Root Cause */}
        <div className="rep-sec-head stagger d5">
          <span className="num">04</span>
          <h3 className="title">Root cause</h3>
        </div>

        <div className="rep-rc-banner stagger d5">
          <div className="rep-rc-kicker">Ally's Finding · High Confidence</div>
          <h4 className="rep-rc-text">
            Your growth isn't a marketing problem — it's a <em>retention leak.</em>{' '}
            Users reach the product but churn before the core value moment.
          </h4>
          <div className="rep-rc-progress-wrap">
            <div className="rep-rc-track">
              <div ref={rcFillRef} className="rep-rc-fill" style={{ width: '0%' }} />
            </div>
            <span className="rep-rc-pct">92%</span>
          </div>
        </div>

        <div className="rep-wc-wrap stagger d5">
          <div className="rep-wc-title">Why Ally reached this conclusion</div>
          <ol className="rep-wc-list">
            {WHY_STEPS.map((step, idx) => (
              <li key={idx} className="rep-wc-item">
                <div className="rep-wc-num">{idx + 1}</div>
                <div>
                  <strong>{step.bold}</strong> — {step.text}
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="rep-impact-boxes stagger d5">
          <div className="rep-impact-box biz">
            <div className="rep-impact-lbl">Expected Business Impact</div>
            <div className="rep-impact-val">+18–24%</div>
            <div className="rep-impact-desc">
              retained revenue lift within two quarters if the week two leak is
              sealed before scaling spend.
            </div>
          </div>
          <div className="rep-impact-box you">
            <div className="rep-impact-lbl">Expected Founder Impact</div>
            <div className="rep-impact-val">One number, fewer bets</div>
            <div className="rep-impact-desc">
              A single weekly metric to watch — less reactive spend, more
              compounding decisions and calmer weeks.
            </div>
          </div>
        </div>

        {/* 05 Supporting Evidence */}
        <div className="rep-sec-head stagger d6">
          <span className="num">05</span>
          <h3 className="title">Supporting evidence</h3>
        </div>

        <div className="rep-ev-grid stagger d6">
          {EVIDENCE.map((ev, idx) => (
            <div key={idx} className="rep-ev-card">
              <div className="rep-ev-val">{ev.val}</div>
              <div className="rep-ev-desc">{ev.desc}</div>
            </div>
          ))}
        </div>

        {/* 06 Priority Actions */}
        <div className="rep-sec-head stagger d6">
          <span className="num">06</span>
          <h3 className="title">Priority actions</h3>
        </div>

        <div className="rep-act-list stagger d6">
          {ACTIONS.map((act) => (
            <div key={act.num} className="rep-act-card">
              <div className="rep-act-num">{act.num}</div>
              <div className="rep-act-content">
                <p className="rep-act-text">{act.text}</p>
                <span className={`rep-act-tag ${act.tag}`}>{act.tagLabel}</span>
              </div>
            </div>
          ))}
        </div>

        {/* 07 Recommended Roadmap */}
        <div className="rep-sec-head stagger d6">
          <span className="num">07</span>
          <h3 className="title">Recommended roadmap</h3>
        </div>

        <div className="rep-rm-grid stagger d6">
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

        {/* 08 Discovery Call */}
        <div className="rep-sec-head stagger d6">
          <span className="num">08</span>
          <h3 className="title">Discovery call</h3>
        </div>

        <div className="rep-cta-card stagger d6">
          <div className="rep-cta-content">
            <h4 className="rep-cta-title">Turn this diagnosis into a plan.</h4>
            <p className="rep-cta-desc">
              Bring this report to a 30-minute session with a GoXL advisor and
              leave with a sequenced 90-day plan.
            </p>
          </div>
          <button
            onClick={() => navigate('/guided/recommend')}
            className="rep-cta-btn"
            type="button"
          >
            <svg viewBox="0 0 24 24">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            Book discovery call
          </button>
        </div>
      </div>

      {/* Sticky Onboarding Guided Footer */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: '64px',
          background: '#06231a',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          zIndex: 100
        }}
      >
        <span style={{ color: '#a7c0b4', fontSize: '13px', fontWeight: 500, fontFamily: 'var(--body)' }}>
          This report is yours to keep.
        </span>
        <button
          className="btn btn-em"
          style={{
            background: '#10B981',
            color: '#06231a',
            fontWeight: 750,
            padding: '10px 18px',
            borderRadius: '8px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            fontFamily: 'var(--display)',
            fontSize: '13px',
            border: 'none',
            cursor: 'pointer'
          }}
          onClick={() => navigate('/guided/recommend')}
        >
          What GoXL recommends
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            style={{ width: 14, height: 14 }}
          >
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </div>
    </div>
  );
}
