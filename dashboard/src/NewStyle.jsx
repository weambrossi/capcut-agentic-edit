import { useState } from 'react';
import { api } from './api.js';

export default function NewStyle({ onCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const id = name.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      onCreated(await api.createStyle({ name, description }));
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <article className="page">
      <header className="page-head">
        <h1>Create style</h1>
        <p className="lede">A style describes how a video should look and feel. You fill in its rules after creating it.</p>
      </header>
      <form className="form" onSubmit={submit}>
        <label className="field" htmlFor="style-name">
          <span>Name</span>
          <input id="style-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Travel vlog" required autoFocus />
          {id && <span className="hint">Saved as <code>.claude/skills/{id}/SKILL.md</code></span>}
        </label>
        <label className="field" htmlFor="style-description">
          <span>When should Claude use it?</span>
          <textarea
            id="style-description"
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. Upbeat travel recap – quick cuts on the beat, map transitions, handwritten captions. Use when the user asks for a travel or trip video."
            required
          />
          <span className="hint">Claude reads this to decide when the style applies, so name the kinds of requests it fits.</span>
        </label>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="submit" className="btn primary" disabled={saving}>{saving ? 'Creating…' : 'Create style'}</button>
          <a href="#/styles" className="btn">Cancel</a>
        </div>
      </form>
    </article>
  );
}
