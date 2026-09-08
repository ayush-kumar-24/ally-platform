import { useCallback, useEffect, useMemo, useState } from 'react';
import { bookCall, getSlots, listCalls } from '../services/discovery';
import { explainLimit } from '../services/plans';
import { useCallAccess, refreshCallAccess } from '../hooks/useCallAccess';
import { DnaLoading } from '../components/DnaState';
import { useApp } from '../context/AppContext';

/* The four fixed July dates and six fixed times that used to live here were
   props-in-name-only: the page fetched real slots, a real quote and the real
   call list, then rendered a hardcoded grid and ignored all three. "Confirm
   booking" called showToast and never bookCall, so founders were shown a
   success message for a call that did not exist. Everything below is driven by
   the API. */

const WHAT_YOU_GET = [
  ['What happens —', '30 focused minutes; your advisor arrives already briefed by Ally.'],
  ['Why it matters —', 'a diagnosis only compounds once it becomes a sequenced plan.'],
  ['What you get —', 'your root cause pressure-tested and 3 actions turned into moves.'],
  ['You leave with —', 'a 90-day founder roadmap and one weekly north-star metric.'],
];

function InfoCard() {
  return (
    <div className="dc-info-card">
      <div className="dc-info-badge">The next step in your clarity</div>
      <h2 className="dc-info-title">Turn the diagnosis into a plan.</h2>
      <p className="dc-info-desc">
        Ally found the root cause. This is where a GoXL advisor — who has already
        read your Founder Report — helps you act on it. Not a sales call. The next
        step in your clarity journey.
      </p>
      <div className="dc-info-list">
        {WHAT_YOU_GET.map(([lead, rest]) => (
          <div className="dc-info-item" key={lead}>
            <div className="dc-info-ic">
              <svg viewBox="0 0 12 12"><polyline points="2 6 5 9 10 3" /></svg>
            </div>
            <div className="dc-info-text"><strong>{lead}</strong> {rest}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** How each status reads to the founder. The raw value was printed straight out
 *  of the database ("pending", "no_show"), which tells someone waiting on a paid
 *  call almost nothing about what happens next. */
const STATUS_COPY = {
  /* Nothing creates a pending call any more -- booking confirms itself. Kept
     for rows written before that change, which are still real bookings a
     founder can open. */
  pending: 'Waiting for us to confirm',
  confirmed: 'Confirmed',
  rescheduled: 'Moved — waiting for us to confirm',
  cancelled: 'Cancelled',
  completed: 'Done',
  no_show: 'Missed',
};

/** Existing bookings. Never gated: a call already on the books is theirs to see.
 *
 *  THE JOIN LINK. This row used to show the date and the raw status and nothing
 *  else -- no link, no button. That mattered far more than it looks, because
 *  there was no OTHER route either: the host calendar is a personal Gmail, so
 *  Google cannot invite the founder as an attendee, and with EMAIL_HOST unset
 *  our own confirmation email logs instead of sending. A founder could book, pay
 *  and be confirmed, and never receive the joining link by any path at all.
 *
 *  `meeting_link` was in the API response the whole time (CallRead) and simply
 *  never rendered. Showing it here is the one delivery path that cannot silently
 *  fail, because it does not depend on mail or on Workspace.
 *  See docs/DEAD-SETTINGS-AND-CALL-DELIVERY.md. */
function BookedCalls({ calls }) {
  if (!calls?.length) return null;
  // Cancelled calls stay listed (a founder should be able to see one was
  // cancelled), but they must never offer a way in.
  const joinable = (c) => c.meeting_link && (c.status === 'confirmed' || c.status === 'rescheduled');
  return (
    <div className="dc-booked">
      <h3 className="dc-picker-title">Your calls</h3>
      {calls.map((c) => (
        <div className="dc-booked-row" key={c.call_id ?? c.scheduled_at}>
          <div className="dc-booked-when">
            {new Date(c.scheduled_at).toLocaleString(undefined, {
              weekday: 'short', day: 'numeric', month: 'short',
              hour: 'numeric', minute: '2-digit',
            })}
          </div>
          <div className="dc-booked-meta">
            {STATUS_COPY[c.status] || c.status}{c.timezone ? ` · ${c.timezone}` : ''}
          </div>
          {joinable(c) ? (
            <a
              className="dc-join"
              href={c.meeting_link}
              target="_blank"
              rel="noopener noreferrer"
            >
              Join call
            </a>
          ) : c.status === 'pending' ? (
            <span className="dc-booked-note">
              We&apos;ll send the joining link once this is confirmed.
            </span>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function Scheduler({ slots, timezone, price, onBook, onBooked }) {
  const { showToast } = useApp();
  const [selected, setSelected] = useState(null);
  const [saving, setSaving] = useState(false);
  const [limit, setLimit] = useState(null);

  /* Real slots are a flat list of ISO datetimes (SlotsResponse.slots), so the
     day/time split is derived rather than assumed -- a week with a public
     holiday in it simply has fewer days, instead of four buttons that always
     say Mon-Thu whatever the server offered. */
  const days = useMemo(() => {
    const grouped = new Map();
    for (const iso of slots) {
      const key = new Date(iso).toDateString();
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(iso);
    }
    return [...grouped.entries()].map(([key, times]) => ({ key, times }));
  }, [slots]);

  const [activeDay, setActiveDay] = useState(null);
  const day = days.find((d) => d.key === activeDay) ?? days[0] ?? null;

  if (!days.length) {
    return (
      <div className="dc-picker-card">
        <div>
          <h3 className="dc-picker-title">Pick a time</h3>
          <span className="dc-picker-sub">No slots open right now</span>
        </div>
        <p className="dc-locked-copy">
          There are no bookable times in the next few days. Try again shortly —
          new slots open as advisors free up.
        </p>
      </div>
    );
  }

  const confirm = async () => {
    if (!selected || saving) return;
    setSaving(true);
    setLimit(null);
    try {
      await onBook(selected, timezone);
      // The server confirms on the spot now, so this can say so. It used to
      // write the row `pending` and wait for someone on the team to press
      // Confirm, which is why this said "requested".
      showToast('Booked ✓ The joining link is in your email');
      onBooked?.();
    } catch (error) {
      /* Kept as a safety net rather than a live path: nothing entitlement-gates
         a request today. If a limit is ever reintroduced server-side it is
         shown in place rather than as a toast -- that needs a decision, and
         toasts vanish. */
      const explained = explainLimit(error);
      if (explained) setLimit(explained);
      /* The one a founder will actually hit: two people picking the same slot
         within a few seconds, or a page left open until the slot aged out of
         the window. Branching on `code` rather than the status because the
         backend sends the exact error class, and "try again" is wrong advice
         when the answer is "pick a different time". */
      else if (error?.code === 'SlotTakenError' || error?.code === 'SlotNotOfferedError') {
        showToast(error.detail || 'That slot has gone. Please pick another time.');
        onBooked?.();   // re-reads availability, so the gone slot disappears
      } else showToast("That didn't go through. Nothing was charged — try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="dc-picker-card">
      <div>
        <h3 className="dc-picker-title">Pick a time</h3>
        <span className="dc-picker-sub">
          {timezone ? `All times ${timezone}` : 'All times local'} · 30 minutes
          {price ? ` · ₹${price}` : ''}
        </span>
      </div>

      {/* Said before they pick, not after. The slots shown ARE the offer --
          picking one books it and sends the joining link. */}
      <p className="dc-request-note">
        Pick a time and it&apos;s booked. We&apos;ll email you the joining link
        straight away. Nothing is charged
        {price ? `; a call is ₹${price}` : ''}.
      </p>

      <div className="dc-days-row">
        {days.map((d) => {
          const date = new Date(d.times[0]);
          return (
            <button
              key={d.key}
              className={`dc-day-btn ${day?.key === d.key ? 'active' : ''}`}
              type="button"
              onClick={() => { setActiveDay(d.key); setSelected(null); }}
            >
              <span className="dc-day-lbl">
                {date.toLocaleDateString(undefined, { weekday: 'short' }).toUpperCase()}
              </span>
              <span className="dc-day-val">{date.getDate()}</span>
            </button>
          );
        })}
      </div>

      <div className="dc-times-grid">
        {day?.times.map((iso) => (
          <button
            key={iso}
            className={`dc-time-btn ${selected === iso ? 'active' : ''}`}
            type="button"
            onClick={() => setSelected(iso)}
          >
            {new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
          </button>
        ))}
      </div>

      {limit && (
        <div className="dc-limit" role="alert">
          <strong>{limit.title}</strong>
          <span>{limit.message}</span>
        </div>
      )}

      <button
        className="dc-confirm-btn"
        type="button"
        onClick={confirm}
        disabled={!selected || saving}
      >
        {saving ? 'Booking…' : selected ? 'Book this time' : 'Select a time'}
      </button>
    </div>
  );
}

/**
 * The scheduler is shown to every founder, because every founder can ask for a
 * call: the request is not entitlement-gated and consumes no allowance. The
 * quote is read alongside it only to name the price.
 */
export default function DiscoveryCall() {
  const [slots, setSlots] = useState([]);
  const [timezone, setTimezone] = useState(null);
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const { price } = useCallAccess();

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([getSlots().catch(() => null), listCalls().catch(() => [])])
      .then(([s, c]) => {
        setSlots(s?.slots ?? []);
        setTimezone(s?.timezone ?? null);
        setCalls(c ?? []);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const book = async (scheduledAt, tz) => {
    const created = await bookCall({ scheduledAt, timezone: tz });
    refreshCallAccess();   // re-read the quote; the price is the team's to change
    load();
    return created;
  };

  // Only the slots and the call list gate the render. The quote supplies a
  // price and nothing else, so a slow or failed quote must not hold up a page
  // that works perfectly well without it.
  if (loading) return <DnaLoading label="Loading discovery calls…" />;

  return (
    <div className="dc-container">
      <div className="dc-grid stagger d1">
        <InfoCard />
        <Scheduler slots={slots} timezone={timezone} price={price}
                   onBook={book} onBooked={load} />
      </div>
      <BookedCalls calls={calls} />
    </div>
  );
}
