// Local JSON API for the dashboard, mounted on the Vite dev/preview server (see vite.config.js).
// Everything stays on this machine: skills are read from and written to .claude/skills, videos
// go to references/videos, history comes from git.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { httpError, newStyleFile, parseSkill, replaceSection } from './skills.js';
import {
  MAX_BYTES, VIDEO_TYPES, listReferences, makeThumb, probe, readLibrary, sniffVideo, syncReferenceDocs, thumbPath,
  withLocalState, writeLibrary,
} from './references.js';
import { isCapcutRunning, listCapcutDrafts, listRecords, recordEdit, reviseEdit, setStyle } from './edits.js';

const run = promisify(execFile);
const ID = /^[a-z0-9][a-z0-9-]{0,63}$/;

export function createApi(root) {
  const skillsDir = path.join(root, '.claude', 'skills');

  const skillFile = (id) => {
    if (!ID.test(id)) throw httpError(400, 'Invalid skill id.');
    const file = path.join(skillsDir, id, 'SKILL.md');
    if (!fs.existsSync(file)) throw httpError(404, `No skill named "${id}".`);
    return file;
  };

  const loadSkills = () => fs.readdirSync(skillsDir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && fs.existsSync(path.join(skillsDir, d.name, 'SKILL.md')))
    .map((d) => parseSkill(d.name, fs.readFileSync(path.join(skillsDir, d.name, 'SKILL.md'), 'utf8')))
    .sort((a, b) => a.title.localeCompare(b.title));

  const styles = () => loadSkills().filter((s) => s.kind === 'style');
  const sync = () => syncReferenceDocs(root, styles());

  const routes = [
    ['GET', /^\/api\/skills$/, () => loadSkills()],

    ['POST', /^\/api\/styles$/, async (req) => {
      const { name, description } = await json(req);
      const id = String(name || '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      if (!ID.test(id)) throw httpError(400, 'Give the style a name with letters or numbers.');
      if (!String(description || '').trim()) throw httpError(400, 'Add a short description of when to use this style.');
      const dir = path.join(skillsDir, id);
      if (fs.existsSync(dir)) throw httpError(409, `A skill named "${id}" already exists.`);
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, 'SKILL.md'), newStyleFile({ id, description }));
      sync();
      return parseSkill(id, fs.readFileSync(path.join(dir, 'SKILL.md'), 'utf8'));
    }],

    ['PUT', /^\/api\/skills\/([^/]+)\/section$/, async (req, [id]) => {
      const file = skillFile(id);
      const { heading, original, text } = await json(req);
      if (!heading || typeof text !== 'string') throw httpError(400, 'heading and text are required.');
      const raw = fs.readFileSync(file, 'utf8');
      fs.writeFileSync(file, replaceSection(raw, heading, original, text));
      return parseSkill(id, fs.readFileSync(file, 'utf8'));
    }],

    ['PUT', /^\/api\/skills\/([^/]+)\/source$/, async (req, [id]) => {
      const file = skillFile(id);
      const { original, text } = await json(req);
      if (typeof text !== 'string' || !text.trim()) throw httpError(400, 'The file cannot be empty.');
      if (fs.readFileSync(file, 'utf8') !== original) {
        throw httpError(409, 'The file was changed outside the dashboard. Reload to see the latest version.');
      }
      fs.writeFileSync(file, text.endsWith('\n') ? text : text + '\n');
      sync();
      return parseSkill(id, fs.readFileSync(file, 'utf8'));
    }],

    ['GET', /^\/api\/skills\/([^/]+)\/history$/, async (req, [id]) => {
      const rel = path.relative(root, skillFile(id));
      const log = await git(root, ['log', '--follow', '--format=%H%x1f%h%x1f%aI%x1f%an%x1f%s', '--', rel]);
      const status = await git(root, ['status', '--porcelain', '--', rel]);
      return {
        uncommitted: Boolean(status.trim()),
        commits: log.split('\n').filter(Boolean).map((l) => {
          const [hash, short, date, author, subject] = l.split('\x1f');
          return { hash, short, date, author, subject };
        }),
      };
    }],

    ['GET', /^\/api\/skills\/([^/]+)\/history\/([0-9a-f]{7,40})$/, async (req, [id, hash]) => {
      skillFile(id);
      const rel = `.claude/skills/${id}/SKILL.md`;
      return { text: await git(root, ['show', `${hash}:${rel}`]) };
    }],

    // edit records (Learn From Edits, issues #1-#2)
    ['GET', /^\/api\/edits$/, () => ({
      records: listRecords(root),
      drafts: listCapcutDrafts(),
      capcutRunning: isCapcutRunning(),
    })],
    ['POST', /^\/api\/edits$/, async (req) => {
      const { draft, style } = await json(req);
      return recordEdit(root, { draft, style: style || null, styles: styles().map((s) => s.id) });
    }],
    ['POST', /^\/api\/edits\/([a-z0-9-]+)\/revise$/, async (req, [id]) => {
      const { draft, force } = await json(req);
      return reviseEdit(root, id, { draft: draft || null, force: Boolean(force) });
    }],
    ['PATCH', /^\/api\/edits\/([a-z0-9-]+)$/, async (req, [id]) => {
      const { style } = await json(req);
      return setStyle(root, id, style || null, styles().map((s) => s.id));
    }],

    ['GET', /^\/api\/references$/, () => listReferences(root)],

    ['POST', /^\/api\/references$/, async (req, _, url) => {
      const name = (url.searchParams.get('name') || '').trim();
      const notes = (url.searchParams.get('notes') || '').trim();
      const original = path.basename(url.searchParams.get('filename') || '');
      const ext = path.extname(original).toLowerCase();
      const styleIds = validStyles(url.searchParams.get('styles'), styles());
      if (!VIDEO_TYPES[ext]) throw httpError(415, 'Use an MP4, MOV, M4V or WebM file.');
      const id = crypto.randomBytes(6).toString('hex');
      const rel = `references/videos/${id}${ext}`;
      const size = await saveUpload(req, path.join(root, rel), ext);
      const entry = {
        id,
        name: name || path.basename(original, ext),
        file: rel,
        originalName: original,
        type: VIDEO_TYPES[ext],
        size,
        ...(await probe(path.join(root, rel))),
        styles: styleIds,
        notes,
        addedAt: new Date().toISOString(),
      };
      await makeThumb(root, id, path.join(root, rel), entry.duration);
      writeLibrary(root, [...readLibrary(root), entry]);
      sync();
      return withLocalState(root, entry);
    }],

    ['PATCH', /^\/api\/references\/([0-9a-f]{12})$/, async (req, [id]) => {
      const body = await json(req);
      const videos = readLibrary(root);
      const v = videos.find((x) => x.id === id);
      if (!v) throw httpError(404, 'That reference no longer exists.');
      if (body.name !== undefined) {
        if (!String(body.name).trim()) throw httpError(400, 'The name cannot be empty.');
        v.name = String(body.name).trim();
      }
      if (body.notes !== undefined) v.notes = String(body.notes).trim();
      if (body.styles !== undefined) v.styles = validStyles(body.styles, styles());
      writeLibrary(root, videos);
      sync();
      return withLocalState(root, v);
    }],

    ['DELETE', /^\/api\/references\/([0-9a-f]{12})$/, (req, [id]) => {
      const videos = readLibrary(root);
      const v = videos.find((x) => x.id === id);
      if (!v) throw httpError(404, 'That reference no longer exists.');
      fs.rmSync(path.join(root, v.file), { force: true });
      fs.rmSync(thumbPath(root, id), { force: true });
      writeLibrary(root, videos.filter((x) => x.id !== id));
      sync();
      return { ok: true };
    }],
  ];

  async function handle(req, res, next) {
    const url = new URL(req.url, 'http://localhost');
    if (!url.pathname.startsWith('/api/')) return next();
    try {
      const file = url.pathname.match(/^\/api\/references\/([0-9a-f]{12})\/file$/);
      if (file && req.method === 'GET') return serveVideo(req, res, file[1]);
      const thumb = url.pathname.match(/^\/api\/references\/([0-9a-f]{12})\/thumb$/);
      if (thumb && req.method === 'GET') {
        const p = thumbPath(root, thumb[1]);
        if (!fs.existsSync(p)) throw httpError(404, 'No thumbnail.');
        res.writeHead(200, { 'Content-Type': 'image/jpeg', 'Content-Length': fs.statSync(p).size });
        return fs.createReadStream(p).pipe(res);
      }
      const route = routes.find(([m, re]) => m === req.method && re.test(url.pathname));
      if (!route) throw httpError(404, 'Not found.');
      const result = await route[2](req, url.pathname.match(route[1]).slice(1), url);
      send(res, 200, result);
    } catch (e) {
      if (!e.status) console.error(e);
      send(res, e.status || 500, { error: e.message });
    }
  }

  function serveVideo(req, res, id) {
    const v = readLibrary(root).find((x) => x.id === id);
    const file = v && path.join(root, v.file);
    if (!file || !fs.existsSync(file)) throw httpError(404, 'Video file not found on this machine.');
    const size = fs.statSync(file).size;
    const range = /bytes=(\d*)-(\d*)/.exec(req.headers.range || '');
    let start = 0;
    let end = size - 1;
    if (range) {
      start = range[1] ? Number(range[1]) : size - Number(range[2]);
      end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
      if (start > end || start < 0) {
        res.writeHead(416, { 'Content-Range': `bytes */${size}` });
        return res.end();
      }
    }
    res.writeHead(range ? 206 : 200, {
      'Content-Type': v.type,
      'Content-Length': end - start + 1,
      'Accept-Ranges': 'bytes',
      ...(range && { 'Content-Range': `bytes ${start}-${end}/${size}` }),
    });
    fs.createReadStream(file, { start, end }).pipe(res);
  }

  return { handle, sync };
}

function validStyles(value, styles) {
  const ids = (Array.isArray(value) ? value : String(value || '').split(',')).map((s) => String(s).trim()).filter(Boolean);
  const known = new Set(styles.map((s) => s.id));
  const unknown = ids.filter((s) => !known.has(s));
  if (unknown.length) throw httpError(400, `Unknown style: ${unknown.join(', ')}.`);
  if (!ids.length) throw httpError(400, 'Attach the video to at least one style.');
  return [...new Set(ids)];
}

/** Stream the request body to `dest`, checking the file signature and size as it arrives. */
function saveUpload(req, dest, ext) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  const part = dest + '.part';
  return new Promise((resolve, reject) => {
    const out = fs.createWriteStream(part);
    let size = 0;
    let checked = false;
    let head = Buffer.alloc(0);
    let failed = false;
    const fail = (err) => {
      if (failed) return;
      failed = true;
      req.resume();
      out.destroy();
      fs.rmSync(part, { force: true });
      reject(err);
    };
    req.on('data', (chunk) => {
      if (failed) return;
      size += chunk.length;
      if (size > MAX_BYTES) return fail(httpError(413, 'Videos up to 4 GB are supported.'));
      if (!checked) {
        head = Buffer.concat([head, chunk]);
        if (head.length >= 8) {
          checked = true;
          if (!sniffVideo(head, ext)) return fail(httpError(415, "That file isn't a valid video of its type."));
        }
      }
      if (!out.write(chunk)) {
        req.pause();
        out.once('drain', () => req.resume());
      }
    });
    req.on('end', () => {
      if (failed) return;
      if (!checked) return fail(httpError(400, 'The upload was empty.'));
      out.end(() => {
        fs.renameSync(part, dest);
        resolve(size);
      });
    });
    req.on('error', fail);
    req.on('aborted', () => fail(httpError(400, 'Upload cancelled.')));
  });
}

function json(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (c) => {
      body += c;
      if (body.length > 1e6) reject(httpError(413, 'Request too large.'));
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        reject(httpError(400, 'Invalid JSON.'));
      }
    });
    req.on('error', reject);
  });
}

function send(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

async function git(root, args) {
  try {
    return (await run('git', args, { cwd: root, maxBuffer: 10 * 1024 ** 2 })).stdout;
  } catch (e) {
    throw httpError(500, `git ${args[0]} failed: ${e.stderr || e.message}`.trim());
  }
}
