import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { computeGap, loadVision, saveSummary, saveTerritory, TERRITORIES } from '../services/vision';
import { DnaError, DnaLoading } from '../components/DnaState';
import Modal from '../components/Modal';
import { IconAnchor, IconAward, IconChat, IconClock, IconDollar, IconEdit, IconPlus, IconTrendingUp, IconUsers } from '../utils/icons';

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

const EMPTY_TERRITORY = { statement: '', tag1: '', tag2: '' };

function TerritoryCard({ territory, data, onEdit, onTalk }) {
  const isEmpty = !data.statement.trim();
  const Icon = TERRITORY_ICON[territory.key];
  return (
    <div className={`vt-card${isEmpty ? ' is-empty' : ''}`}>
      {/* The edit surface and the "talk to Ally about this one" action are
          siblings, not nested buttons -- a <button> inside a <button> is
          invalid HTML and the inner click would also fire the outer one. */}
      <button type="button" className="vt-card-body" onClick={() => onEdit(territory.key)}>
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
      <button type="button" className="vt-talk" onClick={() => onTalk(territory, data)}>
        <IconChat /> {isEmpty ? 'Brainstorm this with Ally' : 'Talk to Ally about this'}
      </button>
    </div>
  );
}

function TerritoryEditor({ territory, data, onSave, onClose }) {
  const [statement, setStatement] = useState(data.statement);
  const [tag1, setTag1] = useState(data.tag1);
  const [tag2, setTag2] = useState(data.tag2);
  const [saving, setSaving] = useState(false);

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
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button
            type="button"
            className="btn btn-em"
            disabled={!statement.trim() || saving}
            onClick={async () => {
              setSaving(true);
              try {
                await onSave({ statement: statement.trim(), tag1: tag1.trim(), tag2: tag2.trim() });
                onClose();
              } catch {
                // Save failed -- onSave() already surfaced a toast. Leave the
                // modal open so the founder's draft isn't lost and they can retry.
              } finally {
                setSaving(false);
              }
            }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default function VisionPage() {
  const navigate = useNavigate();
  const { showToast } = useApp();
  const [state, setState] = useState({ status: 'loading', vision: null, error: null });
  const [editingKey, setEditingKey] = useState(null);

  const load = () => {
    setState((s) => ({ ...s, status: 'loading', error: null }));
    loadVision()
      .then((vision) => setState({ status: 'ready', vision, error: null }))
      .catch((err) => setState({ status: 'error', vision: null, error: err }));
  };

  useEffect(load, []);

  const saveOneTerritory = async (key, value) => {
    try {
      const saved = await saveTerritory(key, value);
      setState((s) => ({ ...s, vision: { ...s.vision, territories: { ...s.vision.territories, [key]: saved } } }));
      showToast('Saved to your vision');
    } catch {
      showToast("Couldn't save that. Try again.");
      throw new Error('save failed');
    }
  };

  // Debounced so the VISION/CURRENT/unit inputs (which update on every
  // keystroke, unlike the territory editor's explicit Save button) don't
  // fire a request per character -- see hooks/useDebounce.js's own note on
  // the same tradeoff for the admin search box.
  const pendingSummary = useRef({});
  const summaryTimer = useRef(null);
  const updateSummary = (field, value) => {
    setState((s) => ({ ...s, vision: { ...s.vision, summary: { ...s.vision.summary, [field]: value } } }));
    pendingSummary.current[field] = value;
    clearTimeout(summaryTimer.current);
    summaryTimer.current = setTimeout(() => {
      const fields = pendingSummary.current;
      pendingSummary.current = {};
      saveSummary(fields).catch(() => showToast("Couldn't save your vision summary. Try again."));
    }, 500);
  };

  if (state.status === 'loading') return <DnaLoading label="Loading your vision…" />;
  if (state.status === 'error') return <DnaError onRetry={load} />;

  const { vision } = state;
  const filledCount = TERRITORIES.filter(t => vision.territories[t.key]?.statement.trim()).length;
  const gap = computeGap(vision.summary.target, vision.summary.current);
  const hasSummary = vision.summary.target.trim() || vision.summary.current.trim();

  // Opens Ally chat pre-filled with the founder's own words about that one
  // territory -- dropped into the composer for them to review/edit, never
  // sent on their behalf. No fabricated "Ally already thinks X" text; the
  // prompt just carries what they themselves wrote (or the territory's own
  // prompt question, if they haven't written anything yet).
  const talkAboutTerritory = (territory, data) => {
    const prefill = data.statement.trim()
      ? `Let's talk through my vision for ${territory.label}: "${data.statement.trim()}"`
      : `I want to think through my vision for ${territory.label} — ${territory.placeholder}`;
    navigate('/app/ally-chat', { state: { prefill } });
  };

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
          <button
            type="button"
            className="btn btn-em"
            onClick={() => navigate('/app/ally-chat', {
              state: {
                prefill: filledCount
                  ? `I want to talk through my overall vision — here's what I've written so far:\n\n${TERRITORIES
                      .filter(t => vision.territories[t.key]?.statement.trim())
                      .map(t => `${t.label}: ${vision.territories[t.key].statement.trim()}`)
                      .join('\n')}`
                  : 'I want to talk through my long-term vision, even though I haven’t written it down yet.',
              },
            })}
          >
            Talk to Ally about my vision
          </button>
        </div>
      </header>

      <div className="vt-grid">
        {TERRITORIES.map((t) => (
          <TerritoryCard
            key={t.key}
            territory={t}
            data={vision.territories[t.key] || EMPTY_TERRITORY}
            onEdit={setEditingKey}
            onTalk={talkAboutTerritory}
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
          data={vision.territories[editingKey] || EMPTY_TERRITORY}
          onSave={(value) => saveOneTerritory(editingKey, value)}
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
