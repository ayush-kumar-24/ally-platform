import { useEffect, useState } from 'react';
import { useApp } from '../context/AppContext';
import { createGoal, deleteGoal as deleteGoalApi, listGoals, updateGoal } from '../services/goals';
import { DnaError, DnaLoading } from '../components/DnaState';
import Modal from '../components/Modal';
import { IconCheck, IconEdit, IconPlus, IconTrash } from '../utils/icons';

function GoalCard({ goal, onEdit, onDelete, disabled }) {
  return (
    <article className="gl-card">
      <div className="gl-card-top">
        <h3>{goal.title}</h3>
        <div className="gl-card-acts">
          <button type="button" className="gl-ic-btn" onClick={() => onEdit(goal)} disabled={disabled} aria-label="Edit">
            <IconEdit />
          </button>
          <button type="button" className="gl-ic-btn" onClick={() => onDelete(goal.id)} disabled={disabled} aria-label="Delete">
            <IconTrash />
          </button>
        </div>
      </div>
      {goal.subtitle && <p>{goal.subtitle}</p>}
    </article>
  );
}

function GoalEditor({ goal, onSave, onClose }) {
  const [title, setTitle] = useState(goal?.title || '');
  const [subtitle, setSubtitle] = useState(goal?.subtitle || '');

  return (
    <Modal open onClose={onClose} title={goal ? 'Edit goal' : 'Add a goal'}>
      <div className="vt-editor">
        <label className="vt-field">
          <span>The outcome</span>
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
                 placeholder="e.g. ₹5Cr annual revenue" autoFocus />
        </label>
        <label className="vt-field">
          <span>Where it stands (optional)</span>
          <input type="text" value={subtitle} onChange={(e) => setSubtitle(e.target.value)}
                 placeholder="e.g. ₹3.4Cr achieved · due 31 Mar 2027" />
        </label>
        <div className="vt-editor-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className="btn btn-em"
            disabled={!title.trim()}
            onClick={() => {
              onSave({
                id: goal?.id ?? null,
                title: title.trim(),
                subtitle: subtitle.trim(),
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

export default function GoalsPage() {
  const { user, showToast } = useApp();
  const [state, setState] = useState({ status: 'loading' });
  const [editing, setEditing] = useState(null);
  const [showEditor, setShowEditor] = useState(false);
  // Per-goal save/delete in flight, so a slow request can't be fired twice
  // from a second click and the button can show it's working.
  const [pending, setPending] = useState(false);

  const load = () => {
    setState({ status: 'loading' });
    listGoals()
      .then((goals) => setState({ status: 'ready', goals }))
      .catch((error) => setState({ status: 'error', error }));
  };

  useEffect(load, [user?.founderId]);

  const goals = state.status === 'ready' ? state.goals : [];

  const saveGoal = async (value) => {
    setPending(true);
    try {
      if (value.id) {
        const updated = await updateGoal(value.id, { title: value.title, subtitle: value.subtitle });
        setState((s) => ({ ...s, goals: s.goals.map((g) => (g.id === updated.id ? updated : g)) }));
      } else {
        const created = await createGoal({ title: value.title, subtitle: value.subtitle });
        setState((s) => ({ ...s, goals: [created, ...s.goals] }));
      }
    } catch {
      // The modal already closed optimistically -- tell them it didn't
      // actually save rather than silently dropping the goal.
      showToast("Couldn't save that goal. Try again.");
    } finally {
      setPending(false);
    }
  };

  const deleteGoal = async (id) => {
    setPending(true);
    try {
      await deleteGoalApi(id);
      setState((s) => ({ ...s, goals: s.goals.filter((g) => g.id !== id) }));
    } catch {
      showToast("Couldn't delete that goal. Try again.");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="gl-page">
      <section className="gl-hero">
        <div className="gl-kicker">Goals</div>
        <h1>Outcomes you are actively moving.</h1>
        <p>Longer-horizon founder, business and life goals live here. Today's tasks stay in Plan Your Day.</p>
      </section>

      {state.status === 'ready' && (
        <div className="gl-toolbar">
          <span className="gl-count">{goals.length ? `${goals.length} active` : 'No goals yet'}</span>
          <button type="button" className="btn btn-em" onClick={() => { setEditing({}); setShowEditor(true); }}>
            <IconPlus /> Add goal
          </button>
        </div>
      )}

      {state.status === 'loading' && <DnaLoading label="Loading your goals…" />}
      {state.status === 'error' && <DnaError onRetry={load} />}

      {state.status === 'ready' && (
        goals.length === 0 ? (
          <div className="gl-empty">
            <IconCheck />
            <p>Nothing set yet. Add the outcome you're actually moving toward right now.</p>
          </div>
        ) : (
          <div className="gl-grid">
            {goals.map((goal) => (
              <GoalCard
                key={goal.id}
                goal={goal}
                onEdit={(g) => { setEditing(g); setShowEditor(true); }}
                onDelete={deleteGoal}
                disabled={pending}
              />
            ))}
          </div>
        )
      )}

      {showEditor && (
        <GoalEditor
          goal={editing?.id ? editing : null}
          onSave={saveGoal}
          onClose={() => setShowEditor(false)}
        />
      )}
    </div>
  );
}
