import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { getFramework } from '../data/frameworks';
import {
  FirstPrinciples, EightyTwenty, EisenhowerMatrix, DecisionMatrix, Swot,
  BusinessModelCanvas, Okrs, Ikigai, LeanStartup,
} from '../components/FrameworkDiagrams';
import { formatUsedDate, loadNotes, recordUsed, saveNote } from '../services/frameworks';
import { DnaError, DnaLoading } from '../components/DnaState';
import { IconArrowLeft, IconChat, IconEdit } from '../utils/icons';
import NotFound from './NotFound';

const FRAMEWORK_DIAGRAMS = {
  'first-principles': FirstPrinciples,
  '80-20': EightyTwenty,
  'eisenhower-matrix': EisenhowerMatrix,
  'decision-matrix': DecisionMatrix,
  swot: Swot,
  'business-model-canvas': BusinessModelCanvas,
  okrs: Okrs,
  ikigai: Ikigai,
  'lean-startup': LeanStartup,
};

export default function FrameworkDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showToast } = useApp();
  const framework = getFramework(id);

  const [status, setStatus] = useState('loading'); // 'loading' | 'ready' | 'error'
  const [lastUsedIso, setLastUsedIso] = useState(null);
  const [note, setNote] = useState('');
  const [editingNote, setEditingNote] = useState(false);
  const [draft, setDraft] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  // Opening this page IS "using" the framework -- the one honest signal
  // available without a real usage-tracking feature on the backend. Recorded
  // once per visit, not on every render.
  const load = () => {
    if (!getFramework(id)) return;
    setStatus('loading');
    Promise.all([recordUsed(id), loadNotes()])
      .then(([usedIso, notes]) => {
        setLastUsedIso(usedIso);
        setNote(notes[id] || '');
        setStatus('ready');
      })
      .catch(() => setStatus('error'));
  };

  useEffect(load, [id]);

  if (!framework) return <NotFound />;
  if (status === 'loading') return <DnaLoading label="Opening this framework…" />;
  if (status === 'error') return <DnaError onRetry={load} />;

  const Diagram = FRAMEWORK_DIAGRAMS[framework.id];

  const commitNote = async () => {
    setSavingNote(true);
    try {
      const saved = await saveNote(framework.id, draft);
      setNote(saved);
      setEditingNote(false);
    } catch {
      showToast("Couldn't save your note. Try again.");
    } finally {
      setSavingNote(false);
    }
  };

  return (
    <div className="fwd-page">
      <button type="button" className="fwd-back" onClick={() => navigate('/app/frameworks')}>
        <IconArrowLeft /> All frameworks
      </button>

      <div className="fwd-kicker">Thinking toolkit</div>
      <h1>{framework.title}</h1>
      <p className="fwd-tagline">{framework.tagline}</p>
      <div className="fwd-used">Last used: {formatUsedDate(lastUsedIso)}</div>

      {Diagram && (
        <div className="fwd-diagram">
          <Diagram />
        </div>
      )}

      <section className="fwd-section">
        <h2>What it is</h2>
        <p>{framework.whatItIs}</p>
      </section>

      <section className="fwd-section">
        <h2>When to reach for it</h2>
        <ul>
          {framework.whenToUse.map((line, i) => <li key={i}>{line}</li>)}
        </ul>
      </section>

      <section className="fwd-section">
        <h2>How to apply it</h2>
        <ol className="fwd-steps">
          {framework.howToApply.map((step, i) => (
            <li key={i}><span className="fwd-step-num">{i + 1}</span><span>{step}</span></li>
          ))}
        </ol>
      </section>

      <section className="fwd-section fwd-example">
        <h2>A worked example</h2>
        <p>{framework.example}</p>
      </section>

      <section className="fwd-section">
        <h2>Your note</h2>
        {editingNote ? (
          <div className="fwd-note-editor">
            <textarea
              className="modal-textarea"
              rows={3}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="How did you actually use this? What did it change?"
              autoFocus
            />
            <div className="fwd-note-acts">
              <button type="button" className="btn btn-ghost" onClick={() => setEditingNote(false)} disabled={savingNote}>Cancel</button>
              <button type="button" className="btn btn-em" onClick={commitNote} disabled={savingNote}>
                {savingNote ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        ) : note ? (
          <button type="button" className="fwd-note-existing" onClick={() => { setDraft(note); setEditingNote(true); }}>
            <blockquote>{note}</blockquote>
            <span className="fwd-note-edit-hint"><IconEdit /> Edit</span>
          </button>
        ) : (
          <button type="button" className="fwd-note-add" onClick={() => { setDraft(''); setEditingNote(true); }}>
            <IconEdit /> Add a note on how you used this
          </button>
        )}
      </section>

      <div className="fwd-cta">
        <button
          type="button"
          className="btn btn-em"
          onClick={() => navigate('/app/ally-chat', {
            state: { prefill: `I want to apply the ${framework.title} framework to something I'm working through right now.` },
          })}
        >
          <IconChat /> Talk to Ally about applying this
        </button>
      </div>
    </div>
  );
}
