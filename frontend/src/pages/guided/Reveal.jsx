import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

function buildDiagnosis(profile, problem) {
  const founder = profile?.building || 'your company';
  const stage = (profile?.stage || 'Early traction').toLowerCase();
  const challenge = (profile?.challenges || 'growth').toLowerCase();
  const customer = (profile?.customer || 'your users').toLowerCase();
  const working = (profile?.working || 'Strategist').toLowerCase();
  const problemLine = problem || profile?.perceivedProblem || 'growth has started to stall';

  return [
    {
      role: 'ally',
      text: `I've been sitting with everything you told me — ${founder}, your ${stage} stage, the pull toward ${challenge}. One thing keeps catching my attention: ${problemLine}. Before we chase tactics, I want to understand the founder behind the decisions. When progress stalls, what's your honest instinct — push harder on what's working, or stop and look elsewhere?`,
      pill: `Recalling your founder profile · matching against ${customer}`,
      confidence: null,
    },
    {
      role: 'me',
      text: `Honestly? I usually push harder. More effort, more distribution, more momentum. That's how I've always tried to get us unstuck.`,
      pill: null,
      confidence: null,
    },
    {
      role: 'ally',
      text: `I've connected that with something you said earlier — your energy naturally flows toward ${challenge}. That's a genuine strength; it helped you get here. But it may also be why the leak stays hidden. This looks less like a top-of-funnel issue and more like a first-value gap. Walk me through it — what does a new user actually have to do before they feel the product click?`,
      pill: `Linking founder behaviour · ${working} pattern inferred`,
      confidence: 74,
    },
  ];
}

const QUICK_REPLIES = [
  'We ask them to set up a profile first',
  "There's no structured onboarding yet",
  'We show a product tour',
];

export default function Reveal() {
  const navigate = useNavigate();
  const { user } = useApp();
  const profile = user?.founderProfile || {};
  const [input, setInput] = useState('');
  const scrollRef = useRef(null);
  const kgRef = useRef(null);
  const messages = useMemo(() => buildDiagnosis(profile, user?.problem), [profile, user?.problem]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
    if (kgRef.current) {
      setTimeout(() => {
        kgRef.current?.classList.add('draw');
      }, 400);
    }
  }, []);

  return (
    <section className="view chat-view active" style={{ minHeight: '100%' }}>
      <div className="chat">
        <div className="chat-main">
          <div className="chat-dims" style={{ paddingTop: '84px' }}>
            {['Founder', 'Retention', 'Acquisition', 'Product', 'Pricing', 'Team', 'Cash flow'].map((chip, index) => (
              <button key={chip} className={`dim-chip${index < 3 ? ' on' : ''}`} type="button">
                <span className="p" />
                {chip}
              </button>
            ))}
          </div>

          <div className="chat-scroll" ref={scrollRef}>
            {messages.map((message, index) => (
              <div key={index} className={`msg ${message.role === 'me' ? 'me' : 'ally'}`}>
                <span className={`m-av ${message.role === 'me' ? 'me' : 'ally'}`}>{message.role === 'me' ? (user?.initials || 'A').charAt(0) : '✦'}</span>
                <div>
                  <div className="bubble">{message.text}</div>
                  {message.pill && (
                    <div className="reason">
                      <span className="dots"><span></span><span></span><span></span></span>
                      {message.pill}
                    </div>
                  )}
                  {typeof message.confidence === 'number' && (
                    <div className="conf">
                      <div className="l">Confidence</div>
                      <div className="bar"><i style={{ width: `${message.confidence}%` }} /></div>
                      <div className="pct">{message.confidence}%</div>
                    </div>
                  )}
                  <div className="m-meta">Just now</div>
                </div>
              </div>
            ))}
          </div>

          <div className="suggs">
            {QUICK_REPLIES.map((reply) => (
              <button key={reply} className="sugg" type="button" onClick={() => setInput(reply)}>{reply}</button>
            ))}
          </div>

          <div className="chat-input">
            <div className="ci-row">
              <textarea
                rows={1}
                placeholder="Tell Ally what's really on your mind..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) e.preventDefault();
                }}
              />
              <button className="ci-btn" type="button" aria-label="Voice input">
                <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
              </button>
              <button className="ci-btn send" type="button" aria-label="Continue" onClick={() => navigate('/guided/root-cause')}>
                <svg viewBox="0 0 24 24"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" /></svg>
              </button>
            </div>
            <div className="ci-hint">Ally reasons across your founder profile and 10 business dimensions · Enter to send</div>
          </div>
        </div>

        <aside className="kg-panel" aria-label="Live knowledge graph" style={{ paddingTop: '86px' }}>
          <h3>Live knowledge graph</h3>
          <p className="kp-sub">How Ally is connecting what you say to the underlying cause.</p>
          <div className="kg" ref={kgRef}>
            <svg viewBox="0 0 260 210" preserveAspectRatio="xMidYMid meet">
              <path className="edge" d="M40,40 C110,40 90,95 130,95" />
              <path className="edge" d="M40,120 C110,120 100,100 130,95" />
              <path className="edge" d="M40,180 C110,180 110,110 130,100" />
              <path className="edge hot" d="M130,95 C190,95 190,150 220,150" />
              <circle className="kn" cx="40" cy="40" r="7" fill="rgba(255,255,255,.25)" />
              <circle className="kn" cx="40" cy="120" r="7" fill="rgba(255,255,255,.25)" />
              <circle className="kn" cx="40" cy="180" r="7" fill="rgba(255,255,255,.25)" />
              <circle className="kg-ring" cx="220" cy="150" r="11" />
              <circle className="kn pulse-m" cx="130" cy="97" r="8" fill="#34d399" />
              <circle className="kn pulse-r" cx="220" cy="150" r="10" fill="#A8D94A" />
              <circle className="kg-sig s1" r="3" />
              <circle className="kg-sig s2" r="3" />
              <circle className="kg-sig s3" r="3" />
              <circle className="kg-sig hot" r="3.4" />
              <text className="kg-lbl" x="52" y="43">Flat growth</text>
              <text className="kg-lbl" x="52" y="123">Rising spend</text>
              <text className="kg-lbl" x="52" y="183">Week-2 silence</text>
              <text className="kg-lbl hot" x="96" y="118">Mechanism</text>
              <text className="kg-lbl hot" x="176" y="172">Root cause</text>
            </svg>
          </div>
          <div className="kg-legend">
            <div className="kg-leg"><span className="d" style={{ background: 'rgba(255,255,255,.3)' }} /> Symptoms you described</div>
            <div className="kg-leg"><span className="d" style={{ background: '#34d399' }} /> Mechanism Ally inferred</div>
            <div className="kg-leg"><span className="d" style={{ background: '#A8D94A' }} /> Root cause · 92% confidence</div>
          </div>
        </aside>
      </div>

      <button className="btn btn-em j-btn-lg" type="button" onClick={() => navigate('/guided/root-cause')} style={{ position: 'fixed', right: '22px', bottom: '22px', zIndex: 120 }}>
        See Ally think
        <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
      </button>
    </section>
  );
}
