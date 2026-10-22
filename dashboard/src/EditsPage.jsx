import { useCallback, useEffect, useState } from 'react';
import { api, formatDate } from './api.js';

/** Edit records: Claude's original draft and the user's revised version (Learn From Edits #1–#2). */
export default function EditsPage({ styles }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(() => api.edits().then(setData, (e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const replace = (r) => setData((d) => ({ ...d, records: d.records.map((x) => (x.id === r.id ? r : x)) }));

  return (
    <article className="page">
      <header className="page-head">
        <h1>Edit history</h1>
        <p className="lede">
          Claude's original drafts and your revised versions, saved locally in <code>edits/</code>. Comparing them to suggest
          style changes comes later (issues #3–#8).
        </p>
      </header>
      {error && <p className="error">{error}</p>}
      {!data ? (
        !error && <p className="muted">Loading…</p>
      ) : (
        <div className="stack stack-top">
          {data.capcutRunning && (
            <p className="note">CapCut is open. Close it before capturing a revision: it rewrites drafts when it quits.</p>
          )}
          <RecordForm drafts={data.drafts} styles={styles} onRecorded={(r) => setData((d) => ({ ...d, records: [r, ...d.records] }))} />
          {data.records.length === 0 ? (
            <p className="muted">
              No edits recorded yet. Edits are recorded automatically when Claude saves a CapCut draft, or record one above.
            </p>
          ) : (
            <ul className="edits">
              {data.records.map((r) => (
                <EditRow key={r.id} record={r} styles={styles} drafts={data.drafts} onChange={replace} />
              ))}
            </ul>
          )}
        </div>
      )}
    </article>
  );
}

function RecordForm({ drafts, styles, onRecorded }) {
  const [draft, setDraft] = useState('');
  const [style, setStyle] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      onRecorded(await api.recordEdit({ draft, style }));
      setDraft('');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="inline-form" onSubmit={submit}>
      <label className="field" htmlFor="record-draft">
        <span>Record a CapCut draft as Claude's original</span>
        <select id="record-draft" value={draft} onChange={(e) => setDraft(e.target.value)} required>
          <option value="">Choose a draft…</option>
          {drafts.map((d) => <option key={d.name} value={d.name}>{d.name} · {formatDate(d.modified)}</option>)}
        </select>
      </label>
      <label className="field" htmlFor="record-style">
        <span>Style</span>
        <select id="record-style" value={style} onChange={(e) => setStyle(e.target.value)}>
          <option value="">None</option>
          {styles.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
        </select>
      </label>
      <button type="submit" className="btn" disabled={busy || !draft}>{busy ? 'Recording…' : 'Record'}</button>
      {error && <p className="error full">{error}</p>}
    </form>
  );
}

function Summary({ label, part }) {
  if (!part) return <div className="summary"><span className="muted">{label}</span><span className="muted">Not captured</span></div>;
  const s = part.summary;
  const types = Object.entries(s.byType).map(([t, n]) => `${n} ${t}`).join(', ');
  return (
    <div className="summary">
      <span className="muted">{label}</span>
      <span>{s.duration}s · {s.segments} segments{types && <span className="muted"> ({types})</span>}</span>
    </div>
  );
}

function EditRow({ record: r, styles, drafts, onChange }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState('');
  const [force, setForce] = useState(false);
  const titles = Object.fromEntries(styles.map((s) => [s.id, s.title]));

  async function capture() {
    setBusy(true);
    setError('');
    try {
      onChange(await api.reviseEdit(r.id, { draft: draft || null, force }));
      setDraft('');
      setForce(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function changeStyle(style) {
    try {
      onChange(await api.setEditStyle(r.id, style));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <li className="edit">
      <div className="row-between">
        <strong className="ref-name">{r.draftName}</strong>
        <span className={'badge' + (r.status === 'generated' ? ' is-starter' : '')}>
          {r.status === 'generated' ? 'Waiting for your revision' : 'Revised'}
        </span>
      </div>
      <div className="edit-meta muted small">
        <label htmlFor={`style-${r.id}`} className="sr-only">Style</label>
        <select id={`style-${r.id}`} className="select-quiet" value={r.style || ''} onChange={(e) => changeStyle(e.target.value)}>
          <option value="">No style</option>
          {styles.map((s) => <option key={s.id} value={s.id}>{titles[s.id]}</option>)}
        </select>
        <span>Recorded {formatDate(r.createdAt)}{r.source === 'hook' ? ' automatically' : ''}</span>
        {r.revisedAt && <span>Revised {formatDate(r.revisedAt)}</span>}
        <code>{r.id}</code>
      </div>
      <Summary label="Original" part={r.original} />
      <Summary label="Revised" part={r.revised} />
      {error && (
        <div className="edit-fix">
          <p className="error">{error}</p>
          <label className="field" htmlFor={`draft-${r.id}`}>
            <span>Capture from a different draft</span>
            <select id={`draft-${r.id}`} value={draft} onChange={(e) => setDraft(e.target.value)}>
              <option value="">Find it automatically</option>
              {drafts.map((d) => <option key={d.name} value={d.name}>{d.name}</option>)}
            </select>
          </label>
          <label className="check" htmlFor={`force-${r.id}`}>
            <input id={`force-${r.id}`} type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
            It's the same project even if the timeline id differs
          </label>
        </div>
      )}
      <div className="actions">
        <button type="button" className="btn" onClick={capture} disabled={busy}>
          {busy ? 'Capturing…' : r.revised ? 'Capture again' : 'Capture my revision'}
        </button>
      </div>
    </li>
  );
}
