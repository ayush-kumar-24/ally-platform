import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useReport } from '../hooks/useReport';
import { api } from '../lib/api';

/* The report is now driven entirely by the backend (/api/v1/reports/{id}). The
   engine owns every fact; this screen only lays out the sections + prose it
   returns. No raw scores are shown — business health and pillars render as
   bands. Sections the backend does not return (cut evidence/impact/roadmap, or
   the distress-suppressed CTA) simply do not render. */

const REPORT_ID = import.meta.env.VITE_DEV_REPORT_ID || 1;

// Band -> ring fill (visual only, no number shown) and card colour class.
const BAND_FILL = { 'Critical Gap': 22, 'Needs Attention': 45, Developing: 66, Strong: 86 };
const BAND_CLASS = {
  'Critical Gap': 'fd-cat-red',
  'Needs Attention': 'fd-cat-orange',
  Developing: 'fd-cat-orange',
  Strong: 'fd-cat-green',
};

const sectionOf = (data, key) => data?.sections?.find((s) => s.key === key);

export default function Report() {
  const navigate = useNavigate();
  const { data, loading, error } = useReport(REPORT_ID);
  const ringRef = useRef(null);
  const [busy, setBusy] = useState(null);

  const biz = sectionOf(data, 'business_dna');
  const overallBand = biz?.facts?.overall_band;

  useEffect(() => {
    if (ringRef.current && overallBand) {
      const fill = BAND_FILL[overallBand] ?? 60;
      const offset = Math.round(270 * (1 - fill / 100)); // r=43 -> circumference ~270
      setTimeout(() => {
        if (ringRef.current) ringRef.current.style.strokeDashoffset = String(offset);
      }, 350);
    }
  }, [overallBand]);

  if (loading) {
    return (
      <div className="fd-container">
        <p className="rep-summary-text stagger d1">Loading your clarity report…</p>
      </div>
    );
  }
  if (error) {
    return (
      <div className="fd-container">
        <p className="rep-summary-text stagger d1">
          We couldn’t load your report{error.status ? ` (${error.status})` : ''}. {error.message}
        </p>
      </div>
    );
  }
  if (!data) return null;

  const summary = sectionOf(data, 'founder_summary');
  const fdna = sectionOf(data, 'founder_dna');
  const arch = fdna?.facts?.archetype;
  const psych = sectionOf(data, 'psychological_note');
  const pillars = biz?.facts?.pillars || [];
  const problem = sectionOf(data, 'problem_path');
  const actions = sectionOf(data, 'priority_actions');
  const cta = sectionOf(data, 'discovery_cta');
  const confirm = actions?.facts?.confirm_actions || [];
  const solve = actions?.facts?.solve_actions || [];

  const download = async () => {
    try {
      setBusy('pdf');
      const blob = await api.reports.exportPdf(REPORT_ID);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `clarity-report-${REPORT_ID}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Download failed: ' + e.message);
    } finally {
      setBusy(null);
    }
  };

  const share = async () => {
    try {
      setBusy('share');
      const r = await api.reports.createShare(REPORT_ID);
      try {
        await navigator.clipboard.writeText(r.share_url);
      } catch {
        /* clipboard blocked — still show the link */
      }
      alert('Share link copied:\n' + r.share_url);
    } catch (e) {
      alert('Share failed: ' + e.message);
    } finally {
      setBusy(null);
    }
  };

  let n = 0;
  const num = () => String(++n).padStart(2, '0');

  const actionItems = [
    ...confirm.map((a) => ({ ...a, tag: 'Confirm first' })),
    ...solve.map((a) => ({ ...a, tag: 'Start solving' })),
  ].flatMap((a) => (a.next_actions || []).map((text) => ({ text, tag: a.tag })));

  return (
    <div className="fd-container">
      {/* Hero */}
      <div className="fd-hero stagger d1">
        <div className="fd-hero-content">
          <div className="fd-hero-kicker">Founder DNA Report</div>
          <h2 className="fd-hero-title">Your clarity report</h2>
          {summary?.prose && <p className="fd-hero-desc">{summary.prose}</p>}
          <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
            <button
              className="btn btn-em"
              style={{ padding: '9px 16px', borderRadius: 10, fontSize: 13 }}
              onClick={download}
              disabled={!!busy}
              type="button"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" style={{ width: 14, height: 14 }}>
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              {busy === 'pdf' ? 'Preparing…' : 'Download PDF'}
            </button>
            <button
              className="btn btn-dark-ghost"
              style={{ padding: '9px 16px', borderRadius: 10, fontSize: 13 }}
              onClick={share}
              disabled={!!busy}
              type="button"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" style={{ width: 14, height: 14 }}>
                <circle cx="18" cy="5" r="3" />
                <circle cx="6" cy="12" r="3" />
                <circle cx="18" cy="19" r="3" />
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
              </svg>
              {busy === 'share' ? 'Creating…' : 'Share'}
            </button>
          </div>
        </div>

        {overallBand && (
          <div className="rep-ring">
            <svg viewBox="0 0 100 100">
              <circle className="bg" cx="50" cy="50" r="43" />
              <circle ref={ringRef} className="fg" cx="50" cy="50" r="43" />
            </svg>
            <div className="rep-ring-c">
              <b style={{ fontSize: 14, lineHeight: 1.1, textAlign: 'center' }}>{overallBand}</b>
              <span>Business health</span>
            </div>
          </div>
        )}
      </div>

      {/* Founder summary */}
      {summary?.prose && (
        <>
          <div className="rep-sec-head stagger d2">
            <span className="num">{num()}</span>
            <h3 className="title">Founder summary</h3>
          </div>
          <p className="rep-summary-text stagger d2">{summary.prose}</p>
        </>
      )}

      {/* Founder DNA — from the archetype, not fixed dimension scores */}
      {fdna && (
        <>
          <div className="rep-sec-head stagger d3">
            <span className="num">{num()}</span>
            <h3 className="title">Founder DNA</h3>
          </div>
          {fdna.prose && <p className="rep-intro-text stagger d3">{fdna.prose}</p>}
          {arch?.name && (
            <div className="fd-card stagger d3" style={{ marginBottom: 32 }}>
              <div className="fd-card-top">
                <div className="fd-card-info">
                  <div className="fd-card-title-wrap">
                    <h4 className="fd-card-title">
                      {arch.name}
                      {arch.tentative ? ' · working hypothesis' : ''}
                    </h4>
                    {arch.core_motivation && (
                      <span className="fd-card-subtitle">Driven by {arch.core_motivation}</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Psychological state note (Section H) — only when the engine includes it */}
      {psych?.prose && (
        <>
          <div className="rep-sec-head stagger d3">
            <span className="num">{num()}</span>
            <h3 className="title">{psych.heading}</h3>
          </div>
          <p className="rep-intro-text stagger d3">{psych.prose}</p>
        </>
      )}

      {/* Business DNA — bands + descriptions, never raw scores */}
      {biz && (
        <>
          <div className="rep-sec-head stagger d4">
            <span className="num">{num()}</span>
            <h3 className="title">Business DNA</h3>
          </div>
          {biz.prose && <p className="rep-intro-text stagger d4">{biz.prose}</p>}
          <div className="fd-grid stagger d4" style={{ marginBottom: 32 }}>
            {pillars.map((p, i) => (
              <div key={i} className={`fd-card ${BAND_CLASS[p.band] || ''}`}>
                <div className="fd-card-top">
                  <div className="fd-card-info">
                    <div className="fd-card-title-wrap">
                      <h4 className="fd-card-title">{p.pillar_name}</h4>
                    </div>
                  </div>
                  <div className="fd-card-score" style={{ fontSize: 12, letterSpacing: '.01em' }}>
                    {p.band}
                  </div>
                </div>
                {p.band_description && <p className="fd-card-desc">{p.band_description}</p>}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Root cause */}
      {problem?.prose && (
        <>
          <div className="rep-sec-head stagger d5">
            <span className="num">{num()}</span>
            <h3 className="title">Root cause</h3>
          </div>
          <div className="rep-rc-banner stagger d5">
            <div className="rep-rc-kicker">Ally’s finding</div>
            <h4 className="rep-rc-text">{problem.prose}</h4>
          </div>
        </>
      )}

      {/* Priority actions — the actual confirm/solve steps */}
      {actionItems.length > 0 && (
        <>
          <div className="rep-sec-head stagger d6">
            <span className="num">{num()}</span>
            <h3 className="title">Priority actions</h3>
          </div>
          {actions?.prose && <p className="rep-intro-text stagger d6">{actions.prose}</p>}
          <div className="rep-act-list stagger d6">
            {actionItems.map((a, i) => (
              <div key={i} className="rep-act-card">
                <div className="rep-act-num">{i + 1}</div>
                <div className="rep-act-content">
                  <p className="rep-act-text">{a.text}</p>
                  <span className="rep-act-tag high">{a.tag}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Discovery CTA — the backend omits this under distress */}
      {cta?.prose && (
        <>
          <div className="rep-sec-head stagger d6">
            <span className="num">{num()}</span>
            <h3 className="title">{cta.heading}</h3>
          </div>
          <div className="rep-cta-card stagger d6">
            <div className="rep-cta-content">
              <h4 className="rep-cta-title">Turn this diagnosis into a plan.</h4>
              <p className="rep-cta-desc">{cta.prose}</p>
            </div>
            <button onClick={() => navigate('/app/billing')} className="rep-cta-btn" type="button">
              <svg viewBox="0 0 24 24">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              Book discovery call
            </button>
          </div>
        </>
      )}
    </div>
  );
}
