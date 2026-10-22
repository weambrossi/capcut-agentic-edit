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
- `CLAUDE.md` – project rules Claude loads every session
- `make_*.py` – Python renderers for past projects (reference implementations for the skills)
- `patches/` – local fixes applied to the vendored MCP server
- `vendor/` – git submodules: [capcut-mcp-server](https://github.com/Atx-Guy/capcut-mcp-server),
  [VectCutAPI](https://github.com/sun-guannan/VectCutAPI)

## Adding a style

Create `.claude/skills/<name>/SKILL.md` with a `name` and `description` frontmatter (the
description is what makes Claude pick it), then describe format, visuals, sound and pacing.
