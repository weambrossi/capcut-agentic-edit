# Dashboard architecture

`dashboard/` is a local tool for browsing and editing video styles, editing skills and inspiration
videos. Run it with `cd dashboard && npm run dev` (http://localhost:5180).

## Decisions

**Markdown stays the source of truth.** Styles and skills are the `SKILL.md` files Claude already
loads from `.claude/skills/`. The dashboard reads them on every request and writes back to them;
there is no separate database.

**Styles vs. editing skills is a frontmatter field.** A skill whose frontmatter has
`metadata: kind: style` is a video style; every other skill is an editing skill. `metadata.source`
(`custom` or `starter`) groups styles in the sidebar, and `metadata.uses` lists the editing skills a
style relies on. `metadata` is the Agent Skills field for extra properties, so Claude Code keeps
loading the files as before. Nothing is inferred: a style with no `uses` shows no skills.

**Rules are the file's `##` sections.** The Rules tab shows five sections by heading — Format,
Pacing & Transitions, Captions & Typography, Sound, Color & Visual Effects — plus any other
sections the file has. Saving a section rewrites only that section's text (`replaceSection` in
`server/skills.js`), so frontmatter, comments, tables and unknown sections are kept byte for byte.
If the section changed on disk since it was loaded, the save is refused rather than overwriting it.
"Advanced: view source" edits the whole file, with the same check.

**The API runs inside Vite.** `server/api.js` is mounted as middleware on the dev and preview
servers, so there is no second process and no new dependencies. It is a local tool only: there is
no auth, and it should not be exposed beyond localhost.

**History is git.** The History tab is `git log --follow` for the style's `SKILL.md`, with each
revision viewable via `git show`. Restoring a revision is not built yet (see the Learn From Edits
issues).

**Reference videos are local files plus committed metadata.**

| What | Where | In git |
|------|-------|--------|
| Video files | `references/videos/<id>.<ext>` | No (gitignored) |
| Thumbnails | `references/thumbs/<id>.jpg` | No (gitignored) |
| Names, notes, style links, file info | `references/library.json` | Yes |
| Per-style list for Claude | `.claude/skills/<style>/references.md` | Yes (generated) |

Uploads stream straight to disk, are checked by extension and file signature (MP4/MOV `ftyp`, WebM
EBML), capped at 4 GB, and get a random 12-hex-character id as the filename. ffprobe/ffmpeg fill in
resolution, duration and a thumbnail when installed. A clone without the video files still shows
the metadata, with "File not on this machine".

## How Claude finds reference videos

1. Each style's `SKILL.md` ends with a **Reference videos** section that tells Claude to read
   `references.md` in the same folder before planning an edit.
2. The dashboard regenerates every style's `references.md` after any upload, edit or removal, and
   when the dev server starts. It lists each video's name, path, resolution, duration, size, other
   styles and the user's notes.
3. When Claude loads a style skill it follows that link the same way it follows any file a skill
   references.

Claude cannot watch a video from its path. `references.md` tells it to extract frames with ffmpeg
and look at them, and to transcribe audio with whisper-cli, both tools this repo already uses.
Automatic analysis of references is future work.

## Future work

- **Richer style ↔ skill relationships.** `uses` is a plain list. Per-style configuration of a skill
  (e.g. "caption-generation with word-by-word pop") would need a schema for skill parameters and
  is not designed yet.
- **Editing skills.** None exist yet. Good first candidates pulled out of the current scripts:
  caption rendering, SFX hits (`make_sfx.py`, `synth_*`), silence removal, zoom punches.
- **Reference analysis.** Claude can only study a reference by extracting frames or transcribing
  it by hand. Tracked in [#9](https://github.com/weambrossi/capcut-agentic-edit/issues/9).
