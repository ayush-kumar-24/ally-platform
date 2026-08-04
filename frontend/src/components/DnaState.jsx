/**
 * Shared states for the DNA pages.
 *
 * Kept in one place so Founder DNA and Business DNA say the same thing in the same
 * situation. The four states exist because each needs different copy and a
 * different next action — "run a diagnosis" is wrong advice for someone who
 * already has a report.
 */

import { Link } from 'react-router-dom';

export function DnaLoading({ label = 'Loading your DNA…' }) {
  return (
    <div className="fd-container">
      <div className="fd-state" role="status" aria-live="polite"
           style={{ textAlign: 'center', padding: '64px 24px', color: 'var(--muted, #556458)' }}>
        {label}
      </div>
    </div>
  );
}

function Panel({ emoji, title, message, action }) {
  return (
    <div className="fd-container">
      <div className="fd-state" style={{
        maxWidth: 560, margin: '56px auto', padding: '34px 28px', textAlign: 'center',
        background: 'var(--ivory-2, #fbf7f2)', border: '1px solid var(--bd, #e7e0d6)',
        borderRadius: 14,
      }}>
        <div style={{ fontSize: 30, marginBottom: 12 }} aria-hidden="true">{emoji}</div>
        <h2 style={{ margin: '0 0 10px', fontSize: 20, color: 'var(--ink, #16241c)' }}>{title}</h2>
        <p style={{
          margin: '0 auto 20px', maxWidth: 440, fontSize: 14, lineHeight: 1.65,
          color: 'var(--muted, #556458)',
        }}>{message}</p>
        {action}
      </div>
    </div>
  );
}

const primaryLink = {
  display: 'inline-block', padding: '11px 20px', borderRadius: 9,
  background: 'var(--emerald, #10B981)', color: '#fff', fontWeight: 700,
  textDecoration: 'none', fontSize: 14,
};

/**
 * No diagnosis has been completed — the only state where "start one" is right.
 *
 * `kind` is the FULL noun phrase, not a prefix. It used to have "DNA" appended
 * here, which read correctly for the two DNA pages and produced "Your Report DNA"
 * and "Your Next steps DNA" on the other two.
 */
export function DnaNoReport({ kind = 'Founder DNA' }) {
  return (
    <Panel
      emoji="🧬"
      title={`Your ${kind} isn't ready yet`}
      message={`It comes out of a diagnosis — Ally reads the person and the
        business behind your answers. Run the diagnosis and this page
        fills in with your own profile.`}
      action={<Link to="/app/diagnosis" style={primaryLink}>Start Founder Diagnosis</Link>}
    />
  );
}

/** A report exists but this section wasn't generated. Different problem, different fix. */
export function DnaNoSection({ kind = 'Founder' }) {
  return (
    <Panel
      emoji="📄"
      title={`This report has no ${kind} DNA section`}
      message={`Your diagnosis completed, but this particular section wasn't
        generated for it. Your full report is still available.`}
      action={<Link to="/app/report" style={primaryLink}>View your report</Link>}
    />
  );
}

export function DnaError({ onRetry }) {
  return (
    <Panel
      emoji="⚠️"
      title="Couldn't load your DNA"
      message="Something went wrong fetching this. Your data is safe — this is a display problem."
      action={onRetry
        ? <button type="button" onClick={onRetry} style={{ ...primaryLink, border: 0, cursor: 'pointer' }}>
            Try again
          </button>
        : null}
    />
  );
}
