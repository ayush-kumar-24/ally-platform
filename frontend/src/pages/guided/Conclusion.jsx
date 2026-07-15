import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const LINES = [
  { b: 'I observed', t: ' — growth stays flat while spend keeps climbing.', c: 58 },
  { b: 'I ruled out', t: ' — pricing, positioning and sales effort. All healthy.', c: 66 },
  { b: 'The evidence that mattered', t: ' — a −38% drop from week one to week two, clustered at day 11.', c: 80 },
  { b: 'My confidence rose', t: ' — every thread converged on the same mechanism.', c: 88 },
  { b: 'The conclusion', t: ' — a first-value retention leak, not a reach problem.', c: 92 },
];

export default function Conclusion() {
  const navigate = useNavigate();
  const [activeCount, setActiveCount] = useState(0);
  const [confidence, setConfidence] = useState(0);
  const [showCta, setShowCta] = useState(false);

  useEffect(() => {
    let k = 0;
    const step = () => {
      if (k < LINES.length) {
        setActiveCount(k + 1);
        setConfidence(LINES[k].c);
        k++;
        setTimeout(step, 950);
      } else {
        setTimeout(() => {
          setShowCta(true);
        }, 450);
      }
    };

    const initialTimer = setTimeout(step, 220);
    return () => clearTimeout(initialTimer);
  }, []);

  return (
    <section className="view j-stage active">
      <div className="j-inner">
        <div className="reveal-ring">
          <div className="reveal-core">
            <svg viewBox="0 0 24 24">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </div>
        </div>
        <div className="j-eye">Ally is reaching a conclusion</div>
        <h1 className="j-title">Before I show you <em>here's how I got here.</em></h1>

        <ul className="reveal-log">
          {LINES.map((item, idx) => (
            <li key={idx} className={idx < activeCount ? 'on' : ''}>
              <span className="rl-dot" />
              <span>
                <b>{item.b}</b>{item.t}
              </span>
            </li>
          ))}
        </ul>

        <div className={`reveal-conf${activeCount > 0 ? ' on' : ''}`}>
          <span className="rc-l">Confidence</span>
          <div className="rc-b">
            <i style={{ width: `${confidence}%` }}></i>
          </div>
          <span className="rc-p">{confidence}%</span>
        </div>

        <div className="j-actions" style={{
          opacity: showCta ? 1 : 0,
          pointerEvents: showCta ? 'auto' : 'none',
          transition: 'opacity 0.5s ease-in-out',
          marginTop: '28px'
        }}>
          <button className="btn btn-em j-btn-lg" type="button" onClick={() => navigate('/guided/report')}>
            <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: 'currentColor', strokeWidth: 2.2, marginRight: '8px', display: 'inline-block', verticalAlign: 'middle' }}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>
            <span style={{ verticalAlign: 'middle' }}>Reveal my Founder Report</span>
          </button>
        </div>
      </div>
    </section>
  );
}
