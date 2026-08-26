import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { completionPercent, loadDashboard, markTourSeen, relativeDay } from '../services/dashboard';
import { loadVision } from '../services/vision';
import { listGoals } from '../services/goals';
import { getLatestReport, getRecommendations } from '../services/reports';
import { DnaLoading } from '../components/DnaState';
import FeedbackPrompt from '../components/FeedbackPrompt';
import { FEEDBACK } from '../services/feedback';
import { useCallAccess } from '../hooks/useCallAccess';
import { greetingNow } from '../utils/helpers';
import {
  IconArrowRight,
  IconAward,
  IconChat,
  IconCompass,
  IconDocument,
  IconList,
  IconMapPin,
  IconTrendingUp,
  IconX,
} from '../utils/icons';

/**
 * toActions — same parsing as RecommendationsPage.jsx's toActions() (duplicated
 * rather than imported, same reasoning that page's own docstring gives: this
 * page is allowed to read the same report differently without being coupled
 * to that one). Plain action strings only -- the reference mockup's Bottleneck
 * card shows per-item evidence bullets and a numeric confidence score; neither
 * exists on /reports/:id/recommendations, so neither is shown here.
 */
function toActions(recs) {
  const facts = recs?.section?.facts;
  if (!facts) return [];
  const groups = [...(facts.solve_actions ?? []), ...(facts.confirm_actions ?? [])]
    .slice()
    .sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99));
  return groups.flatMap((g) => g.next_actions ?? []);
}

/** Percentage toward the founder's own vision target, only when both fields
 *  parse as plain numbers (same rule as vision.js's computeGap -- this is one
 *  founder's own two fields, not a fabricated score). Null means "don't know",
 *  never 0. */
function progressPct(target, current) {
  const t = parseFloat(String(target ?? '').replace(/[^\d.-]/g, ''));
  const c = parseFloat(String(current ?? '').replace(/[^\d.-]/g, ''));
  if (!target || !current || Number.isNaN(t) || Number.isNaN(c) || t <= 0) return null;
  return Math.max(0, Math.min(100, Math.round((c / t) * 100)));
}

/** The compass gauge -- an SVG dial, ported from the reference mockup's
 *  Founder's Compass Overview. `pct` null renders a resting needle and an
 *  empty arc rather than a fabricated reading. */
function CompassGauge({ pct }) {
  const r = 118;
  const circumference = 2 * Math.PI * r;
  const known = pct != null;
  const offset = circumference - ((known ? pct : 0) / 100) * circumference;
  const angle = known ? -90 + (pct / 100) * 180 : -90;
  return (
    <figure className="compass-gauge" aria-label={known ? `${pct}% toward your vision target` : 'Not enough data yet'}>
      <svg viewBox="0 0 300 300" role="img" aria-hidden="true">
        <circle cx="150" cy="150" r="118" fill="none" stroke="rgba(27,67,50,.1)" strokeWidth="1" />
        <circle cx="150" cy="150" r="96" fill="none" stroke="rgba(27,67,50,.07)" strokeWidth="1" />
        <circle
          cx="150" cy="150" r="118" fill="none" stroke="var(--emerald)" strokeWidth="3" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset} transform="rotate(-90 150 150)"
          style={{ transition: 'stroke-dashoffset 1s var(--ease)' }}
        />
        <g style={{ transformOrigin: '150px 150px', transition: 'transform 1.1s var(--ease)', transform: `rotate(${angle}deg)` }}>
          <path d="M150 62 L156 150 L150 160 L144 150 Z" fill="var(--forest)" />
          <path d="M150 160 L156 150 L150 232 L144 150 Z" fill="rgba(27,67,50,.16)" />
        </g>
        <circle cx="150" cy="150" r="6" fill="var(--ivory-2)" stroke="var(--forest)" strokeWidth="1.5" />
      </svg>
      <figcaption className="compass-gauge-center">
        <b>{known ? `${pct}%` : '—'}</b>
        <span>{known ? 'toward your target' : 'not enough data'}</span>
      </figcaption>
    </figure>
  );
}

/* ScoreRing, StatCard, Pill and COMPASS_TILES (the old flat tile grid) were
   removed here -- the new Founder's Compass Overview structure below
   replaces what they rendered: readouts cover the score/stat cards, and the
   five stones + loop diagram sections replace the tile grid as navigation. */

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, startTour } = useApp();
  const [showBanner, setShowBanner] = useState(true);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // North star (Vision + Goals) and Bottleneck/Next steps (report recommendations)
  // are fetched separately from loadDashboard()'s six sources -- same "resolve to
  // null on failure" rule so one missing piece dims one section, not the page.
  const [compassExtra, setCompassExtra] = useState(null);
  // Every discovery-call surface on this page hangs off this one signal.
  const { canBook: canBookCall } = useCallAccess();

  const load = useCallback(() => {
    setLoading(true);
    loadDashboard()
      .then(setData)
      .finally(() => setLoading(false));

    Promise.all([
      loadVision().catch(() => null),
      listGoals().catch(() => null),
      getLatestReport().catch(() => null),
    ]).then(async ([vision, goals, report]) => {
      const recs = report ? await getRecommendations(report.report_id).catch(() => null) : null;
      setCompassExtra({ vision, goals, hasReport: Boolean(report), actions: toActions(recs) });
    });
  }, []);

  useEffect(load, [load]);

  // Server name wins; the context value is the optimistic one set at login.
  const fullName = data?.profile?.full_name || user?.name || '';
  const firstName = fullName.split(' ')[0] || 'there';
  // Shared helper rather than a local copy -- three of these had drifted apart.
  const greeting = greetingNow();

  // `available: false` means "no diagnosis yet" — a real answer, not a failure.
  // Distinguishing it from a fetch error is what lets a new founder see an honest
  // empty state instead of a fabricated score.
  const health = data?.health;
  const hasHealth = Boolean(health?.available);
  const band = hasHealth ? health.band : null;
  const pillars = health?.pillars ?? [];
  const redFlags = health?.red_flags ?? [];

  const profilePct = completionPercent(data?.progress);
  const summary = data?.summary;

  /* Everything below used to be invented in the markup -- three conversations
     that never happened, a booked call that did not exist, report scores nobody
     produced. It is all real, and all already served by /dashboard/overview. */
  const overview = data?.overview;
  const conversations = overview?.recent_conversations ?? [];
  const recentReports = overview?.recent_reports ?? [];
  const call = overview?.upcoming_call;
  const hasCall = Boolean(call?.available);
  const metrics = overview?.metrics;

  const sessions = metrics?.sessions_completed ?? summary?.completed_sessions ?? 0;
  const reports = metrics?.reports ?? summary?.total_reports ?? 0;

  // North star: real Vision + Goals data, no invented single "statement" field.
  // Vision has six territories, not one -- 'business' is the closest read to
  // the mockup's aspirational one-liner; falls back to the first written
  // territory, then to an honest empty prompt.
  const visionTerritories = compassExtra?.vision?.territories;
  const visionSummary = compassExtra?.vision?.summary;
  const northStarStatement = visionTerritories?.business?.statement?.trim()
    || Object.values(visionTerritories || {}).find((t) => t?.statement?.trim())?.statement?.trim()
    || '';
  const goalsList = compassExtra?.goals ?? [];
  const topGoal = goalsList[0] || null;
  const northStarPct = progressPct(visionSummary?.target, visionSummary?.current);

  // Bottleneck + today's next steps: same report.recommendations data
  // RecommendationsPage.jsx reads -- plain action strings, no fabricated
  // evidence bullets or confidence score (see toActions()'s docstring above).
  const hasReport = Boolean(compassExtra?.hasReport);
  const recActions = compassExtra?.actions ?? [];
  const bottleneckAction = recActions[0] || null;
  const nextStepsPreview = recActions.slice(0, 3);

  const latestConversation = conversations[0] || null;

  const discuss = (text) => {
    navigate('/app/ally-chat', {
      state: { prefill: text ? `Let's talk through this: "${text}"` : 'I want to talk through what matters most right now.' },
    });
  };

  const plan = data?.plan;
  const planLabel = plan?.plan_name ? `Ally ${plan.plan_name}` : 'Ally';
  const isFree = (plan?.tier ?? 'free') === 'free';
  const tokenPct = plan?.daily_token_limit
    ? Math.min(100, Math.round((plan.daily_tokens_used / plan.daily_token_limit) * 100))
    : 0;

  // The onboarding banner is only truthful once the profile really is complete.
  // `show_tour` is the server's answer to "have they been offered this yet",
  // read from founders.tour_seen_at. Previously dismissal lived only in React
  // state, so the banner came back on every reload however many times it was
  // closed. Defaults to showing when the overview hasn't loaded -- a founder
  // who has genuinely never seen it should still be offered it.
  const profileComplete = profilePct === 100;
  /* Gated on the overview actually having arrived. This defaulted to `true`
     while loading, so the celebration banner rendered on mount and then
     vanished a moment later — a large block appearing and disappearing at the
     top of the page on every visit. */
  const tourUnseen = Boolean(overview) && overview.welcome?.show_tour !== false;

  /* `loading` was computed and never read: the page mounted its full chrome
     with zero-value fallbacks and then reflowed once the six sources resolved,
     so a returning founder briefly saw "no diagnosis yet / no reports / no
     conversations" before their real data replaced it. */
  if (loading && !data) {
    return (
      <div className="dash-page">
        <div className="dash-inner">
          <DnaLoading label="Loading your dashboard…" />
        </div>
      </div>
    );
  }

  return (
    <div className="dash-page">
      <div className="dash-inner">
        {showBanner && profileComplete && tourUnseen && (
          <section className="dash-banner">
            <div className="dash-banner-ic">🎉</div>
            <div className="dash-banner-body">
              {/* h2, not h3: this banner renders above the "How can Ally help
                  you today?" h2, so an h3 here gave the page h1 → h3 → h2. */}
              <h2>Congratulations, {firstName}. Your Founder Profile is now complete.</h2>
              <p>
                You've unlocked the complete Ally experience. Beyond diagnosis, Ally can now
                become your daily thinking partner.
              </p>
              <div className="dash-banner-actions">
                <button
                  className="btn btn-em"
                  type="button"
                  onClick={() => {
                    setShowBanner(false);
                    startTour();
                  }}
                >
                  <IconArrowRight />
                  {/* No duration in the label any more: the tour now covers
                      every section rather than six, and its length varies with
                      what the founder has unlocked (11 stops without a report,
                      16 with one). A fixed "60-second" claim would be wrong
                      for everybody. */}
                  Take the product tour
                </button>
                {/* Declining has to be recorded too, or the banner returns on
                    the next reload having just been told "maybe later". */}
                <button
                  className="btn btn-ghost"
                  type="button"
                  onClick={() => { setShowBanner(false); markTourSeen(); }}
                >
                  Maybe Later
                </button>
              </div>
              {/* Was "You can start this tour anytime from Settings" -- no
                  Settings screen has ever offered it. It is offered here and
                  once more after your first diagnosis. */}
              <div className="dash-banner-foot">We'll offer it again after your first diagnosis.</div>
            </div>
            <button className="dash-dismiss" type="button" onClick={() => setShowBanner(false)} aria-label="Dismiss banner">
              <IconX />
            </button>
          </section>
        )}

        <header className="compass-page-head">
          <div className="compass-kicker">{greeting}, {firstName} · Founder's Compass</div>
          <h1 className="compass-headline">Your living map of where you've been, where you are, and <em>where you're going.</em></h1>
        </header>

        <section className="compass-askbar-wrap">
          <form
            className="compass-askbar"
            onSubmit={(e) => {
              e.preventDefault();
              const text = e.currentTarget.elements.compassAsk.value.trim();
              discuss(text);
            }}
          >
            <input name="compassAsk" type="text" placeholder="Ask Ally about anything on this page…" autoComplete="off" />
            <button className="btn btn-em btn-sm" type="submit"><IconArrowRight />Ask Ally</button>
          </form>
        </section>

        {/* CURRENT STATE — real readouts, no invented deltas (there is no
            historical trend data to compute a "week over week" change from). */}
        <section className="compass-section">
          <div className="compass-section-head">
            <div className="compass-eyebrow">Current state</div>
            <h2>Where you're reading right now</h2>
          </div>
          <div className="compass-readouts">
            <div className="compass-readout">
              <span className="crl">Founder clarity</span>
              <span className="crv">{band || '—'}</span>
              <span className="crs">{hasHealth ? 'From your latest diagnosis' : 'Run a diagnosis to see this'}</span>
            </div>
            <div className="compass-readout">
              <span className="crl">Dimensions scanned</span>
              <span className="crv">{pillars.length || '—'}</span>
              <span className="crs">{pillars.length ? 'From your latest diagnosis' : 'No diagnosis yet'}</span>
            </div>
            <div className="compass-readout">
              <span className="crl">Red flags</span>
              <span className="crv">{hasHealth ? redFlags.length : '—'}</span>
              <span className="crs">{hasHealth ? (redFlags.length ? 'Needs attention' : 'None detected') : 'No diagnosis yet'}</span>
            </div>
            <div className="compass-readout">
              <span className="crl">Reports</span>
              <span className="crv">{reports || '—'}</span>
              <span className="crs">{sessions ? `${sessions} session${sessions === 1 ? '' : 's'} completed` : 'No sessions yet'}</span>
            </div>
          </div>
        </section>

        {/* NORTH STAR — the founder's own Vision + Goals, nothing invented. */}
        <section className="compass-section">
          <div className="compass-northstar">
            <div>
              <div className="compass-eyebrow">Your north star</div>
              {northStarStatement ? (
                <p className="compass-statement">"{northStarStatement}"</p>
              ) : (
                <p className="compass-statement is-empty">You haven't written your vision yet.</p>
              )}
              <dl className="compass-ns-rows">
                <div className="compass-ns-row"><dt>Vision</dt><dd>{visionSummary?.target?.trim() || 'Not set yet'}</dd></div>
                <div className="compass-ns-row"><dt>Goal this year</dt><dd>{topGoal?.title || 'No goals set yet'}</dd></div>
                {topGoal?.subtitle && (
                  <div className="compass-ns-row"><dt>Next milestone</dt><dd>{topGoal.subtitle}</dd></div>
                )}
              </dl>
              <div className="btn-row" style={{ marginTop: 22 }}>
                <button className="btn btn-em" type="button" onClick={() => navigate('/app/vision')}>View vision</button>
                <button className="btn btn-ghost" type="button" onClick={() => navigate('/app/goals')}>See goals <IconArrowRight /></button>
              </div>
            </div>
            <CompassGauge pct={northStarPct} />
          </div>
        </section>

        {/* BOTTLENECK — the founder's own top diagnosis recommendation, or an
            honest lock when there's no diagnosis to draw one from yet. No
            invented evidence bullets or confidence score -- see toActions(). */}
        <section className="compass-section">
          {hasReport ? (
            <article className="compass-bottleneck">
              <div className="compass-eyebrow">What Ally would flag first</div>
              {bottleneckAction ? (
                <>
                  <p className="compass-bottleneck-text">{bottleneckAction}</p>
                  <div className="btn-row" style={{ marginTop: 18 }}>
                    <button className="btn btn-em" type="button" onClick={() => discuss(bottleneckAction)}>
                      <IconChat /> Discuss with Ally
                    </button>
                    <button className="btn btn-ghost" type="button" onClick={() => navigate('/app/recommendations')}>
                      All recommendations
                    </button>
                  </div>
                </>
              ) : (
                <p className="compass-bottleneck-text is-empty">Your latest report didn't produce a top recommendation.</p>
              )}
            </article>
          ) : (
            <article className="compass-bottleneck is-locked">
              <div className="compass-eyebrow">What Ally would flag first</div>
              <p className="compass-bottleneck-text is-empty">
                Complete your diagnosis and Ally will surface the one thing most worth your attention.
              </p>
              <button className="btn btn-em" type="button" onClick={() => navigate('/app/founder-dna-journey')} style={{ marginTop: 14 }}>
                Start Founder Diagnosis
              </button>
            </article>
          )}
        </section>

        {/* FIVE STONES — pure navigation to the pages that build this picture. */}
        <section className="compass-section">
          <div className="compass-section-head">
            <div className="compass-eyebrow">Your five stones</div>
            <h2>The five things Ally keeps track of</h2>
            <p className="compass-sub">Each one feeds the next.</p>
          </div>
          <div className="compass-stones">
            <button className="compass-stone" type="button" onClick={() => navigate('/app/journey')}>
              <span className="cs-ix">01</span><IconMapPin />
              <span className="cs-title">Founder journey</span>
              <span className="cs-sub">Where you've been</span>
            </button>
            <button className="compass-stone" type="button" onClick={() => navigate('/app/founder-dna')}>
              <span className="cs-ix">02</span><IconCompass />
              <span className="cs-title">Motivation codes</span>
              <span className="cs-sub">Why you build</span>
            </button>
            <button className="compass-stone" type="button" onClick={() => navigate('/app/vision')}>
              <span className="cs-ix">03</span><IconTrendingUp />
              <span className="cs-title">Vision</span>
              <span className="cs-sub">Where you're going</span>
            </button>
            <button className="compass-stone" type="button" onClick={() => navigate('/app/goals')}>
              <span className="cs-ix">04</span><IconList />
              <span className="cs-title">Goals &amp; milestones</span>
              <span className="cs-sub">What you're building toward</span>
            </button>
            <button className="compass-stone" type="button" onClick={() => navigate('/app/next-steps')}>
              <span className="cs-ix">05</span><IconArrowRight />
              <span className="cs-title">Next steps</span>
              <span className="cs-sub">What matters now</span>
            </button>
          </div>
        </section>

        {/* RECENT CONVERSATION — the founder's real last thread, or an honest
            empty state. Same data as the old "Recent conversations" list,
            shown as a single preview here instead of a list. */}
        <section className="compass-section">
          <div className="compass-section-head">
            <div className="compass-eyebrow">Continue where you left off</div>
            <h2>Your last conversation with Ally</h2>
          </div>
          {latestConversation ? (
            <article className="compass-convo">
              <div className="cc-title">{latestConversation.title || 'Untitled conversation'}</div>
              <div className="cc-meta">
                {relativeDay(latestConversation.last_message_at || latestConversation.created_at)}
                {latestConversation.message_count != null
                  ? ` · ${latestConversation.message_count} message${latestConversation.message_count === 1 ? '' : 's'}`
                  : ''}
              </div>
              <button className="btn btn-em btn-sm" type="button" onClick={() => navigate('/app/ally-chat')} style={{ marginTop: 16 }}>
                Continue with Ally
              </button>
            </article>
          ) : (
            <p className="dash-empty">You haven't talked to Ally yet. Your conversations will show up here.</p>
          )}
        </section>

        {/* TODAY'S NEXT STEPS — same recommendation actions as Bottleneck's
            source, just up to three of them, each with its own Discuss CTA. */}
        <section className="compass-section">
          <div className="compass-section-head">
            <div className="compass-eyebrow">Today's next steps</div>
            <h2>{hasReport ? 'Pulled from your diagnosis' : 'Nothing pulled yet'}</h2>
          </div>
          {nextStepsPreview.length > 0 ? (
            <ol className="compass-steps">
              {nextStepsPreview.map((text, i) => (
                <li key={i} className="compass-step">
                  <span className="cst-num">{String(i + 1).padStart(2, '0')}</span>
                  <div className="cst-body">
                    <p>{text}</p>
                    <button type="button" className="btn btn-em btn-sm" onClick={() => discuss(text)}>
                      <IconChat /> Discuss
                    </button>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="dash-empty">
              {hasReport ? 'Your latest report has no next steps to show here.' : 'Complete your diagnosis to see next steps here.'}
            </p>
          )}
        </section>

        {/* WHAT CHANGED — no time-series metric exists yet to compute a real
            week-over-week delta from, so this is an honest "coming soon"
            rather than an invented trend, same treatment as Journey. */}
        <section className="compass-section">
          <div className="compass-section-head">
            <div className="compass-eyebrow">What changed since your last check-in</div>
            <h2>Coming soon</h2>
          </div>
          <p className="dash-empty">
            Tracking founder, business and execution trends week over week isn't built yet —
            it needs history Ally hasn't started collecting.
          </p>
        </section>

        {/* LOOP — pure navigation, mirrors the mockup's 12-node loop diagram
            mapped onto this app's real routes. */}
        <section className="compass-section">
          <div className="compass-section-head">
            <div className="compass-eyebrow">How the compass works</div>
            <h2>One loop, running continuously</h2>
            <p className="compass-sub">Everything you do feeds back into your journey.</p>
          </div>
          <div className="compass-loop">
            <button className="compass-loop-node" type="button" onClick={() => navigate('/app/journey')}><b>01 · You</b>My journey</button>
            <button className="compass-loop-node" type="button" onClick={() => navigate('/app/founder-dna')}><b>02 · You</b>My motivations</button>
            <button className="compass-loop-node" type="button" onClick={() => navigate('/app/vision')}><b>03 · You</b>My vision</button>
            <button className="compass-loop-node" type="button" onClick={() => navigate('/app/goals')}><b>04 · You</b>My goals</button>
            <button className="compass-loop-node" type="button" onClick={() => navigate('/app/business-dna')}><b>05 · Signals</b>My current reality</button>
            <button className="compass-loop-node is-ai" type="button" onClick={() => navigate('/app/founder-dna')}><b>06 · Ally</b>Founder + Business DNA</button>
            <button className="compass-loop-node is-ai" type="button" onClick={() => navigate('/app/founder-dna-journey')}><b>07 · Ally</b>Adaptive diagnosis</button>
            <button className="compass-loop-node is-ai" type="button" onClick={() => navigate('/app/ally-chat')}><b>08 · Ally</b>Talk to Ally</button>
            <button className="compass-loop-node" type="button" onClick={() => navigate('/app/next-steps')}><b>09 · You</b>Next steps</button>
            <button className="compass-loop-node" type="button" onClick={() => navigate('/app/plan')}><b>10 · You</b>Execution</button>
            <button className="compass-loop-node" type="button" onClick={() => navigate('/app/achievements')}><IconAward /><b>11 · You</b>Achievement</button>
            <button className="compass-loop-node is-you" type="button" onClick={() => navigate('/app/journey')}><b>12 · Back to 01</b>My journey evolves</button>
          </div>
        </section>

        {/* Discovery call is now the ONLY thing left in the left column (its
            two siblings moved into the new Bottleneck/recent-conversation
            sections above) -- when it's hidden, the left column would render
            empty and the grid would leave a large blank gap on the left. */}
        <section className={`dash-grid${(canBookCall || hasCall) ? '' : ' no-left-col'}`}>
          <div className="dash-stack">
            {/* Hidden entirely when they cannot book, EXCEPT when they already
                have a call on the books -- an existing booking is theirs and
                hiding it would be worse than advertising the feature. Hiding
                beats an upsell slot here: the dashboard already carries a plan
                card doing that job, and a second one turns the page into a
                pitch. */}
            {(canBookCall || hasCall) && (
            <section className="dash-section">
              <div className="dash-section-head">
                <div className="dash-section-title">Upcoming discovery call</div>
              </div>
              {hasCall ? (
                <div className="dash-call">
                  <div className="dash-call-kicker">
                    {call.status === 'confirmed' ? 'Confirmed' : call.status}
                    {call.duration_minutes ? ` · ${call.duration_minutes} min` : ''}
                  </div>
                  <div className="dash-call-row">
                    <div className="dash-call-date">
                      <b>{new Date(call.scheduled_at).toLocaleDateString(undefined, { day: 'numeric' })}</b>
                      <span>{new Date(call.scheduled_at).toLocaleDateString(undefined, { month: 'short' }).toUpperCase()}</span>
                    </div>
                    <div className="dash-call-copy">
                      <div className="dash-call-title">Founder strategy session</div>
                      <div className="dash-call-sub">
                        {new Date(call.scheduled_at).toLocaleString(undefined, {
                          weekday: 'short', hour: 'numeric', minute: '2-digit',
                        })}
                        {call.timezone ? ` · ${call.timezone}` : ''} · with a GoXL advisor
                      </div>
                    </div>
                  </div>
                  <button className="btn btn-ghost dash-call-btn" type="button"
                          onClick={() => navigate('/app/discovery-call')}>
                    Manage booking
                  </button>
                </div>
              ) : (
                <div className="dash-call">
                  {/* Was a hardcoded "Confirmed · 14 JUL" for every founder, including
                      those who had never booked anything. */}
                  <p className="dash-empty">You have no call booked.</p>
                  <button className="btn btn-ghost dash-call-btn" type="button"
                          onClick={() => navigate('/app/discovery-call')}>
                    Book a discovery call
                  </button>
                </div>
              )}
            </section>
            )}
          </div>

          <div className="dash-stack">
            {/* Every value here was hardcoded to "Ally Free" and "18 / 20",
                so a founder on Pro was told they were on Free and shown usage
                belonging to nobody. */}
            <section className="dash-section dash-plan">
              <div className="dash-plan-top">
                <div>
                  <div className="dash-kicker">Your plan</div>
                  <div className="dash-plan-title">{planLabel}</div>
                </div>
                <span className="dash-badge small">{planLabel}</span>
              </div>
              <div className="dash-plan-row">
                <span>Billing</span>
                <b>{isFree ? 'Free forever' : 'Active subscription'}</b>
              </div>
              <div className="dash-meter">
                <div>
                  <div className="dash-meter-row">
                    <span>Daily tokens</span>
                    <b>{plan ? `${plan.daily_tokens_used} / ${plan.daily_token_limit}` : '—'}</b>
                  </div>
                  <div className="dash-meter-bar"><i style={{ width: `${tokenPct}%` }} /></div>
                </div>
                <div>
                  <div className="dash-meter-row">
                    <span>Credits</span>
                    <b>{plan ? plan.credits_balance : '—'}</b>
                  </div>
                </div>
                {/* With no allowance left this row read "₹300 per call", which
                    quotes a price for something the founder cannot actually buy
                    -- there is no payment flow in the app yet. Quoting a price
                    you cannot take is worse than saying nothing. */}
                {canBookCall && (
                <div>
                  <div className="dash-meter-row">
                    <span>Free discovery calls</span>
                    <b>
                      {plan
                        ? (plan.free_calls_remaining > 0
                          ? `${plan.free_calls_remaining} left`
                          : <span className="dash-upgrade">₹{plan.call_price_inr} per call</span>)
                        : '—'}
                    </b>
                  </div>
                </div>
                )}
              </div>
              <div className="dash-plan-actions">
                <button className="btn btn-em" type="button" onClick={() => navigate('/app/billing')}>
                  <IconArrowRight />
                  {isFree ? 'Upgrade' : 'Manage plan'}
                </button>
              </div>
            </section>

            {/* Unprompted feedback, always available. The two prompted ones
                (after a diagnosis, after reading a report) are asked once each;
                this one has no target and can be given as often as they like. */}
            <section className="dash-section">
              <div className="dash-section-head">
                <div className="dash-section-title">Tell us how it's going</div>
              </div>
              <p className="dash-empty" style={{ padding: '4px 2px 0' }}>
                Ally is early. If something is working, or isn't, we'd rather hear it than guess.
              </p>
              <button
                className="dash-feedback-open"
                type="button"
                onClick={() => setFeedbackOpen(true)}
              >
                Give feedback
              </button>
            </section>

            <section className="dash-section">
              <div className="dash-section-head">
                <div className="dash-section-title">Recent reports</div>
                <button className="dash-link" type="button" onClick={() => navigate('/app/report')}>All <IconArrowRight /></button>
              </div>
              {/* Three invented reports with invented scores of 74/68/61 --
                  shown even to founders who had never run a diagnosis. */}
              <div className="dash-list reports">
                {recentReports.length === 0 && (
                  <p className="dash-empty">
                    No reports yet. Your first one arrives when you finish a diagnosis.
                  </p>
                )}
                {recentReports.map((r) => (
                  <button
                    key={r.report_id}
                    className="dash-list-row report"
                    type="button"
                    onClick={() => navigate('/app/report')}
                  >
                    <span className="dash-list-ic soft"><IconDocument /></span>
                    <span className="dash-list-body">
                      <span className="dash-list-title">{r.title || 'Founder diagnosis'}</span>
                      <span className="dash-list-sub">{relativeDay(r.generated_at)}</span>
                    </span>
                    {/* Band, never a number -- same disclosure rule as the ring. */}
                    <span className="dash-list-score band">{r.band || '—'}</span>
                  </button>
                ))}
              </div>
            </section>
          </div>
        </section>
      </div>

      <FeedbackPrompt
        type={FEEDBACK.GENERAL}
        when={feedbackOpen}
        dedupe={false}
        onResolved={() => setFeedbackOpen(false)}
        title="How's Ally working for you?"
        subtitle="Anything at all — what's useful, what isn't, what's missing."
      />
    </div>
  );
}

