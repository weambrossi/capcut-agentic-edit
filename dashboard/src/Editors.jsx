import { useState } from 'react';
import { marked } from 'marked';
import { api } from './api.js';

export function Markdown({ text, inline = false }) {
  const html = inline ? marked.parseInline(text) : marked.parse(text);
  return inline
    ? <span className="md-inline" dangerouslySetInnerHTML={{ __html: html }} />
    : <div className="md" dangerouslySetInnerHTML={{ __html: html }} />;
}

/** One `## heading` of a SKILL.md, shown rendered and editable in place. */
export function SectionEditor({ skillId, heading, text, onSaved, emptyLabel = 'Not defined yet.' }) {
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const exists = text !== undefined;

  async function save() {
    setSaving(true);
    setError('');
    try {
      onSaved(await api.saveSection(skillId, { heading, original: exists ? text : null, text: draft }));
      setDraft(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rule" id={'rule-' + heading.toLowerCase().replace(/[^a-z]+/g, '-')}>
      <div className="rule-head">
        <h3>{heading}</h3>
        {draft === null && (
          <button type="button" className="link-btn" onClick={() => setDraft(text || '')}>
            {text ? 'Edit' : 'Add'}
          </button>
        )}
      </div>
      {draft === null ? (
        text ? <Markdown text={text} /> : <p className="muted">{emptyLabel}</p>
      ) : (
        <div className="editor">
          <textarea
            id={'edit-' + skillId + '-' + heading}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={Math.min(18, Math.max(5, draft.split('\n').length + 1))}
            spellCheck="false"
            autoFocus
          />
          <p className="hint">Markdown. Only this section of SKILL.md is rewritten.</p>
          {error && <p className="error">{error}</p>}
          <div className="actions">
            <button type="button" className="btn primary" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
            <button type="button" className="btn" onClick={() => { setDraft(null); setError(''); }}>Cancel</button>
          </div>
        </div>
      )}
    </section>
  );
}

/** The whole SKILL.md as written, with a raw edit fallback for anything the sections don't cover. */
export function SourceView({ skill, onSaved }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState('');

  async function save() {
    setError('');
    try {
      onSaved(await api.saveSource(skill.id, { original: skill.raw, text: draft }));
      setDraft(null);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <section className="source">
      <button type="button" className="link-btn" onClick={() => setOpen(!open)} aria-expanded={open}>
        {open ? 'Hide source' : 'Advanced: view source'}
      </button>
      {open && (
        <div className="source-body">
          <div className="rule-head">
            <code className="muted">{skill.path}</code>
            {draft === null && <button type="button" className="link-btn" onClick={() => setDraft(skill.raw)}>Edit source</button>}
          </div>
          {draft === null ? (
            <pre className="code">{skill.raw}</pre>
          ) : (
            <div className="editor">
              <textarea id={'source-' + skill.id} value={draft} onChange={(e) => setDraft(e.target.value)} rows={28} spellCheck="false" />
              {error && <p className="error">{error}</p>}
              <div className="actions">
                <button type="button" className="btn primary" onClick={save}>Save file</button>
                <button type="button" className="btn" onClick={() => { setDraft(null); setError(''); }}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
