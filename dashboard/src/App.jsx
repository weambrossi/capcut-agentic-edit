import { useEffect, useMemo, useState } from 'react';
import { marked } from 'marked';
import { skills } from './skills.js';

const title = (name) => name.replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase());

function useSelected() {
  const initial = () => {
    const id = window.location.hash.slice(1);
    return skills.some((s) => s.id === id) ? id : skills[0]?.id;
  };
  const [id, setId] = useState(initial);
  useEffect(() => {
    const onHash = () => setId(initial());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return id;
}

export default function App() {
  const selectedId = useSelected();
  const skill = skills.find((s) => s.id === selectedId);
  const html = useMemo(() => (skill ? marked.parse(skill.body) : ''), [skill]);
  const starters = skills.filter((s) => s.starter).length;

  return (
    <div className="app">
      <aside className="side">
        <header className="brand">
          <h1>Edit styles</h1>
          <p>
            {skills.length} styles · {skills.length - starters} from past edits
            {starters ? ` · ${starters} starter` : ''}
          </p>
        </header>
        <nav className="list">
          {skills.map((s) => (
            <a key={s.id} href={'#' + s.id} className={'item' + (s.id === selectedId ? ' is-active' : '')}>
              <span className="item-top">
                <span className="item-name">{title(s.name)}</span>
                <span className={'dot' + (s.starter ? ' is-starter' : '')} title={s.starter ? 'Starter defaults' : 'From a past edit'} />
              </span>
              <span className="item-desc">{s.description.split(' – ')[1]?.split('. Use when')[0] || s.description}</span>
            </a>
          ))}
        </nav>
      </aside>

      <main className="main">
        {skill ? (
          <article>
            <div className="eyebrow">
              <span className={'status' + (skill.starter ? ' is-starter' : '')}>
                {skill.starter ? 'Starter defaults' : 'From a past edit'}
              </span>
              <code>{skill.path}</code>
            </div>
            <h2>{title(skill.name)}</h2>
            <p className="lede">{skill.description}</p>
            <div className="md" dangerouslySetInnerHTML={{ __html: html }} />
          </article>
        ) : (
          <p className="empty">No skills yet. Add one at .claude/skills/&lt;name&gt;/SKILL.md.</p>
        )}
      </main>
    </div>
  );
}
