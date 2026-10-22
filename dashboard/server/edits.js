// Edit records for Learn From Previous Edits (docs/prds/LEARN_FROM_EDITS.md, issues #1 and #2).
// A record pairs the timeline Claude generated with the version the user revised in CapCut.
// Records live in edits/<id>/ and are gitignored: they hold caption text and local paths.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { httpError } from './skills.js';

export const capcutDraftsDir = () => process.env.CAPCUT_DRAFTS_DIR
  || path.join(os.homedir(), 'Movies', 'CapCut', 'User Data', 'Projects', 'com.lveditor.draft');

const editsDir = (root) => path.join(root, 'edits');
const EDIT_ID = /^[a-z0-9][a-z0-9-]{0,80}$/;

/**
 * The timeline file of a draft folder. Newer CapCut keeps it in Timelines/<main id>/draft_info.json
 * (the root copy can be empty); drafts written by VectCutAPI only have the root file.
 */
export function readTimeline(draftDir) {
  const candidates = [];
  try {
    const project = JSON.parse(fs.readFileSync(path.join(draftDir, 'Timelines', 'project.json'), 'utf8'));
    candidates.push(path.join(draftDir, 'Timelines', project.main_timeline_id, 'draft_info.json'));
  } catch { /* no multi-timeline project */ }
  candidates.push(path.join(draftDir, 'draft_info.json'));
  const existing = candidates.filter((f) => fs.existsSync(f));
  if (!existing.length) throw httpError(404, `No draft_info.json in ${draftDir}.`);
  // when both exist, the more recently written one is what CapCut last saved
  const file = existing.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
  const text = fs.readFileSync(file, 'utf8');
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw httpError(422, `${file} isn't readable JSON (this CapCut version may encrypt drafts).`);
  }
  return { file, text, json };
}

/** Counts that make a record readable at a glance; the real comparison is issue #3. */
export function summarize(info) {
  const tracks = info.tracks || [];
  const byType = {};
  let segments = 0;
  for (const t of tracks) {
    const n = (t.segments || []).length;
    byType[t.type] = (byType[t.type] || 0) + n;
    segments += n;
  }
  return {
    duration: Math.round((info.duration || 0) / 1e4) / 100,
    tracks: tracks.length,
    segments,
    byType,
    canvas: info.canvas_config ? `${info.canvas_config.width}×${info.canvas_config.height}` : null,
    fps: info.fps || null,
  };
}

/** A draft folder name or path → absolute folder. */
export function resolveDraft(draft) {
  if (!draft) throw httpError(400, 'Which draft? Pass a CapCut draft name or a folder path.');
  const abs = path.isAbsolute(draft) ? draft : path.join(capcutDraftsDir(), draft);
  if (!fs.existsSync(abs)) throw httpError(404, `Draft folder not found: ${abs}`);
  return abs;
}

export function listCapcutDrafts() {
  const dir = capcutDraftsDir();
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && fs.existsSync(path.join(dir, d.name, 'draft_info.json')))
    .map((d) => ({ name: d.name, modified: fs.statSync(path.join(dir, d.name, 'draft_info.json')).mtime.toISOString() }))
    .sort((a, b) => b.modified.localeCompare(a.modified));
}

export function isCapcutRunning() {
  try {
    execFileSync('pgrep', ['-x', 'CapCut'], { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function styleRevision(root, style) {
  if (!style) return null;
  const rel = `.claude/skills/${style}/SKILL.md`;
  try {
    const hash = execFileSync('git', ['log', '-1', '--format=%H', '--', rel], { cwd: root, encoding: 'utf8' }).trim();
    const dirty = execFileSync('git', ['status', '--porcelain', '--', rel], { cwd: root, encoding: 'utf8' }).trim();
    return { commit: hash || null, uncommittedChanges: Boolean(dirty) };
  } catch {
    return null;
  }
}

const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'draft';

export function readRecord(root, id) {
  if (!EDIT_ID.test(id)) throw httpError(400, 'Invalid edit id.');
  const file = path.join(editsDir(root), id, 'record.json');
  if (!fs.existsSync(file)) throw httpError(404, `No edit record "${id}".`);
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeRecord(root, record) {
  const file = path.join(editsDir(root), record.id, 'record.json');
  fs.writeFileSync(file, JSON.stringify(record, null, 2) + '\n');
  return record;
}

export function listRecords(root) {
  const dir = editsDir(root);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((id) => fs.existsSync(path.join(dir, id, 'record.json')))
    .map((id) => readRecord(root, id))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

/** Issue #1: snapshot the timeline Claude generated. */
export function recordEdit(root, { draft, style = null, source = 'manual', styles = [] }) {
  if (style && !styles.includes(style)) throw httpError(400, `Unknown style "${style}".`);
  const draftDir = resolveDraft(draft);
  const timeline = readTimeline(draftDir);
  const now = new Date();
  const name = path.basename(draftDir);
  const id = `${now.toISOString().slice(0, 10)}-${slug(name)}-${crypto.randomBytes(2).toString('hex')}`;
  fs.mkdirSync(path.join(editsDir(root), id), { recursive: true });
  fs.writeFileSync(path.join(editsDir(root), id, 'original.json'), timeline.text);
  return writeRecord(root, {
    id,
    style,
    styleRevision: styleRevision(root, style),
    editor: 'capcut',
    source,
    draftName: name,
    timelineId: timeline.json.id || null,
    generatedPath: draftDir,
    capcutPath: draftDir.startsWith(capcutDraftsDir()) ? draftDir : null,
    createdAt: now.toISOString(),
    revisedAt: null,
    status: 'generated',
    original: { file: 'original.json', from: timeline.file, summary: summarize(timeline.json) },
    revised: null,
  });
}

/** Where the user's revised copy of a record's draft lives in CapCut. */
function findCapcutCopy(record) {
  if (record.capcutPath && fs.existsSync(record.capcutPath)) return record.capcutPath;
  const dir = capcutDraftsDir();
  const byName = path.join(dir, record.draftName);
  if (fs.existsSync(byName)) return byName;
  // CapCut may rename the folder on import; fall back to the timeline id
  for (const d of listCapcutDrafts()) {
    try {
      if (readTimeline(path.join(dir, d.name)).json.id === record.timelineId) return path.join(dir, d.name);
    } catch { /* unreadable draft */ }
  }
  return null;
}

/** Issue #2: snapshot the version the user revised in CapCut. */
export function reviseEdit(root, id, { draft = null, force = false } = {}) {
  const record = readRecord(root, id);
  if (isCapcutRunning()) {
    throw httpError(409, 'Close CapCut first: it rewrites the draft when it quits, so a snapshot taken now may be out of date.');
  }
  const draftDir = draft ? resolveDraft(draft) : findCapcutCopy(record);
  if (!draftDir) {
    throw httpError(404, `Couldn't find "${record.draftName}" in ${capcutDraftsDir()}. Pass the draft name or folder.`);
  }
  const timeline = readTimeline(draftDir);
  if (record.timelineId && timeline.json.id !== record.timelineId && !force) {
    throw httpError(409, `"${path.basename(draftDir)}" has a different timeline id than the recorded draft. Use force if you're sure it's the same project.`);
  }
  fs.writeFileSync(path.join(editsDir(root), id, 'revised.json'), timeline.text);
  return writeRecord(root, {
    ...record,
    capcutPath: draftDir,
    revisedAt: new Date().toISOString(),
    status: 'revised',
    revised: { file: 'revised.json', from: timeline.file, summary: summarize(timeline.json) },
  });
}

export function setStyle(root, id, style, styles) {
  if (style && !styles.includes(style)) throw httpError(400, `Unknown style "${style}".`);
  const record = readRecord(root, id);
  return writeRecord(root, { ...record, style, styleRevision: styleRevision(root, style) });
}

/**
 * The style Claude was using in a session: whichever style skill the transcript mentions last
 * (a Skill call or a read of its SKILL.md). Null if none.
 */
export function styleFromTranscript(text, styles) {
  let best = null;
  let at = -1;
  for (const s of styles) {
    const i = Math.max(text.lastIndexOf(`"skill":"${s}"`), text.lastIndexOf(`.claude/skills/${s}/SKILL.md`));
    if (i > at) {
      at = i;
      best = s;
    }
  }
  return best;
}

/** The folder capcut_save_draft wrote, from its response text or the backend's default location. */
export function draftFromSaveResponse(root, input, responseText) {
  const m = responseText.match(/"draft_url"\s*:\s*"([^"]+)"/) || responseText.match(/(\/[^\s"'`]*dfd_[^\s"'`]*)/);
  const candidates = [m && m[1], input?.draft_id && path.join(root, 'vendor', 'VectCutAPI', input.draft_id)];
  return candidates.find((p) => p && path.isAbsolute(p) && fs.existsSync(p)) || null;
}
