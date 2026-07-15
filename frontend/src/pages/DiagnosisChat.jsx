import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const DIM_CHIPS = ['All', 'Revenue', 'Strategy', 'Team', 'Operations', 'Finance', 'Market'];

const DIAG_MESSAGES = [
  { role: 'ally', text: 'Welcome to your diagnosis session. I\'ll ask you structured questions across 10 founder and business dimensions. Ready to start?', time: '2 min ago' },
  { role: 'me', text: 'Yes, let\'s do it. I want to understand what\'s holding us back from crossing ₹10Cr ARR.', time: '2 min ago' },
  { role: 'ally', text: 'Let\'s start with revenue. Looking at your data: MRR is ₹58L, growing at 8% MoM. But your net revenue retention is 91% — slightly below the 110% benchmark for your stage. Where do you feel the biggest drag?', time: '1 min ago', confidence: 84 },
  { role: 'me', text: 'I think it\'s churn from SME segment. Enterprise seems fine.', time: '1 min ago' },
  { role: 'ally', text: 'That pattern is important. I\'m now cross-referencing your founder DNA — you show a strong "builder" pattern with lower sales instinct scores. This often creates a gap in SME customer success investment.', time: 'Just now', confidence: 91 },
];

export default function DiagnosisChat() {
  const navigate = useNavigate();
  const [activeDim, setActiveDim] = useState('All');
  const [messages] = useState(DIAG_MESSAGES);
  const [input, setInput] = useState('');
  const [kgVisible, setKgVisible] = useState(true);
  const kgRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    if (kgRef.current) setTimeout(() => kgRef.current?.classList.add('draw'), 800);
  }, []);

  return (
    <div className="chat" style={{ height: 'calc(100vh - 64px)' }}>
      <div className="chat-main">
        {/* Dimension chips */}
        <div className="chat-dims">
          {DIM_CHIPS.map(d => (
            <button key={d} className={`dim-chip${activeDim === d ? ' on' : ''}`} onClick={() => setActiveDim(d)}>
              <span className="p" />
              {d}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="chat-scroll" ref={scrollRef}>
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className={`m-av ${m.role}`}>{m.role === 'ally' ? '🤝' : 'RV'}</div>
              <div>
                <div className="bubble">{m.text}</div>
                {m.confidence && <ConfBar pct={m.confidence} />}
                <div className="m-meta">{m.time}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Suggestions */}
        <div className="suggs">
          <button className="sugg">Tell me more about the SME churn pattern</button>
          <button className="sugg">What's my founder DNA score for Sales?</button>
          <button className="sugg">Show me the root cause hypothesis</button>
        </div>

        {/* Input */}
        <div className="chat-input">
          <div className="ci-row">
            <textarea
              rows={1}
              placeholder="Answer Ally's question or ask anything..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) e.preventDefault(); }}
            />
            <button className="ci-btn send" title="Send">
              <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
          <div className="ci-hint">Structured diagnosis · 10 dimensions · Est. 15 min</div>
        </div>
      </div>

      {/* Knowledge Graph Panel */}
      {kgVisible && (
        <div className="kg-panel">
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
        </div>
      )}
    </div>
  );
}

function ConfBar({ pct }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) setTimeout(() => { if (ref.current) ref.current.style.width = `${pct}%`; }, 300);
  }, [pct]);
  return (
    <div className="conf">
      <div className="l">Confidence</div>
      <div className="bar"><i ref={ref} /></div>
      <div className="pct">{pct}%</div>
    </div>
  );
}
