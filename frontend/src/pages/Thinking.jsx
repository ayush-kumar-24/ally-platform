import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getBusinessPillars } from '../services/reference';
import { getLatestReport } from '../services/reports';

/* "(6/10)" was a fixed string shown to every founder regardless of how much had
   actually been scanned, as was the "Root cause hypothesis formed" step. The
   backend does not report per-step progress during this wait, so the labels no
   longer quote counts they cannot know. */
const TIMELINE = [
  { label: 'Founder DNA mapped', done: true },
  { label: 'Business dimensions scanned', done: true },
  { label: 'Forming a root-cause hypothesis', now: true },
  { label: 'Cross-referencing evidence', done: false },
  { label: 'Generating clarity report', done: false },
];


export default function Thinking() {
  // Pillar names come from reference data so this screen names the same
  // dimensions the diagnosis actually scans.
  const [dimensions, setDimensions] = useState([]);
  const [waited, setWaited] = useState(0);

  /* This mapped each pillar down to a bare string, but the markup below reads
     `s.name` and `s.status` off each item — so every row rendered an empty name
     and a status pill permanently reading "done". Keep the shape the markup
     expects, and tolerate the API returning plain strings. */
  useEffect(() => {
    let cancelled = false;
    getBusinessPillars()
      .then(res => {
        if (cancelled) return;
        setDimensions((res.pillars ?? res.items ?? []).map(p => (
          typeof p === 'string'
            ? { name: p, status: null }
            : { name: p.name ?? p.label ?? '', status: p.status ?? null }
        )));
      })
      .catch(() => { if (!cancelled) setDimensions([]); });
    return () => { cancelled = true; };
  }, []);

  const navigate = useNavigate();
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

  const scanRefs = useRef([]);

  useEffect(() => {
    // Indeterminate progress: the real work happens server-side and does not
    // report a percentage, so showing a specific number would be theatre.
    // Timers are collected and cleared — this effect re-runs whenever the
    // dimension count changes, and previously left one orphan per row behind.
    const timers = scanRefs.current.map((el, i) => (
      el ? setTimeout(() => { el.style.width = '100%'; }, 400 + i * 150) : null
    ));
    return () => timers.forEach(t => t && clearTimeout(t));
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
                      {/* Only claim a state the server actually reported. This
                          used to print "done" next to every dimension whether or
                          not anything had been scanned. */}
                      {s.status && (
                        <span className={`s-st ${s.status}`}>{s.status === 'busy' ? 'scanning' : 'done'}</span>
                      )}
                    </div>
                    <div className="s-bar"><i ref={el => scanRefs.current[i] = el} /></div>
                  </div>
                ))}
              </div>
            </div>

            {/* "Confidence Evolution" showed a hard 0% and a "2 still
                processing" count that were both fixed strings — setConfidence
                was never called and nothing tracked per-dimension progress. The
                server does not expose a confidence figure during the wait, so
                this now says it is working rather than quoting a number it does
                not have. */}
            <div className="panel" style={{ marginTop: 12 }}>
              <h3>Reasoning depth</h3>
              <div className="conf-evo">
                <div className="ce-track">
                  <div className="ce-fill ce-indeterminate" />
                </div>
                <div className="ce-note">
                  {dimensions.length
                    ? `Weighing ${dimensions.length} business dimensions against your founder profile.`
                    : 'Weighing your business dimensions against your founder profile.'}
                </div>
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
