export default function Sidebar({ route, styles, editingSkills, references }) {
  const refCount = (id) => references.filter((r) => r.styles.includes(id)).length;
  const groups = [
    ['Custom', styles.filter((s) => s.source === 'custom')],
    ['Starter', styles.filter((s) => s.source === 'starter')],
  ].filter(([, list]) => list.length);
  const activeStyle = route.section === 'styles' ? route.id || styles[0]?.id : null;

  return (
    <aside className="side">
      <div className="side-title">Video editing</div>
      <nav className="nav" aria-label="Sections">
        <div className="nav-head">
          <a href="#/styles" className={'nav-section' + (route.section === 'styles' ? ' is-open' : '')}>Video styles</a>
          <a href="#/new-style" className="nav-add" title="New style" aria-label="New style">+</a>
        </div>
        {groups.map(([label, list]) => (
          <div key={label} className="nav-group">
            <div className="nav-group-label">{label}</div>
            {list.map((s) => (
              <a key={s.id} href={`#/styles/${s.id}`} className={'nav-item' + (s.id === activeStyle ? ' is-active' : '')}>
                <span className="nav-item-name">{s.title}</span>
                {refCount(s.id) > 0 && <span className="nav-count" title="Reference videos">{refCount(s.id)}</span>}
              </a>
            ))}
          </div>
        ))}
        <a href="#/new-style" className={'nav-item nav-create' + (route.section === 'new-style' ? ' is-active' : '')}>Create style</a>

        <div className="nav-head nav-head-gap">
          <a href="#/skills" className={'nav-section' + (route.section === 'skills' ? ' is-open' : '')}>Editing skills</a>
          <span className="nav-count">{editingSkills.length}</span>
        </div>
        {editingSkills.map((s) => (
          <a key={s.id} href={`#/skills/${s.id}`} className={'nav-item' + (route.section === 'skills' && route.id === s.id ? ' is-active' : '')}>
            <span className="nav-item-name">{s.title}</span>
          </a>
        ))}
      </nav>
    </aside>
  );
}
