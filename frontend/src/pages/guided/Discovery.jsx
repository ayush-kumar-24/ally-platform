import { useNavigate } from 'react-router-dom';

const DAYS = [
  { d: 'Mon', n: '14' },
  { d: 'Tue', n: '15' },
  { d: 'Wed', n: '16' },
  { d: 'Thu', n: '17' },
];

const TIMES = ['10:00 AM', '11:30 AM', '1:00 PM', '2:30 PM', '4:30 PM', '6:00 PM'];

export default function Discovery() {
  const navigate = useNavigate();
  const day = 2;
  const time = 4;

  return (
    <section className="view call-view active">
      <button className="btn btn-em j-btn-lg" type="button" onClick={() => navigate('/guided/success')} style={{ position: 'fixed', right: '18px', bottom: '18px', zIndex: 120 }}>
        Finish
        <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
      </button>

      <div className="pad">
        <div className="book">
          <div className="book-info">
            <span className="rep-badge">The next step in your clarity</span>
            <h2>Turn the diagnosis into a plan.</h2>
            <p>Ally found the root cause. This is where a GoXL advisor — who has already read your Founder Report — helps you act on it. Not a sales call. The next step in your clarity journey.</p>
            <ul className="bi-list">
              <li>
                <span className="ck">
                  <svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg>
                </span>
                <span><b>What happens —</b> 30 focused minutes; your advisor arrives already briefed by Ally.</span>
              </li>
              <li>
                <span className="ck">
                  <svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg>
                </span>
                <span><b>Why it matters —</b> a diagnosis only compounds once it becomes a sequenced plan.</span>
              </li>
              <li>
                <span className="ck">
                  <svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg>
                </span>
                <span><b>What you get —</b> your root cause pressure-tested and 3 actions turned into moves.</span>
              </li>
              <li>
                <span className="ck">
                  <svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg>
                </span>
                <span><b>You leave with —</b> a 90-day founder roadmap and one weekly north-star metric.</span>
              </li>
            </ul>
          </div>

          <div className="card book-pick">
            <h3>Pick a time</h3>
            <p className="bp-sub">All times IST · 30 minutes</p>
            <div className="days" id="bookDays">
              {DAYS.map((item, i) => (
                <button
                  key={item.n}
                  type="button"
                  className={`day ${i === day ? 'sel' : ''}`}
                >
                  <div className="dow">{item.d}</div>
                  <div className="dnum">{item.n}</div>
                </button>
              ))}
            </div>
            <div className="slots" id="bookSlots">
              {TIMES.map((item, i) => (
                <button
                  key={item}
                  type="button"
                  className={`slot ${i === time ? 'sel' : ''}`}
                >
                  {item}
                </button>
              ))}
            </div>
            <button
              className="btn btn-em"
              id="bookConfirm"
              type="button"
              onClick={() => navigate('/guided/success')}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              Confirm booking
            </button>
            <div style={{ marginTop: '12px', fontSize: '12px', color: 'var(--muted-2)', textAlign: 'center' }}>
              Selected: {DAYS[day].d} {DAYS[day].n} at {TIMES[time]}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
