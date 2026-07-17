import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import AuthTransition from '../components/AuthTransition';


const DIMS = [
  {
    key: 'Growth',
    icon: (className) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M3 17l6-6 4 4 7-7" />
        <path d="M14 7h6v6" />
      </svg>
    ),
    q: "We're spending more on marketing every month, but our growth has completely flatlined.",
    scan: ['Acquisition', 'Retention', 'Pricing', 'Positioning'],
    map: ['Spend ↑', 'Churn leak', 'Retention'],
    root: "Your growth isn't a marketing problem — it's a retention leak. You're refilling a bucket with a hole in it.",
    conf: 92,
    acts: [
      "Fix the 30-day churn cliff before adding a rupee of spend",
      "Re-segment around your 3 highest-LTV customer types",
      "Tie one core metric to retention, not just acquisition"
    ]
  },
  {
    key: 'Sales',
    icon: (className) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M4 4h16v4H4z" />
        <path d="M6 8v12h12V8M9 12h6" />
      </svg>
    ),
    q: "My team is busy all day, but our close rate keeps dropping and I genuinely don't get it.",
    scan: ['Pipeline', 'Qualification', 'Pricing', 'Sales Motion'],
    map: ['Activity ↑', 'Weak qualifying', 'Pipeline quality'],
    root: "This isn't an effort problem — it's qualification. You're filling the pipeline with deals that were never going to close.",
    conf: 88,
    acts: [
      "Add a hard qualification gate before any demo",
      "Kill the bottom 40% of stalled pipeline this week",
      "Coach the team on discovery, not closing"
    ]
  },
  {
    key: 'Cash Flow',
    icon: (className) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="6" width="18" height="13" rx="2" />
        <circle cx="12" cy="12.5" r="2.5" />
      </svg>
    ),
    q: "We're profitable on paper, but I'm constantly anxious about making payroll each month.",
    scan: ['Collections', 'Margins', 'Burn', 'Working Capital'],
    map: ['Profit on paper', 'Cash trapped', 'Collections timing'],
    root: "You don't have a profit problem — you have a timing problem. Cash is trapped in receivables and slow collections.",
    conf: 90,
    acts: [
      "Move new contracts to Net-15 payment terms",
      "Automate dunning on every overdue invoice",
      "Build a rolling 13-week cash forecast"
    ]
  },
  {
    key: 'Team',
    icon: (className) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20a6 6 0 0 1 12 0M16 6a3 3 0 0 1 0 6m5 8a5 5 0 0 0-4-5" />
      </svg>
    ),
    q: "I've hired genuinely great people, but I still feel like everything depends on me.",
    scan: ['Ownership', 'Decision Rights', 'Hiring', 'Process'],
    map: ['Great hires', 'No ownership', 'Decision rights'],
    root: "It's not a hiring problem — it's a decision-rights problem. Your team can't act because they don't own outcomes.",
    conf: 87,
    acts: [
      "Name a clear owner for each of your 5 core outcomes",
      "Shift from approving decisions to setting guardrails",
      "Document the 3 decisions you keep re-making"
    ]
  },
  {
    key: 'Product',
    icon: (className) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M21 8l-9-5-9 5 9 5 9-5z" />
        <path d="M3 8v8l9 5 9-5V8" />
      </svg>
    ),
    q: "We keep shipping features, but our users still aren't activating. What are we missing?",
    scan: ['Onboarding', 'Core Loop', 'Value Prop', 'Retention'],
    map: ['More features', 'Drop-off', 'First value moment'],
    root: "More features won't fix this. Users are churning before they ever reach your core value moment.",
    conf: 91,
    acts: [
      "Map the exact step users drop off in onboarding",
      "Cut two features and sharpen the first five minutes",
      "Define and instrument your real 'aha' moment"
    ]
  },
  {
    key: 'Strategy',
    icon: (className) => (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="3" />
        <path d="M12 3v3m0 12v3m9-9h-3M6 12H3" />
      </svg>
    ),
    q: "We have ten priorities and somehow none of them are moving fast enough.",
    scan: ['Focus', 'Sequencing', 'Market', 'Moat'],
    map: ['10 priorities', 'Diffused energy', 'The one constraint'],
    root: "Ten priorities means zero priorities. Your strategy is diffused across bets that all compete for the same energy.",
    conf: 89,
    acts: [
      "Pick the single constraint that unlocks the others",
      "Sequence the other nine behind it",
      "Say no to the three that don't compound"
    ]
  }
];

export default function LandingPage() {
  const navigate = useNavigate();
  const { setUser } = useApp();
  const [currentDim, setCurrentDim] = useState(-1);
  const [stage, setStage] = useState(0);
  const [scannedVisibleCount, setScannedVisibleCount] = useState(0);
  const [actionsVisibleCount, setActionsVisibleCount] = useState(0);
  const [graphDrawn, setGraphDrawn] = useState(false);
  const [nodePopped, setNodePopped] = useState([false, false, false]);
  const [rootCauseVisible, setRootCauseVisible] = useState(false);
  const [progressPercent, setProgressPercent] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [timelineActiveIndex, setTimelineActiveIndex] = useState(-1);
  const [timelineHeight, setTimelineHeight] = useState(0);
  const [showAuthTransition, setShowAuthTransition] = useState(false);

  const demoPanelRef = useRef(null);
  const timelineRef = useRef(null);
  const containerRef = useRef(null);
  const timersRef = useRef([]);
  const intervalRef = useRef(null);

  // Scroll listeners for sticky nav and timeline
  useEffect(() => {
    const handleScroll = () => {
      const scrollY = containerRef.current ? containerRef.current.scrollTop : window.scrollY;
      setScrolled(scrollY > 24);

      // Timeline scroll tracker
      if (timelineRef.current) {
        const steps = timelineRef.current.querySelectorAll('.step');
        const vOffset = window.innerHeight * 0.55;
        let active = -1;

        steps.forEach((st, i) => {
          const rect = st.getBoundingClientRect();
          if (rect.top < vOffset) {
            st.classList.add('active');
            active = i;
          } else {
            st.classList.remove('active');
          }
        });

        const wrapRect = timelineRef.current.getBoundingClientRect();
        const totalHeight = wrapRect.height - 60;
        let fillVal = 0;
        if (active > -1) {
          const actRect = steps[active].getBoundingClientRect();
          fillVal = Math.max(0, Math.min(totalHeight, actRect.top - wrapRect.top + 30));
        }
        setTimelineHeight(fillVal);
        setTimelineActiveIndex(active);
      }
    };

    const container = containerRef.current || window;
    container.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => {
      container.removeEventListener('scroll', handleScroll);
    };
  }, []);

  // IntersectionObserver for cockpit demo auto-start
  useEffect(() => {
    if ('IntersectionObserver' in window && demoPanelRef.current) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && currentDim === -1) {
            setCurrentDim(0);
          }
        });
      }, { threshold: 0.25 });

      observer.observe(demoPanelRef.current);
      return () => observer.disconnect();
    } else {
      setCurrentDim(0);
    }
  }, [currentDim]);

  // Scroll-reveal via IntersectionObserver + Scroll Fallback
  useEffect(() => {
    const lp = containerRef.current;
    if (!lp) return;

    const checkReveal = () => {
      const elements = lp.querySelectorAll('.lp-reveal:not(.in)');
      const containerHeight = lp.clientHeight || window.innerHeight;
      elements.forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.top < containerHeight + 200) {
          el.classList.add('in');
        }
      });
    };

    let io;
    if ('IntersectionObserver' in window) {
      io = new IntersectionObserver((entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) {
            en.target.classList.add('in');
            io.unobserve(en.target);
          }
        });
      }, {
        root: lp,
        threshold: 0.001,
        rootMargin: '0px 0px 200px 0px'
      });

      lp.querySelectorAll('.lp-reveal').forEach((el) => {
        io.observe(el);
      });
    } else {
      lp.querySelectorAll('.lp-reveal').forEach((el) => {
        el.classList.add('in');
      });
    }

    lp.addEventListener('scroll', checkReveal, { passive: true });
    const t1 = setTimeout(checkReveal, 100);
    const t2 = setTimeout(checkReveal, 400);

    return () => {
      if (io) io.disconnect();
      lp.removeEventListener('scroll', checkReveal);
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []);

  const clearTimers = () => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const runDemoCycle = (idx, force = false) => {
    clearTimers();
    const d = DIMS[idx];
    if (!d) return;

    // Reset UI states
    setStage(0);
    setScannedVisibleCount(0);
    setActionsVisibleCount(0);
    setGraphDrawn(false);
    setNodePopped([false, false, false]);
    setRootCauseVisible(false);
    setProgressPercent(0);

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion || isPaused) {
      setStage(6);
      setScannedVisibleCount(4);
      setActionsVisibleCount(3);
      setGraphDrawn(true);
      setNodePopped([true, true, true]);
      setRootCauseVisible(true);
      setProgressPercent(d.conf);
      return;
    }

    // Stage 0 - Question (starts immediately)

    // Stage 1 - Reasoning (scan chips light up one by one)
    timersRef.current.push(setTimeout(() => {
      setStage(1);
      for (let i = 0; i < 4; i++) {
        timersRef.current.push(setTimeout(() => {
          setScannedVisibleCount(i + 1);
        }, i * 130));
      }
    }, 420));

    // Stage 2 - Knowledge Graph (draws lines & pops nodes)
    timersRef.current.push(setTimeout(() => {
      setStage(2);
      setGraphDrawn(true);
      for (let i = 0; i < 3; i++) {
        timersRef.current.push(setTimeout(() => {
          setNodePopped(prev => {
            const next = [...prev];
            next[i] = true;
            return next;
          });
        }, i * 180));
      }
    }, 1150));

    // Stage 3 - Pattern Detection
    timersRef.current.push(setTimeout(() => {
      setStage(3);
    }, 1900));

    // Stage 4 - Root Cause
    timersRef.current.push(setTimeout(() => {
      setStage(4);
      setRootCauseVisible(true);
    }, 2350));

    // Stage 5 - Confidence Bar Count up
    timersRef.current.push(setTimeout(() => {
      setStage(5);
      let val = 0;
      intervalRef.current = setInterval(() => {
        val += 3;
        if (val >= d.conf) {
          val = d.conf;
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        setProgressPercent(val);
      }, 34);
    }, 2900));

    // Stage 6 - Recommendation (priority actions show up)
    timersRef.current.push(setTimeout(() => {
      setStage(6);
      for (let i = 0; i < 3; i++) {
        timersRef.current.push(setTimeout(() => {
          setActionsVisibleCount(i + 1);
        }, i * 170));
      }
    }, 3600));
  };

  useEffect(() => {
    if (currentDim >= 0) {
      runDemoCycle(currentDim);
    }
    return clearTimers;
  }, [currentDim, isPaused]);

  // Smooth scroll helper inside landing page container
  const scrollToId = (id) => {
    const el = document.getElementById(id);
    if (el && containerRef.current) {
      const top = el.offsetTop - 76 + 4;
      containerRef.current.scrollTo({ top, behavior: 'smooth' });
    }
  };

  const handleLogin = (provider) => {
    setUser(prev => ({
      ...prev,
      authProvider: provider,
      name: 'Ayush Sharma',
      email: provider === 'linkedin' ? 'ayush.sharma@brightloom.in' : 'ayush@brightloom.in',
      initials: 'AS'
    }));
    setShowAuthTransition(true);
  };

  return (
    <div id="landing-page" ref={containerRef} className="scrollbar-thin">
      {showAuthTransition && (
        <AuthTransition onComplete={() => navigate('/guided/welcome')} />
      )}
      {/* ── STICKY NAV ────────────────────────────────────────────── */}
      <nav className={`lp-nav ${scrolled ? 'lp-scrolled' : ''}`} aria-label="Main navigation">
        <a href="#lp-hero" onClick={(e) => { e.preventDefault(); containerRef.current?.scrollTo({ top: 0, behavior: 'smooth' }); }} className="lp-nav-logo" aria-label="GoXL Ally — go to top">
          <div className="lnl-mark">Go<span className="x">XL</span></div>
        </a>

        <div className="lp-nav-links" role="list">
          <a href="#lp-story" onClick={(e) => { e.preventDefault(); scrollToId('lp-story'); }}>Our Story</a>
          <a href="#lp-engine" onClick={(e) => { e.preventDefault(); scrollToId('lp-engine'); }}>Inside the Engine</a>
          <a href="#lp-features" onClick={(e) => { e.preventDefault(); scrollToId('lp-features'); }}>Why Ally</a>
          <a href="#lp-how" onClick={(e) => { e.preventDefault(); scrollToId('lp-how'); }}>The Clarity Method</a>
          <a href="#lp-final" onClick={(e) => { e.preventDefault(); scrollToId('lp-final'); }}>Get Started</a>
        </div>

        <div className={`lp-nav-cta ${scrolled ? 'lp-show-auth' : ''}`}>
          <button className="lp-auth-btn lp-nav-auth" onClick={() => handleLogin('google')} data-lp-login="google" type="button">
            <svg className="g" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.8-6.8C35.6 2.4 30.1 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.2 17.7 9.5 24 9.5z" />
              <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9.1h12.4c-.5 2.9-2.1 5.3-4.6 7l7.1 5.5c4.2-3.9 6.6-9.6 6.6-16.4z" />
              <path fill="#FBBC05" d="M10.5 28.3c-.5-1.4-.7-2.9-.7-4.3s.3-3 .7-4.3l-7.9-6.1C1 16.7 0 20.2 0 24s1 7.3 2.6 10.4l7.9-6.1z" />
              <path fill="#34A853" d="M24 48c6.1 0 11.3-2 15-5.5l-7.1-5.5c-2 1.4-4.6 2.2-7.9 2.2-6.3 0-11.6-3.7-13.5-9.1l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
            </svg>
            <span className="na-label">Google</span>
          </button>
          <button className="lp-auth-btn lp-li lp-nav-auth" onClick={() => handleLogin('linkedin')} data-lp-login="linkedin" type="button">
            <svg className="g" viewBox="0 0 24 24" fill="#fff" aria-hidden="true">
              <path d="M4.98 3.5A2.5 2.5 0 1 0 5 8.5a2.5 2.5 0 0 0-.02-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21H19.6v-5.3c0-1.26-.02-2.9-1.77-2.9-1.77 0-2.04 1.38-2.04 2.8V21H9z" />
            </svg>
            <span className="na-label">LinkedIn</span>
          </button>
        </div>
      </nav>

      {/* ── HERO · LOGIN ─────────────────────────────────────────── */}
      <section className="lp-hero" id="lp-hero" aria-label="Hero section">
        <span className="lp-hero-orb1" aria-hidden="true"></span>
        <span className="lp-hero-orb2" aria-hidden="true"></span>
        <div className="lp-hero-particles" aria-hidden="true">
          {Array.from({ length: 45 }).map((_, i) => {
            const dur = 9 + Math.random() * 10;
            const delay = -Math.random() * dur;
            const x = Math.random() * 100;
            const sz = 2 + Math.random() * 2.4;
            return (
              <i
                key={i}
                style={{
                  left: `${x}%`,
                  width: `${sz}px`,
                  height: `${sz}px`,
                  animationDuration: `${dur}s`,
                  animationDelay: `${delay}s`
                }}
              />
            );
          })}
        </div>

        <div className="lp-hero-inner">
          <div className="j-avatar"><img src="/ally-logo.png" alt="" /></div>
          <div className="j-eye"><span className="lv"></span> GoXL &middot; Ally</div>
          <h1>Meet Ally, your <em>founder DNA</em> engine.</h1>
          <p className="lp-hero-sub">In about 20 minutes, Ally learns how you lead and finds what's really holding your business back. You'll leave with a clarity report and your next move.</p>

          <div className="lp-auth" role="group" aria-label="Login options">
            <button className="lp-auth-btn" onClick={() => handleLogin('google')} type="button">
              <svg className="g" viewBox="0 0 48 48" aria-hidden="true">
                <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.8-6.8C35.6 2.4 30.1 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.2 17.7 9.5 24 9.5z" />
                <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9.1h12.4c-.5 2.9-2.1 5.3-4.6 7l7.1 5.5c4.2-3.9 6.6-9.6 6.6-16.4z" />
                <path fill="#FBBC05" d="M10.5 28.3c-.5-1.4-.7-2.9-.7-4.3s.3-3 .7-4.3l-7.9-6.1C1 16.7 0 20.2 0 24s1 7.3 2.6 10.4l7.9-6.1z" />
                <path fill="#34A853" d="M24 48c6.1 0 11.3-2 15-5.5l-7.1-5.5c-2 1.4-4.6 2.2-7.9 2.2-6.3 0-11.6-3.7-13.5-9.1l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
              </svg>
              Continue with Google
            </button>
            <button className="lp-auth-btn lp-li" onClick={() => handleLogin('linkedin')} type="button">
              <svg className="g" viewBox="0 0 24 24" fill="#fff" aria-hidden="true">
                <path d="M4.98 3.5A2.5 2.5 0 1 0 5 8.5a2.5 2.5 0 0 0-.02-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21H19.6v-5.3c0-1.26-.02-2.9-1.77-2.9-1.77 0-2.04 1.38-2.04 2.8V21H9z" />
              </svg>
              Continue with LinkedIn
            </button>
          </div>
          <p className="lp-auth-fine">Private &amp; encrypted · we never share your business.<br /><span style={{ opacity: 0.7 }}>Demo — simulated login, no account created</span></p>
        </div>

        {/* scroll cue */}
        <div className="lp-scroll-cue" aria-hidden="true" onClick={() => scrollToId('lp-engine')} style={{ cursor: 'pointer' }}>
          <span>Scroll to explore</span>
          <div className="track"><i></i></div>
        </div>
      </section>

      {/* ── OUR STORY · Why GoXL exists ──────────────────────────── */}
      <section className="story" id="lp-story">
        <div className="lp-wrap">
          <div className="feat-head">
            <div className="lp-eyebrow center lp-reveal">Why GoXL exists</div>
            <h2 className="lp-reveal d1">Built from an unfulfilled dream.</h2>
            <p className="lp-reveal d2">Entrepreneurs aren't short on effort — they're short on clarity. Every founder hits moments of uncertainty, decision fatigue, and isolation. Passion and hard work alone don't fix that; the real gap is structure and the right support at the right time.</p>
          </div>

          <blockquote className="story-quote lp-reveal d2">
            <p className="q">"I gave everything I had — time, money, effort, passion — and still felt stuck and alone. That's when I realized: the problem was never a lack of effort. It was a lack of clarity, guidance, and structure. GoXL exists so no founder has to go through that alone."</p>
            <cite className="attribution">Viraj Desai, Founder, GoXL</cite>
          </blockquote>

          <div className="story-steps lp-reveal d3">
            <div className="story-step">
              <span className="n">01</span>
              <h3 className="t-k">Diagnose</h3>
              <p className="t-d">We assess your Founder DNA and identify exactly where your business stands.</p>
            </div>
            <div className="story-step">
              <span className="n">02</span>
              <h3 className="t-k">Define</h3>
              <p className="t-d">We align your vision with clear, achievable outcomes and priorities.</p>
            </div>
            <div className="story-step">
              <span className="n">03</span>
              <h3 className="t-k">Deliver</h3>
              <p className="t-d">We build the structure, systems, and connections to get you there — sustainably.</p>
            </div>
          </div>

          <p className="story-closing lp-reveal d3">Entrepreneurship shouldn't just be successful — it should be sustainable, structured, and deeply fulfilling.</p>
        </div>
      </section>

      {/* ── SECTION 1 · Inside the Engine ───────────────────────── */}
      <section className="cockpit dark" id="lp-engine">
        <span className="orb1" aria-hidden="true"></span>
        <span className="orb2" aria-hidden="true"></span>
        <div className="lp-wrap">
          <div className="cockpit-head">
            <div className="lp-eyebrow center light lp-reveal">Inside the engine</div>
            <h2 className="lp-reveal d1">Ask anything. Watch Ally think it through.</h2>
            <p className="lp-reveal d2">Move across a founder's situation and watch Ally trace the symptom back to the <span className="real">real</span> problem — reasoning in real time, step by step.</p>
          </div>

          <div className="dims lp-reveal d2">
            {DIMS.map((d, idx) => (
              <button
                key={d.key}
                className={`dim-btn ${currentDim === idx ? 'on' : ''}`}
                onClick={() => setCurrentDim(idx)}
                type="button"
              >
                {d.icon('')}
                {d.key}
              </button>
            ))}
          </div>

          {/* 7-stage reasoning tracker */}
          <div className="rtrack lp-reveal d2">
            <span className="rprog" style={{ width: currentDim >= 0 ? `${(stage / 6) * 86 + 7}%` : '7%' }}></span>
            {['Question', 'Reasoning', 'Knowledge Graph', 'Pattern Detection', 'Root Cause', 'Confidence', 'Recommendation'].map((label, i) => (
              <div
                key={label}
                className={`rnode ${stage === i ? 'active' : ''} ${stage > i ? 'done' : ''}`}
              >
                <span className="rdot"></span>
                <span className="rlbl">{label}</span>
              </div>
            ))}
          </div>

          <div className="demo-panel lp-reveal d3" ref={demoPanelRef}>
            <div className="demo-left">
              <div className="demo-tag"><span className="fb">F</span> A founder asks</div>
              <div className="demo-question">{currentDim >= 0 ? DIMS[currentDim].q : ''}</div>
              <div className="demo-scan-lbl">Ally is scanning across</div>
              <div className="demo-scan">
                {currentDim >= 0 && DIMS[currentDim].scan.map((s, i) => (
                  <span key={s} className={`sc ${scannedVisibleCount > i ? 'show' : ''}`}>
                    <span className="cd"></span>{s}
                  </span>
                ))}
              </div>
            </div>
            <div className="demo-right">
              <div className="demo-reason"><span className="rdot"><span></span></span> Ally reasons · connecting the dots</div>
              <div className={`kgraph ${graphDrawn ? 'draw' : ''}`}>
                <svg viewBox="0 0 460 132">
                  {/* context web */}
                  <path className="lnk faint" d="M56,44 C130,20 180,24 236,40" />
                  <path className="lnk faint" d="M56,44 C120,70 150,84 236,86" />
                  <path className="lnk faint" d="M236,86 C300,100 340,96 402,64" />
                  {/* primary causal chain */}
                  <path className="lnk" d="M56,44 C150,44 150,86 236,86" />
                  <path className="lnk hot" d="M236,86 C330,86 330,46 420,46" />
                  {/* satellite context nodes */}
                  <circle className={`node sat ${nodePopped[0] ? 'pop' : ''}`} cx="150" cy="22" r="4" />
                  <circle className={`node sat ${nodePopped[1] ? 'pop' : ''}`} cx="150" cy="108" r="4" />
                  <circle className={`node sat ${nodePopped[2] ? 'pop' : ''}`} cx="330" cy="104" r="4" />
                  {/* main nodes */}
                  <circle className="node" cx="56" cy="44" r="7" fill="rgba(255,255,255,.3)" />
                  <circle className="node" cx="236" cy="86" r="7" fill="rgba(255,255,255,.3)" />
                  <circle className="node hot" cx="420" cy="46" r="9" fill="#10B981" />
                  <text className="knode-label" x="56" y="26" textAnchor="middle">{currentDim >= 0 ? DIMS[currentDim].map[0] : 'Symptom'}</text>
                  <text className="knode-label" x="236" y="110" textAnchor="middle">{currentDim >= 0 ? DIMS[currentDim].map[1] : 'Mechanism'}</text>
                  <text className="knode-label hot" x="420" y="28" textAnchor="middle">{currentDim >= 0 ? DIMS[currentDim].map[2] : 'Root cause'}</text>
                </svg>
              </div>
              <div className="demo-root-lbl">◎ The real root cause</div>
              <div className={`demo-root ${rootCauseVisible ? 'show' : ''}`}>{currentDim >= 0 ? DIMS[currentDim].root : ''}</div>
              <div className="demo-conf">
                <span className="lbl">Diagnosis confidence</span>
                <span className="bar"><span className="fill" style={{ width: `${progressPercent}%`, transition: stage === 5 ? 'width 1.3s var(--ease-out)' : 'none' }}></span></span>
                <span className="pct">{progressPercent}%</span>
              </div>
              <div className="demo-actions-lbl">Three priority actions</div>
              <div className="demo-actions">
                {currentDim >= 0 && DIMS[currentDim].acts.map((a, i) => (
                  <div key={i} className={`demo-act ${actionsVisibleCount > i ? 'show' : ''}`}>
                    <span className="n">{i + 1}</span>
                    <span className="t">{a}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="engine-ctrls lp-reveal d3">
            <button className="eng-btn" onClick={() => setIsPaused(!isPaused)} aria-pressed={isPaused} type="button">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                {isPaused ? (
                  <path d="M8 5v14l11-7z" />
                ) : (
                  <>
                    <rect x="6" y="5" width="4" height="14" rx="1" />
                    <rect x="14" y="5" width="4" height="14" rx="1" />
                  </>
                )}
              </svg>
              {isPaused ? ' Resume' : ' Pause'}
            </button>
            <button className="eng-btn" onClick={() => { if (currentDim >= 0) runDemoCycle(currentDim, true); }} type="button">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 5V2L8 6l4 4V7a5 5 0 1 1-5 5H5a7 7 0 1 0 7-7z" />
              </svg>
              Replay
            </button>
          </div>

          <div className="demo-foot lp-reveal d3">
            <p>This is a 30-second preview. Your full Clarity Report goes far deeper.</p>
            <button className="lp-nav-btn btn-emerald small btn-sheen" onClick={() => scrollToId('lp-final')} type="button">
              Get Your Clarity Report <span className="ar" aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </section>

      {/* ── SECTION 2 · Why Ally is Different ───────────────────── */}
      <section className="feat" id="lp-features">
        <div className="lp-wrap">
          <div className="feat-head">
            <div className="lp-eyebrow center lp-reveal">Why Ally is different</div>
            <h2 className="lp-reveal d1">Not a chatbot. A reasoning engine built for founders.</h2>
            <p className="lp-reveal d2">Every part of Ally is designed to do one thing brilliantly — find what's actually holding you back, and tell you what to do about it.</p>
          </div>
          <div className="bento lp-reveal d2">
            <div className="tile wide lp-reveal">
              <h3 className="t-k">Reasons across 10+ business dimensions</h3>
              <p className="t-d">Growth, sales, cash flow, team, product, strategy and more — weighed together, the way a great advisor holds your whole business in their head.</p>
              <div className="mv viz-dims" aria-hidden="true">
                {Array.from({ length: 10 }).map((_, i) => (
                  <i key={i} style={{ height: `${[40, 65, 48, 80, 58, 92, 70, 52, 84, 62][i]}%` }}></i>
                ))}
              </div>
            </div>
            <div className="tile small lp-reveal d1">
              <h3 className="t-k">Root cause, not symptom</h3>
              <p className="t-d">Ally traces the visible problem back to the mechanism underneath.</p>
              <div className="mv viz-path" aria-hidden="true">
                <svg viewBox="0 0 360 84">
                  <path className="p" d="M26,60 C110,60 110,28 180,28 C250,28 258,48 334,40" />
                  <path className="p hot" d="M26,60 C110,60 110,28 180,28 C250,28 258,48 334,40" />
                  <circle className="ripple" cx="334" cy="40" r="7" />
                  <circle className="nd" cx="26" cy="60" r="6" />
                  <circle className="nd hot" cx="334" cy="40" r="7" />
                  <circle className="signal" cx="0" cy="0" r="4" />
                </svg>
              </div>
            </div>
            <div className="tile small lp-reveal d2 dark-tile">
              <h3 className="t-k">A real Clarity Report</h3>
              <p className="t-d">Blind spots, growth constraints and a founder health score — on paper.</p>
              <div className="viz-ring" aria-hidden="true">
                <svg viewBox="0 0 58 58">
                  <circle cx="29" cy="29" r="24" fill="none" stroke="rgba(255,255,255,.12)" strokeWidth="6" />
                  <circle cx="29" cy="29" r="24" fill="none" stroke="#34d399" strokeWidth="6" strokeLinecap="round" strokeDasharray="150" strokeDashoffset="45" transform="rotate(-90 29 29)" />
                </svg>
              </div>
            </div>
            <div className="tile mid lp-reveal">
              <h3 className="t-k">Priority actions that compound</h3>
              <p className="t-d">Not a to-do list. Three moves, sequenced so the first one unlocks the next.</p>
              <div className="mv viz-ticks" aria-hidden="true">
                <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6 9 17l-5-5" /></svg> Fix the one constraint first</span>
                <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6 9 17l-5-5" /></svg> Sequence the rest behind it</span>
                <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6 9 17l-5-5" /></svg> Say no to what doesn't compound</span>
              </div>
            </div>
            <div className="tile mid lp-reveal d1">
              <h3 className="t-k">Private, encrypted, founder-only</h3>
              <p className="t-d">Your business is yours. Every conversation with Ally is end-to-end encrypted and never shared.</p>
              <div className="mv viz-lock" aria-hidden="true">
                <span className="mesh"></span>
                <span className="shield"></span><span className="shield b"></span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                  <rect x="5" y="11" width="14" height="10" rx="2.5" />
                  <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── SECTION 3 · The GoXL Clarity Method ─────────────────── */}
      <section className="how" id="lp-how">
        <span className="glow g1" aria-hidden="true"></span>
        <span className="glow g2" aria-hidden="true"></span>
        <div className="lp-wrap">
          <div className="how-head">
            <div className="lp-eyebrow center lp-reveal">The GoXL Clarity Method™</div>
            <h2 className="lp-reveal d1">Five disciplined phases. One clear answer.</h2>
            <p className="lp-reveal d2">Not a chatbot script — a repeatable diagnostic method, encrypted end to end and built on real founder frameworks.</p>
          </div>
          <div className="steps" id="steps" ref={timelineRef}>
            <span className="fill" style={{ height: `${timelineHeight}px` }}></span>
            <div className={`step ${timelineActiveIndex === 0 ? 'active' : ''}`}>
              <div className="ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <path d="M3 11a9 9 0 0 1 18 0v4a2 2 0 0 1-2 2h-1v-6h3M5 17H4a2 2 0 0 1-2-2v-4h3v6Z" />
                </svg>
              </div>
              <div className="body">
                <div className="k">
                  <span className="num">01</span>
                  <span className="phase">Intake</span>
                  <h3>Listen</h3>
                </div>
                <p>Ally asks sharp, founder-specific questions and listens for what you're not saying.</p>
              </div>
            </div>
            <div className={`step ${timelineActiveIndex === 1 ? 'active' : ''}`}>
              <div className="ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1M7.7 16.3l-2.1 2.1" />
                </svg>
              </div>
              <div className="body">
                <div className="k">
                  <span className="num">02</span>
                  <span className="phase">Model</span>
                  <h3>Understand</h3>
                </div>
                <p>It maps your context, goals, and constraints into a living model of your business.</p>
              </div>
            </div>
            <div className={`step ${timelineActiveIndex === 2 ? 'active' : ''}`}>
              <div className="ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <circle cx="11" cy="11" r="7" />
                  <path d="m21 21-4.3-4.3M11 8v6m-3-3h6" />
                </svg>
              </div>
              <div className="body">
                <div className="k">
                  <span className="num">03</span>
                  <span className="phase">Root-Cause Trace</span>
                  <h3>Diagnose</h3>
                </div>
                <p>Ally traces symptoms to root causes across 10+ dimensions — the way a great advisor would.</p>
              </div>
            </div>
            <div className={`step ${timelineActiveIndex === 3 ? 'active' : ''}`}>
              <div className="ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6M9 13h6m-6 4h4" />
                </svg>
              </div>
              <div className="body">
                <div className="k">
                  <span className="num">04</span>
                  <span className="phase">Clarity Report</span>
                  <h3>Reveal</h3>
                </div>
                <p>You get a Founder Clarity Report: blind spots, growth constraints, and a health score.</p>
              </div>
            </div>
            <div className={`step ${timelineActiveIndex === 4 ? 'active' : ''}`}>
              <div className="ic">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                  <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />
                </svg>
              </div>
              <div className="body">
                <div className="k">
                  <span className="num">05</span>
                  <span className="phase">Action Sequence</span>
                  <h3>Guide</h3>
                </div>
                <p>Three priority actions that actually compound — sequenced for impact, not just a to-do list.</p>
              </div>
            </div>
          </div>
          <p className="how-philo lp-reveal">Because to us, entrepreneurship isn't a career choice — it's a <span className="accent">way of life.</span></p>
        </div>
      </section>

      {/* ── SECTION 4 · One Conversation from Clarity ────────────── */}
      <section className="final dark" id="lp-final">
        <span className="orb1" aria-hidden="true"></span>
        <span className="orb2" aria-hidden="true"></span>
        <div className="lp-wrap final-in">
          <div className="lp-eyebrow center light lp-reveal">One conversation from clarity</div>
          <h2 className="lp-reveal d1">Stop guessing. <span className="accent">Start knowing.</span></h2>
          <p className="lp-reveal d2">Sit down with Ally for one honest conversation. Walk away with the real root cause and the three moves that matter — this week, not someday.</p>

          <div className="lp-reveal d3">
            <span className="cta-wrap">
              <button className="btn btn-emerald btn-lg btn-sheen magnetic" onClick={() => handleLogin('google')} type="button">
                Start Your Diagnosis <span className="ar" aria-hidden="true">→</span>
              </button>
            </span>
          </div>

          <p className="final-reassure lp-reveal d3">No credit card. No sales call. Just clarity.</p>

          <ol className="final-next lp-reveal d4" aria-label="What happens next">
            <li>
              <span className="fn-n">1</span>
              <div>
                <b>Answer a few sharp questions</b>
                <span>~30 minutes, at your own pace.</span>
              </div>
            </li>
            <li>
              <span className="fn-n">2</span>
              <div>
                <b>Ally traces your root cause</b>
                <span>Across 10+ business dimensions, live.</span>
              </div>
            </li>
            <li>
              <span className="fn-n">3</span>
              <div>
                <b>Get your Clarity Report</b>
                <span>Health score, blind spots, 3 priority actions.</span>
              </div>
            </li>
          </ol>

          <div className="chips lp-reveal d5">
            <span className="chip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <rect x="5" y="11" width="14" height="9" rx="2" />
                <path d="M8 11V7a4 4 0 0 1 8 0v4" />
              </svg>
              End-to-end encrypted &amp; private
            </span>
            <span className="chip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M20 6 9 17l-5-5" />
              </svg>
              Built by GoXL Consulting
            </span>
            <span className="chip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v5l3 2" />
              </svg>
              Clarity in ~30 minutes
            </span>
          </div>
        </div>
      </section>

      {/* ── FOOTER ────────────────────────────────────────────────── */}
      <footer className="footer">
        <span className="orb e orb1"></span>
        <div className="wrap">
          <div className="footer-grid">
            <div>
              <a href="#lp-hero" onClick={(e) => { e.preventDefault(); containerRef.current?.scrollTo({ top: 0, behavior: 'smooth' }); }} className="logo" aria-label="GoXL — home">
                <span>
                  <div className="lnl-mark text-white">Go<span className="x text-emerald">XL</span></div>
                  <span className="sub">Consulting Solutions Pvt. Ltd.</span>
                </span>
              </a>
              <p className="footer-about">We enable Entrepreneurship as a Way of Life — a purpose-driven state of mind for continuous growth by creating value and impact.</p>
              <a className="footer-mail" href="mailto:info@goxl.in">info@goxl.in</a>
            </div>
            <div>
              <h4>Product</h4>
              <ul>
                <li><a href="#lp-engine" onClick={(e) => { e.preventDefault(); scrollToId('lp-engine'); }}>The Engine</a></li>
                <li><a href="#lp-how" onClick={(e) => { e.preventDefault(); scrollToId('lp-how'); }}>How it Works</a></li>
                <li><a href="#lp-final" onClick={(e) => { e.preventDefault(); scrollToId('lp-final'); }}>The Report</a></li>
                <li><a href="#lp-final" onClick={(e) => { e.preventDefault(); scrollToId('lp-final'); }}>Founders</a></li>
              </ul>
            </div>
            <div>
              <h4>Company</h4>
              <ul>
                <li><a href="#lp-features" onClick={(e) => { e.preventDefault(); scrollToId('lp-features'); }}>What Ally does</a></li>
                <li><a href="#lp-how" onClick={(e) => { e.preventDefault(); scrollToId('lp-how'); }}>Our method</a></li>
                <li><a href="mailto:info@goxl.in">Contact</a></li>
              </ul>
            </div>
            <div>
              <h4>Get started</h4>
              <ul>
                <li><a href="#lp-final" onClick={(e) => { e.preventDefault(); scrollToId('lp-final'); }}>Start a diagnosis</a></li>
                <li><a href="#lp-final" onClick={(e) => { e.preventDefault(); scrollToId('lp-final'); }}>See a sample report</a></li>
                <li><a href="mailto:info@goxl.in">Talk to GoXL</a></li>
              </ul>
            </div>
          </div>
          <div className="footer-bottom">
            <span>&copy; 2026 GoXL Consulting Solutions Pvt. Ltd. All rights reserved.</span>
            <span><a href="mailto:info@goxl.in">Privacy</a><a href="mailto:info@goxl.in">Terms</a></span>
          </div>
        </div>
      </footer>
    </div>
  );
}
