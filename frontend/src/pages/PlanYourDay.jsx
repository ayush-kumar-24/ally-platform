import { useState, useEffect, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import PlanGate from '../components/PlanGate';
import { FEATURES } from '../services/plans';
import { addTask, listTasks, setTaskStatus } from '../services/planning';
import { ApiError } from '../services/api';
import { greetingNow } from '../utils/helpers';

/* There were five suggestion chips here -- "Investor meeting at 10", "Call
   Rahul", "Review CAC" and so on. They were somebody's imagined day, and
   "Rahul" was the mock founder's name. Prefilling a founder's plan with
   invented tasks is the opposite of asking them what their day holds. */

const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };
const sortByPriority = (tasks) =>
  [...tasks].sort((a, b) => (PRIORITY_RANK[a.priority] ?? 1) - (PRIORITY_RANK[b.priority] ?? 1));

function completedAtLabel(task) {
  if (!task.completed_at) return '';
  return new Date(task.completed_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

/** "Today" / "Overdue" / "12 Aug" — a due date read the way a person reads it. */
function dueLabel(task) {
  if (!task?.due_date) return '';
  const today = new Date().toISOString().slice(0, 10);
  if (task.due_date === today) return 'Today';
  if (task.due_date < today) return 'Overdue';
  return new Date(`${task.due_date}T00:00:00`).toLocaleDateString(undefined, {
    day: 'numeric', month: 'short',
  });
}

function PlanYourDayInner() {
  const { user, showToast } = useApp();
  const [activeTab, setActiveTab] = useState('ally');
  const [inputText, setInputText] = useState('');
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [dateString, setDateString] = useState('');

  useEffect(() => {
    const options = { weekday: 'long', month: 'long', day: 'numeric' };
    setDateString(new Date().toLocaleDateString('en-US', options));
  }, []);

  const refresh = useCallback(async () => {
    try {
      const items = await listTasks();
      setTasks(items);
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : 'Could not load your tasks — please refresh.');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { refresh(); }, [refresh]);

  const activeGoals = sortByPriority(tasks.filter(t => t.status !== 'done'));
  const completedGoals = tasks.filter(t => t.status === 'done');

  const handleToggleActive = async (task) => {
    // Optimistic: flip locally first so the checkbox feels instant, reconcile
    // (or roll back) once the request actually resolves.
    setTasks(prev => prev.map(t => (t.task_id === task.task_id ? { ...t, status: 'done' } : t)));
    try {
      await setTaskStatus(task.task_id, 'done');
      refresh(); // pick up the real completed_at stamp
    } catch (err) {
      setTasks(prev => prev.map(t => (t.task_id === task.task_id ? task : t))); // roll back
      showToast(err instanceof ApiError ? err.detail : 'Could not mark that task done — please try again.');
    }
  };

  const handleToggleCompleted = async (task) => {
    setTasks(prev => prev.map(t => (t.task_id === task.task_id ? { ...t, status: 'todo' } : t)));
    try {
      await setTaskStatus(task.task_id, 'todo');
    } catch (err) {
      setTasks(prev => prev.map(t => (t.task_id === task.task_id ? task : t)));
      showToast(err instanceof ApiError ? err.detail : 'Could not reopen that task — please try again.');
    }
  };

  const handlePlanMyDay = async () => {
    const text = inputText.trim();
    if (!text || submitting) return;
    setSubmitting(true);
    setInputText('');
    try {
      // "Plan with Ally" accepts a comma-separated brain-dump and turns each
      // phrase into its own task -- deterministic splitting, not AI parsing;
      // it doesn't infer times or durations, only what's actually in the text.
      const titles = activeTab === 'ally'
        ? text.split(',').map(s => s.trim()).filter(Boolean)
        : [text];
      for (const title of titles) {
        await addTask(title, { priority: 'medium' });
      }
      await refresh();
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : 'Could not add that task — please try again.');
      setInputText(text); // give it back so nothing typed is lost
    } finally {
      setSubmitting(false);
    }
  };

  const totalGoals = tasks.length;
  const completionPct = totalGoals > 0 ? Math.round((completedGoals.length / totalGoals) * 100) : 0;
  const strokeDashoffset = 308 - (completionPct / 100) * 308;

  /* Genuinely the soonest due task. This used to fall back to activeGoals[0] --
     an arbitrary task with no due date at all -- under a "reminder" heading. */
  const nextReminder = activeGoals
    .filter(t => t.due_date)
    .sort((a, b) => String(a.due_date).localeCompare(String(b.due_date)))[0] || null;
  const firstName = (user?.name || 'there').split(' ')[0];

  return (
    <div className="pad plan-wrap">
      {/* Salutation Header */}
      <div className="plan-head stagger d1">
        <div style={{ textSelf: 'flex-start' }}>
          <div className="pl-input-hint" style={{ fontSize: '15px', fontWeight: 650, color: '#b7895f', marginBottom: '8px' }}>
            {/* Was hardcoded "Good evening" — shown to everyone, all day.
                Dashboard.jsx already uses the shared helper. */}
            {greetingNow()}, {firstName} 👋
          </div>
          {/* Demoted from h1: PlatformLayout's topbar already renders an h1 for
              every /app/* route, so this made two per page. */}
          <h2 className="plan-title" style={{ fontFamily: 'var(--display)', fontSize: '32px', fontWeight: 800, color: 'var(--forest, #1b4332)', margin: '0 0 6px' }}>Plan Your Day</h2>
          <p className="plan-sub" style={{ fontFamily: 'var(--body)', fontSize: '13.5px', color: 'var(--muted, #556458)', margin: 0 }}>
            Set today's priorities. Ally will keep you accountable and remind you to stay on track.
          </p>
        </div>
        <div
          className="plan-date"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            background: '#ffffff',
            border: '1px solid var(--bd, #e7e0d6)',
            borderRadius: '10px',
            padding: '8px 14px',
            fontSize: '12.5px',
            fontWeight: 700,
            color: 'var(--forest, #1B4332)',
            height: 'fit-content'
          }}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            style={{ width: 14, height: 14 }}
          >
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          {dateString}
        </div>
      </div>

      {/* Mode selection tabs.

          These were click-only <div>s: not focusable, no role, no key handler.
          The manual-task path was the only way to add a task by typing, and a
          keyboard user could never reach it. Real <button>s in a tablist, with
          arrow keys and a roving tabindex. */}
      <div className="pl-tabs stagger d2" style={{ marginTop: 24 }} role="tablist" aria-label="Planning mode">
        <button
          type="button"
          role="tab"
          id="pl-tab-ally"
          aria-selected={activeTab === 'ally'}
          aria-controls="pl-panel-ally"
          tabIndex={activeTab === 'ally' ? 0 : -1}
          className={`pl-tab ${activeTab === 'ally' ? 'active' : ''}`}
          onClick={() => setActiveTab('ally')}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
              e.preventDefault();
              setActiveTab('manual');
              document.getElementById('pl-tab-manual')?.focus();
            }
          }}
        >
          <div className="pl-tab-ic">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div className="pl-tab-content">
            <span className="pl-tab-title">Plan with Ally</span>
            <span className="pl-tab-desc">Just talk — I'll organize it.</span>
          </div>
        </button>

        <button
          type="button"
          role="tab"
          id="pl-tab-manual"
          aria-selected={activeTab === 'manual'}
          aria-controls="pl-panel-manual"
          tabIndex={activeTab === 'manual' ? 0 : -1}
          className={`pl-tab ${activeTab === 'manual' ? 'active' : ''}`}
          onClick={() => setActiveTab('manual')}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
              e.preventDefault();
              setActiveTab('ally');
              document.getElementById('pl-tab-ally')?.focus();
            }
          }}
        >
          <div className="pl-tab-ic">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          </div>
          <div className="pl-tab-content">
            <span className="pl-tab-title">Plan manually</span>
            <span className="pl-tab-desc">Create tasks yourself.</span>
          </div>
        </button>
      </div>

      {/* Content wrapper */}
      <div className="plan-grid stagger d3">
        <div className="plan-main">
          {/* Ask Ally card */}
          {activeTab === 'ally' ? (
            <div className="pl-input-card" id="pl-panel-ally" role="tabpanel" aria-labelledby="pl-tab-ally">
              <div className="pl-input-header">
                <div className="pl-input-avatar">
                  <svg viewBox="0 0 24 24">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </div>
                <div className="pl-input-header-text">
                  <span className="pl-input-title">
                    Tell me about your day, {firstName}.
                  </span>
                  <span className="pl-input-subtitle">
                    Meetings, calls, deadlines — however it comes to you.
                  </span>
                </div>
              </div>

              <label className="sr-only" htmlFor="pl-day">Tell Ally about your day</label>
              <textarea
                id="pl-day"
                className="pl-textarea"
                placeholder="Whatever's on your plate today…"
                value={inputText}
                disabled={submitting}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handlePlanMyDay())}
              />

              <div className="pl-input-footer">
                <div className="pl-input-hint">
                  <span className="dot" />
                  Comma-separate a few things and I'll add them as separate tasks.
                </div>
                <button className="pl-plan-btn" onClick={handlePlanMyDay} disabled={submitting}>
                  Plan my day
                </button>
              </div>
            </div>
          ) : (
            <div className="pl-input-card" style={{ gap: '12px' }} id="pl-panel-manual" role="tabpanel" aria-labelledby="pl-tab-manual">
              <div className="pl-input-header">
                <span className="pl-input-title">Add task manually</span>
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <label className="sr-only" htmlFor="pl-manual-task">Task description</label>
                <input
                  id="pl-manual-task"
                  type="text"
                  className="pl-textarea"
                  style={{ minHeight: 'auto', height: '40px', padding: '0 12px' }}
                  placeholder="Task description..."
                  value={inputText}
                  disabled={submitting}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handlePlanMyDay()}
                />
                <button
                  className="pl-plan-btn"
                  style={{ height: '40px', padding: '0 20px', flexShrink: 0 }}
                  onClick={handlePlanMyDay}
                  disabled={submitting}
                >
                  Add task
                </button>
              </div>
            </div>
          )}

          {/* Today's goals list */}
          <div className="sec-row">
            <div className="sec-title" style={{ fontSize: '15px', fontWeight: 750 }}>
              Today's goals
            </div>
            <div className="plan-count" style={{ fontSize: '12px', color: 'var(--muted-2)' }}>
              {activeGoals.length} to do
            </div>
          </div>

          <div className="pl-goal-list" style={{ marginBottom: 32 }}>
            {loading ? (
              <div className="plan-empty" style={{ background: '#ffffff', padding: '24px', borderRadius: '14px', border: '1px solid var(--bd)' }}>
                <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>Loading your tasks…</p>
              </div>
            ) : activeGoals.length === 0 ? (
              /* "All caught up!" was shown to everyone with nothing active --
                 including a founder opening this page for the very first time,
                 who has not caught up on anything. */
              <div className="plan-empty" style={{ background: '#ffffff', padding: '24px', borderRadius: '14px', border: '1px solid var(--bd)' }}>
                {tasks.length === 0 ? (
                  <>
                    <h3 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 4px' }}>Nothing planned yet.</h3>
                    <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>
                      Tell Ally what your day holds and it'll break it into tasks.
                    </p>
                  </>
                ) : (
                  <>
                    <h3 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 4px' }}>All caught up.</h3>
                    <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>
                      Nothing left on today's list.
                    </p>
                  </>
                )}
              </div>
            ) : (
              activeGoals.map((task) => (
                <div key={task.task_id} className="pl-goal-row">
                  <button
                    className="pl-checkbox"
                    type="button"
                    role="checkbox"
                    aria-checked="false"
                    aria-label={`Mark "${task.title}" as done`}
                    onClick={() => handleToggleActive(task)}
                  >
                    <svg viewBox="0 0 12 12" aria-hidden="true">
                      <polyline points="2 6 5 9 10 3" />
                    </svg>
                  </button>
                  <div className="pl-goal-content">
                    <h4 className="pl-goal-title">{task.title}</h4>
                    <div className="pl-goal-badges">
                      <span className={`pl-badge ${task.priority}`}>
                        {task.priority}
                      </span>
                      {task.due_date && (
                        <span className="pl-meta-item">
                          <svg viewBox="0 0 24 24">
                            <circle cx="12" cy="12" r="10" />
                            <polyline points="12 6 12 12 16 14" />
                          </svg>
                          due {task.due_date}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Completed goals list */}
          <div className="sec-row">
            <div className="sec-title" style={{ fontSize: '15px', fontWeight: 750 }}>
              Completed today
            </div>
            <div className="plan-count" style={{ fontSize: '12px', color: 'var(--muted-2)' }}>
              {completedGoals.length} done
            </div>
          </div>

          <div className="pl-completed-list">
            {completedGoals.length === 0 ? (
              <div className="plan-empty" style={{ background: 'transparent', padding: '16px', border: '1.5px dashed var(--bd)', borderRadius: '12px', textAlign: 'center' }}>
                <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>No tasks completed yet. Start checking off goals!</p>
              </div>
            ) : (
              // Was a plain div with onClick: un-completing a task was
              // mouse-only, unreachable by keyboard and invisible to screen
              // readers.
              completedGoals.map((task) => (
                <div
                  key={task.task_id}
                  className="pl-completed-row"
                  role="checkbox"
                  aria-checked="true"
                  aria-label={`Mark "${task.title}" as not done`}
                  tabIndex={0}
                  onClick={() => handleToggleCompleted(task)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleToggleCompleted(task);
                    }
                  }}
                  style={{ cursor: 'pointer' }}
                >
                  <div className="pl-checkbox" aria-hidden="true">
                    <svg viewBox="0 0 12 12">
                      <polyline points="2 6 5 9 10 3" />
                    </svg>
                  </div>
                  <div className="pl-completed-content">
                    <h4 className="pl-completed-title">{task.title}</h4>
                    <span className="pl-completed-time">
                      Completed{completedAtLabel(task) ? ` at ${completedAtLabel(task)}` : ''}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right side panel */}
        <div className="plan-aside">
          {/* Progress Card */}
          <div className="pl-prog-card">
            <div className="pl-prog-title">Today's progress</div>

            <div className="pl-prog-ring">
              <svg viewBox="0 0 110 110">
                {/* plan.css references stroke: url(#plGrad) on .fg -- the
                    gradient must live inside an <svg> to render at all (it
                    was previously a bare <defs> outside any svg, which React
                    can't mount and the browser can't resolve). */}
                <defs>
                  <linearGradient id="plGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#10B981" />
                    <stop offset="100%" stopColor="#A8D94A" />
                  </linearGradient>
                </defs>
                <circle className="bg" cx="55" cy="55" r="49" />
                <circle
                  className="fg"
                  cx="55"
                  cy="55"
                  r="49"
                  style={{ strokeDashoffset }}
                />
              </svg>
              <div className="pl-prog-ring-c">
                <b>
                  {completionPct}
                  <span>%</span>
                </b>
                <small>Done</small>
              </div>
            </div>

            <div className="pl-prog-stats">
              <b>{totalGoals}</b> goals
              <span
                style={{
                  width: '4px',
                  height: '4px',
                  borderRadius: '50%',
                  background: '#6c7a70'
                }}
              />
              <b>{completedGoals.length}</b> completed
            </div>

            <div className="pl-prog-footer">
              <span className="dot" />
              {completionPct >= 100
                ? "Excellent! You've crushed all targets today."
                : completionPct >= 50
                ? "You're halfway there. Keep going."
                : 'Start your engine. Let us get to work.'}
            </div>
          </div>

          {/* Only shown when something is actually scheduled. It used to render
              regardless, with "--:--" and "No upcoming goals" under a heading
              that promised a reminder. */}
          {nextReminder && (
            <>
              <div className="pl-reminder-kicker">Next due</div>
              <div className="pl-reminder-card">
                <div className="pl-reminder-ic">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                </div>
                <div className="pl-reminder-content">
                  <span className="pl-reminder-time">{dueLabel(nextReminder)}</span>
                  <span className="pl-reminder-title">{nextReminder.title}</span>
                </div>
              </div>
              <p className="pl-reminder-hint">
                Ally nudges you about overdue or due-today tasks while you're in the app.
              </p>
            </>
          )}

          {/* A "Daily Motivation" card sat here reading "Complete the hardest
              task first." -- the same sentence for every founder, every day,
              forever. Labelling a constant "daily" is the giveaway. */}
        </div>
      </div>
    </div>
  );
}


/**
 * Plan Your Day is a paid feature (Starter and above). The gate here is a
 * courtesy so a Free founder sees an explanation instead of a broken page.
 *
 * The enforcement is `require_plan_your_day`, applied to the whole /planning
 * router, which answers 403 to a free founder. That is the check that counts:
 * this component decides what to render, not who may call the API. Keep both --
 * removing the gate below only makes the page ugly, but trusting it as the sole
 * control is how the paywall was open with this comment claiming otherwise.
 */
export default function PlanYourDay() {
  return (
    <PlanGate
      feature={FEATURES.PLAN_YOUR_DAY}
      requiredPlan="Starter"
      title="Plan Your Day is a Starter feature"
      message="Upgrade to Starter to turn Ally's next steps into a daily plan."
    >
      <PlanYourDayInner />
    </PlanGate>
  );
}
