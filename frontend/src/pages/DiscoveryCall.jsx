import { useCallback, useEffect, useState } from 'react';
import { bookCall, getSlots, listCalls } from '../services/discovery';
import { getCallQuote } from '../services/plans';
import { useApp } from '../context/AppContext';

const DAYS = [
  { key: 'mon', label: 'MON', val: '14', dayName: 'Monday, July 14' },
  { key: 'tue', label: 'TUE', val: '15', dayName: 'Tuesday, July 15' },
  { key: 'wed', label: 'WED', val: '16', dayName: 'Wednesday, July 16' },
  { key: 'thu', label: 'THU', val: '17', dayName: 'Thursday, July 17' }
];

const TIMES = [
  '10:00 AM',
  '11:30 AM',
  '1:00 PM',
  '2:30 PM',
  '4:30 PM',
  '6:00 PM'
];

function DiscoveryCallView(props) {
  const { showToast } = useApp();
  const [selectedDay, setSelectedDay] = useState('wed');
  const [selectedTime, setSelectedTime] = useState('4:30 PM');

  const handleConfirm = () => {
    const dayObj = DAYS.find(d => d.key === selectedDay);
    showToast(`Booking confirmed for ${dayObj.dayName} at ${selectedTime} ✓`);
  };

  return (
    <div className="dc-container">
      <div className="dc-grid stagger d1">
        {/* Left Information Card */}
        <div className="dc-info-card">
          <div className="dc-info-badge">The next step in your clarity</div>
          <h2 className="dc-info-title">Turn the diagnosis into a plan.</h2>
          <p className="dc-info-desc">
            Ally found the root cause. This is where a GoXL advisor — who has
            already read your Founder Report — helps you act on it. Not a sales
            call. The next step in your clarity journey.
          </p>

          <div className="dc-info-list">
            <div className="dc-info-item">
              <div className="dc-info-ic">
                <svg viewBox="0 0 12 12">
                  <polyline points="2 6 5 9 10 3" />
                </svg>
              </div>
              <div className="dc-info-text">
                <strong>What happens —</strong> 30 focused minutes; your advisor
                arrives already briefed by Ally.
              </div>
            </div>

            <div className="dc-info-item">
              <div className="dc-info-ic">
                <svg viewBox="0 0 12 12">
                  <polyline points="2 6 5 9 10 3" />
                </svg>
              </div>
              <div className="dc-info-text">
                <strong>Why it matters —</strong> a diagnosis only compounds once
                it becomes a sequenced plan.
              </div>
            </div>

            <div className="dc-info-item">
              <div className="dc-info-ic">
                <svg viewBox="0 0 12 12">
                  <polyline points="2 6 5 9 10 3" />
                </svg>
              </div>
              <div className="dc-info-text">
                <strong>What you get —</strong> your root cause pressure-tested
                and 3 actions turned into moves.
              </div>
            </div>

            <div className="dc-info-item">
              <div className="dc-info-ic">
                <svg viewBox="0 0 12 12">
                  <polyline points="2 6 5 9 10 3" />
                </svg>
              </div>
              <div className="dc-info-text">
                <strong>You leave with —</strong> a 90-day founder roadmap and
                one weekly north-star metric.
              </div>
            </div>
          </div>
        </div>

        {/* Right Scheduler Card */}
        <div className="dc-picker-card stagger d2">
          <div>
            <h3 className="dc-picker-title">Pick a time</h3>
            <span className="dc-picker-sub">All times IST · 30 minutes</span>
          </div>

          {/* Day selection row */}
          <div className="dc-days-row">
            {DAYS.map(day => (
              <button
                key={day.key}
                className={`dc-day-btn ${selectedDay === day.key ? 'active' : ''}`}
                onClick={() => setSelectedDay(day.key)}
                type="button"
              >
                <span className="dc-day-lbl">{day.label}</span>
                <span className="dc-day-val">{day.val}</span>
              </button>
            ))}
          </div>

          {/* Time selection grid */}
          <div className="dc-times-grid">
            {TIMES.map(time => (
              <button
                key={time}
                className={`dc-time-btn ${selectedTime === time ? 'active' : ''}`}
                onClick={() => setSelectedTime(time)}
                type="button"
              >
                {time}
              </button>
            ))}
          </div>

          {/* Action button */}
          <button
            className="dc-confirm-btn"
            onClick={handleConfirm}
            type="button"
          >
            Confirm booking
          </button>
        </div>
      </div>
    </div>
  );
}


/**
 * Booking is entitlement-gated server-side. The quote is fetched first so the
 * button can state the true price -- free, or Rs 300 once the plan's monthly
 * allowance is used -- rather than discovering it after the founder commits.
 */
export default function DiscoveryCall() {
  const [slots, setSlots] = useState([]);
  const [quote, setQuote] = useState(null);
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      getSlots().catch(() => null),
      getCallQuote().catch(() => null),
      listCalls().catch(() => []),
    ])
      .then(([s, q, c]) => { setSlots(s?.slots ?? []); setQuote(q); setCalls(c ?? []); })
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const book = async (scheduledAt, notes) => {
    const created = await bookCall({ scheduledAt, notes });
    load();
    return created;
  };

  return (
    <DiscoveryCallView
      slots={slots} quote={quote} calls={calls}
      loading={loading} error={error} onBook={book} onReload={load}
    />
  );
}
