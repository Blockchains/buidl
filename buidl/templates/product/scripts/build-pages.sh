#!/usr/bin/env bash
# Build the static site (app + deck) into $1 (default _site). Runs the full CI first so Pages never ships an untested build.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(mkdir -p "${1:-$ROOT/_site}" && cd "${1:-$ROOT/_site}" && pwd)"
bash "$ROOT/scripts/ci.sh"
cp -r "$ROOT/web/dist/." "$OUT/"
echo "site -> $OUT"
