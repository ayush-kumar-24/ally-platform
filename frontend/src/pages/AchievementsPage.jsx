import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import {
  createAchievement,
  deleteAchievement as deleteAchievementApi,
  getEngagement,
  listAchievements,
  updateAchievement,
} from '../services/achievements';
import { DnaError, DnaLoading } from '../components/DnaState';
import Modal from '../components/Modal';
import { IconAward, IconChat, IconEdit, IconPlus, IconTrash } from '../utils/icons';

const CATEGORIES = ['Business', 'Leadership', 'Team', 'Impact', 'Personal'];

function AchievementCard({ item, onEdit, onDelete, disabled }) {
  return (
    <article className="ach-card">
      <div className="ach-card-top">
        <h3>{item.title}</h3>
        <div className="ach-card-acts">
          <button type="button" className="ach-ic-btn" onClick={() => onEdit(item)} disabled={disabled} aria-label="Edit">
            <IconEdit />
          </button>
          <button type="button" className="ach-ic-btn" onClick={() => onDelete(item.id)} disabled={disabled} aria-label="Delete">
            <IconTrash />
          </button>
        </div>
      </div>
      {item.description && <p>{item.description}</p>}
      {(item.category || item.date) && (
        <span className="ach-tag">{[item.category, item.date].filter(Boolean).join(' · ')}</span>
      )}
    </article>
  );
}

function AchievementEditor({ item, onSave, onClose }) {
  const [title, setTitle] = useState(item?.title || '');
  const [description, setDescription] = useState(item?.description || '');
  const [category, setCategory] = useState(item?.category || CATEGORIES[0]);
  const [date, setDate] = useState(item?.date || '');

  return (
    <Modal open onClose={onClose} title={item ? 'Edit achievement' : 'Add an achievement'}>
      <div className="vt-editor">
        <label className="vt-field">
          <span>What happened</span>
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
                 placeholder="e.g. Crossed ₹1Cr ARR" autoFocus />
        </label>
        <label className="vt-field">
          <span>A line of context (optional)</span>
          <textarea className="modal-textarea" rows={2} value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="What made this one matter." />
        </label>
        <div className="vt-field-row">
          <label className="vt-field">
            <span>Category</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label className="vt-field">
            <span>When</span>
            <input type="text" value={date} onChange={(e) => setDate(e.target.value)}
                   placeholder="e.g. Jul 2026" />
          </label>
        </div>
        <div className="vt-editor-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className="btn btn-em"
            disabled={!title.trim()}
            onClick={() => {
              onSave({
                id: item?.id ?? null,
                title: title.trim(),
                description: description.trim(),
                category,
                date: date.trim(),
              });
              onClose();
            }}
          >
            Save
          </button>
        </div>
      </div>
    </Modal>
  );
}

function EngagementGate({ engagement }) {
  const navigate = useNavigate();
  const pct = Math.min(100, Math.round((engagement.messageCount / engagement.threshold) * 100));
  return (
    <section className="ach-gate">
      <div className="ach-gate-ic"><IconChat /></div>
      <h2>Keep talking to Ally to unlock this</h2>
      <p>
        Achievements come from what Ally learns about you in conversation — there isn't
        enough of your story yet for this to mean anything. You're at{' '}
        <b>{engagement.messageCount} of {engagement.threshold}</b> messages.
      </p>
      <div className="ach-gate-bar"><i style={{ width: `${pct}%` }} /></div>
      <button type="button" className="btn btn-em" onClick={() => navigate('/app/ally-chat')}>
        Talk to Ally
      </button>
    </section>
  );
}

export default function AchievementsPage() {
  const { showToast } = useApp();
  const [engagement, setEngagement] = useState(null);
  const [state, setState] = useState({ status: 'loading', items: [], error: null });
  const [editing, setEditing] = useState(null); // null = closed, {} = new, {...} = editing existing
  const [showEditor, setShowEditor] = useState(false);
  const [pending, setPending] = useState(false);

  const loadItems = () => {
    setState((s) => ({ ...s, status: 'loading', error: null }));
    listAchievements()
      .then((items) => setState({ status: 'ready', items, error: null }))
      .catch((err) => setState({ status: 'error', items: [], error: err }));
  };

  useEffect(() => {
    let cancelled = false;
    getEngagement().then((e) => { if (!cancelled) setEngagement(e); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (engagement?.unlocked) loadItems();
  }, [engagement?.unlocked]);

  const saveItem = async (value) => {
    setPending(true);
    try {
      if (value.id) {
        const updated = await updateAchievement(value.id, value);
        setState((s) => ({ ...s, items: s.items.map((i) => (i.id === updated.id ? updated : i)) }));
      } else {
        const created = await createAchievement(value);
        setState((s) => ({ ...s, items: [created, ...s.items] }));
      }
    } catch {
      showToast("Couldn't save that achievement. Try again.");
    } finally {
      setPending(false);
    }
  };

  const deleteItem = async (id) => {
    setPending(true);
    try {
      await deleteAchievementApi(id);
      setState((s) => ({ ...s, items: s.items.filter((i) => i.id !== id) }));
    } catch {
      showToast("Couldn't delete that achievement. Try again.");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="ach-page">
      <section className="ach-hero">
        <div className="ach-kicker">Your Achievements</div>
        <h1>Progress worth remembering.</h1>
        <p>Business wins, personal growth and impact milestones discovered across your journey.</p>
      </section>

      {engagement === null && <DnaLoading label="Checking in with Ally…" />}

      {engagement !== null && !engagement.unlocked && <EngagementGate engagement={engagement} />}

      {engagement?.unlocked && (
        <>
          {state.status === 'loading' && <DnaLoading label="Loading your achievements…" />}

          {state.status === 'error' && (
            <DnaError onRetry={loadItems} />
          )}

          {state.status === 'ready' && (
            <>
              <div className="ach-toolbar">
                <span className="ach-count">
                  {state.items.length ? `${state.items.length} recorded` : 'None recorded yet'}
                </span>
                <button
                  type="button"
                  className="btn btn-em"
                  disabled={pending}
                  onClick={() => { setEditing({}); setShowEditor(true); }}
                >
                  <IconPlus /> Add achievement
                </button>
              </div>

              {state.items.length === 0 ? (
                <div className="ach-empty">
                  <IconAward />
                  <p>Nothing added yet. When something feels worth remembering, put it here.</p>
                </div>
              ) : (
                <div className="ach-grid">
                  {state.items.map((item) => (
                    <AchievementCard
                      key={item.id}
                      item={item}
                      disabled={pending}
                      onEdit={(i) => { setEditing(i); setShowEditor(true); }}
                      onDelete={deleteItem}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}

      {showEditor && (
        <AchievementEditor
          item={editing?.id ? editing : null}
          onSave={saveItem}
          onClose={() => setShowEditor(false)}
        />
      )}
    </div>
  );
}
