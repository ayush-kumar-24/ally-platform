import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';

const INITIAL_ACTIVE = [
  {
    id: 'act-1',
    text: 'Finish the landing page',
    priority: 'high',
    time: '11:00 AM',
    duration: '45 mins'
  },
  {
    id: 'act-2',
    text: 'Review pricing strategy',
    priority: 'medium',
    time: '2:00 PM',
    duration: '30 mins'
  },
  {
    id: 'act-3',
    text: 'Draft the Q3 roadmap',
    priority: 'medium',
    time: '4:00 PM',
    duration: '1 hr'
  }
];

const INITIAL_COMPLETED = [
  {
    id: 'done-1',
    text: 'Reply to the investor update',
    time: '9:52 AM'
  },
  {
    id: 'done-2',
    text: 'Team standup',
    time: '10:18 AM'
  },
  {
    id: 'done-3',
    text: 'Ship pricing page copy',
    time: '8:38 AM'
  }
];

const CHIP_SUGGESTIONS = [
  'Investor meeting at 10',
  'Finish the pitch deck',
  'Call Rahul',
  'Review CAC',
  'Book hotel'
];

export default function PlanYourDay() {
  const { user } = useApp();
  const [activeTab, setActiveTab] = useState('ally');
  const [inputText, setInputText] = useState('');
  const [activeGoals, setActiveGoals] = useState(INITIAL_ACTIVE);
  const [completedGoals, setCompletedGoals] = useState(INITIAL_COMPLETED);

  const [dateString, setDateString] = useState('');

  useEffect(() => {
    // Format: Tuesday, July 14
    const options = { weekday: 'long', month: 'long', day: 'numeric' };
    setDateString(new Date().toLocaleDateString('en-US', options));
  }, []);

  const handleToggleActive = (goal) => {
    setActiveGoals(prev => prev.filter(g => g.id !== goal.id));
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const formattedTime = `${hours % 12 || 12}:${minutes < 10 ? '0' : ''}${minutes} ${ampm}`;
    setCompletedGoals(prev => [
      ...prev,
      { id: goal.id, text: goal.text, time: formattedTime }
    ]);
  };

  const handleToggleCompleted = (goal) => {
    setCompletedGoals(prev => prev.filter(g => g.id !== goal.id));
    setActiveGoals(prev => [
      ...prev,
      {
        id: goal.id,
        text: goal.text,
        priority: 'medium',
        time: '5:00 PM',
        duration: '30 mins'
      }
    ]);
  };

  const handlePlanMyDay = () => {
    if (!inputText.trim()) return;
    const newGoal = {
      id: `custom-${Date.now()}`,
      text: inputText.trim(),
      priority: 'high',
      time: '12:00 PM',
      duration: '30 mins'
    };
    setActiveGoals(prev => [newGoal, ...prev]);
    setInputText('');
  };

  const handleChipClick = (chip) => {
    setInputText(prev => (prev ? `${prev}, ${chip}` : chip));
  };

  const totalGoals = activeGoals.length + completedGoals.length;
  const completionPct = totalGoals > 0 ? Math.round((completedGoals.length / totalGoals) * 100) : 0;
  const strokeDashoffset = 308 - (completionPct / 100) * 308;

  const nextReminder = activeGoals.length > 0 ? activeGoals[0] : null;
  const firstName = (user?.name || 'Ayush Sharma').split(' ')[0];

  return (
    <div className="pad plan-wrap">
      {/* Salutation Header */}
      <div className="plan-head stagger d1">
        <div style={{ textSelf: 'flex-start' }}>
          <div className="pl-input-hint" style={{ fontSize: '15px', fontWeight: 650, color: '#b7895f', marginBottom: '8px' }}>
            Good evening, {firstName} 👋
          </div>
          <h1 className="plan-title" style={{ fontFamily: 'var(--display)', fontSize: '32px', fontWeight: 800, color: 'var(--forest, #1b4332)', margin: '0 0 6px' }}>Plan Your Day</h1>
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

      {/* Mode selection tabs */}
      <div className="pl-tabs stagger d2" style={{ marginTop: 24 }}>
        <div
          className={`pl-tab ${activeTab === 'ally' ? 'active' : ''}`}
          onClick={() => setActiveTab('ally')}
        >
          <div className="pl-tab-ic">
            <svg viewBox="0 0 24 24">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div className="pl-tab-content">
            <span className="pl-tab-title">Plan with Ally</span>
            <span className="pl-tab-desc">Just talk — I'll organize it.</span>
          </div>
        </div>

        <div
          className={`pl-tab ${activeTab === 'manual' ? 'active' : ''}`}
          onClick={() => setActiveTab('manual')}
        >
          <div className="pl-tab-ic">
            <svg viewBox="0 0 24 24">
              <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          </div>
          <div className="pl-tab-content">
            <span className="pl-tab-title">Plan manually</span>
            <span className="pl-tab-desc">Create tasks yourself.</span>
          </div>
        </div>
      </div>

      {/* Content wrapper */}
      <div className="plan-grid stagger d3">
        <div className="plan-main">
          {/* Ask Ally card */}
          {activeTab === 'ally' ? (
            <div className="pl-input-card">
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

              <textarea
                className="pl-textarea"
                placeholder="e.g. Investor meeting at 10, finish the pitch deck, call Rahul, review CAC..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handlePlanMyDay())}
              />

              <div className="pl-chips">
                {CHIP_SUGGESTIONS.map((chip, idx) => (
                  <button
                    key={idx}
                    className="pl-chip-btn"
                    onClick={() => handleChipClick(chip)}
                  >
                    {chip}
                  </button>
                ))}
              </div>

              <div className="pl-input-footer">
                <div className="pl-input-hint">
                  <span className="dot" />
                  I'll sort priority, time & grouping.
                </div>
                <button className="pl-plan-btn" onClick={handlePlanMyDay}>
                  Plan my day
                </button>
              </div>
            </div>
          ) : (
            <div className="pl-input-card" style={{ gap: '12px' }}>
              <div className="pl-input-header">
                <span className="pl-input-title">Add task manually</span>
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <input
                  type="text"
                  className="pl-textarea"
                  style={{ minHeight: 'auto', height: '40px', padding: '0 12px' }}
                  placeholder="Task description..."
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handlePlanMyDay()}
                />
                <button
                  className="pl-plan-btn"
                  style={{ height: '40px', padding: '0 20px', flexShrink: 0 }}
                  onClick={handlePlanMyDay}
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
            {activeGoals.length === 0 ? (
              <div className="plan-empty" style={{ background: '#ffffff', padding: '24px', borderRadius: '14px', border: '1px solid var(--bd)' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 4px' }}>All caught up!</h3>
                <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>No active tasks remaining for today.</p>
              </div>
            ) : (
              activeGoals.map((goal) => (
                <div key={goal.id} className="pl-goal-row">
                  <button
                    className="pl-checkbox"
                    onClick={() => handleToggleActive(goal)}
                  >
                    <svg viewBox="0 0 12 12">
                      <polyline points="2 6 5 9 10 3" />
                    </svg>
                  </button>
                  <div className="pl-goal-content">
                    <h4 className="pl-goal-title">{goal.text}</h4>
                    <div className="pl-goal-badges">
                      <span className={`pl-badge ${goal.priority}`}>
                        {goal.priority}
                      </span>
                      <span className="pl-meta-item">
                        <svg viewBox="0 0 24 24">
                          <circle cx="12" cy="12" r="10" />
                          <polyline points="12 6 12 12 16 14" />
                        </svg>
                        {goal.time}
                      </span>
                      <span className="pl-meta-item">
                        <svg viewBox="0 0 24 24">
                          <circle cx="12" cy="12" r="10" />
                          <line x1="8" y1="12" x2="16" y2="12" />
                        </svg>
                        {goal.duration}
                      </span>
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
              completedGoals.map((goal) => (
                <div
                  key={goal.id}
                  className="pl-completed-row"
                  onClick={() => handleToggleCompleted(goal)}
                  style={{ cursor: 'pointer' }}
                >
                  <div className="pl-checkbox">
                    <svg viewBox="0 0 12 12">
                      <polyline points="2 6 5 9 10 3" />
                    </svg>
                  </div>
                  <div className="pl-completed-content">
                    <h4 className="pl-completed-title">{goal.text}</h4>
                    <span className="pl-completed-time">
                      Completed at {goal.time}
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
            <defs>
              <linearGradient id="plGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#10B981" />
                <stop offset="100%" stopColor="#A8D94A" />
              </linearGradient>
            </defs>
            <div className="pl-prog-title">Today's progress</div>

            <div className="pl-prog-ring">
              <svg viewBox="0 0 110 110">
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

          {/* Upcoming Reminder Card */}
          <div className="pl-reminder-kicker">Upcoming reminder</div>
          <div className="pl-reminder-card">
            <div className="pl-reminder-ic">
              <svg viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <div className="pl-reminder-content">
              <span className="pl-reminder-time">
                {nextReminder ? nextReminder.time : '--:--'}
              </span>
              <span className="pl-reminder-title">
                {nextReminder ? nextReminder.text : 'No upcoming goals'}
              </span>
            </div>
          </div>
          <p className="pl-reminder-hint">
            Reminder notifications will appear here.
          </p>

          {/* Daily Motivation Card */}
          <div
            className="pl-reminder-kicker"
            style={{ fontSize: '10px', color: 'var(--emerald-dark)' }}
          >
            Daily motivation
          </div>
          <div className="pl-motiv-card">
            <div className="pl-reminder-ic" style={{ background: 'rgba(16, 185, 129, 0.12)' }}>
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
              >
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
            </div>
            <div>
              <div className="pl-motiv-kicker">Daily Motivation</div>
              <p className="pl-motiv-text">Complete the hardest task first.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
