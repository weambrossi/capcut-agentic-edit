import { RULE_SECTIONS, REFERENCES_HEADING } from '../server/skills.js';
import { Markdown, SectionEditor, SourceView } from './Editors.jsx';
import Examples from './Examples.jsx';
import History from './History.jsx';

const TABS = [['overview', 'Overview'], ['rules', 'Rules'], ['examples', 'Examples'], ['history', 'History']];

const findSection = (style, heading) => style.sections.find((s) => s.heading.toLowerCase() === heading.toLowerCase());

/** First bullet or sentence of a section, for the overview summary. */
function firstPoint(text) {
  const line = text.split('\n').find((l) => l.trim() && !l.startsWith('|'));
  return line ? line.replace(/^\s*(?:[-*]|\d+\.)\s+/, '') : '';
}

export default function StylePage({ style, tab, styles, editingSkills, references, onSkillSaved, onReferencesChanged }) {
  const mine = references.filter((r) => r.styles.includes(style.id));
  const current = TABS.some(([t]) => t === tab) ? tab : 'overview';

  return (
    <article className="page">
      <header className="page-head">
        <div className="meta-row">
          <span className={'badge' + (style.source === 'starter' ? ' is-starter' : '')}>{style.source === 'starter' ? 'Starter' : 'Custom'}</span>
          <code>{style.path}</code>
        </div>
        <h1>{style.title}</h1>
      </header>

      <nav className="tabs" aria-label="Style sections">
        {TABS.map(([id, label]) => (
          <a key={id} href={`#/styles/${style.id}/${id}`} className={'tab' + (current === id ? ' is-active' : '')} aria-current={current === id ? 'page' : undefined}>
            {label}
            {id === 'examples' && mine.length > 0 && <span className="tab-count">{mine.length}</span>}
          </a>
        ))}
      </nav>

      {current === 'overview' && <Overview style={style} editingSkills={editingSkills} references={mine} />}
      {current === 'rules' && <Rules style={style} onSaved={onSkillSaved} />}
      {current === 'examples' && (
        <Examples style={style} styles={styles} references={references} onChange={onReferencesChanged} />
      )}
      {current === 'history' && <History skill={style} />}
    </article>
  );
}

function Overview({ style, editingSkills, references }) {
  const known = new Set(editingSkills.map((s) => s.id));
  return (
    <div className="stack">
      <p className="lede">{style.description}</p>

      <section>
        <h2 className="label">Style settings</h2>
        <dl className="facts">
          {RULE_SECTIONS.map((h) => {
            const s = findSection(style, h);
            return (
              <div key={h} className="fact">
                <dt><a href={`#/styles/${style.id}/rules`}>{h}</a></dt>
                <dd>{s && s.text ? <Markdown inline text={firstPoint(s.text)} /> : <span className="muted">Not defined</span>}</dd>
              </div>
            );
          })}
        </dl>
      </section>

      <section>
        <h2 className="label">Editing skills</h2>
        {style.uses.length ? (
          <ul className="chips">
            {style.uses.map((id) => (
              <li key={id}>
                {known.has(id) ? <a className="chip" href={`#/skills/${id}`}>{id}</a> : <span className="chip is-missing" title="No skill with this name">{id}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">
            None linked. List editing skills under <code>metadata: uses:</code> in this style's SKILL.md to show them here.
          </p>
        )}
      </section>

      <section>
        <div className="row-between">
          <h2 className="label">Reference videos</h2>
          <a href={`#/styles/${style.id}/examples`}>{references.length ? 'View all' : 'Add videos'}</a>
        </div>
        {references.length ? (
          <ul className="ref-mini">
            {references.slice(0, 4).map((r) => (
              <li key={r.id}>
                <a href={`#/styles/${style.id}/examples`}>{r.name}</a>
                {r.notes && <span className="muted"> · {r.notes.split('\n')[0]}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No reference videos yet.</p>
        )}
      </section>
    </div>
  );
}

function Rules({ style, onSaved }) {
  const canonical = new Set(RULE_SECTIONS.map((h) => h.toLowerCase()));
  const other = style.sections.filter((s) => !canonical.has(s.heading.toLowerCase()) && s.heading !== REFERENCES_HEADING);
  return (
    <div className="stack">
      {style.intro && <div className="intro"><Markdown text={style.intro} /></div>}
      {RULE_SECTIONS.map((h) => (
        <SectionEditor key={h} skillId={style.id} heading={h} text={findSection(style, h)?.text} onSaved={onSaved} />
      ))}
      {other.length > 0 && (
        <>
          <h2 className="label label-gap">Other sections</h2>
          {other.map((s) => (
            <SectionEditor key={s.heading} skillId={style.id} heading={s.heading} text={s.text} onSaved={onSaved} />
          ))}
        </>
      )}
      <SourceView skill={style} onSaved={onSaved} />
    </div>
  );
}
