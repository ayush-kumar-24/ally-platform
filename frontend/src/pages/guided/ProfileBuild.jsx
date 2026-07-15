import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

/* 13 questions — Ally builds a live Founder DNA, grouped Business / Founder.
   Faithful port of #v-profile from ally-platform-main.html. */
const PROFILE_Q = [
  /* BUSINESS DNA */
  { k: 'stage', g: 'business', lbl: 'Entrepreneurial Stage', q: 'First — which stage best describes where you are right now?', opts: ['Idea', 'Early traction', 'Scaling', 'Plateau'], def: 'Early traction' },
  { k: 'building', g: 'business', lbl: "What You're Building", q: 'In one line — what are you building?', ph: 'e.g. an AI copilot that prevents SaaS churn', def: 'An AI copilot that helps SaaS teams prevent churn' },
  { k: 'problem', g: 'business', lbl: 'Problem Statement', q: "What's the core problem you take away for people?", ph: 'The pain you solve…', def: "Teams lose customers to churn they can't see coming" },
  { k: 'customer', g: 'business', lbl: 'Customer Segment', q: 'Who is this really for? Describe your ideal customer.', ph: 'e.g. B2B SaaS teams, 6–50 people', def: 'B2B SaaS product & growth teams' },
  { k: 'industry', g: 'business', lbl: 'Industry', q: 'Which industry feels closest to home?', opts: ['SaaS / B2B', 'D2C / Consumer', 'Fintech', 'Healthtech', 'Marketplace', 'AI / ML', 'Services'], def: 'SaaS / B2B' },
  { k: 'challenges', g: 'business', lbl: 'Biggest Challenges', q: "What's the biggest thing holding you back right now?", opts: ['Retention', 'Acquisition', 'Activation', 'Pricing', 'Hiring', 'Focus', 'Cash flow'], def: 'Retention' },
  { k: 'goal90', g: 'business', lbl: '90-Day Goal', q: 'Fast-forward 90 days — what has to be true for you to feel it went well?', ph: 'Your next 90 days…', def: 'Lift 30-day retention by 10 points' },
  { k: 'vision', g: 'business', lbl: 'One-Year Vision', q: 'Now zoom out — where do you want this to be in a year?', ph: 'A year from now…', def: 'The default way SaaS teams predict and prevent churn' },
  /* FOUNDER DNA */
  { k: 'why', g: 'founder', lbl: 'Why You Started', q: 'This one matters most — what made you start this?', ph: 'The real reason…', def: 'I watched a company die from churn we caught too late' },
  { k: 'working', g: 'founder', lbl: 'Working Style', q: 'How do you want me to show up for you?', opts: ['Coach', 'Co-Founder', 'Strategist', 'Analyst', 'Challenger'], def: 'Strategist' },
  { k: 'experience', g: 'founder', lbl: 'Experience Level', q: 'How much of this road have you walked before?', opts: ['First-time founder', 'Second-time founder', 'Serial founder', 'Operator turned founder'], def: 'Second-time founder' },
  { k: 'feeling', g: 'founder', lbl: 'Current Feeling', q: 'Honestly — how are you feeling about it all today?', opts: ['?? Energised', '?? Optimistic', '?? Steady', '?? Stretched', '?? Overwhelmed'], def: '?? Stretched' },
  { k: 'reflection', g: 'founder', lbl: 'Stage Reflection', adaptive: true, q: '', ph: 'Say what’s really on your mind…', def: 'The teams that reach the first win almost never leave' },
];

const PQ_ADAPT = {
  Idea: 'What belief are you betting everything on?',
  'Early traction': 'What early signal tells you this is working?',
  Scaling: 'What has to break for you to reach the next level?',
  Plateau: 'What are you no longer willing to tolerate?',
};

const GROUPS = [
  { key: 'business', label: 'Business DNA' },
  { key: 'founder', label: 'Founder DNA' },
];

function profAck(k, a) {
  switch (k) {
    case 'stage': return 'Got it — ' + a.toLowerCase() + '. That reframes what I look for; the risks are different at every stage.';
    case 'building': return '“' + a + '” — specific and real. I can already picture who this is for.';
    case 'problem': return "That's the heart of it. Naming the problem this clearly tells me you've felt it yourself.";
    case 'customer': return 'Noted — ' + a + ". Knowing exactly who it's for sharpens every recommendation I'll make.";
    case 'industry': return a + ' founders usually live or die on repeat behaviour, not the first sale — I\'ll keep that lens on.';
    case 'challenges': return '“' + a + '” — thank you for being direct. That\'s the thread I\'ll pull hardest on.';
    case 'goal90': return "A clear 90-day target. I'll hold everything I learn against whether it moves that number.";
    case 'vision': return "That's a strong north star. It tells me which trade-offs you'll be willing to make.";
    case 'why': return "Thank you — that's the part most founders skip. It tells me what you'll protect even when it's slower.";
    case 'working': return 'Good to know. I\'ll show up as your ' + a.toLowerCase() + ' — direct where it helps, never noise.';
    case 'experience': return a + ' — that shapes how I pitch things: less hand-holding, more signal.';
    case 'feeling': return "Thanks for being honest about that. I'll factor how you're carrying this into how I pace us.";
    case 'reflection': return "That's a real answer. I've got a clear read on you now.";
    default: return 'Got it — thank you.';
  }
}

const reduce = typeof window !== 'undefined' && window.matchMedia
  ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false;

const sleep = (ms) => new Promise((r) => setTimeout(r, reduce ? Math.min(ms, 50) : ms));

export default function ProfileBuild() {
  const navigate = useNavigate();
  const { user, setUser } = useApp();
  const first = user?.name ? user.name.split(' ')[0] : 'there';
  const initial = (user?.initials || first).charAt(0);

  const [messages, setMessages] = useState([]);
  const [typing, setTyping] = useState(false);
  const [suggs, setSuggs] = useState([]);
  const [placeholder, setPlaceholder] = useState('Type your answer to Ally…');
  const [input, setInput] = useState('');
  const [fields, setFields] = useState({});
  const [groupsOpen, setGroupsOpen] = useState({});
  const [emptyGone, setEmptyGone] = useState(false);
  const [complete, setComplete] = useState(false);
  const [showBar, setShowBar] = useState(false);
  const [undTarget, setUndTarget] = useState(0);
  const [undDisplay, setUndDisplay] = useState(0);
  const [undNote, setUndNote] = useState('Listening…');
  const [undUp, setUndUp] = useState(false);

  const scrollRef = useRef(null);
  const taRef = useRef(null);
  const qiRef = useRef(0);
  const awaitingRef = useRef(false);
  const profileRef = useRef({});
  const started = useRef(false);
  const noteTimer = useRef(null);

  const scrollToBottom = () => {
    const s = scrollRef.current;
    if (s) s.scrollTop = s.scrollHeight;
  };
  useEffect(scrollToBottom, [messages, typing]);

  useEffect(() => {
    if (reduce) { setUndDisplay(undTarget); return; }
    let raf;
    const from = undDisplay;
    const t0 = performance.now();
    const tick = (now) => {
      const k = Math.min(1, (now - t0) / 900);
      setUndDisplay(Math.round(from + (undTarget - from) * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [undTarget]);

  const addAlly = useCallback((text) => setMessages((m) => [...m, { who: 'ally', text }]), []);
  const addMe = useCallback((text) => setMessages((m) => [...m, { who: 'me', text }]), []);

  const bumpUnd = useCallback((target, note) => {
    setUndTarget(target);
    if (note) {
      setUndNote(note);
      setUndUp(true);
      if (noteTimer.current) clearTimeout(noteTimer.current);
      noteTimer.current = setTimeout(() => { setUndUp(false); setUndNote('Listening…'); }, 1700);
    }
  }, []);

  const pqText = (q) => (q.adaptive ? (PQ_ADAPT[profileRef.current.stage] || 'What matters most to you right now?') : q.q);

  const confirmField = useCallback((k, text, animate) => {
    const q = PROFILE_Q.find((x) => x.k === k);
    setEmptyGone(true);
    setGroupsOpen((o) => ({ ...o, [q.g]: true }));
    if (animate && !reduce) {
      setFields((f) => ({ ...f, [k]: { status: 'building', text } }));
      setTimeout(() => {
        setFields((f) => ({ ...f, [k]: { status: 'on', text, justin: true } }));
        setTimeout(() => setFields((f) => ({ ...f, [k]: { ...f[k], justin: false } })), 800);
      }, 560);
    } else {
      setFields((f) => ({ ...f, [k]: { status: 'on', text } }));
    }
  }, []);

  const present = useCallback((i) => {
    const q = PROFILE_Q[i];
    setSuggs(q.opts || []);
    setPlaceholder(q.ph || 'Type your answer…');
    awaitingRef.current = true;
    if (taRef.current) taRef.current.focus();
  }, []);

  const finish = useCallback(() => {
    setSuggs([]);
    bumpUnd(100, 'Founder DNA complete');
    setComplete(true);
    setUser((prev) => ({
      ...prev,
      stage: profileRef.current.stage || prev.stage,
      problem: profileRef.current.problem || prev.problem,
      company: profileRef.current.building || prev.company,
      founderProfile: {
        ...(prev?.founderProfile || {}),
        ...profileRef.current,
      },
    }));
    addAlly(`That's everything I need, ${first}. I've got a clear read on you now — give me a moment to form a first impression.`);
    setShowBar(true);
  }, [addAlly, bumpUnd, first, setUser]);

  const askQ = useCallback(async (i) => {
    if (i >= PROFILE_Q.length) { finish(); return; }
    setTyping(true);
    await sleep(820);
    setTyping(false);
    addAlly(pqText(PROFILE_Q[i]));
    present(i);
  }, [addAlly, present, finish]);

  const answer = useCallback(async (raw) => {
    const text = (raw || '').trim();
    if (!text || !awaitingRef.current) return;
    awaitingRef.current = false;
    const i = qiRef.current;
    const q = PROFILE_Q[i];
    addMe(text);
    setInput('');
    setSuggs([]);
    if (taRef.current) taRef.current.style.height = 'auto';
    profileRef.current = { ...profileRef.current, [q.k]: text };
    confirmField(q.k, text, true);
    const nextQi = i + 1;
    qiRef.current = nextQi;

    await sleep(600);
    const n = Object.keys(profileRef.current).length;
    bumpUnd(Math.round((n / PROFILE_Q.length) * 100), 'Ally learned something new');

    setTyping(true);
    await sleep(900);
    setTyping(false);
    if (nextQi < PROFILE_Q.length) {
      addAlly(profAck(q.k, text));
      await sleep(640);
      askQ(nextQi);
    } else {
      finish();
    }
  }, [addMe, confirmField, bumpUnd, addAlly, askQ, finish]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      addAlly(`Hey ${first} — let's build your picture together. No forms, I promise. I'll ask; you answer however feels natural.`);
      await sleep(750);
      askQ(0);
    })();
  }, []);

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); answer(taRef.current.value); }
  };
  const onInput = (e) => {
    setInput(e.target.value);
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  };
  const onVoice = () => {
    const q = PROFILE_Q[qiRef.current] || {};
    setInput(q.def || "Here's my honest answer.");
    if (taRef.current) taRef.current.focus();
  };

  const groupCount = (g) =>
    PROFILE_Q.filter((q) => q.g === g && fields[q.k]?.status === 'on').length;

  return (
    <section className="view chat-view active" id="v-profile">
      <div className="chat">
        <div className="chat-main">
          <div className="chat-scroll" ref={scrollRef} aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.who === 'me' ? 'me' : 'ally'}`}>
                <span className={`m-av ${m.who === 'me' ? 'me' : 'ally'}`}>{m.who === 'me' ? initial : '?'}</span>
                <div><div className="bubble">{m.text}</div></div>
              </div>
            ))}
            {typing && (
              <div className="typing">
                <span className="m-av ally">?</span>
                <div className="bubble"><span className="td"><span /><span /><span /></span></div>
              </div>
            )}
          </div>

          <div className="suggs">
            {suggs.map((o) => (
              <button key={o} className="sugg" type="button" onClick={() => answer(o)}>{o}</button>
            ))}
          </div>

          <div className="chat-input">
            <div className="ci-row">
              <label className="sr-only" htmlFor="profText">Your answer to Ally</label>
              <textarea
                id="profText"
                ref={taRef}
                rows={1}
                placeholder={placeholder}
                value={input}
                onChange={onInput}
                onKeyDown={onKeyDown}
              />
              <button className="ci-btn" type="button" aria-label="Voice input" onClick={onVoice}>
                <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
              </button>
              <button className="ci-btn send" type="button" aria-label="Send" onClick={() => answer(taRef.current.value)}>
                <svg viewBox="0 0 24 24"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" /></svg>
              </button>
            </div>
            <p className="ci-hint">Ally is building your founder profile as you talk · Enter to send</p>
          </div>
        </div>

        <aside className="kg-panel prof-panel" aria-label="Your Founder DNA">
          <h3>Building Your Founder DNA</h3>
          <p className="kp-sub">Every answer helps Ally understand how you think, build, and lead.</p>
          <div className="understanding">
            <div className="und-row"><span className="und-l">Understanding</span><span className="und-pct">{undDisplay}%</span></div>
            <div className="und-bar"><i style={{ width: `${undTarget}%` }} /></div>
            <div className={`und-note${undUp ? ' up' : ''}`}>{undNote}</div>
          </div>

          <div className="prof-fields">
            <div className={`pf-empty${emptyGone ? ' gone' : ''}`}>
              <span className="pf-empty-ic"><span className="lv" /></span>
              <span className="pf-empty-t">I’m listening…</span>
              <span className="pf-empty-s">Your Founder DNA appears here as you answer.</span>
            </div>

            {GROUPS.map((gr) => {
              const qs = PROFILE_Q.filter((q) => q.g === gr.key);
              return (
                <div key={gr.key} className={`pfg${groupsOpen[gr.key] ? ' open' : ''}`}>
                  <div className="pfg-head">
                    <span className="pfg-t">{gr.label}</span>
                    <span className="pfg-c">{groupCount(gr.key)} / {qs.length}</span>
                  </div>
                  <div className="pfg-rows">
                    {qs.map((q) => {
                      const f = fields[q.k];
                      const status = f?.status;
                      const cls = 'pf' + (status === 'on' ? ' on' : '') + (status === 'building' ? ' building' : '') + (f?.justin ? ' justin' : '');
                      const val = status === 'on' ? f.text : status === 'building' ? 'Building…' : 'Waiting…';
                      const tag = status === 'on' ? 'Learned' : status === 'building' ? 'Building' : '';
                      return (
                        <div key={q.k} className={cls}>
                          <div className="pf-l">
                            <span className="pf-ck"><svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg></span>
                            {q.lbl}
                            <span className="pf-tag">{tag}</span>
                          </div>
                          <div className="pf-v">{val}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}

            <div className={`pf-complete${complete ? ' on' : ''}`}>
              <span className="pf-complete-ck"><svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg></span>
              <span className="pf-complete-t">Founder Profile Complete</span>
              <span className="pf-complete-s">Everything Ally learned here will guide every future conversation.</span>
            </div>
          </div>
        </aside>
      </div>

      {showBar && (
        <div className="j-bar on" style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', zIndex: 100 }}>
          <span className="jb-note">Your Founder DNA is ready.</span>
          <div className="spacer" />
          <button className="btn btn-em cta-pulse" type="button" onClick={() => navigate('/guided/tour')}>
            Continue <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>
      )}
    </section>
  );
}

