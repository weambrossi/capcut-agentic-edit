import { Markdown, SourceView } from './Editors.jsx';

/** Editing skills: reusable capabilities (any SKILL.md without `metadata.kind: style`). */
export default function SkillsPage({ skills, styles, selectedId, onSaved }) {
  const usedBy = (id) => styles.filter((s) => s.uses.includes(id));
  const skill = skills.find((s) => s.id === selectedId);

  if (skill) {
    return (
      <article className="page">
        <header className="page-head">
          <div className="meta-row"><a href="#/skills">Editing skills</a><code>{skill.path}</code></div>
          <h1>{skill.title}</h1>
        </header>
        <div className="stack">
          <p className="lede">{skill.description}</p>
          <UsedBy styles={usedBy(skill.id)} />
          {skill.intro && <Markdown text={skill.intro} />}
          {skill.sections.map((s) => (
            <section key={s.heading} className="rule">
              <div className="rule-head"><h3>{s.heading}</h3></div>
              <Markdown text={s.text} />
            </section>
          ))}
          <SourceView skill={skill} onSaved={onSaved} />
        </div>
      </article>
    );
  }

  return (
    <article className="page">
      <header className="page-head">
        <h1>Editing skills</h1>
        <p className="lede">
          Reusable things Claude can do in any style, like caption generation, silence removal or audio mixing.
          Styles list the skills they use under <code>metadata: uses:</code>.
        </p>
      </header>
      {skills.length === 0 ? (
        <div className="empty-block">
          <p>No editing skills yet.</p>
          <p className="muted">
            Add one as <code>.claude/skills/&lt;name&gt;/SKILL.md</code> with a <code>name</code> and{' '}
            <code>description</code>. Any skill without <code>metadata: kind: style</code> shows up here.
          </p>
        </div>
      ) : (
        <ul className="list">
          {skills.map((s) => (
            <li key={s.id}>
              <a href={`#/skills/${s.id}`} className="list-row">
                <strong>{s.title}</strong>
                <span className="muted">{s.description}</span>
                <UsedBy styles={usedBy(s.id)} compact />
              </a>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function UsedBy({ styles, compact }) {
  if (!styles.length) return compact ? null : <p className="muted">Not used by any style yet.</p>;
  return <p className="muted small">Used by {styles.map((s) => s.title).join(', ')}</p>;
}
