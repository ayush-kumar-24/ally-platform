import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { completionPercent, loadDashboard, markTourSeen, relativeDay } from '../services/dashboard';
import { DnaLoading } from '../components/DnaState';
import FeedbackPrompt from '../components/FeedbackPrompt';
import { FEEDBACK } from '../services/feedback';
import { useCallAccess } from '../hooks/useCallAccess';
import { greetingNow } from '../utils/helpers';
import {
  IconArrowRight,
  IconChat,
  IconCheck,
  IconDocument,
  IconLightbulb,
  IconLock,
  IconTrendingUp,
  IconX,
} from '../utils/icons';

/**
 * The clarity ring.
 *
 * Shows the band, not a number. The API deliberately never serves a raw score
 * (see backend/app/schemas/dashboard.py) -- `fill_pct` exists precisely so the
 * ring can be drawn without disclosing one. This used to read
 * `health.overall_score`, a field that does not exist in the response, so it
 * rendered a confident "0 clarity" for every founder including those with a
 * finished diagnosis.
 */
function ScoreRing({ fillPct, band, hasDiagnosis }) {
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.max(0, Math.min(100, fillPct ?? 0));
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div className="dash-ring" aria-label={band ? `Clarity band: ${band}` : 'No diagnosis yet'}>
      <svg viewBox="0 0 92 92" aria-hidden="true">
        <defs>
          <linearGradient id="dash-ring-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38d39f" />
            <stop offset="100%" stopColor="#9ce14b" />
          </linearGradient>
        </defs>
        <circle className="bg" cx="46" cy="46" r={radius} />
        <circle
          className="fg"
          cx="46"
          cy="46"
          r={radius}
          style={{ strokeDasharray: circumference, strokeDashoffset: offset }}
        />
      </svg>
      <div className="mid">
        <b className={band ? 'dash-ring-band' : ''}>{band || '—'}</b>
        {/* A finished diagnosis can still carry no band. Saying "no diagnosis
            yet" to someone who has one is a different lie from saying nothing. */}
        <span>{band ? 'clarity' : hasDiagnosis ? 'not banded' : 'no diagnosis yet'}</span>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, unit, sub, progress, tone = 'emerald' }) {
  return (
    <div className="dash-stat">
      <div className="k">
        <span className={`dot ${tone}`}>{icon}</span>
        {label}
      </div>
      <div className="v">
        {value}
        <span className="u">{unit}</span>
      </div>
      <div className="s">{sub}</div>
      <div className="bar">
        <i style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

function Pill({ children, active = false }) {
  return <span className={`dash-pill${active ? ' active' : ''}`}>{children}</span>;
}

/* The Compass grid, ported from the GoXL Ally reference mockup's dashboard.
   The mockup shows 13 tiles; only the ones with `path` have a real page in
   this app today, so the rest render as visibly inert "Coming soon" tiles
   rather than linking to nothing. */
const COMPASS_TILES = [
  { title: 'Adaptive Diagnosis', path: '/app/founder-dna-journey', mini: 'Understand what is really wrong',
    desc: 'Describe a business symptom, answer adaptive questions and let Ally trace it to the underlying root cause.' },
  { title: 'Talk to Ally', path: '/app/ally-chat', mini: 'Your thinking partner',
    desc: 'Brainstorm ideas, pressure-test decisions and get strategic guidance using context Ally already knows.' },
  { title: 'Founder DNA', path: '/app/founder-dna', mini: 'Understand yourself as a founder',
    desc: 'Understand your archetype, decision patterns, leadership style, strengths, blind spots and personal growth areas.' },
  { title: 'Your Vision', path: '/app/vision', mini: 'Turn ambition into milestones',
    desc: 'Define the future you want across life, business, impact, finances, ideal day and legacy, then make it measurable.' },
  { title: 'Business DNA', path: '/app/business-dna', mini: 'See the whole business clearly',
    desc: 'Review the health signals, constraints and patterns shaping your company across its core business dimensions.' },
  { title: 'Journey', path: '/app/journey', mini: 'Learn from your path',
    desc: 'Revisit the decisions, lessons, pivots and turning points that shaped how you build and lead today.' },
  { title: 'Your Achievements', path: null, mini: 'Recognise meaningful progress',
    desc: 'Capture business wins, leadership growth and impact milestones that Ally discovers across your journey.' },
  { title: 'Goals', path: null, mini: 'Track longer-term outcomes',
    desc: 'Set measurable business, founder and life outcomes, monitor progress and identify the next milestone.' },
  { title: 'Recommendations', path: '/app/next-steps', mini: 'Know what to do next',
    desc: "See Ally's prioritised guidance after it considers your diagnosis, DNA, vision, energy, business and goals together." },
  { title: 'Plan Your Day', path: '/app/plan', mini: "Focus today's execution",
    desc: 'Convert current goals and recommendations into a focused daily plan with clear priorities and time blocks.' },
  { title: 'Frameworks', path: null, mini: 'Think through complexity',
    desc: 'Use your personal thinking toolkit to structure difficult decisions, assumptions, priorities and experiments.' },
  { title: 'Reports', path: '/app/report', mini: 'Keep a record of insights',
    desc: 'Review complete diagnosis reports, supporting evidence, confidence levels and sequenced action roadmaps.' },
  { title: 'Profile & Settings', path: '/app/profile', mini: 'Manage your account',
    desc: 'Manage personal details, preferences, account data, subscription, billing history and invoices.' },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, startTour } = useApp();
  const [showBanner, setShowBanner] = useState(true);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Every discovery-call surface on this page hangs off this one signal.
  const { canBook: canBookCall } = useCallAccess();

  const load = useCallback(() => {
    setLoading(true);
    loadDashboard()
      .then(setData)
      .finally(() => setLoading(false));
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
  const fillPct = hasHealth ? health.fill_pct : null;
  const pillars = health?.pillars ?? [];
  const redFlags = health?.red_flags ?? [];

  const profilePct = completionPercent(data?.progress);
  const summary = data?.summary;

  /* Everything below used to be invented in the markup -- three conversations
     that never happened, a booked call that did not exist, report scores nobody
     produced. It is all real, and all already served by /dashboard/overview. */
  const overview = data?.overview;
  const diagnosis = overview?.latest_diagnosis;
  const hasDiagnosis = Boolean(diagnosis?.available);
  const nextAction = overview?.upcoming_actions?.[0] || null;
  const conversations = overview?.recent_conversations ?? [];
  const recentReports = overview?.recent_reports ?? [];
  const call = overview?.upcoming_call;
  const hasCall = Boolean(call?.available);
  const metrics = overview?.metrics;

  const sessions = metrics?.sessions_completed ?? summary?.completed_sessions ?? 0;
  const reports = metrics?.reports ?? summary?.total_reports ?? 0;

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
                  Take a 60-second Product Tour
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

        <section className="compass-hero">
          <div className="compass-kicker">{greeting}, {firstName} · Your Compass</div>
          <h2 className="compass-quote">"Clarity doesn't come from doing more. It comes from knowing <em>what matters next.</em>"</h2>
          <p className="compass-note">A quick view of your founder, business and momentum — everything important, in one place.</p>
        </section>

        <section className="compass-grid" aria-label="Workspace overview">
          {COMPASS_TILES.map((tile) => (
            <article
              key={tile.title}
              className={`compass-glimpse${tile.path ? '' : ' is-disabled'}`}
              role={tile.path ? 'button' : undefined}
              tabIndex={tile.path ? 0 : -1}
              onClick={tile.path ? () => navigate(tile.path) : undefined}
              onKeyDown={tile.path ? (e) => { if (e.key === 'Enter' || e.key === ' ') navigate(tile.path); } : undefined}
            >
              <span className="cg-top">
                <h3>{tile.title}</h3>
                <span className="cg-arrow">{tile.path ? 'Overview' : 'Coming soon'}</span>
              </span>
              <p>{tile.desc}</p>
              <span className="cg-mini">{tile.mini}</span>
            </article>
          ))}
        </section>

        <section className="dash-feature">
          <div className="dash-feature-copy">
            <div className="dash-kicker">Your latest diagnosis</div>
            <div className="dash-feature-tag">
              <span className="dot" /> Your founder clarity
            </div>
            <h3>
              {hasDiagnosis
                ? (diagnosis.title || 'Your diagnosis is ready.')
                : 'Your diagnosis hasn’t run yet.'}
            </h3>
            <p>
              {hasDiagnosis
                ? diagnosis.summary
                : 'Once you complete a diagnosis, Ally traces your symptoms to a single root cause and explains it here.'}
            </p>
            <div className="dash-feature-acts">
              {hasDiagnosis ? (
                <>
                  <button className="btn btn-em" type="button" onClick={() => navigate('/app/ally-chat')}>
                    <IconChat />
                    Discuss with Ally
                  </button>
                  <button className="btn btn-dark-ghost" type="button" onClick={() => navigate('/app/report')}>
                    View full report
                  </button>
                </>
              ) : (
                <button className="btn btn-em" type="button" onClick={() => navigate('/app/founder-dna-journey')}>
                  <IconArrowRight />
                  Start your diagnosis
                </button>
              )}
            </div>
          </div>
          <ScoreRing fillPct={fillPct} band={band} hasDiagnosis={hasDiagnosis} />
        </section>

        <section className="dash-progress">
          <div className="dash-section-head compact">
            <div className="dash-section-title">Your progress</div>
          </div>

          <div className="dash-pills">
            <Pill active={profilePct === 100}>Founder profile</Pill>
            <Pill active={sessions > 0}>Conversation</Pill>
            <Pill active={sessions > 0}>Diagnosis</Pill>
            <Pill active={reports > 0}>Report</Pill>
            <Pill active={hasHealth}>Next steps</Pill>
            {/* Was hardcoded false, so a founder who had booked a call still saw it unlit. */}
            {/* A progress track ending in a step they cannot take reads as an
                incomplete journey rather than a finished one. Kept only if it
                is reachable, or already done. */}
            {(canBookCall || (metrics?.discovery_calls_booked ?? 0) > 0) && (
              <Pill active={(metrics?.discovery_calls_booked ?? 0) > 0}>Discovery call</Pill>
            )}
          </div>

          <div className="dash-stats">
            <StatCard icon={<IconCheck />} label="Founder clarity"
                      value={band || '—'} unit=""
                      sub={hasHealth ? 'From your latest diagnosis' : 'Run a diagnosis to see this'}
                      progress={fillPct ?? 0} />
            <StatCard icon={<IconTrendingUp />} label="Dimensions scanned"
                      value={pillars.length} unit={pillars.length ? 'scanned' : ''}
                      sub={pillars.length ? 'From your latest diagnosis' : 'No diagnosis yet'}
                      progress={pillars.length ? 100 : 0} />
            <StatCard icon={<IconLightbulb />} label="Red flags"
                      value={redFlags.length} unit={redFlags.length === 1 ? 'found' : 'found'}
                      sub={redFlags.length ? 'Needs attention' : 'None detected'}
                      progress={redFlags.length ? 100 : 0} />
            <StatCard icon={<IconDocument />} label="Reports"
                      value={reports} unit={reports === 1 ? 'report' : 'reports'}
                      sub={sessions ? `${sessions} session${sessions === 1 ? '' : 's'} completed` : 'No sessions yet'}
                      progress={reports ? 100 : 0} />
          </div>
        </section>

        <section className="dash-grid">
          <div className="dash-stack">
            <section className="dash-section dash-note-card">
              <div className="dash-section-head">
                <div>
                  <div className="dash-kicker">Next recommended action</div>
                  <div className="dash-section-title">
                    {nextAction?.title || (hasDiagnosis ? 'Nothing outstanding' : 'Not yet')}
                  </div>
                </div>
                {nextAction && (
                  <button className="dash-link" type="button" onClick={() => navigate('/app/plan')}>
                    See roadmap <IconArrowRight />
                  </button>
                )}
              </div>
              <p>
                {nextAction?.description
                  || (hasDiagnosis
                    ? 'You have no open actions right now. Plan your day to add one.'
                    : 'Your action plan is written from your diagnosis — run one and Ally will tell you where to start.')}
              </p>
              <div className="dash-note-actions">
                <button className="btn btn-primary" type="button"
                        onClick={() => navigate(hasDiagnosis ? '/app/plan' : '/app/founder-dna-journey')}>
                  {nextAction ? 'Open your plan'
                    : hasDiagnosis ? 'Plan your day'
                    : 'Start your diagnosis'}
                </button>
              </div>
            </section>

            <section className="dash-section">
              <div className="dash-section-head">
                <div className="dash-section-title">Recent conversations</div>
                <button className="dash-link" type="button" onClick={() => navigate('/app/ally-chat')}>Open <IconArrowRight /></button>
              </div>
              <div className="dash-list">
                {conversations.length === 0 && (
                  <p className="dash-empty">
                    You haven’t talked to Ally yet. Your conversations will show up here.
                  </p>
                )}
                {conversations.map((c) => (
                  <button
                    key={c.conversation_id}
                    className="dash-list-row"
                    type="button"
                    onClick={() => navigate('/app/ally-chat')}
                  >
                    <span className="dash-list-ic"><IconChat /></span>
                    <span className="dash-list-body">
                      <span className="dash-list-title">{c.title || 'Untitled conversation'}</span>
                      <span className="dash-list-sub">
                        {c.message_count != null
                          ? `${c.message_count} message${c.message_count === 1 ? '' : 's'}`
                          : 'Conversation'}
                      </span>
                    </span>
                    <span className="dash-list-meta">{relativeDay(c.last_message_at || c.created_at)}</span>
                  </button>
                ))}
              </div>
            </section>

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

        <section className="dash-unlock">
          <div className="dash-section-head">
            <div className="dash-section-title">Unlock more with Ally</div>
            <button className="dash-link" type="button" onClick={() => navigate('/app/billing')}>See plans <IconArrowRight /></button>
          </div>
          <div className="dash-unlock-grid">
            <article className="dash-unlock-card">
              <div className="dash-unlock-viz ring"></div>
              <div className="dash-unlock-lock"><IconLock /></div>
              <h4>Weekly Founder MRI</h4>
              <p>A deep scan of your leadership blind spots and momentum.</p>
              <div className="dash-unlock-foot">
                <span className="dash-unlock-link">Upgrade to Pro <IconArrowRight /></span>
                <span className="dash-unlock-help">Why is this locked?</span>
              </div>
            </article>
            <article className="dash-unlock-card">
              <div className="dash-unlock-viz bars"></div>
              <div className="dash-unlock-lock"><IconLock /></div>
              <h4>Compare against 10,000 founders</h4>
              <p>Compare your patterns against 10,000+ founders in your space.</p>
              <div className="dash-unlock-foot">
                <span className="dash-unlock-link">Upgrade to Pro+ <IconArrowRight /></span>
                <span className="dash-unlock-help">Why is this locked?</span>
              </div>
            </article>
            <article className="dash-unlock-card">
              <div className="dash-unlock-viz spark"></div>
              <div className="dash-unlock-lock"><IconLock /></div>
              <h4>AI Decision Support</h4>
              <p>Pressure-test big calls with Ally before you commit.</p>
              <div className="dash-unlock-foot">
                <span className="dash-unlock-link">Upgrade to Pro <IconArrowRight /></span>
                <span className="dash-unlock-help">Why is this locked?</span>
              </div>
            </article>
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

