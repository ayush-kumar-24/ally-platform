import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MOCK_DIMENSIONS } from '../data/mockData';

const HYPOS = [
  { label: 'Sales-founder mismatch', sub: 'Founder DNA · Revenue', verdict: 'keep', on: true },
  { label: 'SME churn structural gap', sub: 'Revenue · Team', verdict: 'keep', on: true },
  { label: 'Pricing strategy misalignment', sub: 'Strategy · Market', verdict: null, on: false },
  { label: 'Product velocity vs. market fit', sub: 'Product · Market', verdict: null, on: false },
];

const TIMELINE = [
  { label: 'Founder DNA mapped', done: true },
  { label: 'Business dimensions scanned (6/10)', done: true },
  { label: 'Root cause hypothesis formed', now: true },
  { label: 'Cross-referencing evidence', done: false },
  { label: 'Generating clarity report', done: false },
];

const SCANS = [
  { name: 'Revenue', status: 'ok', pct: 76 },
  { name: 'Product', status: 'ok', pct: 62 },
  { name: 'Team', status: 'busy', pct: 48 },
  { name: 'Operations', status: 'ok', pct: 70 },
  { name: 'Finance', status: 'busy', pct: 55 },
  { name: 'Market', status: 'ok', pct: 80 },
];

export default function Thinking() {
  const navigate = useNavigate();
  const [confidence, setConfidence] = useState(0);
  const confRef = useRef(null);
  const scanRefs = useRef([]);

  useEffect(() => {
    const t1 = setTimeout(() => setConfidence(73), 600);
    scanRefs.current.forEach((el, i) => {
      if (el) setTimeout(() => { el.style.width = `${SCANS[i].pct}%`; }, 400 + i * 150);
    });
    return () => clearTimeout(t1);
  }, []);

  return (
    <div className="think">
      <div className="pad" style={{ maxWidth: 1000 }}>
        <div className="think-head stagger d1">
          <div className="eye">
            <span className="live" />
            Ally is reasoning live
          </div>
          <h2>Building your clarity picture</h2>
          <p>I'm cross-referencing your founder DNA against 10 business dimensions to find the single root constraint.</p>
        </div>

        <div className="think-grid stagger d2">
          {/* Left: hypothesis stream */}
          <div>
            <div className="panel">
              <h3>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#34d399" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                Hypothesis Stream
              </h3>
              <div className="hypo">
                {HYPOS.map((h, i) => (
                  <div key={i} className={`hypo-item${h.on ? ' on' : ''}`}>
                    <div className="hypo-ic">{i + 1}</div>
                    <div>
                      <div className="h-t">{h.label}</div>
                      <div className="h-s">{h.sub}</div>
                      {h.verdict && <div className={`h-verdict ${h.verdict}`}>{h.verdict === 'keep' ? '✓ Retained' : '✗ Dropped'}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel" style={{ marginTop: 12 }}>
              <h3>Reasoning Timeline</h3>
              <div className="tl">
                {TIMELINE.map((t, i) => (
                  <div key={i} className={`tl-i${t.done ? ' done' : t.now ? ' now' : ''}`}>
                    <div className="tl-rail">
                      <div className="tl-dot" />
                      {i < TIMELINE.length - 1 && <div className="tl-line" />}
                    </div>
                    <div className="tl-t">{t.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right: dimension scans + confidence */}
          <div>
            <div className="panel">
              <h3>Dimension Scan</h3>
              <div className="scan">
                {SCANS.map((s, i) => (
                  <div key={i} className={`scan-c${s.status === 'busy' ? ' busy' : ' ok'}`}>
                    <div className="s-top">
                      <span className="s-n">{s.name}</span>
                      <span className={`s-st ${s.status}`}>{s.status === 'busy' ? 'scanning' : 'done'}</span>
                    </div>
                    <div className="s-bar"><i ref={el => scanRefs.current[i] = el} /></div>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel" style={{ marginTop: 12 }}>
              <h3>Confidence Evolution</h3>
              <div className="conf-evo">
                <div className="ce-big">{confidence}<span className="u">%</span></div>
                <div className="ce-track">
                  <div className="ce-fill" style={{ width: `${confidence}%`, transition: 'width 1.4s cubic-bezier(.22,1,.3,1)' }} />
                </div>
                <div className="ce-note">Based on {SCANS.filter(s => s.status === 'ok').length} scanned dimensions · 2 still processing</div>
              </div>
            </div>

            <div className="think-cta">
              <button className="btn btn-em" onClick={() => navigate('/app/report')} style={{ marginRight: 10 }}>
                View Report →
              </button>
              <button className="btn btn-dark-ghost" onClick={() => navigate('/app/diagnosis')}>
                Continue Diagnosis
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
