#!/usr/bin/env bash
# Copy the dependency-free conversion modules out of the PadPilot repo.
# They are vendored (not imported) because a Decky plugin ships self-contained.
set -euo pipefail
SRC="${1:-$HOME/projects/padpilot/padpilot}"
DST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/py_modules/padpilot_core"
for f in ccp.py steaminput.py; do
    cp "$SRC/$f" "$DST/$f"
    echo "synced $f"
done
# they import each other as a package; make the vendored copy self-consistent
sed -i 's/^from \.ccp import/from .ccp import/' "$DST/steaminput.py"
echo "core synced from $SRC"
