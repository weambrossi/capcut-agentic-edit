# capcut-agentic-edit

Agentic video editing for CapCut. Claude builds edits two ways:

1. **CapCut drafts via MCP** – the `capcut` MCP server (`vendor/capcut-mcp-server`) drives the
   VectCutAPI backend on `localhost:9001` (`./start_backend.sh`). Tools: `capcut_create_draft`,
   `capcut_add_video/audio/image/text/subtitle/sticker/effect/keyframe`, `capcut_get_duration`,
   `capcut_save_draft`. Use this when the result should stay editable in CapCut.
2. **Python renders** – `make_*.py` compose frames with Pillow/numpy and encode with ffmpeg. Use
   this for motion graphics CapCut can't do well (smash zooms, confetti, podiums, custom captions),
   then drop the rendered clip into the draft.

## Style skills

Pick the skill that matches the edit before planning it:

- `.claude/skills/funny-edit` – meme pacing, punch zooms, SFX hits, pop-in stickers
- `.claude/skills/promo-video` – 30 s vertical ad: hook, title card, one line per shot, CTA end card
- `.claude/skills/serious-video` – calm pacing, clean captions, no gags

Each style folder has a generated `references.md`: the user's inspiration videos for that style
(local files in `references/videos/`) and what they like about each. Read it before planning an
edit in that style. Don't edit it by hand; it is rebuilt from `references/library.json` by the
dashboard (`cd dashboard && npm run dev`, see `docs/dashboard.md`).

Skills with `metadata: kind: style` in their frontmatter are video styles; any other skill is an
editing skill (a reusable capability). A style lists the editing skills it uses under
`metadata: uses:`.

When you save a CapCut draft with `capcut_save_draft`, a hook records it as an original edit in
`edits/` (local, gitignored) and tells you the record id. Pass that id on to the user: after they
revise the draft in CapCut and close it, `node scripts/edits.mjs revise <id>` (or the dashboard's
Edit history page) captures their version for Learn From Edits (`docs/prds/LEARN_FROM_EDITS.md`).
For drafts built another way, record them with `node scripts/edits.mjs record <draft> --style <style>`.

## Rules

- **Close CapCut before touching `draft_info.json`.** CapCut overwrites it on exit. Back up the
  draft into `backups/` first (see `add_vote_heads.py`).
- CapCut is sandboxed to `~/Movies`; media referenced by a draft must live there.
- Preview before a full render: scripts take `--preview T1,T2` or write `preview_*.jpg` frames.
  Look at them before rendering the whole clip.
- Never edit files under `vendor/` directly. Changes to the MCP server go in `patches/` and are
  applied by `setup.sh`.
- Source footage stays outside the repo (`~/Downloads`, `~/Movies`). `out/`, `assets/` (except
  `assets/sfx/`), `stickers/`, `backups/` and `models/` are gitignored.

## Existing projects

- `make_rent_a_dent.py` – 30 s 9:16 promo, full Python render (reference for `promo-video`).
- `votes_config.py`, `add_vote_heads.py`, `make_celebration.py`, `make_q23.py`, `make_broll.py`,
  `make_sfx.py` – "1008 funniest" vote video: graphics rendered in Python, then patched into the
  CapCut draft (reference for `funny-edit`).
- Transcribe footage for timing with `whisper-cli -m models/ggml-base.en.bin -f <audio.wav>`.
