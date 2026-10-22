// Every SKILL.md under .claude/skills, read at build time (and live in dev).
const files = import.meta.glob('../../.claude/skills/*/SKILL.md', {
  query: '?raw',
  import: 'default',
  eager: true,
});

function parse(path, raw) {
  const match = raw.match(/^---\n([\s\S]*?)\n---\n?/);
  const meta = {};
  if (match) {
    for (const line of match[1].split('\n')) {
      const i = line.indexOf(':');
      if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    }
  }
  const body = match ? raw.slice(match[0].length) : raw;
  const id = path.split('/').at(-2);
  return {
    id,
    name: meta.name || id,
    description: meta.description || '',
    // a skill still on placeholder values says so in an HTML comment
    starter: /STARTER DEFAULTS/.test(body),
    // the page shows its own title, so drop the file's leading "# Heading"
    body: body.replace(/<!--[\s\S]*?-->\n?/g, '').trimStart().replace(/^# .*\n+/, ''),
    path: '.claude/skills/' + id + '/SKILL.md',
  };
}

export const skills = Object.entries(files)
  .map(([path, raw]) => parse(path, raw))
  .sort((a, b) => a.name.localeCompare(b.name));
