import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const HYPOTHESES = [
  { id: 'H1', title: 'Growth is capped by acquisition cost', meta: 'Tested against CAC + spend', state: 'Ruled out' },
  { id: 'H2', title: 'Pricing is deterring conversion', meta: 'Compared to market + win rates', state: 'Ruled out' },
  { id: 'H3', title: 'Users churn before first value', meta: 'Week-two cohort drop-off', state: 'Strong signal' },
  { id: 'H4', title: 'Founder attention skews top-of-funnel', meta: 'Execution-behaviour pattern', state: 'Confirmed' },
];

const DIMENSIONS = [
  { label: 'Growth & acquisition', value: 100, status: 'Done' },
  { label: 'Retention & lifecycle', value: 72, status: 'Scanning...' },
  { label: 'Pricing & positioning', value: 100, status: 'Done' },
  { label: 'Sales & pipeline', value: 100, status: 'Done' },
  { label: 'Product & onboarding', value: 68, status: 'Scanning...' },
  { label: 'Founder behaviour', value: 100, status: 'Done' },
  { label: 'Team & ownership', value: 0, status: 'Queued' },
  { label: 'Cash & runway', value: 0, status: 'Queued' },
];

const TIMELINE = [
  'Listened to founder context, mindset and decision style',
  'Mapped symptoms: flat growth despite rising spend',
  'Ruled out pricing, positioning and sales effort',
  'Tracing retention - analysing first-value moment',
  'Confirm root cause and generate priority actions',
];

export default function RootCause() {
  const navigate = useNavigate();
  const rootBarRef = useRef(null);
  const confBarRef = useRef(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const t1 = setTimeout(() => setActive(1), 350);
    const t2 = setTimeout(() => setActive(2), 750);
    const t3 = setTimeout(() => setActive(3), 1100);
    if (rootBarRef.current) setTimeout(() => { if (rootBarRef.current) rootBarRef.current.style.width = '92%'; }, 500);
    if (confBarRef.current) setTimeout(() => { if (confBarRef.current) confBarRef.current.style.width = '74%'; }, 350);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, []);

  return (
    <section className="view think active">
      <div className="pad">
        <div className="think-head">
          <span className="eye">
            <span className="live" />
            Ally is thinking
          </span>
          <h2>Watch Ally find the real cause.</h2>
          <p>This isn't a loading screen. Ally is connecting everything you shared to find the one real cause.</p>
        </div>

        <div className="think-grid">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="panel">
              <h3>
                <svg width="15" height="15" viewBox="0 0 24 24" style={{ stroke: 'var(--emerald-bright)', fill: 'none', strokeWidth: 2 }}>
                  <path d="M9 18h6M10 22h4M12 2a7 7 0 0 0-4 12c1 1 1 2 1 3h6c0-1 0-2 1-3a7 7 0 0 0-3-12Z" />
                </svg>
                Hypothesis generation
              </h3>
              <div className="hypo">
                {HYPOTHESES.map((item, i) => (
                  <div key={item.id} className={`hypo-item ${i <= active ? 'on' : ''}`}>
                    <div className="hypo-ic">{item.id}</div>
                    <div style={{ flex: 1 }}>
                      <div className="h-t">{item.title}</div>
                      <div className="h-s">{item.meta}</div>
                    </div>
                    <div className="h-verdict" style={{ color: item.state === 'Confirmed' ? 'var(--emerald-bright)' : 'var(--on-dark-dim)' }}>{item.state}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel">
              <h3>
                <svg width="15" height="15" viewBox="0 0 24 24" style={{ stroke: 'var(--emerald-bright)', fill: 'none', strokeWidth: 2 }}>
                  <path d="M3 3v18h18" />
                  <path d="m19 9-5 5-4-4-3 3" />
                </svg>
                Business dimension mapping
              </h3>
              <div className="scan">
                {DIMENSIONS.map((item) => {
                  let statusClass = 'wait';
                  if (item.status === 'Scanning...') statusClass = 'busy';
                  else if (item.status === 'Done') statusClass = 'ok';
                  return (
                    <div key={item.label} className={`scan-c ${statusClass}`}>
                      <div className="s-top">
                        <div className="s-n">{item.label}</div>
                        <span className={`s-st ${statusClass}`}>{item.status}</span>
                      </div>
                      <div className="s-bar">
                        <i style={{ width: `${item.value}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="panel">
              <h3>
                <svg width="15" height="15" viewBox="0 0 24 24" style={{ stroke: 'var(--emerald-bright)', fill: 'none', strokeWidth: 2 }}>
                  <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
                  <circle cx="12" cy="12" r="4" />
                </svg>
                Confidence evolution
              </h3>
              <div className="conf-evo">
                <div className="ce-big">
                  74<span className="u">%</span>
                </div>
                <div className="ce-track">
                  <div ref={confBarRef} className="ce-fill" />
                </div>
                <div className="ce-note">Growing as evidence accumulates…</div>
              </div>
            </div>

            <div className="panel">
              <h3>
                <svg width="15" height="15" viewBox="0 0 24 24" style={{ stroke: 'var(--emerald-bright)', fill: 'none', strokeWidth: 2 }}>
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 7v5l3 2" />
                </svg>
                Reasoning timeline
              </h3>
              <div className="tl">
                {TIMELINE.map((item, i) => (
                  <div key={item} className={`tl-i ${i < active ? 'done' : i === active ? 'now' : ''}`}>
                    <div className="tl-rail">
                      <div className="tl-dot" />
                      <div className="tl-line" />
                    </div>
                    <div className="tl-t">{item}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="think-cta">
          <button className="btn btn-em" type="button" onClick={() => navigate('/guided/conclusion')}>
            <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>
            Ally has reached a conclusion — open the report
          </button>
        </div>
      </div>
    </section>
  );
}
