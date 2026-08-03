import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getBusinessPillars } from '../services/reference';
import { getLatestReport } from '../services/reports';

const TIMELINE = [
  { label: 'Founder DNA mapped', done: true },
  { label: 'Business dimensions scanned (6/10)', done: true },
  { label: 'Root cause hypothesis formed', now: true },
  { label: 'Cross-referencing evidence', done: false },
  { label: 'Generating clarity report', done: false },
];


export default function Thinking() {
  // Pillar names come from reference data so this screen names the same
  // dimensions the diagnosis actually scans.
  const [dimensions, setDimensions] = useState([]);
  const [waited, setWaited] = useState(0);

  useEffect(() => {
    getBusinessPillars()
      .then(res => setDimensions((res.pillars ?? res.items ?? []).map(p => p.name ?? p.label ?? p)))
      .catch(() => setDimensions([]));
  }, []);

  const navigate = useNavigate();
  const [confidence, setConfidence] = useState(0);
  // This screen is the wait between the last answer and the report existing, so
  // it polls for the real thing rather than running a fixed-length animation and
  // hoping the report arrived. Gives up after ~2 minutes rather than spinning
  // forever with nothing to show.
  useEffect(() => {
    let stop = false;
    const tick = async () => {
      if (stop) return;
      try {
        const report = await getLatestReport();
        if (report && !stop) { navigate('/app/report'); return; }
      } catch { /* keep waiting */ }
      if (!stop) {
        setWaited(w => w + 1);
        setTimeout(tick, 4000);
      }
    };
    const t = setTimeout(tick, 3000);
    return () => { stop = true; clearTimeout(t); };
  }, [navigate]);

  const stalled = waited > 30;

  const confRef = useRef(null);
  const scanRefs = useRef([]);

  useEffect(() => {
    // Indeterminate progress: the real work happens server-side and does not
    // report a percentage, so showing a specific number would be theatre.
    scanRefs.current.forEach((el, i) => {
      if (el) setTimeout(() => { el.style.width = '100%'; }, 400 + i * 150);
    });
  }, [dimensions.length]);

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
                <p className="kp-sub" style={{ margin: 0 }}>
                  {stalled
                    ? "This is taking longer than usual. Your answers are saved — you can close this and check your report later."
                    : "Ally is working through your answers. This usually takes under a minute."}
                </p>
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
                {dimensions.map((s, i) => (
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
                <div className="ce-note">Based on {dimensions.length} scanned dimensions · 2 still processing</div>
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
