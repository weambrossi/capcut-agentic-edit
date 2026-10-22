import { test } from 'node:test';
import assert from 'node:assert/strict';
import { newStyleFile, parseSkill, replaceSection } from './skills.js';
import { renderReferencesMd, sniffVideo } from './references.js';

const FILE = `---
name: demo-style
description: Demo – fast cuts. Use when testing: ratio 9:16.
metadata:
  kind: style
  source: custom
  uses: [caption-generation, audio-mixing]
---

# Demo

Intro line.
<!-- keep me -->

## Format

- 9:16

## Unknown thing

\`\`\`
## not a heading
\`\`\`

## Sound

- boom
`;

test('parses frontmatter, metadata and sections', () => {
  const s = parseSkill('demo-style', FILE);
  assert.equal(s.kind, 'style');
  assert.equal(s.source, 'custom');
  assert.equal(s.description, 'Demo – fast cuts. Use when testing: ratio 9:16.');
  assert.deepEqual(s.uses, ['caption-generation', 'audio-mixing']);
  assert.deepEqual(s.sections.map((x) => x.heading), ['Format', 'Unknown thing', 'Sound']);
  assert.equal(s.intro, 'Intro line.');
});

test('skills without metadata are editing skills', () => {
  const s = parseSkill('captions', '---\nname: captions\ndescription: Make captions.\n---\n\nBody\n');
  assert.equal(s.kind, 'skill');
  assert.deepEqual(s.uses, []);
});

test('replacing a section leaves everything else byte-for-byte', () => {
  const out = replaceSection(FILE, 'Format', '- 9:16', '- 16:9\n- 30 fps');
  assert.equal(out, FILE.replace('- 9:16\n', '- 16:9\n- 30 fps\n'));
  assert.ok(out.includes('<!-- keep me -->'));
  assert.ok(out.includes('## not a heading'));
});

test('replacing the last section keeps a single trailing newline', () => {
  const out = replaceSection(FILE, 'Sound', '- boom', '- whoosh');
  assert.ok(out.endsWith('## Sound\n\n- whoosh\n'));
});

test('stale edits are refused', () => {
  assert.throws(() => replaceSection(FILE, 'Format', '- 4:3', 'x'), { status: 409 });
});

test('a missing section is added before Reference videos', () => {
  const withRefs = FILE + '\n## Reference videos\n\nSee references.md.\n';
  const out = replaceSection(withRefs, 'Color & Visual Effects', null, '- warm grade');
  assert.ok(out.indexOf('## Color & Visual Effects') < out.indexOf('## Reference videos'));
  assert.equal(parseSkill('x', out).sections.find((s) => s.heading === 'Color & Visual Effects').text, '- warm grade');
});

test('new style files parse as custom styles with all rule sections', () => {
  const s = parseSkill('travel-vlog', newStyleFile({ id: 'travel-vlog', description: 'Trips.\nUse for travel.' }));
  assert.equal(s.kind, 'style');
  assert.equal(s.description, 'Trips. Use for travel.');
  assert.equal(s.sections.length, 6);
});

test('video signatures', () => {
  const mp4 = Buffer.from([0, 0, 0, 0x20, 0x66, 0x74, 0x79, 0x70]);
  const webm = Buffer.from([0x1a, 0x45, 0xdf, 0xa3, 0, 0, 0, 0]);
  assert.ok(sniffVideo(mp4, '.mp4'));
  assert.ok(sniffVideo(mp4, '.mov'));
  assert.ok(sniffVideo(webm, '.webm'));
  assert.ok(!sniffVideo(webm, '.mp4'));
  assert.ok(!sniffVideo(Buffer.from('hello world'), '.mp4'));
});

test('references.md lists only this style\'s videos with notes', () => {
  const videos = [
    { id: 'a', name: 'Beat cuts', file: 'references/videos/a.mp4', size: 2e6, width: 1080, height: 1920, duration: 31, styles: ['funny-edit', 'promo-video'], notes: 'Cuts on every beat.', addedAt: '2026-10-22T00:00:00Z' },
    { id: 'b', name: 'Other', file: 'references/videos/b.mp4', size: 1e6, styles: ['promo-video'], notes: '', addedAt: '2026-10-22T00:00:00Z' },
  ];
  const md = renderReferencesMd({ id: 'funny-edit', title: 'Funny edit' }, videos, { 'promo-video': 'Promo video' });
  assert.ok(md.includes('## Beat cuts'));
  assert.ok(md.includes('`references/videos/a.mp4` (1080×1920, 0:31, 1.9 MB)'));
  assert.ok(md.includes('Also a reference for: Promo video'));
  assert.ok(md.includes('Cuts on every beat.'));
  assert.ok(!md.includes('## Other'));
});
