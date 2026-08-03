import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { completionPercent, loadDashboard } from '../services/dashboard';
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

function ScoreRing({ score }) {
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="dash-ring" aria-label={`Clarity score ${score}`}>
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
        <b>{score}</b>
        <span>clarity</span>
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

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, startTour } = useApp();
  const [showBanner, setShowBanner] = useState(true);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

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
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

  // `available: false` means "no diagnosis yet" — a real answer, not a failure.
  // Distinguishing it from a fetch error is what lets a new founder see an honest
  // empty state instead of a fabricated score.
  const health = data?.health;
  const hasHealth = Boolean(health?.available);
  const score = hasHealth ? Math.round(health.overall_score ?? 0) : null;
  const pillars = health?.pillars ?? [];
  const redFlags = health?.red_flags ?? [];

  const profilePct = completionPercent(data?.progress);
  const summary = data?.summary;
  const sessions = summary?.completed_sessions ?? 0;
  const reports = summary?.total_reports ?? 0;

  // The onboarding banner is only truthful once the profile really is complete.
  const profileComplete = profilePct === 100;

  return (
    <div className="dash-page">
      <div className="dash-inner">
        {showBanner && profileComplete && (
          <section className="dash-banner">
            <div className="dash-banner-ic">🎉</div>
            <div className="dash-banner-body">
              <h3>Congratulations, {firstName}. Your Founder Profile is now complete.</h3>
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
                <button className="btn btn-ghost" type="button" onClick={() => setShowBanner(false)}>
                  Maybe Later
                </button>
              </div>
              <div className="dash-banner-foot">You can start this tour anytime from Settings.</div>
            </div>
            <button className="dash-dismiss" type="button" onClick={() => setShowBanner(false)} aria-label="Dismiss banner">
              <IconX />
            </button>
          </section>
        )}

        <header className="dash-head">
          <div className="dash-head-eyebrow">{greeting}, {firstName}</div>
          <h2>How can Ally help you today?</h2>
        </header>

        <section className="dash-actions">
          <button className="dash-action-card" type="button" onClick={() => navigate('/app/ally-chat')}>
            <div className="dash-action-top">
              <div className="dash-action-ic ic-chat">
                <IconChat />
              </div>
            </div>
            <h3>Chat with Ally</h3>
            <p>
              Ask anything about your business. Brainstorm, pressure-test ideas, and get strategic guidance - or pick up a previous conversation.
            </p>
            <div className="dash-chips">
              <span className="dash-chip">Marketing</span>
              <span className="dash-chip">Sales</span>
              <span className="dash-chip">Hiring</span>
              <span className="dash-chip">Fundraising</span>
              <span className="dash-chip">Pricing</span>
            </div>
            <div className="dash-action-foot">
              <span className="dash-action-btn">Open Chat <IconArrowRight /></span>
              <span className="dash-badge">Always available</span>
            </div>
          </button>

          <button className="dash-action-card alt" type="button" onClick={() => navigate('/app/diagnosis')}>
            <div className="dash-action-top">
              <div className="dash-action-ic ic-diag">
                <IconLightbulb />
              </div>
            </div>
            <h3>Start Founder Diagnosis</h3>
            <p>
              A 20-minute structured AI assessment that traces the real root cause holding your business back - end to end.
            </p>
            <div className="dash-chips">
              <span className="dash-chip">Founder DNA</span>
              <span className="dash-chip">Business DNA</span>
              <span className="dash-chip">Root Cause</span>
              <span className="dash-chip">Founder Report</span>
            </div>
            <div className="dash-action-foot">
              <span className="dash-action-link">Start Diagnosis <IconArrowRight /></span>
              <span className="dash-badge quiet">~20 min</span>
            </div>
          </button>
        </section>

        <section className="dash-feature">
          <div className="dash-feature-copy">
            <div className="dash-kicker">Your latest diagnosis</div>
            <div className="dash-feature-tag">
              <span className="dot" /> Your founder clarity
            </div>
            <h3>Retention is your core constraint - not acquisition.</h3>
            <p>
              Ally understood how you lead and decide, then traced four business symptoms to a single root cause. Fix this first and the rest compound.
            </p>
            <div className="dash-feature-acts">
              <button className="btn btn-em" type="button" onClick={() => navigate('/app/ally-chat')}>
                <IconChat />
                Discuss with Ally
              </button>
              <button className="btn btn-dark-ghost" type="button" onClick={() => navigate('/app/report')}>
                View full report
              </button>
            </div>
          </div>
          <ScoreRing score={score ?? 0} />
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
            <Pill active={false}>Discovery call</Pill>
          </div>

          <div className="dash-stats">
            <StatCard icon={<IconCheck />} label="Founder clarity"
                      value={score ?? '—'} unit={score === null ? '' : '/100'}
                      sub={hasHealth ? (health.band || 'Scored') : 'Run a diagnosis to see this'}
                      progress={score ?? 0} />
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
                  <div className="dash-section-title">Retention - root cause</div>
                </div>
                <button className="dash-link" type="button">See roadmap <IconArrowRight /></button>
              </div>
              <p>
                Before adding a rupee of spend, plug the leak: identify the exact step where users go quiet in week two and redesign that first-value moment.
              </p>
              <div className="dash-note-actions">
                <button className="btn btn-primary" type="button" onClick={() => navigate('/app/ally-chat')}>
                  Discuss with Ally
                </button>
                <button className="btn btn-ghost" type="button">
                  Mark done
                </button>
              </div>
            </section>

            <section className="dash-section">
              <div className="dash-section-head">
                <div className="dash-section-title">Recent conversations</div>
                <button className="dash-link" type="button">Open <IconArrowRight /></button>
              </div>
              <div className="dash-list">
                <button className="dash-list-row" type="button" onClick={() => navigate('/app/ally-chat')}>
                  <span className="dash-list-ic"><IconChat /></span>
                  <span className="dash-list-body">
                    <span className="dash-list-title">Why has growth flatlined?</span>
                    <span className="dash-list-sub">Retention - 12 messages - 92% confidence</span>
                  </span>
                  <span className="dash-list-meta">Today</span>
                </button>
                <button className="dash-list-row" type="button" onClick={() => navigate('/app/ally-chat')}>
                  <span className="dash-list-ic"><IconChat /></span>
                  <span className="dash-list-body">
                    <span className="dash-list-title">Is our pricing the problem?</span>
                    <span className="dash-list-sub">Pricing - ruled out - 8 messages</span>
                  </span>
                  <span className="dash-list-meta">2d ago</span>
                </button>
                <button className="dash-list-row" type="button" onClick={() => navigate('/app/ally-chat')}>
                  <span className="dash-list-ic"><IconChat /></span>
                  <span className="dash-list-body">
                    <span className="dash-list-title">Should I raise or extend runway?</span>
                    <span className="dash-list-sub">Cash flow - 6 messages</span>
                  </span>
                  <span className="dash-list-meta">5d ago</span>
                </button>
              </div>
            </section>

            <section className="dash-section">
              <div className="dash-section-head">
                <div className="dash-section-title">Upcoming discovery call</div>
              </div>
              <div className="dash-call">
                <div className="dash-call-kicker">Confirmed - 30 min</div>
                <div className="dash-call-row">
                  <div className="dash-call-date">
                    <b>14</b>
                    <span>JUL</span>
                  </div>
                  <div className="dash-call-copy">
                    <div className="dash-call-title">Founder strategy session</div>
                    <div className="dash-call-sub">Thu - 4:30 PM IST - with a GoXL advisor</div>
                  </div>
                </div>
                <button className="btn btn-ghost dash-call-btn" type="button">
                  Manage booking
                </button>
              </div>
            </section>
          </div>

          <div className="dash-stack">
            <section className="dash-section dash-plan">
              <div className="dash-plan-top">
                <div>
                  <div className="dash-kicker">Your plan</div>
                  <div className="dash-plan-title">Ally Free</div>
                </div>
                <span className="dash-badge small">Ally Free</span>
              </div>
              <div className="dash-plan-row">
                <span>Billing</span>
                <b>Free forever</b>
              </div>
              <div className="dash-meter">
                <div>
                  <div className="dash-meter-row">
                    <span>AI Chat with Ally</span>
                    <b>18 / 20</b>
                  </div>
                  <div className="dash-meter-bar"><i style={{ width: '90%' }} /></div>
                </div>
                <div>
                  <div className="dash-meter-row">
                    <span>AI Business Diagnosis</span>
                    <b>1 / 1</b>
                  </div>
                  <div className="dash-meter-bar"><i style={{ width: '100%' }} /></div>
                </div>
                <div>
                  <div className="dash-meter-row">
                    <span>Document Analysis</span>
                    <b><span className="dash-upgrade">Upgrade to Pro</span></b>
                  </div>
                </div>
              </div>
              <div className="dash-plan-actions">
                <button className="btn btn-em" type="button" onClick={() => navigate('/app/billing')}>
                  <IconArrowRight />
                  Upgrade
                </button>
                <button className="btn btn-ghost" type="button">
                  Manage
                </button>
              </div>
            </section>

            <section className="dash-section">
              <div className="dash-section-head">
                <div className="dash-section-title">Recent reports</div>
                <button className="dash-link" type="button">All <IconArrowRight /></button>
              </div>
              <div className="dash-list reports">
                <button className="dash-list-row report" type="button" onClick={() => navigate('/app/report')}>
                  <span className="dash-list-ic soft"><IconDocument /></span>
                  <span className="dash-list-body">
                    <span className="dash-list-title">Growth & retention diagnosis</span>
                    <span className="dash-list-sub">10 dimensions - 3 priority actions</span>
                  </span>
                  <span className="dash-list-score">74</span>
                </button>
                <button className="dash-list-row report" type="button" onClick={() => navigate('/app/report')}>
                  <span className="dash-list-ic soft"><IconDocument /></span>
                  <span className="dash-list-body">
                    <span className="dash-list-title">Sales pipeline audit</span>
                    <span className="dash-list-sub">6 dimensions - 2 priority actions</span>
                  </span>
                  <span className="dash-list-score">68</span>
                </button>
                <button className="dash-list-row report" type="button" onClick={() => navigate('/app/report')}>
                  <span className="dash-list-ic soft"><IconDocument /></span>
                  <span className="dash-list-body">
                    <span className="dash-list-title">Team and hiring clarity</span>
                    <span className="dash-list-sub">4 dimensions - 3 priority actions</span>
                  </span>
                  <span className="dash-list-score">61</span>
                </button>
              </div>
            </section>
          </div>
        </section>

        <section className="dash-unlock">
          <div className="dash-section-head">
            <div className="dash-section-title">Unlock more with Ally</div>
            <button className="dash-link" type="button">See plans <IconArrowRight /></button>
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
    </div>
  );
}

