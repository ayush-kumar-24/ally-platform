import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { factList, getLatestReport, getReport } from '../services/reports';
import { DnaError, DnaLoading, DnaNoReport } from '../components/DnaState';

function ReportView({ report, meta }) {
  const navigate = useNavigate();

  const sections = report?.sections ?? [];
  const unpopulated = report?.unpopulated_sections ?? [];
  const generated = report?.generated_at ? new Date(report.generated_at) : null;

  return (
    <div className="fd-container">
      {/* Hero */}
      <div className="fd-hero stagger d1">
        <div className="fd-hero-content">
          <div className="fd-hero-kicker">
            Founder Report{generated ? ` · ${generated.toLocaleDateString('en-IN',
              { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}
          </div>
          <h2 className="fd-hero-title">{meta?.title || 'Your diagnosis report'}</h2>
          {meta?.summary && <p className="fd-hero-desc">{meta.summary}</p>}
        </div>
        <div className="fd-hero-score-wrap">
          <div className="fd-hero-label">Report #{report?.report_id}</div>
        </div>
      </div>

      {/* Narrative sections, exactly as the generator produced them. The set and
          order vary by report variant, so nothing here assumes a fixed shape. */}
      {sections.map((sec) => (
        <section key={sec.key} className="fd-report-section stagger d2"
                 style={{ marginTop: 26 }}>
          <div className="fd-section-head">
            <h3 className="fd-section-title">{sec.heading}</h3>
          </div>
          {sec.prose && (
            <p className="fd-card-desc" style={{ whiteSpace: 'pre-line', lineHeight: 1.7 }}>
              {sec.prose}
            </p>
          )}
          {factList(sec.facts).length > 0 && (
            <div className="fd-grid" style={{ marginTop: 14 }}>
              {factList(sec.facts).map((f) => (
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
          )}
        </section>
      ))}

      {/* Named honestly rather than omitted: a founder should know a section
          exists but wasn't generated for their report. */}
      {unpopulated.length > 0 && (
        <p className="fd-section-meta" style={{ marginTop: 22, opacity: 0.75 }}>
          Not generated for this report: {unpopulated.join(', ').replace(/_/g, ' ')}.
        </p>
      )}

      <div style={{ marginTop: 30, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button className="btn btn-em" type="button" onClick={() => navigate('/app/next-steps')}>
          See your next steps
        </button>
        <button className="btn btn-ghost" type="button" onClick={() => navigate('/app/ally-chat')}>
          Discuss this with Ally
        </button>
      </div>
    </div>
  );
}


/**
 * Renders the founder's real report.
 *
 * The narrative is generated server-side (headings, prose and facts per section),
 * so this page displays what the generator produced rather than assuming a fixed
 * set of sections — a report for a distressed founder has a different shape from
 * a standard one, and hardcoding either would misrepresent the other.
 */
export default function Report() {
  const [state, setState] = useState({ status: 'loading' });

  const load = useCallback(() => {
    setState({ status: 'loading' });
    getLatestReport()
      .then(async (latest) => {
        if (!latest) return setState({ status: 'no-report' });
        const full = await getReport(latest.report_id);
        setState({ status: 'ready', report: full, meta: latest });
      })
      .catch((error) => setState({ status: 'error', error }));
  }, []);

  useEffect(load, [load]);

  if (state.status === 'loading') return <DnaLoading label="Loading your report…" />;
  if (state.status === 'no-report') return <DnaNoReport kind="report" />;
  if (state.status === 'error') return <DnaError onRetry={load} />;

  return <ReportView report={state.report} meta={state.meta} />;
}
