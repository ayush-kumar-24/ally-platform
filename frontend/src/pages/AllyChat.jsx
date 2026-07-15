import { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { MOCK_CHAT_HISTORY, MOCK_MESSAGES } from '../data/mockData';

const PROMPT_CARDS = [
  { t: 'Help me increase revenue', s: 'Find the highest-leverage growth lever' },
  { t: 'Review my pricing', s: 'Pressure-test packaging & price points' },
  { t: 'Improve my sales strategy', s: 'Tighten the funnel and close rate' },
  { t: 'Validate my startup idea', s: 'Stress-test demand and assumptions' },
  { t: 'Help me hire my first employee', s: 'Scope the role and where to look' },
  { t: 'Create a GTM strategy', s: 'A go-to-market plan for launch' },
];

const REPLIES = [
  "Great question. Let's break it into the few moves that actually move the needle — then I'll give you a concrete first step you can take this week.",
  "Here's how I'd think about it: start from the constraint, not the tactic. What's the one thing that, if it changed, would make everything else easier?",
  "Good instinct to ask now. There are three ways founders usually approach this — let me lay them out with the trade-offs so you can pick with clear eyes.",
  'Let\'s make this concrete. Tell me one number — your current baseline — and I\'ll show you the realistic range of what "good" looks like from here.',
];

const CHAT_LIMIT = 20;

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

export default function AllyChat() {
  const { user } = useApp();
  const [histOpen, setHistOpen] = useState(false);
  const [activeConv, setActiveConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const [used, setUsed] = useState(18);
  const [replyIdx, setReplyIdx] = useState(0);
  const scrollRef = useRef(null);
  const taRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, typing]);

  const sizeTa = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  };

  const send = (text) => {
    if (!text.trim()) return;
    if (activeConv === null) {
      // first message of a fresh conversation
    }
    setMessages(prev => [...prev, { role: 'me', text, time: 'Just now' }]);
    setInput('');
    sizeTa();
    setUsed(u => Math.min(CHAT_LIMIT, u + 1));
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      setMessages(prev => [...prev, {
        role: 'ally',
        text: REPLIES[replyIdx % REPLIES.length],
        time: 'Just now',
      }]);
      setReplyIdx(i => i + 1);
    }, 1300);
  };

  const remaining = Math.max(0, CHAT_LIMIT - used);
  const near = remaining <= Math.max(2, Math.round(CHAT_LIMIT * 0.15));
  const isEmpty = messages.length === 0;
  const firstName = (user.name || 'Ayush Sharma').split(' ')[0];

  const startNew = () => {
    setActiveConv(null);
    setMessages([]);
    setHistOpen(false);
  };

  return (
    <div className={`ac${histOpen ? ' open' : ''}`} style={{ minHeight: 'calc(100vh - 64px)' }}>

      {/* ── History slide-over ── */}
      <div className="ac-hist">
        <div className="ac-hist-top">
          <div className="h">History</div>
          <button className="ac-hist-x" onClick={() => setHistOpen(false)}>
            <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <button className="ac-new" onClick={startNew}>
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New conversation
        </button>
        <div className="ac-hist-lbl">Recent conversations</div>
        <div className="ac-list">
          {MOCK_CHAT_HISTORY.map(conv => (
            <button key={conv.id} className={`ac-item${activeConv === conv.id ? ' on' : ''}`}
              onClick={() => { setActiveConv(conv.id); setMessages(MOCK_MESSAGES[conv.id] || []); setHistOpen(false); }}>
              <div className="ai-ic">
                <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
              </div>
              <div className="ai-body">
                <div className="ai-t">{conv.title}</div>
                <div className="ai-w">{conv.time} · {conv.messages} msgs</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ── Scrim ── */}
      <div className="ac-scrim" onClick={() => setHistOpen(false)} />

      {/* ── Main area ── */}
      <div className="ac-main">
        {/* Bar */}
        <div className="ac-bar">
          <button className="ac-menu" onClick={() => setHistOpen(o => !o)} title="Conversations">
            <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg>
          </button>
          <div className="ac-ttl">
            <div className="t">{isEmpty ? 'New conversation' : (MOCK_CHAT_HISTORY.find(c => c.id === activeConv)?.title || 'New conversation')}</div>
            <div className="s">General consultation · always on</div>
          </div>
          <button className="ac-barnew" onClick={startNew}>
            <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New
          </button>
        </div>

        {/* Scroll area */}
        <div className="ac-scroll" ref={scrollRef}>
          {isEmpty ? (
            <div className="ac-empty">
              <div className="ac-av">✦</div>
              <h2>{greeting()}, <em>{firstName}</em>. How can I help?</h2>
              <p className="ac-lede">Ask me anything — marketing, sales, hiring, fundraising, pricing, growth or strategy. I'm your always-on thinking partner, no assessment required.</p>
              <div className="ac-cards">
                {PROMPT_CARDS.map((c, i) => (
                  <div key={i} className="ac-pcard" onClick={() => send(c.t)}>
                    <div className="pc-t">{c.t}</div>
                    <div className="pc-s">{c.s}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((m, i) => (
                <div key={i} className={`msg ${m.role}`}>
                  <div className={`m-av ${m.role}`}>{m.role === 'ally' ? '✦' : (user.initials || 'RV').charAt(0)}</div>
                  <div>
                    <div className="bubble">{m.text}</div>
                    {m.confidence && (
                      <ConfBar pct={m.confidence} />
                    )}
                    <div className="m-meta">{m.time}</div>
                  </div>
                </div>
              ))}
              {typing && (
                <div className="typing">
                  <div className="m-av ally">✦</div>
                  <div className="bubble">
                    <div className="td">
                      <span /><span /><span />
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Input */}
        <div className="ac-input">
          <div style={{ maxWidth: 800, margin: '0 auto 8px', textAlign: 'center' }}>
            <span className={`ac-remain${near ? ' near' : ''}`}>
              <span>{remaining} of {CHAT_LIMIT} chats left this month</span>
              <span className="arm-bar"><i style={{ width: `${Math.min(100, Math.round((used / CHAT_LIMIT) * 100))}%` }} /></span>
            </span>
          </div>
          <div className="ci-row">
            <button className="ci-btn" title="Attach a file or image">
              <svg viewBox="0 0 24 24"><path d="M21.4 11.05 12.25 20.2a5.5 5.5 0 01-7.78-7.78l9.19-9.19a3.5 3.5 0 114.95 4.95l-9.2 9.19a1.5 1.5 0 01-2.12-2.12l8.49-8.49"/></svg>
            </button>
            <textarea
              ref={taRef}
              rows={1}
              placeholder="Ask Ally anything about your business…"
              value={input}
              onChange={e => { setInput(e.target.value); sizeTa(); }}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }}
            />
            <button className="ci-btn" title="Voice input" aria-pressed="false">
              <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/></svg>
            </button>
            <button className="ci-btn send" onClick={() => send(input)} title="Send">
              <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
          <p className="ci-hint">Ally is your always-on strategic partner for advice, brainstorming and daily founder questions · Enter to send</p>
        </div>
      </div>
    </div>
  );
}

function ConfBar({ pct }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) setTimeout(() => { if (ref.current) ref.current.style.width = `${pct}%`; }, 200);
  }, [pct]);
  return (
    <div className="conf">
      <div className="l">Confidence</div>
      <div className="bar"><i ref={ref} /></div>
      <div className="pct">{pct}%</div>
    </div>
  );
}
