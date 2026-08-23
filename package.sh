#!/usr/bin/env bash
# Build the installable Decky plugin zip.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/PadPilot.zip"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

[[ -f "$HERE/dist/index.js" ]] || { echo "run 'pnpm run build' first" >&2; exit 1; }

mkdir -p "$STAGE/PadPilot"
cp -r "$HERE/dist" "$HERE/py_modules" "$STAGE/PadPilot/"
# 1.4 MB of sourcemap is not worth shipping; drop the dangling reference too
rm -f "$STAGE/PadPilot/dist/"*.map
sed -i '/sourceMappingURL/d' "$STAGE/PadPilot/dist/index.js"
cp "$HERE/main.py" "$HERE/plugin.json" "$HERE/package.json" \
   "$HERE/README.md" "$HERE/LICENSE" "$STAGE/PadPilot/"
find "$STAGE" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

rm -f "$OUT"
( cd "$STAGE" && zip -qr "$OUT" PadPilot )
echo "$OUT"
unzip -l "$OUT" | tail -1
