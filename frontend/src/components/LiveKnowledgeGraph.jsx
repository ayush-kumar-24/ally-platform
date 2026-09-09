/**
 * components/LiveKnowledgeGraph.jsx — the side panel that shows a founder their
 * own answers being connected to something.
 *
 * It lived inline in DiagnosisChat and only ever appeared there, even though
 * `.chat` (platform.css) is a two-column grid that reserves 300px for it on
 * every page using that layout -- so Founder DNA and Current Problem rendered
 * an empty column beside the conversation. Sharing it fills that column and
 * gives all three phases the same "Ally is listening" feedback.
 *
 * WHY `phase` INSTEAD OF COPY PROPS. The three phases do not produce the same
 * thing, and the panel must not claim they do: Founder DNA does not find a root
 * cause, and Current Problem only decides where the diagnosis starts. Saying
 * "Root cause" in either would be the panel promising a finding that phase
 * cannot make. The wording therefore lives here, keyed by phase, rather than
 * being passed in and drifting per call site.
 */

import { useEffect, useRef } from 'react';

/** What each phase is honestly allowed to say it is building towards. */
const PHASES = {
  'founder-dna': {
    subtitle: 'How Ally is turning what you say into your Founder DNA.',
    mid: ['Listening…', 'Pattern'],
    end: ['In your profile', 'Founder DNA'],
    legend: ['What you told us', 'Pattern Ally inferred', 'Your Founder DNA'],
  },
  'current-problem': {
    subtitle: 'How Ally is connecting the problem you describe to what to test.',
    mid: ['Listening…', 'Theme'],
    end: ['Next: diagnosis', 'Where we start'],
    legend: ['What you described', 'Theme Ally inferred', 'Where the diagnosis starts'],
  },
  diagnosis: {
    subtitle: 'How Ally is connecting what you say to the underlying cause.',
    mid: ['Listening…', 'Mechanism'],
    end: ['In your report', 'Root cause'],
    legend: ['Symptoms you described', 'Mechanism Ally inferred', 'Root cause'],
  },
};

/** The founder's own answers, newest last, short enough to sit on a node. */
function answerLabels(messages) {
  return (messages ?? [])
    .filter(m => m.role === 'me' && m.text?.trim())
    .slice(-3)
    .map(m => (m.text.length > 22 ? `${m.text.slice(0, 21).trimEnd()}…` : m.text));
}

export default function LiveKnowledgeGraph({ phase, messages, resolved = false }) {
  const kgRef = useRef(null);
  const answers = answerLabels(messages);
  const copy = PHASES[phase] ?? PHASES.diagnosis;
  const midLabel = copy.mid[resolved ? 1 : 0];
  const endLabel = copy.end[resolved ? 1 : 0];

  /* Draws the edges in shortly after each new answer. The timer is cleared on
     every re-run: this effect fires per message, and without cleanup each one
     left an orphaned timeout still reaching for a node after unmount. */
  useEffect(() => {
    if (!kgRef.current) return undefined;
    const t = setTimeout(() => kgRef.current?.classList.add('draw'), 800);
    return () => clearTimeout(t);
  }, [messages]);

  return (
    <div className="kg-panel">
      {/* h3, not h2: .kg-panel styles h3 and has no h2 rule, so the heading
          rendered unstyled at browser-default size for as long as this existed. */}
      <h3>Live knowledge graph</h3>
      <p className="kp-sub">{copy.subtitle}</p>
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
          {[43, 123, 183].map((y, i) => (
            <text key={y} className="kg-lbl" x="52" y={y}>{answers[i] || '—'}</text>
          ))}
          {/* Named only once the phase has actually produced it -- while
              questions are still being answered there is nothing truthful to
              put here, so it says what it is doing instead. */}
          <text className="kg-lbl hot" x="96" y="118">{midLabel}</text>
          <text className="kg-lbl hot" x="176" y="172">{endLabel}</text>
        </svg>
      </div>
      <div className="kg-legend">
        <div className="kg-leg">
          <span className="d" style={{ background: 'rgba(255,255,255,.3)' }} /> {copy.legend[0]}
        </div>
        <div className="kg-leg">
          <span className="d" style={{ background: '#34d399' }} /> {copy.legend[1]}
        </div>
        <div className="kg-leg">
          <span className="d" style={{ background: '#A8D94A' }} /> {copy.legend[2]}
        </div>
      </div>
      {answers.length === 0 && (
        <p className="kp-sub" style={{ marginTop: 10 }}>
          Nothing plotted yet — this fills in from your answers as you go.
        </p>
      )}
    </div>
  );
}
