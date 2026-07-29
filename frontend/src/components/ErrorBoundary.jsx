import React from 'react';

/* ─────────────────────────────────────────────
   ErrorBoundary
   Class component — required by React for
   catching rendering errors in the subtree.
───────────────────────────────────────────── */

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
    // In production you could forward to Sentry / LogRocket here
    console.error('[ErrorBoundary] Caught rendering error:', error, errorInfo);
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

    return (
      <div style={styles.overlay}>
        {/* Ambient background orbs */}
        <div style={styles.orb1} />
        <div style={styles.orb2} />

        <div style={styles.card}>
          {/* Icon */}
          <div style={styles.iconWrap}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#10B981' }}>
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </div>

          {/* Heading */}
          <h1 style={styles.heading}>Something went wrong</h1>
          <p style={styles.subtext}>
            <strong style={{ color: '#34d399' }}>{label}</strong> encountered an unexpected error
            and couldn&apos;t render. Your data is safe — this is just a display issue.
          </p>

          {/* Actions */}
          <div style={styles.actions}>
            <button id="eb-go-home-btn" style={styles.primaryBtn} onClick={this.handleReset}>
              Go Back to Safety
            </button>
            <button id="eb-reload-btn" style={styles.secondaryBtn} onClick={() => window.location.reload()}>
              Reload Page
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
