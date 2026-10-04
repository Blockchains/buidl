#!/usr/bin/env bash
# One command for CI and humans: contracts build + test, web test + build.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTRACT="$(python3 -c 'import json;print(json.load(open("'"$ROOT"'/buidl.json"))["contract"])')"
cd "$ROOT/contracts"
forge --version | head -1
forge build --sizes
forge test -vv
mkdir -p "$ROOT/web/public/contracts"
python3 - "$CONTRACT" "$ROOT/web/public/contracts/App.json" <<'PY'
import json, sys
name, dest = sys.argv[1], sys.argv[2]
art = json.load(open(f"out/{name}.sol/{name}.json"))
json.dump({"contractName": name, "abi": art["abi"], "bytecode": art["bytecode"]["object"]}, open(dest, "w"))
print("artifact ->", dest)
PY
cd "$ROOT/web"
npm ci --no-audit --no-fund
CHECK_ARTIFACT=1 npm test
npm run build
npm run deck
test -s dist/index.html && test -s dist/contracts/App.json && test -s dist/deck.html
echo "CI OK"
