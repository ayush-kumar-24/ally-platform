import { useCallback, useEffect, useRef, useState } from 'react';
import { factList, loadDna, pillarList } from '../services/reports';
import { bandFill, bandTone, iconFor } from '../utils/dnaVisuals';
import ClampedText from '../components/ClampedText';
import { DnaError, DnaLoading, DnaNoReport, DnaNoSection } from '../components/DnaState';
import { useNavigate } from 'react-router-dom';

/* The six readiness_pillars (backend-canonical business dimensions). Scores and
   descriptions here are placeholder mock content; 4c wires them to the real
   business_dna snapshot (per-pillar band + description). */
function BusinessDNAView({ section, report }) {
  const navigate = useNavigate();
  const pillars = pillarList(section?.facts);
  // Whatever the section carries besides the pillars. Excluded by key so a
  // pillar is never rendered twice -- once as its own card and again as a
  // flattened "Retention · Strong · ..." string from the generic reader.
  // `overall_band` gets the hero, where the demo puts its headline figure, and
  // `red_flag_pillars` is dropped outright -- it is a list of names already
  // carrying their own "Needs attention" mark on the cards below, so as a card
  // of its own it says the same thing twice.
  const overallBand = section?.facts?.overall_band || null;
  const otherFacts = factList(section?.facts).filter(
    (f) => !['pillars', 'overall band', 'red flag pillars'].includes(f.label.toLowerCase()),
  );


  return (
    <div className="fd-container">
      {/* Dark Forest Hero Banner */}
      <div className="fd-hero stagger d1">
        <div className="fd-hero-content">
          <div className="fd-hero-kicker">Business DNA</div>
          <h2 className="fd-hero-title">
            {section?.heading || 'Your business profile'}
          </h2>
          {/* Clamped, not trimmed: the narrator now keeps this short at the
              source, but a founder's own words still arrive here and this page
              must not turn into a wall of text if one of them runs long. */}
          <ClampedText baseClass="fd-hero-desc" lines={3} text={section?.prose} />
        </div>
        {(overallBand || report?.report_id) && (
          <div className="fd-hero-score-wrap">
            {overallBand && <div className="fd-hero-band">{overallBand}</div>}
            <div className="fd-hero-label">
              {overallBand ? 'Overall' : `From report #${report.report_id}`}
            </div>
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

      {/* Pillars first, as their own structured cards: name, band, a bar
          coloured and filled from that band, and the band's written
          description. `facts` stays an open object, so anything that is NOT a
          pillar still falls through to the generic grid below rather than
          being dropped -- a report that predates pillars renders exactly as it
          did before. */}
      <div className="fd-grid stagger d3">
        {pillars.map((p) => (
          <div key={p.name} className={`fd-card ${bandTone(p.band)}`}>
            <div className="fd-card-top">
              <div className="fd-card-info">
                <div className="fd-card-icon">
                  <svg viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
                    {iconFor(p.name)}
                  </svg>
                </div>
                <div className="fd-card-title-wrap">
                  <h4 className="fd-card-title">{p.name}</h4>
                  {p.redFlag && <span className="fd-card-flag">Needs attention</span>}
                </div>
              </div>
              {/* The band word, not a number. The underlying score is
                  engine-internal and deliberately not published, so printing
                  one here would be inventing a precision the page was never
                  given. */}
              {p.band && <div className="fd-card-band">{p.band}</div>}
            </div>
            {p.band && (
              <div className="fd-progress-track">
                <div className="fd-progress-bar" style={{ width: `${bandFill(p.band)}%` }} />
              </div>
            )}
            {p.description && <ClampedText text={p.description} lines={4} />}
          </div>
        ))}
        {otherFacts.map((f) => (
          <div key={f.label} className="fd-card">
            <div className="fd-card-top">
              <div className="fd-card-info">
                <div className="fd-card-icon">
                  <svg viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
                    {iconFor(f.label)}
                  </svg>
                </div>
                <div className="fd-card-title-wrap">
                  <h4 className="fd-card-title">{f.label}</h4>
                </div>
              </div>
            </div>
            <ClampedText text={f.value} lines={4} />
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

  // Guards against two overlapping loads (React StrictMode's double-invoked
  // mount effect in dev, or any fast remount in production) landing their
  // setState calls out of order -- live-confirmed this let a superseded
  // call's late failure overwrite an already-successful render with an
  // error screen, even though the data had loaded fine. Only the most
  // recently started load is allowed to write state.
  const loadIdRef = useRef(0);

  const load = useCallback(() => {
    const id = ++loadIdRef.current;
    setState({ status: 'loading' });
    loadDna('business').then((result) => {
      if (id === loadIdRef.current) setState(result);
    });
  }, []);

  useEffect(load, [load]);

  if (state.status === 'loading') return <DnaLoading label="Loading your Business DNA…" />;
  if (state.status === 'no-report') return <DnaNoReport kind="Business DNA" />;
  if (state.status === 'no-section') return <DnaNoSection kind="Business" />;
  if (state.status === 'error') return <DnaError onRetry={load} />;

  return <BusinessDNAView section={state.section} report={state.report} />;
}
