# capcut-agentic-edit

Claude Code + CapCut: style skills and scripts for making edits with an agent.

## Setup

```bash
git clone --recurse-submodules https://github.com/weambrossi/capcut-agentic-edit.git
cd capcut-agentic-edit
./setup.sh          # builds the MCP server, VectCutAPI venv, downloads the whisper model
./start_backend.sh  # VectCutAPI on :9001 — leave running
claude              # the capcut MCP server is picked up from .mcp.json
```

Needs Node, Python 3, ffmpeg and CapCut desktop; `brew install whisper-cpp` for transcription.

## Layout

- `.claude/skills/` – edit styles: `funny-edit`, `promo-video`, `serious-video`
- `dashboard/` – local styles dashboard (`npm run dev`)
- `references/` – inspiration-video metadata (videos themselves are gitignored)
- `docs/` – architecture notes, PRDs, feature ideas
- `CLAUDE.md` – project rules Claude loads every session
- `make_*.py` – Python renderers for past projects (reference implementations for the skills)
- `patches/` – local fixes applied to the vendored MCP server
- `vendor/` – git submodules: [capcut-mcp-server](https://github.com/Atx-Guy/capcut-mcp-server),
  [VectCutAPI](https://github.com/sun-guannan/VectCutAPI)

## Styles dashboard

A local Vite + React tool for video styles, editing skills and inspiration videos: browse and edit
each style's rules (written straight back to its SKILL.md), see its git history, and upload
reference videos that Claude reads when it uses the style. Videos stay on your machine in
`references/videos/` (gitignored); their names and notes are committed in
`references/library.json`. Details: [docs/dashboard.md](docs/dashboard.md).

```bash
cd dashboard && npm install && npm run dev   # http://localhost:5180
```

## Adding a style

Use **Create style** in the dashboard, or create `.claude/skills/<name>/SKILL.md` by hand with
`name`, `description` and `metadata: kind: style` in the frontmatter. The description is what makes
Claude pick it. Skills without `kind: style` show up as editing skills.

## Plans

- [Learn From Previous Edits PRD](docs/prds/LEARN_FROM_EDITS.md) (shelved)
- [Additional video editing features](docs/ADDITIONAL_VIDEO_EDITING_FEATURES.md)
