import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  createShareLink, downloadReportPdf, factList,
  getLatestReport, getReport, getReportDocument,
  listShareLinks, revokeShareLink,
} from '../services/reports';
import { DnaError, DnaLoading, DnaNoReport } from '../components/DnaState';
import FeedbackPrompt from '../components/FeedbackPrompt';
import { FEEDBACK } from '../services/feedback';
import { useApp } from '../context/AppContext';
import { getOverview } from '../services/dashboard';

/**
 * The report document, mounted in an isolated frame.
 *
 * An iframe rather than dangerouslySetInnerHTML on purpose: the document brings
 * its own complete stylesheet, and the platform shell's global CSS would
 * otherwise bleed into it — at which point the screen stops matching the PDF,
 * which is the one thing this whole path exists to guarantee. srcDoc frames are
 * same-origin, so the parent can still wire the buttons up directly and the
 * document itself stays script-free (and therefore identical to what Gotenberg
 * renders).
 *
 * The frame is grown to its content height instead of scrolling internally, so
 * the shell's own scroller keeps working — and with it the read-gate below.
 */
function fmtShareDate(iso) {
  if (!iso) return 'its expiry date';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'its expiry date';
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function ReportDocument({ html, onDownload, onShare, frameRef }) {
  const [height, setHeight] = useState(900);

  const wire = useCallback((event) => {
    const frame = event.currentTarget;
    const doc = frame.contentDocument;
    if (!doc) return;

    // documentElement, not body: the shell's bottom padding and the footnote's
    // top margin sit outside body's own box, so measuring body alone left the
    // frame ~45px short and clipped the footer off the end of the report.
    const fit = () => setHeight(Math.max(
      doc.documentElement.scrollHeight, doc.body.scrollHeight));
    fit();
    // Fonts settle after load and reflow the whole document; without this the
    // frame keeps the pre-webfont height and the last section is cut off.
    doc.fonts?.ready?.then(fit).catch(() => {});
    const observer = new ResizeObserver(fit);
    observer.observe(doc.documentElement);
    frame._cleanup = () => observer.disconnect();

    doc.querySelectorAll('[data-report-action="download"]')
       .forEach(el => el.addEventListener('click', onDownload));
    doc.querySelectorAll('[data-report-action="share"]')
       .forEach(el => el.addEventListener('click', onShare));
  }, [onDownload, onShare]);

  useEffect(() => () => frameRef.current?._cleanup?.(), [frameRef]);

  return (
    <iframe
      ref={frameRef}
      title="Your clarity report"
      srcDoc={html}
      onLoad={wire}
      style={{ width: '100%', height, border: 0, display: 'block',
               colorScheme: 'light' }}
    />
  );
}


function ReportView({ report, meta, containerRef }) {
  const navigate = useNavigate();

  const sections = report?.sections ?? [];
  const unpopulated = report?.unpopulated_sections ?? [];
  const generated = report?.generated_at ? new Date(report.generated_at) : null;

  return (
    <div className="fd-container" ref={containerRef}>
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
 * The element that actually scrolls this content.
 *
 * Not the window: the platform shell pins .main to overflow:hidden and scrolls
 * an inner box instead (today #main-content inside .view-wrap, both of which
 * carry overflow-y:auto). Walking up from the content finds whichever one is
 * really moving, so a future layout change cannot quietly break the read gate
 * the way a hardcoded selector would.
 *
 * Deliberately does NOT check whether the box currently overflows: this runs
 * on mount, before fonts and layout have settled, and a not-yet-tall report
 * would look unscrollable and lose its scroll listener for good. Whether there
 * is anything to scroll is decided per-event instead.
 */
function findScroller(node) {
  let el = node?.parentElement;
  while (el && el !== document.body) {
    const overflowY = getComputedStyle(el).overflowY;
    if (overflowY === 'auto' || overflowY === 'scroll') return el;
    el = el.parentElement;
  }
  return null;
}

/**
 * Have they actually read it?
 *
 * Asking the instant the report renders would be asking about something they
 * have not seen. Either signal counts as read: reaching the end of the report,
 * or staying with it long enough that they plainly did not just bounce.
 */
function useHasRead(ready, contentRef, { dwellMs = 25000 } = {}) {
  const [read, setRead] = useState(false);

  useEffect(() => {
    if (!ready || read) return undefined;

    // Dwell is the floor, and the only signal for a report short enough not to
    // scroll. It is not a fallback for a broken scroll listener -- it is the
    // honest answer to "they stayed with it" when there is nothing to scroll.
    const timer = setTimeout(() => setRead(true), dwellMs);

    /* This used to listen on window and read documentElement. Nothing scrolls
       there, so scrollY was permanently 0 and scrollHeight ~= clientHeight,
       which made the very first check pass: the dialog opened the instant the
       report rendered, asking "now that you've read it" about a page still
       sitting at the top. */
    const scroller = findScroller(contentRef.current);
    if (!scroller) return () => clearTimeout(timer);

    const onScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = scroller;
      // "Reached the bottom" only means something when there was somewhere to
      // scroll to. A report that fits on one screen sits permanently at its
      // own bottom -- counting that as read is what made this fire on arrival.
      if (scrollHeight - clientHeight <= 240) return;
      // Near the bottom -- not exactly, since the last pixel is rarely reached.
      if (scrollTop + clientHeight >= scrollHeight - 240) setRead(true);
    };

    scroller.addEventListener('scroll', onScroll, { passive: true });
    onScroll();   // in case they land already scrolled (back-navigation)
    return () => { clearTimeout(timer); scroller.removeEventListener('scroll', onScroll); };
  }, [ready, read, dwellMs, contentRef]);

  return read;
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

  // Guards against two overlapping loads (React StrictMode's double-invoked
  // mount effect in dev, or any fast remount in production) landing their
  // setState calls out of order -- live-confirmed this let a superseded
  // call's late failure overwrite an already-successful render with an
  // error screen, even though the report had loaded fine. Only the most
  // recently started load is allowed to write state.
  const loadIdRef = useRef(0);

  const load = useCallback(() => {
    const id = ++loadIdRef.current;
    setState({ status: 'loading' });
    getLatestReport()
      .then(async (latest) => {
        if (!latest) {
          if (id === loadIdRef.current) setState({ status: 'no-report' });
          return;
        }
        // The rendered document is what the founder should see, but a failure
        // to fetch it must not cost them their report: the JSON narrative still
        // renders through ReportView below. Everyone gets their report.
        const [full, html] = await Promise.all([
          getReport(latest.report_id),
          getReportDocument(latest.report_id).catch(() => null),
        ]);
        if (id === loadIdRef.current) {
          setState({ status: 'ready', report: full, meta: latest, html });
        }
      })
      .catch((error) => {
        if (id === loadIdRef.current) setState({ status: 'error', error });
      });
  }, []);

  useEffect(load, [load]);

  // Hooks cannot live below the early returns, so this is computed here and
  // only becomes true once a report is actually on screen.
  const contentRef = useRef(null);
  const hasRead = useHasRead(state.status === 'ready', contentRef);

  const frameRef = useRef(null);
  const pageNavigate = useNavigate();
  const { startTour, showToast } = useApp();

  const reportId = state.meta?.report_id ?? state.report?.report_id;

  const handleDownload = useCallback(() => {
    if (!reportId) return;
    showToast('Preparing your PDF…');
    downloadReportPdf(reportId)
      .then(() => showToast('Downloaded.'))
      .catch((err) => showToast(
        // 503 is the renderer being momentarily down, and the service has
        // already recovered the API's own sentence for that case -- it says
        // more than anything generic we could put here.
        err?.status === 503
          ? err.message
          : "That download didn't start. Try again in a moment.",
        7000));
  }, [reportId, showToast]);

  /* Live share links, so a founder can take one back.

     The API has listed and revoked shares since the feature shipped; nothing in
     the app ever called either. So creating a link was one click and undoing it
     was an email to support, for thirty days, on a document that needs no
     sign-in to read and contains a personal read of the founder. */
  const [shares, setShares] = useState([]);
  const [revoking, setRevoking] = useState(null);

  const refreshShares = useCallback(() => {
    if (!reportId) return;
    listShareLinks(reportId)
      .then((rows) => setShares(Array.isArray(rows) ? rows : []))
      .catch(() => { /* the list is a convenience; never break the report over it */ });
  }, [reportId]);

  useEffect(() => { refreshShares(); }, [refreshShares]);

  const handleShare = useCallback(() => {
    if (!reportId) return;
    createShareLink(reportId)
      .then(({ share_url }) => navigator.clipboard?.writeText(share_url)
        .then(() => showToast('Share link copied to your clipboard.'))
        .catch(() => showToast(`Share link: ${share_url}`, 8000)))
      .then(refreshShares)
      .catch(() => showToast("Couldn't create a share link. Try again in a moment.", 6000));
  }, [reportId, showToast, refreshShares]);

  const handleRevoke = useCallback((token) => {
    if (!reportId || revoking) return;
    setRevoking(token);
    revokeShareLink(reportId, token)
      .then(() => {
        // Drop it locally rather than waiting for a refetch: the founder just
        // asked for this link to stop working and should see that immediately.
        setShares((prev) => prev.filter((r) => r.share_token !== token));
        showToast('That link has been turned off. It will not open for anyone now.');
      })
      .catch(() => showToast("Couldn't turn that link off. Try again in a moment.", 6000))
      .finally(() => setRevoking(null));
  }, [reportId, revoking, showToast]);

  const offerTour = useCallback(() => {
    // Ask the server rather than assuming: it knows from tour_seen_at whether
    // this founder has been offered the tour before, on any device.
    getOverview()
      .then((o) => { if (o?.welcome?.show_tour) startTour(); })
      .catch(() => { /* not worth interrupting the report over */ });
  }, [startTour]);

  if (state.status === 'loading') return <DnaLoading label="Loading your report…" />;
  if (state.status === 'no-report') return <DnaNoReport kind="report" />;
  if (state.status === 'error') return <DnaError onRetry={load} />;

  return (
    <>
      {state.html ? (
        <div className="fd-container" ref={contentRef}>
          <ReportDocument
            html={state.html}
            frameRef={frameRef}
            onDownload={handleDownload}
            onShare={handleShare}
          />
          <div style={{ marginTop: 30, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button className="btn btn-em" type="button"
                    onClick={() => pageNavigate('/app/next-steps')}>
              See your next steps
            </button>
            <button className="btn btn-ghost" type="button"
                    onClick={() => pageNavigate('/app/ally-chat')}>
              Discuss this with Ally
            </button>
          </div>
        </div>
      ) : (
        <ReportView report={state.report} meta={state.meta} containerRef={contentRef} />
      )}
      {/* Only rendered when links exist -- a founder who has never shared sees
          nothing, and a founder who has sees exactly what is live and who has
          opened it. */}
      {shares.length > 0 && (
        <div style={{ marginTop: 30 }}>
          <h3 style={{ fontSize: 15, margin: '0 0 4px' }}>Links you have shared</h3>
          <p style={{ fontSize: 13, opacity: 0.75, margin: '0 0 12px', maxWidth: '58ch' }}>
            Anyone with one of these can read this report without signing in.
            Turning a link off stops it working straight away.
          </p>
          {shares.map((row) => (
            <div
              key={row.share_token}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                gap: 16, padding: '10px 0', borderTop: '1px solid var(--pr-line, #e8e3da)',
              }}
            >
              <div style={{ minWidth: 0, fontSize: 13.5 }}>
                <div>
                  Opened {row.access_count === 0
                    ? 'no times yet'
                    : `${row.access_count} ${row.access_count === 1 ? 'time' : 'times'}`}
                </div>
                <div style={{ opacity: 0.7, fontSize: 12.5, marginTop: 2 }}>
                  Stops working on {fmtShareDate(row.expires_at)}
                </div>
              </div>
              <button
                className="btn btn-ghost"
                type="button"
                onClick={() => handleRevoke(row.share_token)}
                disabled={revoking === row.share_token}
                style={{ flexShrink: 0 }}
              >
                {revoking === row.share_token ? 'Turning off…' : 'Turn off link'}
              </button>
            </div>
          ))}
        </div>
      )}

      <FeedbackPrompt
        type={FEEDBACK.REPORT}
        when={hasRead}
        reportId={state.meta?.report_id ?? state.report?.report_id}
        title="Was this report useful?"
        subtitle="Now that you've read it — did it tell you something you didn't already know?"
        // The tour was only ever offered from the dashboard banner, so a
        // founder who dismissed it there was never shown it again. Offering it
        // here means it lands when they have just seen what Ally can do --
        // and only if the server says they have not already been shown it.
        onResolved={offerTour}
      />
    </>
  );
}
