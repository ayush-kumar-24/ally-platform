import React from 'react';
import { reportError } from '../services/errorReporting';
import { isChunkLoadError } from '../utils/loadChunk';

/* ─────────────────────────────────────────────
   ErrorBoundary
   Class component — required by React for
   catching rendering errors in the subtree.

   Two very different things land here, and they
   used to be shown identically:

   1. A real crash — a bug, and the founder can
      do nothing but leave.
   2. A STALE BUILD. The app is code-split, so a
      tab opened before a deploy is still asking
      for chunk file names that no longer exist
      (see utils/loadChunk.js). Nothing is broken
      and a reload fixes it completely.

   (2) is common — onboarding is a ~20-minute
   single-tab session, so it is the tab most
   likely to be open when a deploy lands — and
   showing it "Something went wrong" reads as
   "this product is broken" to the one founder
   who was mid-sign-up. It is an update, so it
   now says so, and leads with Reload.
───────────────────────────────────────────── */

/**
 * A DOM that no longer matches the tree React thinks it rendered.
 *
 * React only ever removes a node it put there itself, so "the node to be
 * removed is not a child of this node" means something OUTSIDE React moved or
 * deleted it first. In practice that is the browser or an extension rewriting
 * the page underneath us: Chrome's page translation (it replaces each text
 * node with a <font> wrapper), an AI assistant or writing-tool toolbar, a
 * password manager injecting into a form. Audited 2026-09-18: nothing in this
 * app mutates the DOM inside #root -- every appendChild/removeChild we make is
 * on document.body or document.head, outside React's tree -- and there is only
 * one createRoot.
 *
 * It is worth telling apart because it is NOT a bug in the page the founder is
 * on, and because it explains a symptom that otherwise looks impossible: the
 * failed removal leaves the old DOM orphaned on screen, so the founder sees the
 * previous screen still sitting there with this card rendered BELOW it.
 * Reloading resolves it every time -- the fresh tree and the DOM start in step
 * again.
 */
function isDomSyncError(error) {
  const message = String(error?.message || error || '');
  return (
    error?.name === 'NotFoundError'
    && /removeChild|insertBefore|replaceChild/i.test(message)
  ) || /not a child of this node/i.test(message);
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    console.error('[ErrorBoundary] Caught rendering error:', error, errorInfo);
    /* Reported under its own source so a redeploy's stale chunks never sit in
       the same bucket as real crashes. They need opposite responses: a spike
       of 'chunk_load' is "a deploy caught people mid-flow", a spike of
       'error_boundary' is "we shipped a bug". */
    reportError(error, {
      source: isChunkLoadError(error) ? 'chunk_load'
        : isDomSyncError(error) ? 'dom_sync'
        : 'error_boundary',
      componentStack: errorInfo?.componentStack,
    });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    });
    // Navigate to a safe location if a fallbackPath is provided
    if (this.props.onReset) {
      this.props.onReset();
    } else {
      window.location.href = this.props.fallbackPath || '/';
    }
  };

  toggleDetails = () => {
    this.setState((prev) => ({ showDetails: !prev.showDetails }));
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const { error, errorInfo, showDetails } = this.state;
    const { label = 'This section' } = this.props;
    const staleBuild = isChunkLoadError(error);
    // Not a fault in this page -- something outside React rewrote the DOM.
    // Reload is the fix, so it leads, exactly as it does for a stale build.
    const domSync = !staleBuild && isDomSyncError(error);
    const reloadLeads = staleBuild || domSync;

    const reload = () => window.location.reload();
    // The reload is the fix for a stale build, so it leads. For a real crash
    // it rarely helps, so getting out of the broken screen leads instead.
    const primary = reloadLeads
      ? { id: 'eb-reload-btn', text: 'Reload Page', onClick: reload }
      : { id: 'eb-go-home-btn', text: 'Go Back to Safety', onClick: this.handleReset };
    const secondary = reloadLeads
      ? { id: 'eb-go-home-btn', text: 'Go Back to Safety', onClick: this.handleReset }
      : { id: 'eb-reload-btn', text: 'Reload Page', onClick: reload };

    return (
      <div style={styles.overlay}>
        {/* Ambient background orbs */}
        <div style={styles.orb1} />
        <div style={styles.orb2} />

        <div style={styles.card}>
          {/* Icon. A hazard triangle is the wrong word for an update -- it is
              the first thing read, and it says "broken" before the heading
              gets a chance to say otherwise. A refresh arrow for that case. */}
          <div style={styles.iconWrap}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#10B981' }}>
              {reloadLeads ? (
                <>
                  <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                  <polyline points="21 3 21 9 15 9" />
                </>
              ) : (
                <>
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </>
              )}
            </svg>
          </div>

          {/* Heading */}
          <h1 style={styles.heading}>
            {staleBuild ? 'A new version is ready'
              : domSync ? 'This page needs a refresh'
              : 'Something went wrong'}
          </h1>
          <p style={styles.subtext}>
            {domSync ? (
              <>
                Something outside {label} changed this page while it was updating — usually a
                browser extension or a page translation. Nothing is broken and nothing is lost;
                reloading puts it right.
              </>
            ) : staleBuild ? (
              <>
                We released an update to{' '}
                <strong style={{ color: '#34d399' }}>{label}</strong> while you had this page
                open. Reload to pick it up — you&apos;ll carry on from where you left off, and
                everything you&apos;ve entered is already saved.
              </>
            ) : (
              <>
                <strong style={{ color: '#34d399' }}>{label}</strong> encountered an unexpected
                error and couldn&apos;t render. Your data is safe — this is just a display issue.
              </>
            )}
          </p>

          {/* Actions */}
          <div style={styles.actions}>
            <button id={primary.id} style={styles.primaryBtn} onClick={primary.onClick}>
              {primary.text}
            </button>
            <button id={secondary.id} style={styles.secondaryBtn} onClick={secondary.onClick}>
              {secondary.text}
            </button>
          </div>

          {/* Collapsible error details */}
          <button
            id="eb-toggle-details-btn"
            style={styles.detailsToggle}
            onClick={this.toggleDetails}
            aria-expanded={showDetails}
          >
            {showDetails ? '▲ Hide' : '▼ Show'} technical details
          </button>

          {showDetails && (
            <div style={styles.detailsBox} role="region" aria-label="Error details">
              <p style={styles.detailsLabel}>Error</p>
              <pre style={styles.pre}>{error?.toString()}</pre>
              {errorInfo?.componentStack && (
                <>
                  <p style={styles.detailsLabel}>Component Stack</p>
                  <pre style={styles.pre}>{errorInfo.componentStack}</pre>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }
}

/* ── Inline styles (no external CSS dependency) ── */
const styles = {
  overlay: {
    position: 'relative',
    minHeight: '100vh',
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--forest-night, #06140d)',
    overflow: 'hidden',
    padding: '2rem',
    fontFamily: "var(--body, 'Inter', system-ui, sans-serif)",
  },
  orb1: {
    position: 'absolute',
    top: '-10%',
    left: '-10%',
    width: '480px',
    height: '480px',
    borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(16,185,129,0.18) 0%, transparent 70%)',
    pointerEvents: 'none',
    animation: 'eb-float 8s ease-in-out infinite',
  },
  orb2: {
    position: 'absolute',
    bottom: '-15%',
    right: '-10%',
    width: '560px',
    height: '560px',
    borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(168,217,74,0.10) 0%, transparent 70%)',
    pointerEvents: 'none',
    animation: 'eb-float 11s ease-in-out infinite reverse',
  },
  card: {
    position: 'relative',
    zIndex: 1,
    maxWidth: '520px',
    width: '100%',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.10)',
    borderRadius: '20px',
    padding: '2.5rem 2rem',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    boxShadow: '0 2px 6px -2px rgba(0,0,0,.4), 0 24px 60px -20px rgba(0,0,0,.55)',
    textAlign: 'center',
  },
  iconWrap: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '72px',
    height: '72px',
    borderRadius: '50%',
    background: 'rgba(16,185,129,0.12)',
    border: '1px solid rgba(16,185,129,0.25)',
    marginBottom: '1.5rem',
  },
  heading: {
    margin: '0 0 0.75rem',
    fontSize: '1.625rem',
    fontWeight: 700,
    color: '#eaf3ee',
    fontFamily: "var(--display, 'Montserrat', sans-serif)",
    letterSpacing: '-0.02em',
  },
  subtext: {
    margin: '0 0 2rem',
    fontSize: '0.9375rem',
    lineHeight: 1.65,
    color: '#a7c0b4',
  },
  actions: {
    display: 'flex',
    gap: '0.75rem',
    justifyContent: 'center',
    flexWrap: 'wrap',
    marginBottom: '1.5rem',
  },
  primaryBtn: {
    padding: '0.625rem 1.5rem',
    borderRadius: '10px',
    border: 'none',
    background: 'linear-gradient(135deg, #10B981, #34d399)',
    color: '#06140d',
    fontWeight: 700,
    fontSize: '0.9rem',
    cursor: 'pointer',
    transition: 'opacity 0.2s, transform 0.15s',
    fontFamily: 'inherit',
  },
  secondaryBtn: {
    padding: '0.625rem 1.5rem',
    borderRadius: '10px',
    border: '1px solid rgba(255,255,255,0.12)',
    background: 'rgba(255,255,255,0.06)',
    color: '#eaf3ee',
    fontWeight: 600,
    fontSize: '0.9rem',
    cursor: 'pointer',
    transition: 'background 0.2s, transform 0.15s',
    fontFamily: 'inherit',
  },
  detailsToggle: {
    background: 'none',
    border: 'none',
    color: '#7d9488',
    fontSize: '0.8rem',
    cursor: 'pointer',
    padding: '0.25rem 0.5rem',
    fontFamily: 'inherit',
    transition: 'color 0.2s',
  },
  detailsBox: {
    marginTop: '1rem',
    background: 'rgba(0,0,0,0.3)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '10px',
    padding: '1rem',
    textAlign: 'left',
  },
  detailsLabel: {
    margin: '0 0 0.25rem',
    fontSize: '0.7rem',
    fontWeight: 700,
    color: '#7d9488',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
  },
  pre: {
    margin: '0 0 1rem',
    fontSize: '0.72rem',
    color: '#a7c0b4',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    lineHeight: 1.6,
    fontFamily: "'Fira Code', 'Courier New', monospace",
    maxHeight: '160px',
    overflowY: 'auto',
  },
};

/* ── Inject keyframe for orb animation (once) ── */
if (typeof document !== 'undefined' && !document.getElementById('eb-keyframes')) {
  const style = document.createElement('style');
  style.id = 'eb-keyframes';
  style.textContent = `
    @keyframes eb-float {
      0%, 100% { transform: translate(0, 0) scale(1); }
      50%       { transform: translate(20px, -24px) scale(1.05); }
    }
  `;
  document.head.appendChild(style);
}

export default ErrorBoundary;
