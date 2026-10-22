#!/usr/bin/env node
// Edit records for Learn From Previous Edits (docs/prds/LEARN_FROM_EDITS.md).
//
//   node scripts/edits.mjs record <draft name|folder> [--style funny-edit]   snapshot Claude's draft
//   node scripts/edits.mjs revise <edit id> [--draft <name|folder>] [--force] snapshot your CapCut revision
//   node scripts/edits.mjs list
//   node scripts/edits.mjs set-style <edit id> <style>
//   node scripts/edits.mjs hook        (PostToolUse hook for capcut_save_draft; reads JSON on stdin)
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseSkill } from '../dashboard/server/skills.js';
import {
  draftFromSaveResponse, listRecords, recordEdit, reviseEdit, setStyle, styleFromTranscript,
} from '../dashboard/server/edits.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function styleIds() {
  const dir = path.join(ROOT, '.claude', 'skills');
  return fs.readdirSync(dir)
    .filter((d) => fs.existsSync(path.join(dir, d, 'SKILL.md')))
    .filter((d) => parseSkill(d, fs.readFileSync(path.join(dir, d, 'SKILL.md'), 'utf8')).kind === 'style');
}

function flag(args, name) {
  const i = args.indexOf(name);
  if (i < 0) return undefined;
  const value = args[i + 1];
  args.splice(i, value && !value.startsWith('--') ? 2 : 1);
  return value && !value.startsWith('--') ? value : true;
}

const show = (r) => {
  const s = r.original.summary;
  const rev = r.revised ? `revised ${r.revisedAt.slice(0, 16).replace('T', ' ')}` : 'not revised yet';
  return `${r.id}  ${r.style || '(no style)'}  ${r.draftName}  ${s.duration}s, ${s.segments} segments  · ${rev}`;
};

async function hook() {
  // never block Claude: any failure is reported as context and the hook exits 0
  let context;
  try {
    const input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');
    // MCP results arrive as content blocks ({type: 'text', text}); gather every string in them
    const strings = [];
    (function walk(v) {
      if (typeof v === 'string') strings.push(v);
      else if (v && typeof v === 'object') Object.values(v).forEach(walk);
    })(input.tool_response);
    const response = strings.join('\n');
    const draft = draftFromSaveResponse(ROOT, input.tool_input, response);
    if (!draft) {
      context = 'Edit not recorded: could not find the saved draft folder. Record it with `node scripts/edits.mjs record <folder> --style <style>`.';
    } else {
      const styles = styleIds();
      let style = null;
      try {
        style = styleFromTranscript(fs.readFileSync(input.transcript_path, 'utf8'), styles);
      } catch { /* no transcript */ }
      const r = recordEdit(ROOT, { draft, style, source: 'hook', styles });
      context = `Recorded original edit ${r.id} (style: ${style || 'none detected'}). `
        + (style ? '' : `Set it with \`node scripts/edits.mjs set-style ${r.id} <style>\`. `)
        + `After the user revises the draft in CapCut and closes CapCut, capture it with \`node scripts/edits.mjs revise ${r.id}\` or the dashboard's Edit history page.`;
    }
  } catch (e) {
    context = `Edit not recorded: ${e.message}`;
  }
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: context } }));
}

async function main() {
  const [cmd, ...args] = process.argv.slice(2);
  if (cmd === 'hook') return hook();
  if (cmd === 'record') {
    const style = flag(args, '--style');
    console.log('Recorded', show(recordEdit(ROOT, { draft: args[0], style: style || null, styles: styleIds() })));
  } else if (cmd === 'revise') {
    const draft = flag(args, '--draft');
    const force = Boolean(flag(args, '--force'));
    console.log('Captured revision for', show(reviseEdit(ROOT, args[0], { draft: draft || null, force })));
  } else if (cmd === 'list') {
    const records = listRecords(ROOT);
    console.log(records.length ? records.map(show).join('\n') : 'No edit records yet.');
  } else if (cmd === 'set-style') {
    console.log('Updated', show(setStyle(ROOT, args[0], args[1], styleIds())));
  } else {
    console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').slice(1, 9).join('\n').replace(/^\/\/ ?/gm, ''));
    process.exitCode = cmd ? 1 : 0;
  }
}

main().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
