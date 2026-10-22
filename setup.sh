#!/usr/bin/env bash
# One-time setup after cloning: vendor repos, MCP server build, VectCutAPI venv, whisper model.
# Start the backend afterwards with ./start_backend.sh, then open Claude Code in this folder.
set -euo pipefail
cd "$(dirname "$0")"

git submodule update --init

# capcut-mcp-server: VectCutAPI returns its payload under `output`, the client expects `result`
MCP=vendor/capcut-mcp-server
PATCH=patches/capcut-mcp-server-output-normalize.patch
if git -C "$MCP" apply --check "../../$PATCH" 2>/dev/null; then
  git -C "$MCP" apply "../../$PATCH"
fi
(cd "$MCP" && npm install && npm run build)

# VectCutAPI backend on :9001
API=vendor/VectCutAPI
[ -d "$API/.venv" ] || python3 -m venv "$API/.venv"
"$API/.venv/bin/pip" install -q -r "$API/requirements.txt" -r "$API/requirements-mcp.txt"
[ -f "$API/config.json" ] || cat > "$API/config.json" <<'EOF'
{
  "draft_profile": "capcut_legacy",
  "is_capcut_env": true,
  "port": 9001,
  "is_upload_draft": false
}
EOF

# whisper.cpp model for transcribing footage (brew install whisper-cpp for whisper-cli)
mkdir -p models
[ -f models/ggml-base.en.bin ] || curl -L -o models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin

echo "Done. Run ./start_backend.sh, then start Claude Code in this folder."
