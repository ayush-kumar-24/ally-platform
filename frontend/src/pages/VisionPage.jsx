import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import {
  computeGap, imageProblem, IMAGE_TYPES, loadVision, removeTerritoryImage,
  saveSummary, saveTerritory, setTerritoryCompleted, TERRITORIES, uploadTerritoryImage,
} from '../services/vision';
import { DnaError, DnaLoading } from '../components/DnaState';
import Modal from '../components/Modal';
import { IconAnchor, IconAward, IconChat, IconCheck, IconClock, IconDollar, IconEdit, IconPlus, IconPrinter, IconTrendingUp, IconUsers } from '../utils/icons';

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

function TerritoryCard({ territory, data, onEdit, onTalk, onToggle, onPrint, busy }) {
  const isEmpty = !data.statement.trim();
  const done = Boolean(data.completedAt);
  const Icon = TERRITORY_ICON[territory.key];
  return (
    <div className={`vt-card${isEmpty ? ' is-empty' : ''}${done ? ' is-reached' : ''}`}>
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
            {/* Above the sentence, not below it: the picture is what the
                founder is aiming at and the words are the caption. A card is
                only rendered here once there IS a statement, so this never
                shows a picture with nothing under it -- which is also why the
                editor uploads a chosen file only after the words are saved. */}
            {data.imageUrl && (
              <div className="vt-image">
                <img src={data.imageUrl} alt="" loading="lazy" />
              </div>
            )}
            <p className="vt-statement">{data.statement}</p>
            <div className="vt-tags">
              {data.tag1 && <span className="vt-tag">{data.tag1}</span>}
              {data.tag2 && <span className="vt-tag muted">{data.tag2}</span>}
            </div>
          </>
        )}
      </button>
      <div className="vt-foot">
        <button type="button" className="vt-talk" onClick={() => onTalk(territory, data)}>
          <IconChat /> {isEmpty ? 'Brainstorm this with Ally' : 'Talk to Ally about this'}
        </button>
        {/* Only on a written vision. The backend answers 404 for an unwritten
            one -- there is nothing there to have reached -- so the card simply
            does not offer it rather than letting the founder find that out. */}
        {!isEmpty && (
          <button
            type="button"
            className={`vt-reach${done ? ' on' : ''}`}
            onClick={() => onToggle(territory.key, !done)}
            disabled={busy}
            aria-pressed={done}
            title={done ? 'Reopen this vision' : 'Mark this reached'}
          >
            <IconCheck /> {done ? 'Reached' : 'Mark reached'}
          </button>
        )}
        {/* Same rule as "Mark reached" above: only on a written vision. There
            is nothing to print of a placeholder, and offering it would produce
            a sheet with the prompt question on it and no answer. */}
        {!isEmpty && (
          <button type="button" className="vt-print" onClick={() => onPrint(territory, data)}
                  title="Print this vision">
            <IconPrinter /> Print
          </button>
        )}
      </div>
    </div>
  );
}

function TerritoryEditor({ territory, data, onSave, onUploadImage, onRemoveImage, onClose }) {
  const [statement, setStatement] = useState(data.statement);
  const [tag1, setTag1] = useState(data.tag1);
  const [tag2, setTag2] = useState(data.tag2);
  const [saving, setSaving] = useState(false);
  const [busyImage, setBusyImage] = useState(false);
  const [imageError, setImageError] = useState(null);
  /* A picture chosen BEFORE this territory exists server-side. The upload
     endpoint refuses to hang an image on a vision nobody has written -- and
     rightly: creating an empty statement row to hold one would put a blank
     card on the founder's page. So the file waits here and goes up the moment
     Save has created the row, in the same press.

     This used to be a disabled button reading "Save this vision first, then
     add a picture" -- honest about the constraint, but it made writing a
     vision with a picture two trips through the modal. Words and picture are
     now one form: fill in either, both, or neither. */
  const [pendingFile, setPendingFile] = useState(null);
  const [pendingPreview, setPendingPreview] = useState(null);
  const fileRef = useRef(null);

  // Whether there is a saved statement to attach an upload to RIGHT NOW --
  // the server's rule, not a rule about what the founder may fill in.
  const written = Boolean(data.statement.trim());

  /* Object URLs are held by the browser until revoked, so picking three
     pictures in one sitting would leak all three.

     Revoking lives HERE and nowhere else, keyed on the URL itself: the cleanup
     runs both when the value is replaced and when the modal unmounts, which is
     every case. Revoking inside the setState updater instead -- the obvious
     place -- would put a side effect in a function React is free to call
     twice, and in StrictMode it does, creating two URLs and storing one. */
  useEffect(() => () => { if (pendingPreview) URL.revokeObjectURL(pendingPreview); },
            [pendingPreview]);

  const clearPending = () => {
    setPendingPreview(null);
    setPendingFile(null);
  };

  const pick = async (file) => {
    setImageError(null);
    const problem = imageProblem(file);
    if (problem) { setImageError(problem); return; }

    if (!written) {
      // Nothing to attach to yet. Hold it, show it, upload it on Save.
      setPendingPreview(URL.createObjectURL(file));
      setPendingFile(file);
      if (fileRef.current) fileRef.current.value = '';
      return;
    }

    setBusyImage(true);
    try {
      await onUploadImage(file);
    } catch {
      setImageError("Couldn't upload that. Try again.");
    } finally {
      setBusyImage(false);
      // Cleared so picking the SAME file again still fires onChange -- the
      // input holds its value otherwise and a retry after an error does
      // nothing at all.
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const shownImage = data.imageUrl || pendingPreview;

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
        {/* Optional throughout: a vision is words first, and a founder who
            wants no picture should never be made to feel the card is
            unfinished without one. */}
        <div className="vt-image-field">
          <span className="vt-field-label">Picture (optional)</span>
          {shownImage ? (
            <div className="vt-image-preview">
              <img src={shownImage} alt="" />
              <div className="vt-image-buttons">
                <button type="button" className="btn btn-ghost btn-sm"
                        onClick={() => fileRef.current?.click()} disabled={busyImage || saving}>
                  {busyImage ? 'Uploading…' : 'Replace'}
                </button>
                <button type="button" className="btn btn-ghost btn-sm vt-image-remove"
                        onClick={async () => {
                          setImageError(null);
                          // A pending pick has never been uploaded, so there is
                          // nothing on the server to remove -- just drop it.
                          if (pendingFile) { clearPending(); return; }
                          setBusyImage(true);
                          try { await onRemoveImage(); }
                          catch { setImageError("Couldn't remove that. Try again."); }
                          finally { setBusyImage(false); }
                        }}
                        disabled={busyImage || saving}>
                  Remove
                </button>
              </div>
              {pendingFile && (
                <p className="vt-image-pending">Saved with your vision when you press Save.</p>
              )}
            </div>
          ) : (
            <button type="button" className="vt-image-drop"
                    onClick={() => fileRef.current?.click()}
                    disabled={busyImage || saving}>
              <IconPlus />
              {busyImage ? 'Uploading…' : 'Add a picture'}
            </button>
          )}
          <input
            ref={fileRef}
            type="file"
            accept={IMAGE_TYPES.join(',')}
            hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) pick(f); }}
          />
          {imageError && <p className="vt-image-error">{imageError}</p>}
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
                // The row exists now, so a picture chosen before it did has
                // somewhere to go. Second, not combined: the words are the
                // vision, and they must not be lost to a failed upload.
                if (pendingFile) {
                  try {
                    await onUploadImage(pendingFile);
                    clearPending();
                  } catch {
                    // Deliberately NOT a toast that disappears: the words are
                    // safely saved and only the picture failed, so the modal
                    // stays open saying exactly that, with the file still
                    // chosen so Save retries just the upload.
                    setImageError("Your vision is saved, but the picture didn't upload. Press Save to try again.");
                    return;
                  }
                }
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

/* What actually goes on the paper.

   NOT the card. The card is a tile in a six-up grid with an edit affordance,
   a "talk to Ally" button and a reached toggle -- controls that mean nothing
   printed. A founder printing one vision wants the thing itself, big: the
   picture, the sentence, and what they said would prove it.

   Rendered into the page (hidden on screen by the stylesheet) rather than
   opened in a new window: a popup would be blocked as often as not, and would
   lose the app's fonts and stylesheet with it. */
function VisionPrintSheet({ territory, data }) {
  const Icon = TERRITORY_ICON[territory.key];
  const reached = data.completedAt
    ? new Date(data.completedAt).toLocaleDateString(undefined,
        { day: 'numeric', month: 'long', year: 'numeric' })
    : null;
  return (
    <div className="vision-print-sheet" aria-hidden="true">
      <div className="vps-head">
        <span className="vps-ic"><Icon /></span>
        <span className="vps-label">{territory.label.toUpperCase()}</span>
      </div>
      {data.imageUrl && (
        <div className="vps-image"><img src={data.imageUrl} alt="" /></div>
      )}
      <p className="vps-statement">{data.statement}</p>
      {(data.tag1 || data.tag2) && (
        <div className="vps-tags">
          {data.tag1 && <span className="vps-tag">{data.tag1}</span>}
          {data.tag2 && <span className="vps-tag muted">{data.tag2}</span>}
        </div>
      )}
      {reached && <p className="vps-reached">Reached on {reached}</p>}
      <div className="vps-foot">My Vision Board &middot; Ally by GoXL</div>
    </div>
  );
}

export default function VisionPage() {
  const navigate = useNavigate();
  const { showToast, setHasVision } = useApp();
  const [state, setState] = useState({ status: 'loading', vision: null, error: null });
  const [editingKey, setEditingKey] = useState(null);
  const [reaching, setReaching] = useState(null);
  /* The one vision currently being printed, or null. Held in state rather
     than built imperatively so the sheet is ordinary React that the app's own
     stylesheet reaches. */
  const [printing, setPrinting] = useState(null);

  const load = () => {
    setState((s) => ({ ...s, status: 'loading', error: null }));
    loadVision()
      .then((vision) => setState({ status: 'ready', vision, error: null }))
      .catch((err) => setState({ status: 'error', vision: null, error: err }));
  };

  useEffect(load, []);

  /* The image endpoints return the whole stored territory, so the local copy
     is replaced outright rather than having a URL merged into it -- the server
     is the one that knows what the row now says. */
  const replaceOneTerritory = async (key, promise) => {
    const saved = await promise;
    setState((s) => ({ ...s, vision: { ...s.vision, territories: { ...s.vision.territories, [key]: saved } } }));
    return saved;
  };

  const printVision = (territory, data) => setPrinting({ territory, data });

  /* WAIT FOR THE PICTURE BEFORE OPENING THE DIALOG.

     window.print() captures the page as it stands at that instant. The card's
     <img> is loading="lazy" and the print sheet's copy is freshly mounted, so
     firing immediately prints a vision with a blank space where the founder's
     picture should be -- which is the one thing they opened this to get.

     decode() resolves when the image is actually painted, not merely fetched.
     It is raced against a timeout because a picture that will not load must
     still produce a printout of the words rather than hanging on a dialog
     that never opens. */
  useEffect(() => {
    if (!printing) return undefined;

    let cancelled = false;
    const done = () => {
      document.body.classList.remove('vp-printing');
      setPrinting(null);
    };

    /* Cleared on `afterprint`, NOT on the line after window.print().

       print() blocks until the dialog closes in Chrome and Safari, so clearing
       straight after it looks right there -- but Firefox's print preview
       returns immediately, and clearing then unmounts the sheet while the
       preview is still capturing it, printing a blank page.

       A long fallback covers the browsers that never fire afterprint at all.
       Leaving the flag set costs nothing on screen: every rule that hides the
       page lives inside @media print, so body.vp-printing is inert until
       something actually prints. */
    window.addEventListener('afterprint', done, { once: true });
    const fallback = setTimeout(done, 60000);

    const open = () => {
      if (cancelled) return;
      document.body.classList.add('vp-printing');
      // A frame so the class is applied and the sheet laid out before capture.
      requestAnimationFrame(() => { if (!cancelled) window.print(); });
    };

    const teardown = () => {
      cancelled = true;
      clearTimeout(fallback);
      window.removeEventListener('afterprint', done);
      document.body.classList.remove('vp-printing');
    };

    const url = printing.data.imageUrl;
    if (!url) { open(); return teardown; }

    const img = new Image();
    img.src = url;
    Promise.race([
      img.decode().catch(() => {}),
      new Promise((resolve) => setTimeout(resolve, 3000)),
    ]).then(open);

    return teardown;
  }, [printing]);

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

  /* Keeps the shared flag honest the moment a founder writes their first
     territory, so the sidebar renames itself without a reload. Not cleared on
     unmount: this is a fact about the founder, not a property of the page, and
     the sidebar outlives the page. Computed from `state` rather than the
     `filledCount` further down, which lives past the early returns below --
     a hook cannot. */
  const visionWritten = state.status === 'ready'
    && TERRITORIES.some((t) => state.vision.territories[t.key]?.statement.trim());
  useEffect(() => {
    if (state.status !== 'ready') return;
    setHasVision(visionWritten);
  }, [state.status, visionWritten, setHasVision]);

  if (state.status === 'loading') return <DnaLoading label="Loading your vision…" />;
  if (state.status === 'error') return <DnaError onRetry={load} />;

  const { vision } = state;
  const filledCount = TERRITORIES.filter(t => vision.territories[t.key]?.statement.trim()).length;
  const gap = computeGap(vision.summary.target, vision.summary.current);
  const hasSummary = vision.summary.target.trim() || vision.summary.current.trim();

  /* One territory at a time, keyed rather than a bare boolean, so a slow
     request disables the card being toggled and not the other five. */
  const toggleReached = async (key, next) => {
    setReaching(key);
    try {
      const t = await setTerritoryCompleted(key, next);
      setState((s) => ({
        ...s,
        vision: { ...s.vision, territories: { ...s.vision.territories, [key]: t } },
      }));
      // Only on the way in -- reopening needs no announcement, and the
      // achievement it already wrote deliberately stays.
      if (next) showToast('Reached — saved to Your Achievements.');
    } catch {
      showToast("Couldn't update that vision. Try again.");
    } finally {
      setReaching(null);
    }
  };

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
        {/* No kicker. It named the section -- "Build Your Vision" / "Your Vision
            Board" -- and so does the top bar directly above it, which is where
            that name now lives because it is state-dependent and the bar is the
            page's actual title. Two identical lines stacked is not emphasis, it
            is a stutter, so the headline leads the page instead. */}
        {/* "Build" already opens the label above in the empty state; repeating
            it here read as a stutter. The filled state keeps the verb, because
            its label ("Your Vision Board") does not carry one. */}
        <h1>{filledCount === 0 ? 'The future you actually want.' : 'Build the future you actually want.'}</h1>
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

      {printing && (
        <VisionPrintSheet territory={printing.territory} data={printing.data} />
      )}

      <div className="vt-grid">
        {TERRITORIES.map((t) => (
          <TerritoryCard
            key={t.key}
            territory={t}
            data={vision.territories[t.key] || EMPTY_TERRITORY}
            onEdit={setEditingKey}
            onTalk={talkAboutTerritory}
            onToggle={toggleReached}
            onPrint={printVision}
            busy={reaching === t.key}
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
          onUploadImage={(file) => replaceOneTerritory(editingKey, uploadTerritoryImage(editingKey, file))}
          onRemoveImage={() => replaceOneTerritory(editingKey, removeTerritoryImage(editingKey))}
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
