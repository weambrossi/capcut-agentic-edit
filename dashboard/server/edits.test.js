import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { draftFromSaveResponse, isCapcutRunning, readTimeline, recordEdit, reviseEdit, styleFromTranscript, summarize } from './edits.js';

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'edits-test-'));
const info = (id, segments) => JSON.stringify({
  id, duration: 12_500_000, fps: 30, canvas_config: { width: 1080, height: 1920 },
  tracks: [{ type: 'video', segments: Array(segments).fill({}) }, { type: 'text', segments: [{}] }],
});

test('summarize counts segments by track type', () => {
  assert.deepEqual(summarize(JSON.parse(info('a', 3))), {
    duration: 12.5, tracks: 2, segments: 4, byType: { video: 3, text: 1 }, canvas: '1080×1920', fps: 30,
  });
});

test('readTimeline prefers the newer of root and main-timeline files', () => {
  const d = tmp();
  fs.writeFileSync(path.join(d, 'draft_info.json'), info('root', 0));
  fs.mkdirSync(path.join(d, 'Timelines', 'T1'), { recursive: true });
  fs.writeFileSync(path.join(d, 'Timelines', 'project.json'), JSON.stringify({ main_timeline_id: 'T1' }));
  fs.writeFileSync(path.join(d, 'Timelines', 'T1', 'draft_info.json'), info('main', 5));
  const old = new Date(Date.now() - 60_000);
  fs.utimesSync(path.join(d, 'draft_info.json'), old, old);
  assert.equal(readTimeline(d).json.id, 'main');
});

test('styleFromTranscript returns the style used last', () => {
  const t = '{"input":{"skill":"funny-edit"}}\n{"input":{"file_path":"/r/.claude/skills/promo-video/SKILL.md"}}';
  assert.equal(styleFromTranscript(t, ['funny-edit', 'promo-video']), 'promo-video');
  assert.equal(styleFromTranscript('nothing here', ['funny-edit']), null);
});

test('draftFromSaveResponse finds the folder in JSON or markdown output', () => {
  const root = tmp();
  const d = path.join(root, 'dfd_abc');
  fs.mkdirSync(d);
  assert.equal(draftFromSaveResponse(root, {}, `{"draft_url": "${d}", "status": "saved"}`), d);
  assert.equal(draftFromSaveResponse(root, {}, `Draft saved to \`${d}\``), d);
  assert.equal(draftFromSaveResponse(root, {}, 'saved'), null);
});

test('record then revise snapshots both versions and checks the timeline id', { skip: isCapcutRunning() && 'CapCut is running' }, () => {
  const root = tmp();
  const drafts = tmp();
  process.env.CAPCUT_DRAFTS_DIR = drafts;
  fs.mkdirSync(path.join(drafts, 'proj'));
  fs.mkdirSync(path.join(drafts, 'other'));
  fs.writeFileSync(path.join(drafts, 'proj', 'draft_info.json'), info('T-1', 3));
  fs.writeFileSync(path.join(drafts, 'other', 'draft_info.json'), info('T-2', 1));

  const r = recordEdit(root, { draft: 'proj', style: 'funny-edit', styles: ['funny-edit'] });
  assert.equal(r.status, 'generated');
  assert.equal(r.original.summary.segments, 4);

  fs.writeFileSync(path.join(drafts, 'proj', 'draft_info.json'), info('T-1', 5));
  assert.throws(() => reviseEdit(root, r.id, { draft: 'other' }), { status: 409 });
  const revised = reviseEdit(root, r.id);
  assert.equal(revised.status, 'revised');
  assert.equal(revised.revised.summary.segments, 6);
  assert.equal(JSON.parse(fs.readFileSync(path.join(root, 'edits', r.id, 'original.json'), 'utf8')).tracks[0].segments.length, 3);
  delete process.env.CAPCUT_DRAFTS_DIR;
});
