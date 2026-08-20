import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { FRAMEWORKS } from '../data/frameworks';
import { formatUsedDate, loadLastUsed, loadNotes } from '../services/frameworks';

function FrameworkCard({ framework, lastUsedIso, note, onOpen }) {
  return (
    <article className="fw-card">
      <h3>{framework.title}</h3>
      <p className="fw-tagline">{framework.tagline}</p>

      <div className="fw-meta">
        <div className="fw-meta-row">
          <span className="fw-meta-label">Use when</span>
          <span className="fw-meta-value">{framework.useWhen}</span>
        </div>
        <div className="fw-meta-row">
          <span className="fw-meta-label">Last used</span>
          <span className="fw-meta-value">{formatUsedDate(lastUsedIso)}</span>
        </div>
      </div>

      {note && <blockquote className="fw-note">{note}</blockquote>}

      <button type="button" className="fw-use-btn" onClick={() => onOpen(framework.id)}>
        Use framework
      </button>
    </article>
  );
}

export default function FrameworksPage() {
  const navigate = useNavigate();
  const { user } = useApp();
  const [lastUsed, setLastUsed] = useState({});
  const [notes, setNotes] = useState({});

  useEffect(() => {
    setLastUsed(loadLastUsed(user?.founderId));
    setNotes(loadNotes(user?.founderId));
  }, [user?.founderId]);

  return (
    <div className="fw-page">
      <div className="fw-kicker">Frameworks</div>
      <h1>Your personal thinking toolkit.</h1>
      <p className="fw-sub">
        Not a generic library. These are the frameworks you actually reach for, with context
        from the last time you used them.
      </p>

      <div className="fw-grid">
        {FRAMEWORKS.map((f) => (
          <FrameworkCard
            key={f.id}
            framework={f}
            lastUsedIso={lastUsed[f.id]}
            note={notes[f.id]}
            onOpen={(id) => navigate(`/app/frameworks/${id}`)}
          />
        ))}
      </div>
    </div>
  );
}
