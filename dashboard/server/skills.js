// Reading and lossless section editing of .claude/skills/*/SKILL.md. Pure functions over file text.

// The rule groups the dashboard shows for a style, in order. A SKILL.md section belongs to the
// group whose heading it has (case-insensitive); anything else is an "other" section.
export const RULE_SECTIONS = [
  'Format',
  'Pacing & Transitions',
  'Captions & Typography',
  'Sound',
  'Color & Visual Effects',
];
// managed by the dashboard (points Claude at references.md), not shown as a rule
export const REFERENCES_HEADING = 'Reference videos';

const FRONTMATTER = /^---\n([\s\S]*?)\n---\n?/;

/** name/description plus one level of nesting (`metadata:` with indented keys). */
export function parseFrontmatter(raw) {
  const m = raw.match(FRONTMATTER);
  const meta = {};
  if (!m) return { meta, end: 0 };
  let parent = null;
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^(\s*)([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!kv) continue;
    const [, indent, key, value] = kv;
    if (indent && parent) parent[key] = unquote(value);
    else if (value === '') parent = meta[key] = {};
    else {
      meta[key] = unquote(value);
      parent = null;
    }
  }
  return { meta, end: m[0].length };
}

const unquote = (v) => v.trim().replace(/^(["'])(.*)\1$/, '$2');
const list = (v) => (v ? String(v).replace(/[[\]]/g, '').split(',').map((s) => s.trim()).filter(Boolean) : []);

/**
 * `## ` sections with their exact character ranges in `raw`. `start` is the heading line,
 * `bodyStart` the line after it, `end` the next heading (or end of file).
 */
export function parseSections(raw) {
  const out = [];
  const re = /^## +(.+?)[ \t]*$/gm;
  let m;
  while ((m = re.exec(raw))) {
    // a "## " inside a fenced code block is not a heading
    if (insideFence(raw, m.index)) continue;
    if (out.length) out[out.length - 1].end = m.index;
    out.push({ heading: m[1], start: m.index, bodyStart: Math.min(raw.length, m.index + m[0].length + 1), end: raw.length });
  }
  return out.map((s) => ({ ...s, text: raw.slice(s.bodyStart, s.end).trim() }));
}

function insideFence(raw, index) {
  return ((raw.slice(0, index).match(/^```/gm) || []).length % 2) === 1;
}

export function parseSkill(id, raw) {
  const { meta, end } = parseFrontmatter(raw);
  const md = meta.metadata && typeof meta.metadata === 'object' ? meta.metadata : {};
  const sections = parseSections(raw).map(({ heading, text }) => ({ heading, text }));
  const firstSection = raw.slice(end).search(/^## /m);
  const intro = (firstSection < 0 ? raw.slice(end) : raw.slice(end, end + firstSection))
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/^# .*$/m, '')
    .trim();
  // skills without `metadata.kind` are treated as editing skills; styles say `kind: style`
  const kind = md.kind === 'style' ? 'style' : 'skill';
  const source = md.source === 'custom' || md.source === 'starter'
    ? md.source
    : /STARTER DEFAULTS/.test(raw) ? 'starter' : 'custom';
  return {
    id,
    name: meta.name || id,
    title: meta.title || titleFrom(meta.name || id),
    description: meta.description || '',
    kind,
    source,
    uses: list(md.uses),
    intro,
    sections,
    path: `.claude/skills/${id}/SKILL.md`,
    raw,
  };
}

export const titleFrom = (name) => name.replace(/[-_]+/g, ' ').replace(/^./, (c) => c.toUpperCase());

/**
 * Replace one section's body. `original` must match what the caller saw (trimmed), so an edit
 * made elsewhere is never overwritten. A heading that doesn't exist yet is added before the
 * managed "Reference videos" section, or at the end. Everything outside the section is untouched.
 */
export function replaceSection(raw, heading, original, text) {
  const sections = parseSections(raw);
  const s = sections.find((x) => x.heading.toLowerCase() === heading.toLowerCase());
  const body = text.trim();
  if (!s) {
    if (original) throw httpError(409, `Section "${heading}" no longer exists. Reload and try again.`);
    if (!body) return raw;
    const block = `## ${heading}\n\n${body}\n\n`;
    const refs = sections.find((x) => x.heading === REFERENCES_HEADING);
    if (refs) return raw.slice(0, refs.start) + block + raw.slice(refs.start);
    return raw.replace(/\n*$/, '\n\n') + block.replace(/\n+$/, '\n');
  }
  if (s.text !== (original || '').trim()) {
    throw httpError(409, `"${heading}" was changed outside the dashboard. Reload to see the latest version.`);
  }
  const isLast = s.end === raw.length;
  const block = body ? '\n' + body + (isLast ? '\n' : '\n\n') : '\n';
  return raw.slice(0, s.bodyStart) + block + raw.slice(s.end);
}

export function newStyleFile({ id, description }) {
  const desc = description.replace(/\s+/g, ' ').trim();
  return `---
name: ${id}
description: ${desc}
metadata:
  kind: style
  source: custom
---

# ${titleFrom(id)}

${RULE_SECTIONS.map((h) => `## ${h}\n\n`).join('')}## ${REFERENCES_HEADING}

Before planning an edit, read [references.md](references.md): the user's inspiration videos for
this style and what they like about each.
`;
}

export function httpError(status, message) {
  return Object.assign(new Error(message), { status });
}
