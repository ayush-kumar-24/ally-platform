import { useMemo, useState } from 'react';
import { toKey, todayKey } from '../utils/dateKeys';

/**
 * A compact month calendar for picking the day a task belongs to.
 *
 * Plan Your Day was a flat list with no way to set a date at all — the add-task
 * call never sent one, so `due_date` existed in the schema and was almost
 * always null. A calendar is the natural way to answer "when?", and it is what
 * makes calendar sync mean anything: a task with no date has nowhere to go.
 *
 * Fixed width, fixed cell height. An earlier cut sized cells with
 * `aspect-ratio: 1/1`, which is fine in a narrow column and disastrous in a
 * wide one: at full page width each cell became ~215px tall and six rows ate
 * the entire screen. A date picker is a fixed-size control, not something that
 * grows with its container.
 *
 * Month and year are dropdowns, not just arrows. Arrows alone are fine for
 * "next week" and useless for "March next year" — that is twelve clicks, and
 * nobody counts them, they just give up.
 *
 * Dates are plain `YYYY-MM-DD` strings throughout, never Date objects.
 * `new Date('2026-08-26')` parses as UTC midnight then renders in local time,
 * so anyone west of Greenwich sees the 25th — the off-by-one that makes a
 * planner untrustworthy. Strings compare correctly and cannot drift.
 */

const WEEKDAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
const WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                       'Friday', 'Saturday', 'Sunday'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'];

/** How far the year dropdown reaches either side of now. */
const YEARS_BACK = 3;
const YEARS_FORWARD = 5;

/**
 * The six-week grid containing `month`, Monday-first.
 *
 * Always six rows: a grid that changes height between months makes the page
 * jump and moves the controls out from under the cursor mid-click.
 */
function buildGrid(year, month) {
  const first = new Date(year, month, 1);
  // getDay() is Sunday-first; shift so Monday is column 0.
  const lead = (first.getDay() + 6) % 7;
  const start = new Date(year, month, 1 - lead);

  return Array.from({ length: 42 }, (_, i) => {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    return { key: toKey(date), day: date.getDate(), inMonth: date.getMonth() === month };
  });
}

export default function MonthCalendar({ tasks = [], selectedDate, onSelectDate }) {
  const today = todayKey();
  const [cursor, setCursor] = useState(() => {
    const base = selectedDate ? new Date(`${selectedDate}T00:00:00`) : new Date();
    return { year: base.getFullYear(), month: base.getMonth() };
  });

  const cells = useMemo(() => buildGrid(cursor.year, cursor.month), [cursor]);

  /** date -> { total, done }, so a day shows progress rather than a bare count. */
  const byDate = useMemo(() => {
    const map = new Map();
    for (const task of tasks) {
      if (!task.due_date) continue;
      const entry = map.get(task.due_date) || { total: 0, done: 0 };
      entry.total += 1;
      if (task.status === 'done') entry.done += 1;
      map.set(task.due_date, entry);
    }
    return map;
  }, [tasks]);

  /* Years around now, plus any year a task actually falls in. Without that
     second part a task dated outside the window would be unreachable: the
     dropdown could not select its year, so the founder could never navigate
     to the day their own task sits on. */
  const years = useMemo(() => {
    const now = new Date().getFullYear();
    const span = new Set();
    for (let y = now - YEARS_BACK; y <= now + YEARS_FORWARD; y += 1) span.add(y);
    for (const task of tasks) {
      if (task.due_date) span.add(Number(task.due_date.slice(0, 4)));
    }
    span.add(cursor.year);
    return [...span].sort((a, b) => a - b);
  }, [tasks, cursor.year]);

  const step = (delta) => setCursor(({ year, month }) => {
    const next = new Date(year, month + delta, 1);
    return { year: next.getFullYear(), month: next.getMonth() };
  });

  const jumpToToday = () => {
    const now = new Date();
    setCursor({ year: now.getFullYear(), month: now.getMonth() });
    onSelectDate?.(today);
  };

  return (
    <div className="cal">
      <div className="cal-head">
        <button type="button" className="cal-nav-btn" onClick={() => step(-1)}
                aria-label="Previous month">‹</button>

        <div className="cal-selects">
          <label className="sr-only" htmlFor="cal-month">Month</label>
          <select id="cal-month" className="cal-select" value={cursor.month}
                  onChange={(e) => setCursor(c => ({ ...c, month: Number(e.target.value) }))}>
            {MONTHS.map((name, i) => <option key={name} value={i}>{name}</option>)}
          </select>

          <label className="sr-only" htmlFor="cal-year">Year</label>
          <select id="cal-year" className="cal-select cal-select-year" value={cursor.year}
                  onChange={(e) => setCursor(c => ({ ...c, year: Number(e.target.value) }))}>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>

        <button type="button" className="cal-nav-btn" onClick={() => step(1)}
                aria-label="Next month">›</button>
      </div>

      <div className="cal-weekdays">
        {WEEKDAYS.map((d, i) => (
          // The visible letter is ambiguous (T/T, S/S); the accessible name is not.
          <abbr key={WEEKDAY_NAMES[i]} title={WEEKDAY_NAMES[i]}>{d}</abbr>
        ))}
      </div>

      <div className="cal-grid">
        {cells.map(({ key, day, inMonth }) => {
          const counts = byDate.get(key);
          const classes = [
            'cal-day',
            inMonth ? '' : 'cal-day-out',
            key === today ? 'cal-day-today' : '',
            key === selectedDate ? 'cal-day-selected' : '',
          ].filter(Boolean).join(' ');

          return (
            <button
              key={key}
              type="button"
              className={classes}
              aria-current={key === today ? 'date' : undefined}
              aria-pressed={key === selectedDate}
              // The dots are decoration and say nothing on their own.
              aria-label={counts
                ? `${key}, ${counts.total} task${counts.total === 1 ? '' : 's'}`
                : key}
              onClick={() => onSelectDate?.(key)}
            >
              <span className="cal-day-num">{day}</span>
              {counts && (
                <span className="cal-day-dots" aria-hidden="true">
                  {/* Two dots then a plus. In a 34px cell anything more is a
                      smudge rather than a count. */}
                  {Array.from({ length: Math.min(counts.total, 2) }, (_, i) => (
                    <span key={i}
                          className={`cal-dot${i < counts.done ? ' cal-dot-done' : ''}`} />
                  ))}
                  {counts.total > 2 && <span className="cal-dot cal-dot-more" />}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="cal-foot">
        <button type="button" className="cal-today" onClick={jumpToToday}>Today</button>
        <span className="cal-foot-hint">
          {selectedDate === today
            ? 'Adding to today'
            : `Adding to ${new Date(`${selectedDate}T00:00:00`)
                .toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`}
        </span>
      </div>
    </div>
  );
}
