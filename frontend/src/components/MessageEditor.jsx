import { useEffect, useLayoutEffect, useRef, useState } from 'react';

/**
 * A sent message turned back into a field, in place of its own bubble.
 *
 * In the bubble rather than in the composer on purpose: putting the text down
 * in the composer would have to overwrite whatever the founder had already
 * half-typed there, and silently throwing away someone's unsent sentence to
 * service an edit is a worse trade than the extra component. It also keeps the
 * edit visually attached to the message it belongs to, which is what makes the
 * control legible at all.
 *
 * Enter sends, Shift+Enter is a newline, Escape abandons -- the same contract
 * as the composer, so the keys mean here what they mean everywhere else in the
 * chat.
 */
export default function MessageEditor({ initialText, onSubmit, onCancel }) {
  const [value, setValue] = useState(initialText);
  const ref = useRef(null);

  /* Focus with the caret at the end, not a full selection: the founder opened
     this to adjust what they wrote, and a select-all means the first keystroke
     deletes the sentence they wanted to fix. */
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.focus();
    const end = el.value.length;
    el.setSelectionRange(end, end);
  }, []);

  // Grow to fit, same as the composer. Measured from a collapsed field so the
  // box can shrink again when text is deleted.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    if (el.scrollHeight) el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  const submit = () => {
    const next = value.trim();
    if (!next) return;
    onSubmit(next);
  };

  return (
    <div className="msg-edit">
      <label className="sr-only" htmlFor="msg-edit-field">Edit your message</label>
      <textarea
        id="msg-edit-field"
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.isComposing || e.keyCode === 229) return;   // IME picking a word
          if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
          else if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
        }}
      />
      <div className="msg-edit-row">
        <button type="button" className="msg-edit-btn" onClick={onCancel}>Cancel</button>
        <button
          type="button"
          className="msg-edit-btn primary"
          onClick={submit}
          disabled={!value.trim()}
        >
          Send again
        </button>
      </div>
    </div>
  );
}
