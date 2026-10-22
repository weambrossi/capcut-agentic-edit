#!/usr/bin/env bash
# Run the VectCutAPI server on :9001 (the capcut MCP server talks to it).
cd "$(dirname "$0")/vendor/VectCutAPI"
exec .venv/bin/python capcut_server.py
