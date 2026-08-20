import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { computeGap, loadVision, saveVision, TERRITORIES } from '../services/vision';
import Modal from '../components/Modal';
import { IconAnchor, IconAward, IconClock, IconDollar, IconEdit, IconPlus, IconTrendingUp, IconUsers } from '../utils/icons';

// Purely decorative -- which icon marks which territory. Not a stand-in for
// data (there is none until the founder writes their own vision), just a
// visual anchor so six cards of the same shape are easier to tell apart.
const TERRITORY_ICON = {
  life: IconAnchor,
  business: IconTrendingUp,
  impact: IconUsers,
  financial: IconDollar,
  ideal_day: IconClock,
  legacy: IconAward,
};

function TerritoryCard({ territory, data, onEdit }) {
  const isEmpty = !data.statement.trim();
  const Icon = TERRITORY_ICON[territory.key];
  return (
    <button
      type="button"
      className={`vt-card${isEmpty ? ' is-empty' : ''}`}
      onClick={() => onEdit(territory.key)}
    >
      <div className="vt-top">
        <span className="vt-ic"><Icon /></span>
        <span className="vt-label">{territory.label.toUpperCase()}</span>
        {!isEmpty && <IconEdit className="vt-edit-ic" />}
      </div>
      {isEmpty ? (
        <>
          <p className="vt-placeholder">{territory.placeholder}</p>
          <span className="vt-add"><IconPlus /> Add your vision</span>
        </>
      ) : (
        <>
          <p className="vt-statement">{data.statement}</p>
          <div className="vt-tags">
            {data.tag1 && <span className="vt-tag">{data.tag1}</span>}
            {data.tag2 && <span className="vt-tag muted">{data.tag2}</span>}
          </div>
        </>
      )}
    </button>
  );
}

function TerritoryEditor({ territory, data, onSave, onClose }) {
  const [statement, setStatement] = useState(data.statement);
  const [tag1, setTag1] = useState(data.tag1);
  const [tag2, setTag2] = useState(data.tag2);

  return (
    <Modal open onClose={onClose} title={territory.label}>
      <div className="vt-editor">
        <label className="vt-field">
          <span>{territory.placeholder}</span>
          <textarea
            className="modal-textarea"
            rows={3}
            value={statement}
            onChange={(e) => setStatement(e.target.value)}
            placeholder="Write it the way you'd actually say it — specific, in your own words."
            autoFocus
          />
        </label>
        <div className="vt-field-row">
          <label className="vt-field">
            <span>A number that proves it</span>
            <input type="text" value={tag1} onChange={(e) => setTag1(e.target.value)}
                   placeholder="e.g. 4-day week" />
          </label>
          <label className="vt-field">
            <span>A milestone / date</span>
            <input type="text" value={tag2} onChange={(e) => setTag2(e.target.value)}
                   placeholder="e.g. Mar 2027" />
          </label>
        </div>
        <div className="vt-editor-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className="btn btn-em"
            disabled={!statement.trim()}
            onClick={() => { onSave({ statement: statement.trim(), tag1: tag1.trim(), tag2: tag2.trim() }); onClose(); }}
          >
            Save
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default function VisionPage() {
  const navigate = useNavigate();
  const { user, showToast } = useApp();
  const [vision, setVision] = useState(() => loadVision(user?.founderId));
  const [editingKey, setEditingKey] = useState(null);

  // Re-read if the signed-in founder changes underneath this page (rare, but
  // the id starts null and hydrates a moment after mount).
  useEffect(() => {
    setVision(loadVision(user?.founderId));
  }, [user?.founderId]);

  const persist = (next) => {
    setVision(next);
    saveVision(user?.founderId, next);
  };

  const saveTerritory = (key, value) => {
    const next = { ...vision, territories: { ...vision.territories, [key]: value } };
    persist(next);
    showToast('Saved to your vision');
  };

  const updateSummary = (field, value) => {
    persist({ ...vision, summary: { ...vision.summary, [field]: value } });
  };

  const filledCount = TERRITORIES.filter(t => vision.territories[t.key]?.statement.trim()).length;
  const gap = computeGap(vision.summary.target, vision.summary.current);
  const hasSummary = vision.summary.target.trim() || vision.summary.current.trim();

  return (
    <div className="vis-page">
      <header className="vis-head">
        <div className="vis-kicker">Your Vision</div>
        <h1>Build the future you actually want.</h1>
        <p className="vis-sub">
          {filledCount === 0
            ? 'Six territories connect what you want with a number and the milestone that proves it is becoming real.'
            : `${filledCount} of ${TERRITORIES.length} territories written. Keep going, or revisit one.`}
        </p>
        <div className="vis-head-acts">
          <button type="button" className="btn btn-ghost" onClick={() => setEditingKey(TERRITORIES.find(t => !vision.territories[t.key]?.statement.trim())?.key || TERRITORIES[0].key)}>
            <IconPlus /> Add vision
          </button>
          <button type="button" className="btn btn-em" onClick={() => navigate('/app/ally-chat')}>
            Talk to Ally about my vision
          </button>
        </div>
      </header>

      <div className="vt-grid">
        {TERRITORIES.map((t) => (
          <TerritoryCard
            key={t.key}
            territory={t}
            data={vision.territories[t.key] || { statement: '', tag1: '', tag2: '' }}
            onEdit={setEditingKey}
          />
        ))}
      </div>

      <section className="vis-summary">
        <div className="vis-sum-box">
          <span className="vis-sum-label">VISION</span>
          {editingSummaryField(vision.summary.target, (v) => updateSummary('target', v), 'e.g. ₹100Cr')}
          <span className="vis-sum-sub">
            <input
              className="vis-sum-sub-input"
              type="text"
              value={vision.summary.unit}
              onChange={(e) => updateSummary('unit', e.target.value)}
              placeholder="What this is, and by when"
            />
          </span>
        </div>
        <div className="vis-sum-box">
          <span className="vis-sum-label">CURRENT</span>
          {editingSummaryField(vision.summary.current, (v) => updateSummary('current', v), 'e.g. ₹3.4Cr')}
          <span className="vis-sum-sub">Where you are today</span>
        </div>
        <div className="vis-sum-box gap">
          <span className="vis-sum-label">GAP</span>
          <span className="vis-sum-value">
            {gap !== null ? gap.toLocaleString() : hasSummary ? '—' : '—'}
          </span>
          <span className="vis-sum-sub">
            {gap !== null ? 'Difference between vision and current' : 'Fill in vision + current above to see this'}
          </span>
        </div>
      </section>

      {editingKey && (
        <TerritoryEditor
          territory={TERRITORIES.find(t => t.key === editingKey)}
          data={vision.territories[editingKey] || { statement: '', tag1: '', tag2: '' }}
          onSave={(value) => saveTerritory(editingKey, value)}
          onClose={() => setEditingKey(null)}
        />
      )}
    </div>
  );
}

// Small inline helper so the VISION/CURRENT boxes share one input style
// without a whole extra component file for two lines of JSX.
function editingSummaryField(value, onChange, placeholder) {
  return (
    <input
      className="vis-sum-value-input"
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
    />
  );
}
