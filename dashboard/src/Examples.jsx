import { useRef, useState } from 'react';
import { api, formatBytes, formatDate, formatDuration } from './api.js';

const ACCEPT = '.mp4,.m4v,.mov,.webm,video/mp4,video/quicktime,video/webm';
const OK_EXT = /\.(mp4|m4v|mov|webm)$/i;

/** Inspiration videos for a style: upload, preview, edit metadata, remove. */
export default function Examples({ style, styles, references, onChange }) {
  const mine = references.filter((r) => r.styles.includes(style.id));
  const [staged, setStaged] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [previewing, setPreviewing] = useState(null);
  const [dragging, setDragging] = useState(false);
  const input = useRef(null);

  function addFiles(files) {
    const list = [...files];
    setRejected(list.filter((f) => !OK_EXT.test(f.name)).map((f) => f.name));
    setStaged((s) => [
      ...s,
      ...list.filter((f) => OK_EXT.test(f.name)).map((file) => ({
        key: `${file.name}-${file.size}-${Math.random()}`,
        file,
        name: file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '),
        notes: '',
        styles: [style.id],
      })),
    ]);
  }

  return (
    <div className="stack">
      <div
        className={'drop' + (dragging ? ' is-over' : '')}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
      >
        <p>
          Drop videos here or{' '}
          <button type="button" className="link-btn" onClick={() => input.current.click()}>choose files</button>
        </p>
        <p className="muted">MP4, MOV or WebM. Files stay on this machine in <code>references/videos/</code>.</p>
        <input
          ref={input}
          id="reference-files"
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
        />
      </div>
      {rejected.length > 0 && <p className="error">Not a supported video: {rejected.join(', ')}.</p>}

      {staged.map((item) => (
        <PendingUpload
          key={item.key}
          item={item}
          styles={styles}
          onChange={(next) => setStaged((s) => s.map((x) => (x.key === item.key ? next : x)))}
          onCancel={() => setStaged((s) => s.filter((x) => x.key !== item.key))}
          onUploaded={(ref) => {
            setStaged((s) => s.filter((x) => x.key !== item.key));
            onChange((all) => [...all, ref]);
          }}
        />
      ))}

      {mine.length === 0 && staged.length === 0 ? (
        <p className="muted">
          No reference videos for {style.title} yet. Add edits whose pacing, captions, transitions or music you want
          this style to learn from. Claude sees them, with your notes, when it uses this style.
        </p>
      ) : (
        <ul className="ref-grid">
          {mine.map((r) => (
            <ReferenceCard
              key={r.id}
              reference={r}
              styles={styles}
              onPreview={() => setPreviewing(r)}
              onSaved={(next) => onChange((all) => all.map((x) => (x.id === next.id ? next : x)))}
              onDeleted={() => onChange((all) => all.filter((x) => x.id !== r.id))}
            />
          ))}
        </ul>
      )}

      {previewing && (
        <div className="overlay" role="dialog" aria-modal="true" aria-label={previewing.name} onClick={() => setPreviewing(null)}>
          <div className="player" onClick={(e) => e.stopPropagation()}>
            <div className="row-between">
              <strong>{previewing.name}</strong>
              <button type="button" className="link-btn" onClick={() => setPreviewing(null)}>Close</button>
            </div>
            <video src={api.videoUrl(previewing.id)} controls autoPlay playsInline />
          </div>
        </div>
      )}
    </div>
  );
}

function StylePicker({ styles, value, onChange, idPrefix }) {
  return (
    <fieldset className="picker">
      <legend>Styles</legend>
      {styles.map((s) => (
        <label key={s.id} htmlFor={`${idPrefix}-${s.id}`}>
          <input
            id={`${idPrefix}-${s.id}`}
            type="checkbox"
            checked={value.includes(s.id)}
            onChange={(e) => onChange(e.target.checked ? [...value, s.id] : value.filter((x) => x !== s.id))}
          />
          {s.title}
        </label>
      ))}
    </fieldset>
  );
}

function PendingUpload({ item, styles, onChange, onCancel, onUploaded }) {
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState('');
  const set = (patch) => onChange({ ...item, ...patch });

  async function upload(e) {
    e.preventDefault();
    if (!item.styles.length) return setError('Pick at least one style.');
    setError('');
    setProgress(0);
    try {
      onUploaded(await api.upload(item.file, item, setProgress));
    } catch (err) {
      setError(err.message);
      setProgress(null);
    }
  }

  const busy = progress !== null;
  return (
    <form className="pending" onSubmit={upload}>
      <div className="row-between">
        <span className="muted">{item.file.name} · {formatBytes(item.file.size)}</span>
        {!busy && <button type="button" className="link-btn" onClick={onCancel}>Remove</button>}
      </div>
      <label className="field" htmlFor={`name-${item.key}`}>
        <span>Name</span>
        <input id={`name-${item.key}`} value={item.name} onChange={(e) => set({ name: e.target.value })} required disabled={busy} />
      </label>
      <label className="field" htmlFor={`notes-${item.key}`}>
        <span>What do you like about it? <span className="muted">(optional)</span></span>
        <textarea id={`notes-${item.key}`} rows={3} value={item.notes} onChange={(e) => set({ notes: e.target.value })} disabled={busy}
          placeholder="e.g. Cuts land on every beat; captions pop word by word" />
      </label>
      <StylePicker styles={styles} value={item.styles} onChange={(v) => set({ styles: v })} idPrefix={`styles-${item.key}`} />
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {busy ? `Uploading ${Math.round(progress * 100)}%` : 'Upload'}
        </button>
        {busy && <progress value={progress} max={1} />}
      </div>
    </form>
  );
}

function ReferenceCard({ reference: r, styles, onPreview, onSaved, onDeleted }) {
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState('');
  const titles = Object.fromEntries(styles.map((s) => [s.id, s.title]));
  const info = [
    r.width && `${r.width}×${r.height}`,
    r.duration && formatDuration(r.duration),
    formatBytes(r.size),
    r.originalName.split('.').pop().toUpperCase(),
  ].filter(Boolean).join(' · ');

  async function save(e) {
    e.preventDefault();
    setError('');
    try {
      onSaved(await api.updateReference(r.id, editing));
      setEditing(null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove() {
    if (!window.confirm(`Remove "${r.name}"? The video file is deleted from references/videos/.`)) return;
    try {
      await api.deleteReference(r.id);
      onDeleted();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <li className="ref">
      {r.available ? (
        <button type="button" className="thumb" onClick={onPreview} aria-label={`Preview ${r.name}`}>
          {r.thumb
            ? <img src={api.thumbUrl(r.id)} alt="" loading="lazy" />
            : <video src={`${api.videoUrl(r.id)}#t=1`} preload="metadata" muted playsInline />}
          <span className="play" aria-hidden="true">▶</span>
        </button>
      ) : (
        <div className="thumb is-missing">File not on this machine</div>
      )}

      {editing ? (
        <form className="ref-body" onSubmit={save}>
          <label className="field" htmlFor={`rn-${r.id}`}>
            <span>Name</span>
            <input id={`rn-${r.id}`} value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} required />
          </label>
          <label className="field" htmlFor={`rt-${r.id}`}>
            <span>Notes</span>
            <textarea id={`rt-${r.id}`} rows={3} value={editing.notes} onChange={(e) => setEditing({ ...editing, notes: e.target.value })} />
          </label>
          <StylePicker styles={styles} value={editing.styles} onChange={(v) => setEditing({ ...editing, styles: v })} idPrefix={`rs-${r.id}`} />
          {error && <p className="error">{error}</p>}
          <div className="actions">
            <button type="submit" className="btn primary">Save</button>
            <button type="button" className="btn" onClick={() => { setEditing(null); setError(''); }}>Cancel</button>
          </div>
        </form>
      ) : (
        <div className="ref-body">
          <strong className="ref-name">{r.name}</strong>
          <span className="muted small">{info}</span>
          {r.notes && <p className="ref-notes">{r.notes}</p>}
          <span className="muted small">{r.styles.map((s) => titles[s] || s).join(', ')} · added {formatDate(r.addedAt)}</span>
          <code className="muted small">{r.file}</code>
          {error && <p className="error">{error}</p>}
          <div className="ref-actions">
            {r.available && <button type="button" className="link-btn" onClick={onPreview}>Preview</button>}
            <button type="button" className="link-btn" onClick={() => setEditing({ name: r.name, notes: r.notes, styles: r.styles })}>Edit</button>
            <button type="button" className="link-btn danger" onClick={remove}>Remove</button>
          </div>
        </div>
      )}
    </li>
  );
}
