import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { factList, loadDna } from '../services/reports';
import { DnaError, DnaLoading, DnaNoReport, DnaNoSection } from '../components/DnaState';
import { IconArrowRight, IconChat } from '../utils/icons';
import { accentFor, iconFor } from '../utils/dnaVisuals';
import ClampedText from '../components/ClampedText';

const TABS = [
  { key: 'operate', label: 'How you operate' },
  { key: 'motivation', label: 'Motivation & archetype' },
  { key: 'vision', label: 'Your vision' },
];

/**
 * `archetype` is pulled out of the generic fact grid and given its own
 * treatment -- it's a nested object (name, core_motivation, fit_score,
 * matched_terms), and factList()'s generic flattener joins those into one
 * unlabeled string ("Operator · Building something lasting · 0.62 · ...").
 * `fit_score` here is real: ArchetypeEngine's own lexical-match confidence
 * (backend/app/api/v1/reasoning/engines/archetype.py), not a fabricated
 * number -- shown only when the engine itself called the match confident.
 */
function ArchetypeCard({ archetype }) {
  if (!archetype?.archetype_name) return null;
  const pct = typeof archetype.fit_score === 'number' ? Math.round(archetype.fit_score * 100) : null;
  return (
    <div className="fd-card fd-cat-green" style={{ gridColumn: '1 / -1' }}>
      <div className="fd-card-top">
        <div className="fd-card-info">
          <div className="fd-card-title-wrap">
            <h4 className="fd-card-title">{archetype.archetype_name}</h4>
          </div>
        </div>
      </div>
      {archetype.core_motivation && <p className="fd-card-desc">{archetype.core_motivation}</p>}
      {archetype.is_confident && pct != null && (
        <>
          <div className="fd-progress-track"><div className="fd-progress-bar" style={{ width: `${pct}%` }} /></div>
          <p className="fd-card-subtitle">{pct}% match, from your own words in the diagnosis</p>
        </>
      )}
      {Array.isArray(archetype.matched_terms) && archetype.matched_terms.length > 0 && (
        <p className="fd-card-subtitle">Matched on: {archetype.matched_terms.join(', ')}</p>
      )}
    </div>
  );
}

/** Origin/vision are the founder's own words (onboarding text or a considered
 *  asked answer -- see founder_dna_extras.py's docstring), shown close to
 *  verbatim rather than paraphrased. */
function StoryQuote({ label, text }) {
  if (!text) return null;
  return (
    <div className="fd-card" style={{ gridColumn: '1 / -1' }}>
      <div className="fd-card-title-wrap"><h4 className="fd-card-title">{label}</h4></div>
      <p className="fd-card-desc" style={{ fontStyle: 'italic' }}>&ldquo;{text}&rdquo;</p>
    </div>
  );
}

function FounderDNAView({ section, report }) {
  const navigate = useNavigate();
  const [tab, setTab] = useState('operate');

  const facts = section?.facts || {};
  const archetype = facts.archetype;
  const originText = facts.origin || facts._origin_text;
  const visionText = facts.vision || facts._vision_text;

  // Everything else, generically -- factList() already drops archetype's own
  // internal keys are inside the nested object so they never leak here, and
  // excludes origin/vision/_origin_text/_vision_text explicitly since those
  // get their own dedicated cards instead of the generic grid.
  const operateFacts = factList(facts).filter(
    (f) => !['Archetype', 'Origin', 'Vision', ' origin text', ' vision text']
      .some((k) => f.label.toLowerCase() === k.toLowerCase().trim())
  );

  return (
    <div className="fd-container">
      <div className="fd-hero stagger d1">
        <div className="fd-hero-content">
          <div className="fd-hero-kicker">Founder First · Your Profile</div>
          <h2 className="fd-hero-title">{section?.heading || 'Your founder profile'}</h2>
          {/* Clamped, not trimmed: the narrator now keeps this short at the
              source, but a founder's own words still arrive here and this page
              must not turn into a wall of text if one of them runs long. */}
          <ClampedText baseClass="fd-hero-desc" lines={3} text={section?.prose} />
        </div>
        {report?.report_id && (
          <div className="fd-hero-score-wrap">
            <div className="fd-hero-label">From report #{report.report_id}</div>
          </div>
        )}
      </div>

      <div className="tabs" role="tablist" aria-label="Founder DNA sections" style={{ marginTop: 28 }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className="tab"
            role="tab"
            type="button"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'operate' && (
        <>
          <div className="fd-section-head stagger d2">
            <h3 className="fd-section-title">How you operate</h3>
            <span className="fd-section-meta">Derived from your diagnosis</span>
          </div>
          {operateFacts.length === 0 ? (
            <p className="fd-card-desc">Your latest report didn't produce any operating-pattern facts.</p>
          ) : (
            <div className="fd-grid stagger d3">
              {/* Icon and accent, but deliberately NO bar and no number. There
                  is no score and no band behind a founder dimension -- the
                  engine stores the founder's own answers as text and nothing
                  else -- so a bar here would be drawing a grade for someone's
                  psychology out of thin air. Colour separates one dimension
                  from the next; it does not rate them. */}
              {operateFacts.map((f, i) => (
                <div key={f.label} className={`fd-card ${accentFor(i)}`}>
                  <div className="fd-card-top">
                    <div className="fd-card-info">
                      <div className="fd-card-icon">
                        <svg viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
                          {iconFor(f.label)}
                        </svg>
                      </div>
                      <div className="fd-card-title-wrap"><h4 className="fd-card-title">{f.label}</h4></div>
                    </div>
                  </div>
                  {/* These are the founder's own answers, verbatim and of wildly
                      uneven length -- two words in one dimension, three hundred
                      in the next. Clamped so the grid stays readable, with the
                      whole answer one click away; nothing is cut in storage. */}
                  <ClampedText text={f.value} lines={4} />
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'motivation' && (
        <>
          <div className="fd-section-head stagger d2">
            <h3 className="fd-section-title">Motivation & archetype</h3>
            <span className="fd-section-meta">A best-fit read of your own words, not a fixed label</span>
          </div>
          {archetype?.archetype_name ? (
            <div className="fd-grid stagger d3">
              <ArchetypeCard archetype={archetype} />
            </div>
          ) : (
            <p className="fd-card-desc">Your latest report didn't produce an archetype match.</p>
          )}
          <div className="btn-row" style={{ marginTop: 22 }}>
            <button type="button" className="btn btn-em" onClick={() => navigate('/app/ally-chat', {
              state: { prefill: 'I want to talk through what actually drives me as a founder.' },
            })}>
              <IconChat /> Discuss with Ally
            </button>
          </div>
        </>
      )}

      {tab === 'vision' && (
        <>
          <div className="fd-section-head stagger d2">
            <h3 className="fd-section-title">Your vision</h3>
            <span className="fd-section-meta">Your own words, and your own written vision</span>
          </div>
          <div className="fd-grid stagger d3">
            <StoryQuote label="Where this started" text={originText} />
            <StoryQuote label="What you're building toward" text={visionText} />
          </div>
          {/* Vision territories/summary already have their own dedicated,
              editable page -- linking there instead of duplicating that data
              in a second, read-only view here. */}
          <div className="btn-row" style={{ marginTop: 22 }}>
            <button type="button" className="btn btn-em" onClick={() => navigate('/app/vision')}>
              Open Your Vision <IconArrowRight />
            </button>
          </div>
        </>
      )}
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
    loadDna('founder').then((result) => {
      if (id === loadIdRef.current) setState(result);
    });
  }, []);

  useEffect(load, [load]);

  if (state.status === 'loading') return <DnaLoading label="Loading your Founder DNA…" />;
  if (state.status === 'no-report') return <DnaNoReport kind="Founder DNA" />;
  if (state.status === 'no-section') return <DnaNoSection kind="Founder" />;
  if (state.status === 'error') return <DnaError onRetry={load} />;

  return <FounderDNAView section={state.section} report={state.report} />;
}
