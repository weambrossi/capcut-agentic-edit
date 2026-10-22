import { useEffect, useState } from 'react';
import { api, formatDate } from './api.js';

/** Revisions of a SKILL.md from git. Read-only: restoring a revision is planned, not built. */
export default function History({ skill }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(null);
  const [text, setText] = useState('');

  useEffect(() => {
    api.history(skill.id).then(setData, (e) => setError(e.message));
  }, [skill.id, skill.raw]);

  async function toggle(hash) {
    if (open === hash) return setOpen(null);
    setOpen(hash);
    setText('');
    try {
      setText((await api.revision(skill.id, hash)).text);
    } catch (e) {
      setText(e.message);
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;

  return (
    <div className="stack">
      {data.uncommitted && (
        <p className="note">This file has changes that aren't committed yet. Commit them to add a revision here.</p>
      )}
      {data.commits.length === 0 ? (
        <p className="muted">No revisions yet. Revisions appear here once the file is committed to git.</p>
      ) : (
        <ol className="history">
          {data.commits.map((c) => (
            <li key={c.hash}>
              <button type="button" className="history-row" onClick={() => toggle(c.hash)} aria-expanded={open === c.hash}>
                <span className="history-subject">{c.subject}</span>
                <span className="muted history-meta">{formatDate(c.date)} · <code>{c.short}</code></span>
              </button>
              {open === c.hash && <pre className="code">{text || 'Loading…'}</pre>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
