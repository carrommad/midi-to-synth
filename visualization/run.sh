#!/usr/bin/env bash
# Quick launcher for Roland S-1 Visualizer
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8000

echo "Starting Roland S-1 Wave Visualizer server on port $PORT..."
if command -v python3 &>/dev/null; then
  python3 -m http.server "$PORT" --directory "$DIR"
elif command -v npx &>/dev/null; then
  npx http-server "$DIR" -p "$PORT"
else
  echo "Error: Neither python3 nor npx/http-server found."
  exit 1
fi
