import { useState, useEffect, useCallback, useRef } from 'react';
import { useApp } from '../context/AppContext';
import PlanGate from '../components/PlanGate';
import { FEATURES } from '../services/plans';
import { addTask, deleteTask, listTasks, setTaskStatus, updateTask } from '../services/planning';
import { ApiError } from '../services/api';
import { greetingNow } from '../utils/helpers';
import MonthCalendar from '../components/MonthCalendar';
import { todayKey } from '../utils/dateKeys';
import CalendarConnection from '../components/CalendarConnection';
import { SYNC_LABELS } from '../services/calendar';

/**
 * How a task's calendar state reads to the founder.
 *
 * Renders nothing for 'skipped', which is the normal state for a dateless task
 * or a founder with no calendar connected -- badging that would invent a
 * problem. 'failed' is the one that matters: without it a founder walks away
 * believing a reminder is set when none is.
 */
function SyncBadge({ status }) {
  const meta = SYNC_LABELS[status];
  if (!meta) return null;
  return <span className={`pl-sync pl-sync-${meta.tone}`}>{meta.label}</span>;
}

/* There were five suggestion chips here -- "Investor meeting at 10", "Call
   Rahul", "Review CAC" and so on. They were somebody's imagined day, and
   "Rahul" was the mock founder's name. Prefilling a founder's plan with
   invented tasks is the opposite of asking them what their day holds. */

/** Longest task title the API accepts -- planning/schemas.py caps `title` at
 *  200 characters. Mirrored here so an over-long entry is caught before it is
 *  sent, rather than coming back as a 422 the founder has to interpret.
 *
 *  Deliberately NOT a `maxLength` on the textarea: the cap is per TASK, and
 *  "Plan with Ally" splits on commas, so three 90-character items are a
 *  perfectly valid 280-character box. Capping the box would block that. */
const TASK_TITLE_MAX = 200;

/** The titles a given box of text would become -- comma-split for the Ally
 *  tab, the whole string for manual add. Shared by the submit handler and the
 *  live over-length hint so the two can never disagree about the split. */
const titlesFrom = (text, activeTab) =>
  activeTab === 'ally'
    ? text.split(',').map(s => s.trim()).filter(Boolean)
    : [text.trim()].filter(Boolean);

const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };
const sortByPriority = (tasks) =>
  [...tasks].sort((a, b) => (PRIORITY_RANK[a.priority] ?? 1) - (PRIORITY_RANK[b.priority] ?? 1));

function completedAtLabel(task) {
  if (!task.completed_at) return '';
  return new Date(task.completed_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

/** "i need to review the website" -> "I need to review the website". Titles
 * are stored exactly as typed (no forced casing at the API layer, so a
 * founder's own capitalization choices are never silently overwritten) --
 * this only affects how they're displayed, sitting next to the all-caps
 * priority badge which otherwise makes an un-capitalized title look broken
 * rather than just informal. */
function displayTitle(title) {
  if (!title) return title;
  return title.charAt(0).toUpperCase() + title.slice(1);
}

/** UTC calendar day, matching the convention dueLabel() above already uses
 * for due_date comparisons -- not the founder's local timezone, but
 * consistent with the rest of this file rather than a one-off exception. */
function isToday(isoTimestamp) {
  if (!isoTimestamp) return false;
  return isoTimestamp.slice(0, 10) === new Date().toISOString().slice(0, 10);
}

/** "3 Aug" -- a past day read the way a person reads it, for grouping the
 * completed-history list. */
function dayLabel(isoTimestamp) {
  return new Date(isoTimestamp).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
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

/** The "⋯" menu on every task row -- previously there was no way to edit a
 * typo or change priority after creation, and no way to remove a task at
 * all short of directly editing the database. */
function TaskMenu({ onEdit, onDelete }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div className="pl-task-menu" ref={ref} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        className="pl-task-menu-btn"
        aria-label="Task options"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="5" r="1.8" />
          <circle cx="12" cy="12" r="1.8" />
          <circle cx="12" cy="19" r="1.8" />
        </svg>
      </button>
      {open && (
        <div className="pl-task-menu-list" role="menu">
          <button type="button" role="menuitem" onClick={() => { setOpen(false); onEdit(); }}>
            Edit
          </button>
          <button
            type="button"
            role="menuitem"
            className="danger"
            onClick={() => { setOpen(false); onDelete(); }}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}

/** Replaces a task row in place while editing -- title + priority, the same
 * two fields the manual-add form takes, so editing isn't a different,
 * smaller feature than creating. */
function TaskEditForm({ task, onSave, onCancel, saving }) {
  const [title, setTitle] = useState(task.title);
  const [priority, setPriority] = useState(task.priority);
  const canSave = title.trim().length > 0;

  return (
    <div className="pl-edit-row">
      <label className="sr-only" htmlFor={`pl-edit-${task.task_id}`}>Task description</label>
      <input
        id={`pl-edit-${task.task_id}`}
        type="text"
        className="pl-textarea"
        style={{ minHeight: 'auto', height: '36px', padding: '0 10px', flex: 1 }}
        value={title}
        disabled={saving}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && canSave && onSave({ title: title.trim(), priority })}
        autoFocus
      />
      <div role="radiogroup" aria-label="Priority" className="pl-priority-picker">
        {['low', 'medium', 'high'].map((p) => (
          <button
            key={p}
            type="button"
            role="radio"
            aria-checked={priority === p}
            className={`pl-priority-opt ${p}${priority === p ? ' active' : ''}`}
            disabled={saving}
            onClick={() => setPriority(p)}
          >
            {p}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="pl-plan-btn"
        style={{ height: '36px', padding: '0 14px' }}
        disabled={saving || !canSave}
        onClick={() => onSave({ title: title.trim(), priority })}
      >
        {saving && <span className="pl-spinner" aria-hidden="true" />}
        {saving ? 'Saving…' : 'Save'}
      </button>
      <button type="button" className="pl-edit-cancel" onClick={onCancel} disabled={saving}>
        Cancel
      </button>
    </div>
  );
}

function PlanYourDayInner() {
  const { user, showToast } = useApp();
  const [activeTab, setActiveTab] = useState('ally');
  const [inputText, setInputText] = useState('');
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  // Only the manual-add tab exposes this -- "Plan with Ally" is a quick
  // brain-dump (deterministic comma-splitting, not AI parsing, see the note
  // on handlePlanMyDay below), so it always defaults to medium rather than
  // asking the founder to configure something on a "just talk" path. Every
  // task used to be created medium with no way to set anything else.
  const [manualPriority, setManualPriority] = useState('medium');
  /* The date a new task gets, and which day the list below is filtered to --
     one piece of state, because "the day I'm looking at" and "the day I'm
     adding to" being different is exactly the confusion a calendar should
     remove. Defaults to today so the page opens on the founder's actual day. */
  const [selectedDate, setSelectedDate] = useState(todayKey);
  const [manualTime, setManualTime] = useState('');
  const [calendarConnected, setCalendarConnected] = useState(false);
  /* Escape hatch from the day filter. Reset whenever the founder picks a
     different day -- "show everything" is a momentary override, and leaving
     it latched would silently disable the filter for the rest of the session. */
  const [showAllTasks, setShowAllTasks] = useState(false);
  const [editingTaskId, setEditingTaskId] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);

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

  const handleSaveEdit = async (task, { title, priority }) => {
    setSavingEdit(true);
    try {
      await updateTask(task.task_id, { title, priority });
      setEditingTaskId(null);
      await refresh();
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : 'Could not save changes — please try again.');
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDeleteTask = async (task) => {
    // No undo once this goes through -- confirm first rather than making a
    // stray click permanent.
    if (!window.confirm(`Delete "${displayTitle(task.title)}"? This can't be undone.`)) return;
    try {
      await deleteTask(task.task_id);
      await refresh();
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : 'Could not delete that task — please try again.');
    }
  };

  // Active tasks are never day-scoped -- an unfinished task carries forward
  // every day until it's done, rather than vanishing just because the date
  // changed (that's what a "founder needs to redo their whole list every
  // morning" bug would look like).
  const activeGoals = sortByPriority(tasks.filter(t => t.status !== 'done'));

  /* What the list shows for the day being viewed.
   *
   * The list used to be headed "Today's goals" and show every unfinished task
   * whatever its date, so selecting a day changed nothing visible -- a task
   * added to the 28th appeared instantly under a heading saying "Today's".
   * The one piece of feedback the founder got actively contradicted what had
   * just happened, which is why nobody could tell the calendar did anything.
   *
   * TODAY is deliberately not a strict equality match. The carry-forward rule
   * above is right: an overdue task must not vanish because the clock rolled
   * past midnight, and an undated task is still owed. So "today" means
   * everything still outstanding -- due today, overdue, or undated. Any other
   * day is that day exactly, because a past or future date is a question about
   * that day specifically, not about what is outstanding in general.
   */
  const viewingToday = selectedDate === todayKey();
  const dayGoals = showAllTasks ? activeGoals : activeGoals.filter((t) => (
    viewingToday ? (!t.due_date || t.due_date <= selectedDate)
                 : t.due_date === selectedDate
  ));
  const hiddenCount = activeGoals.length - dayGoals.length;

  /** "Today" / "Fri 28 Aug" -- used by the heading, the header chip and the
   *  add-task placeholder, so all three can never disagree again.
   *
   *  NOT named dayLabel: a module-level dayLabel() already formats completed-
   *  history timestamps, and shadowing it here would turn that call into an
   *  attempt to invoke a string. */
  const headerDateLabel = new Date(`${selectedDate}T00:00:00`)
    .toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

  const selectedDayLabel = viewingToday
    ? 'Today'
    : new Date(`${selectedDate}T00:00:00`).toLocaleDateString(undefined, {
        weekday: 'short', day: 'numeric', month: 'short' });
  const doneGoals = tasks.filter(t => t.status === 'done');
  // "Completed today" used to show every done task the founder has ever had
  // -- a task finished two weeks ago read as finished "today" forever, with
  // no way to tell the two apart. Actually scoped to today now.
  const completedGoals = doneGoals.filter(t => isToday(t.completed_at));
  // Everything else done, grouped by the day it was actually completed --
  // this is the only place a founder can see what they finished on a past
  // day; there was previously no such view at all. Keyed by ISO date (not
  // the display label) so groups sort chronologically regardless of the
  // order tasks came back in.
  const completedHistory = Object.entries(
    doneGoals
      // handleToggleActive optimistically flips status to 'done' before the
      // server responds with a real completed_at -- during that brief
      // window the task has status 'done' but completed_at is still null,
      // which crashed the .slice() below (reported live: marking a task
      // done threw "Something went wrong" every time). isToday(null) is
      // already false, so the plain !isToday filter let these through,
      // filter them out explicitly instead.
      .filter(t => t.completed_at && !isToday(t.completed_at))
      .reduce((groups, t) => {
        const isoDay = t.completed_at.slice(0, 10);
        (groups[isoDay] ||= []).push(t);
        return groups;
      }, {})
  ).sort(([a], [b]) => b.localeCompare(a)); // most recent day first

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

    // "Plan with Ally" accepts a comma-separated brain-dump and turns each
    // phrase into its own task -- deterministic splitting, not AI parsing;
    // it doesn't infer times or durations, only what's actually in the text.
    const titles = titlesFrom(text, activeTab);

    // Checked BEFORE anything is sent or the box is cleared. Reproduced live:
    // a founder who typed a paragraph with no commas in it produced one
    // 345-character title, the API rejected it with a 422, and what surfaced
    // was the raw Pydantic error. That specific leak is fixed server-side
    // (middleware/error_handler.py), but a founder should not have to make a
    // round trip to learn the thing is too long -- and the message they get
    // back cannot tell them the useful part, which is that commas are what
    // splits this into separate tasks.
    const tooLong = titles.find(t => t.length > TASK_TITLE_MAX);
    if (tooLong) {
      showToast(
        activeTab === 'ally'
          ? `That's ${tooLong.length} characters for one task — the limit is ${TASK_TITLE_MAX}. Separate your tasks with commas, or shorten it.`
          : `That's ${tooLong.length} characters — the limit is ${TASK_TITLE_MAX}. Try shortening it.`,
        6000,
      );
      return; // nothing sent, nothing cleared -- what they typed is still there
    }

    setSubmitting(true);
    setInputText('');
    try {
      // Manual add carries whatever the picker is set to; "Plan with Ally"
      // stays medium for every phrase -- it never asked which of several
      // brain-dumped items was more urgent than the others.
      const priority = activeTab === 'manual' ? manualPriority : 'medium';
      // Every task lands on the day being viewed. A brain-dump split into five
      // phrases all belongs to the same day -- that is what made it a dump.
      const dueDate = selectedDate || null;
      const dueTime = activeTab === 'manual' && manualTime ? `${manualTime}:00` : null;
      for (const title of titles) {
        await addTask(title, { priority, dueDate, dueTime });
      }
      setManualTime('');
      await refresh();
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : 'Could not add that task — please try again.');
      setInputText(text); // give it back so nothing typed is lost
    } finally {
      setSubmitting(false);
    }
  };

  // Today's ring, not all-time: was tasks.length/completedGoals before
  // completedGoals got scoped to today, which would have made the
  // denominator include every task ever (active + all-time completions)
  // while the numerator only counted today's -- badly undercounting the
  // moment any history existed. Active tasks carry forward into "today" by
  // design (see the isToday() note above), so they belong in the total.
  /* The first phrase currently over the API's per-task cap, or undefined.
     Drives the inline warning in the input footer -- computed from the SAME
     split the submit handler applies, so what the founder is warned about is
     exactly what would have been rejected. */
  const overLongTitle = titlesFrom(inputText, activeTab).find(t => t.length > TASK_TITLE_MAX);

  const totalGoals = activeGoals.length + completedGoals.length;
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
          {/* The day being planned, not a frozen "today".
              This chip used to render new Date() once on mount, so while the
              calendar said "Adding to Aug 28" the most prominent date on the
              page still read "Saturday, August 22". Two date displays
              disagreeing is worse than either alone -- it is what made the
              calendar look like it did nothing. */}
          {headerDateLabel}
        </div>
      </div>

      {/* Mode selection tabs.

          These were click-only <div>s: not focusable, no role, no key handler.
          The manual-task path was the only way to add a task by typing, and a
          keyboard user could never reach it. Real <button>s in a tablist, with
          arrow keys and a roving tabindex. */}
      {/* Connect/disconnect. Renders nothing when this deployment cannot offer
          calendar sync, so it never advertises a feature that would 503. */}
      <CalendarConnection onChange={(s) => setCalendarConnected(!!s?.connected)}
                          showToast={showToast} />

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
            <span className="pl-tab-desc">List them with commas — I'll add each one.</span>
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
                placeholder={viewingToday
                  ? "Call Rajesh about pricing, draft the follow-up email, book the factory visit…"
                  : `What's on your plate for ${selectedDayLabel}? Separate tasks with commas…`}
                value={inputText}
                disabled={submitting}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), handlePlanMyDay())}
              />

              <div className="pl-input-footer">
                {/* The hint becomes the WARNING when something is already too
                    long, rather than sitting alongside it -- a founder mid-
                    paragraph finds out here, not after submitting. Same split
                    the handler uses, so the two cannot disagree. */}
                <div className="pl-input-hint">
                  <span className="dot" />
                  {overLongTitle
                    ? `That's ${overLongTitle.length} characters for one task — the limit is ${TASK_TITLE_MAX}. Add commas to split it up.`
                    : "Comma-separate a few things and I'll add them as separate tasks."}
                </div>
                <button className="pl-plan-btn" onClick={handlePlanMyDay} disabled={submitting}>
                  {submitting && <span className="pl-spinner" aria-hidden="true" />}
                  {submitting ? 'Planning…' : 'Plan my day'}
                </button>
              </div>
            </div>
          ) : (
            <div className="pl-input-card" style={{ gap: '12px' }} id="pl-panel-manual" role="tabpanel" aria-labelledby="pl-tab-manual">
              <div className="pl-input-header">
                <span className="pl-input-title">Add task manually</span>
              </div>

              {/* Was nowhere -- every manually-added task defaulted to medium
                  with no way to mark anything more or less urgent, even
                  though the badge and sort-by-priority logic both already
                  support all three. */}
              <div role="radiogroup" aria-label="Priority" className="pl-priority-picker">
                {['low', 'medium', 'high'].map((p) => (
                  <button
                    key={p}
                    type="button"
                    role="radio"
                    aria-checked={manualPriority === p}
                    className={`pl-priority-opt ${p}${manualPriority === p ? ' active' : ''}`}
                    disabled={submitting}
                    onClick={() => setManualPriority(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>

              {/* Optional time of day. Without one the task still syncs -- the
                  server places it at a default hour -- but a real time is what
                  makes the "30 minutes before" reminder land when the founder
                  actually needs it. Only shown on the manual tab: a
                  comma-separated brain-dump has no single time. */}
              <div className="pl-time-row" style={{ display: 'flex', alignItems: 'center',
                                                    gap: '8px', marginBottom: '10px' }}>
                <label htmlFor="pl-manual-time"
                       style={{ fontSize: '12px', color: 'var(--muted-2, #6c7a70)' }}>
                  Time (optional)
                </label>
                <input
                  id="pl-manual-time"
                  type="time"
                  className="pl-time-input"
                  style={{ height: '34px', padding: '0 10px', borderRadius: '8px',
                           border: '1px solid var(--bd, #e7e0d6)', fontFamily: 'inherit',
                           fontSize: '12.5px', background: '#fff' }}
                  value={manualTime}
                  disabled={submitting}
                  onChange={(e) => setManualTime(e.target.value)}
                />
                {calendarConnected && (
                  <span style={{ fontSize: '11.5px', color: 'var(--muted-2, #6c7a70)' }}>
                    Reminder 30 min before
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <label className="sr-only" htmlFor="pl-manual-task">Task description</label>
                <input
                  id="pl-manual-task"
                  type="text"
                  className="pl-textarea"
                  style={{ minHeight: 'auto', height: '40px', padding: '0 12px' }}
                  placeholder={viewingToday
                    ? 'Add a task for today…'
                    : `Add a task for ${selectedDayLabel}…`}
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
                  {submitting && <span className="pl-spinner" aria-hidden="true" />}
                  {submitting ? 'Adding…' : 'Add task'}
                </button>
              </div>
            </div>
          )}

          {/* The list for the selected day. The heading is the calendar's main
              feedback: picking a date visibly changes what is listed here, so
              the connection between the two is shown rather than explained. */}
          <div className="sec-row">
            <div className="sec-title" style={{ fontSize: '15px', fontWeight: 750 }}>
              {showAllTasks ? 'All open tasks'
                : viewingToday ? "Today's goals" : `${selectedDayLabel}`}
            </div>
            <div className="plan-count" style={{ fontSize: '12px', color: 'var(--muted-2)',
                                                 display: 'flex', alignItems: 'center', gap: 10 }}>
              <span>{dayGoals.length} to do</span>
              {/* Only offered when it would actually reveal something. A
                  permanent toggle that changes nothing reads as broken. */}
              {(showAllTasks || hiddenCount > 0) && (
                <button
                  type="button"
                  className="pl-showall"
                  onClick={() => setShowAllTasks(v => !v)}
                >
                  {showAllTasks ? 'Show this day only' : `Show all (${activeGoals.length})`}
                </button>
              )}
            </div>
          </div>

          <div className="pl-goal-list" style={{ marginBottom: 32 }}>
            {loading ? (
              <div className="plan-empty" style={{ background: '#ffffff', padding: '24px', borderRadius: '14px', border: '1px solid var(--bd)' }}>
                <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>Loading your tasks…</p>
              </div>
            ) : dayGoals.length === 0 ? (
              /* "All caught up!" was shown to everyone with nothing active --
                 including a founder opening this page for the very first time,
                 who has not caught up on anything. */
              <div className="plan-empty" style={{ background: '#ffffff', padding: '24px', borderRadius: '14px', border: '1px solid var(--bd)' }}>
                {tasks.length === 0 ? (
                  <>
                    <h3 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 4px' }}>Nothing planned yet.</h3>
                    <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>
                      Type your tasks separated by commas and Ally will add each one.
                    </p>
                  </>
                ) : !viewingToday ? (
                  /* An empty OTHER day is not an achievement -- saying "all
                     caught up" about a Thursday three weeks out would be
                     nonsense. It also has to say where the rest of the tasks
                     went, or an empty list reads as data loss. */
                  <>
                    <h3 style={{ fontSize: '15px', fontWeight: 700, margin: '0 0 4px' }}>
                      Nothing on {selectedDayLabel}.
                    </h3>
                    <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>
                      Add a task above and it'll land on this day
                      {hiddenCount > 0 ? `, or show all ${activeGoals.length} open tasks.` : '.'}
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
              dayGoals.map((task) => (
                <div key={task.task_id} className="pl-goal-row">
                  {editingTaskId === task.task_id ? (
                    <TaskEditForm
                      task={task}
                      saving={savingEdit}
                      onSave={(fields) => handleSaveEdit(task, fields)}
                      onCancel={() => setEditingTaskId(null)}
                    />
                  ) : (
                    <>
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
                        <h4 className="pl-goal-title">{displayTitle(task.title)}</h4>
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
                              due {task.due_date}{task.due_time ? ` · ${task.due_time.slice(0, 5)}` : ''}
                            </span>
                          )}
                          {/* Only ever renders for 'synced' or 'failed'. A
                              founder must not be left believing a reminder is
                              set when the push never landed. */}
                          <SyncBadge status={task.calendar_sync_status} />
                        </div>
                      </div>
                      <TaskMenu
                        onEdit={() => setEditingTaskId(task.task_id)}
                        onDelete={() => handleDeleteTask(task)}
                      />
                    </>
                  )}
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
                <p style={{ fontSize: '12.5px', color: 'var(--muted)', margin: 0 }}>
                  {/* Distinct from "never completed anything" -- a founder with
                      real history but nothing done yet today shouldn't be told
                      to "start checking off goals" as if this were their
                      first one. */}
                  {doneGoals.length === 0
                    ? 'No tasks completed yet. Start checking off goals!'
                    : "Nothing completed today yet — see Completed history below for earlier days."}
                </p>
              </div>
            ) : (
              // Was a plain div with onClick: un-completing a task was
              // mouse-only, unreachable by keyboard and invisible to screen
              // readers.
              completedGoals.map((task) => {
                const editing = editingTaskId === task.task_id;
                return (
                  <div
                    key={task.task_id}
                    className="pl-completed-row"
                    // Toggle-to-reopen only applies when not editing -- an
                    // edit form's own clicks (the input, the priority
                    // picker) must not also flip completion via bubbling.
                    {...(editing ? {} : {
                      role: 'checkbox',
                      'aria-checked': 'true',
                      'aria-label': `Mark "${task.title}" as not done`,
                      tabIndex: 0,
                      onClick: () => handleToggleCompleted(task),
                      onKeyDown: (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleToggleCompleted(task);
                        }
                      },
                      style: { cursor: 'pointer' },
                    })}
                  >
                    {editing ? (
                      <TaskEditForm
                        task={task}
                        saving={savingEdit}
                        onSave={(fields) => handleSaveEdit(task, fields)}
                        onCancel={() => setEditingTaskId(null)}
                      />
                    ) : (
                      <>
                        <div className="pl-checkbox" aria-hidden="true">
                          <svg viewBox="0 0 12 12">
                            <polyline points="2 6 5 9 10 3" />
                          </svg>
                        </div>
                        <div className="pl-completed-content">
                          <h4 className="pl-completed-title">{displayTitle(task.title)}</h4>
                          <span className="pl-completed-time">
                            Completed{completedAtLabel(task) ? ` at ${completedAtLabel(task)}` : ''}
                          </span>
                        </div>
                        <TaskMenu
                          onEdit={() => setEditingTaskId(task.task_id)}
                          onDelete={() => handleDeleteTask(task)}
                        />
                      </>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Previously nowhere: every completion before today was shown
              (mislabeled) under "Completed today" forever, with no way to
              tell an old completion from a real one and no way to browse
              past days at all. */}
          {completedHistory.length > 0 && (
            <>
              <div className="sec-row" style={{ marginTop: 28 }}>
                <div className="sec-title" style={{ fontSize: '15px', fontWeight: 750 }}>
                  Completed history
                </div>
              </div>
              {completedHistory.map(([isoDay, dayTasks]) => (
                <div key={isoDay} style={{ marginBottom: 18 }}>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--muted-2, #6c7a70)', margin: '0 0 8px' }}>
                    {dayLabel(dayTasks[0].completed_at)} · {dayTasks.length} completed
                  </div>
                  <div className="pl-completed-list">
                    {dayTasks.map((task) => (
                      <div key={task.task_id} className="pl-completed-row" style={{ cursor: 'default' }}>
                        {editingTaskId === task.task_id ? (
                          <TaskEditForm
                            task={task}
                            saving={savingEdit}
                            onSave={(fields) => handleSaveEdit(task, fields)}
                            onCancel={() => setEditingTaskId(null)}
                          />
                        ) : (
                          <>
                            <div className="pl-checkbox" aria-hidden="true">
                              <svg viewBox="0 0 12 12">
                                <polyline points="2 6 5 9 10 3" />
                              </svg>
                            </div>
                            <div className="pl-completed-content">
                              <h4 className="pl-completed-title">{displayTitle(task.title)}</h4>
                              <span className="pl-completed-time">
                                Completed{completedAtLabel(task) ? ` at ${completedAtLabel(task)}` : ''}
                              </span>
                            </div>
                            <TaskMenu
                              onEdit={() => setEditingTaskId(task.task_id)}
                              onDelete={() => handleDeleteTask(task)}
                            />
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Right side panel */}
        <div className="plan-aside">
          {/* The calendar lives in the aside, not the main column: it is a
              fixed-size picker, and spanning the full content width made every
              day cell enormous and pushed the actual task list off-screen.
              This column is what the layout already reserves for compact
              companion cards. */}
          <MonthCalendar
            tasks={tasks}
            selectedDate={selectedDate}
            onSelectDate={(d) => {
              setSelectedDate(d || todayKey());
              // Picking a day means "show me that day" -- leaving the show-all
              // override latched would make the click appear to do nothing.
              setShowAllTasks(false);
            }}
          />

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
