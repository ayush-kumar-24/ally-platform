import { useEffect, useState } from 'react';
import { useApp } from '../context/AppContext';
import { loadGoals, saveGoals } from '../services/goals';
import Modal from '../components/Modal';
import { IconCheck, IconEdit, IconPlus, IconTrash } from '../utils/icons';

function GoalCard({ goal, onEdit, onDelete }) {
  return (
    <article className="gl-card">
      <div className="gl-card-top">
        <h3>{goal.title}</h3>
        <div className="gl-card-acts">
          <button type="button" className="gl-ic-btn" onClick={() => onEdit(goal)} aria-label="Edit">
            <IconEdit />
          </button>
          <button type="button" className="gl-ic-btn" onClick={() => onDelete(goal.id)} aria-label="Delete">
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
                id: goal?.id || crypto.randomUUID(),
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
  const { user } = useApp();
  const [goals, setGoals] = useState([]);
  const [editing, setEditing] = useState(null);
  const [showEditor, setShowEditor] = useState(false);

  useEffect(() => {
    setGoals(loadGoals(user?.founderId));
  }, [user?.founderId]);

  const persist = (next) => {
    setGoals(next);
    saveGoals(user?.founderId, next);
  };

  const saveGoal = (value) => {
    const exists = goals.some(g => g.id === value.id);
    persist(exists ? goals.map(g => (g.id === value.id ? value : g)) : [value, ...goals]);
  };

  const deleteGoal = (id) => persist(goals.filter(g => g.id !== id));

  return (
    <div className="gl-page">
      <section className="gl-hero">
        <div className="gl-kicker">Goals</div>
        <h1>Outcomes you are actively moving.</h1>
        <p>Longer-horizon founder, business and life goals live here. Today's tasks stay in Plan Your Day.</p>
      </section>

      <div className="gl-toolbar">
        <span className="gl-count">{goals.length ? `${goals.length} active` : 'No goals yet'}</span>
        <button type="button" className="btn btn-em" onClick={() => { setEditing({}); setShowEditor(true); }}>
          <IconPlus /> Add goal
        </button>
      </div>

      {goals.length === 0 ? (
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
            />
          ))}
        </div>
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
