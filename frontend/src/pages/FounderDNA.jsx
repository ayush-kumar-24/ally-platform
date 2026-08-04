import { useCallback, useEffect, useState } from 'react';
import { factList, loadDna } from '../services/reports';
import { DnaError, DnaLoading, DnaNoReport, DnaNoSection } from '../components/DnaState';

function FounderDNAView({ section, report }) {


  return (
    <div className="fd-container">
      {/* Dark Forest Hero Banner */}
      <div className="fd-hero stagger d1">
        <div className="fd-hero-content">
          <div className="fd-hero-kicker">Founder First - Your Archetype</div>
          <h2 className="fd-hero-title">
            {section?.heading || 'Your founder profile'}
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
        <h3 className="fd-section-title">Founder dimensions</h3>
        <span className="fd-section-meta">
          Derived from your diagnosis
        </span>
      </div>

      {/* Facts from the report. `facts` is an open object, so the keys are
          whatever this report produced -- rendered generically rather than
          assuming a fixed set of dimensions. */}
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
 * Founder DNA section" need different advice, and neither is an error. Previously
 * this page rendered a hardcoded archetype for everyone, which read as real.
 */
export default function FounderDNA() {
  const [state, setState] = useState({ status: 'loading' });

  const load = useCallback(() => {
    setState({ status: 'loading' });
    loadDna('founder').then(setState);
  }, []);

  useEffect(load, [load]);

  if (state.status === 'loading') return <DnaLoading label="Loading your Founder DNA…" />;
  if (state.status === 'no-report') return <DnaNoReport kind="Founder DNA" />;
  if (state.status === 'no-section') return <DnaNoSection kind="Founder" />;
  if (state.status === 'error') return <DnaError onRetry={load} />;

  return <FounderDNAView section={state.section} report={state.report} />;
}
