import { useCallback, useEffect, useState } from 'react';
import { factList, loadDna } from '../services/reports';
import { DnaError, DnaLoading, DnaNoReport, DnaNoSection } from '../components/DnaState';
import { useNavigate } from 'react-router-dom';

/* The six readiness_pillars (backend-canonical business dimensions). Scores and
   descriptions here are placeholder mock content; 4c wires them to the real
   business_dna snapshot (per-pillar band + description). */
function BusinessDNAView({ section, report }) {
  const navigate = useNavigate();


  return (
    <div className="fd-container">
      {/* Dark Forest Hero Banner */}
      <div className="fd-hero stagger d1">
        <div className="fd-hero-content">
          <div className="fd-hero-kicker">Business DNA</div>
          <h2 className="fd-hero-title">
            {section?.heading || 'Your business profile'}
          </h2>
          <p className="fd-hero-desc">{section?.prose}</p>
        </div>
        {report?.report_id && (
          <div className="fd-hero-score-wrap">
            <div className="fd-hero-label">From report #{report.report_id}</div>
          </div>
        )}
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

      {/* `facts` is an open object -- rendered generically rather than assuming
          a fixed set of ten dimensions that this report may not contain. */}
      <div className="fd-grid stagger d3">
        {factList(section?.facts).map((f) => (
          <div key={f.label} className="fd-card">
            <div className="fd-card-top">
              <div className="fd-card-info">
                <div className="fd-card-title-wrap">
                  <h4 className="fd-card-title">{f.label}</h4>
                </div>
              </div>
            </div>
            <p className="fd-card-desc">{f.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}


/**
 * Resolves the founder's latest report before rendering.
 *
 * The four states are distinct on purpose: "no diagnosis yet" and "report has no
 * Business DNA section" need different advice, and neither is an error. Previously
 * this page rendered a hardcoded archetype for everyone, which read as real.
 */
export default function BusinessDNA() {
  const [state, setState] = useState({ status: 'loading' });

  const load = useCallback(() => {
    setState({ status: 'loading' });
    loadDna('business').then(setState);
  }, []);

  useEffect(load, [load]);

  if (state.status === 'loading') return <DnaLoading label="Loading your Business DNA…" />;
  if (state.status === 'no-report') return <DnaNoReport kind="Business DNA" />;
  if (state.status === 'no-section') return <DnaNoSection kind="Business" />;
  if (state.status === 'error') return <DnaError onRetry={load} />;

  return <BusinessDNAView section={state.section} report={state.report} />;
}
