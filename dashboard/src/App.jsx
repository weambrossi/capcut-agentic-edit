import { useCallback, useEffect, useState } from 'react';
import { api } from './api.js';
import Sidebar from './Sidebar.jsx';
import StylePage from './StylePage.jsx';
import SkillsPage from './SkillsPage.jsx';
import NewStyle from './NewStyle.jsx';

// #/styles/<id>/<tab>, #/skills, #/skills/<id>, #/new-style
function parseRoute() {
  const [section, id, tab] = window.location.hash.replace(/^#\/?/, '').split('/');
  return { section: section || 'styles', id, tab };
}

export const go = (path) => { window.location.hash = '/' + path; };

export default function App() {
  const [route, setRoute] = useState(parseRoute);
  const [skills, setSkills] = useState(null);
  const [references, setReferences] = useState([]);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([api.skills(), api.references()]);
      setSkills(s);
      setReferences(r);
      setError('');
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    reload();
    const onHash = () => setRoute(parseRoute());
    // pick up edits made to SKILL.md files outside the dashboard
    window.addEventListener('hashchange', onHash);
    window.addEventListener('focus', reload);
    return () => {
      window.removeEventListener('hashchange', onHash);
      window.removeEventListener('focus', reload);
    };
  }, [reload]);

  const styles = (skills || []).filter((s) => s.kind === 'style');
  const editingSkills = (skills || []).filter((s) => s.kind === 'skill');
  const replaceSkill = (next) => setSkills((all) => all.map((s) => (s.id === next.id ? next : s)));

  let page;
  if (!skills) {
    page = <p className="muted">{error || 'Loading…'}</p>;
  } else if (route.section === 'new-style') {
    page = <NewStyle onCreated={async (s) => { await reload(); go(`styles/${s.id}`); }} />;
  } else if (route.section === 'skills') {
    page = <SkillsPage skills={editingSkills} styles={styles} selectedId={route.id} onSaved={replaceSkill} />;
  } else {
    const style = styles.find((s) => s.id === route.id) || styles[0];
    page = style
      ? (
        <StylePage
          key={style.id}
          style={style}
          tab={route.tab || 'overview'}
          styles={styles}
          editingSkills={editingSkills}
          references={references}
          onSkillSaved={replaceSkill}
          onReferencesChanged={setReferences}
        />
      )
      : <EmptyStyles />;
  }

  return (
    <div className="app">
      <Sidebar route={route} styles={styles} editingSkills={editingSkills} references={references} />
      <main className="main">
        {error && skills && <p className="banner">{error}</p>}
        {page}
      </main>
    </div>
  );
}

function EmptyStyles() {
  return (
    <div className="empty">
      <h2>No video styles yet</h2>
      <p>A style describes how a video should look and feel. <a href="#/new-style">Create your first style</a>.</p>
    </div>
  );
}
