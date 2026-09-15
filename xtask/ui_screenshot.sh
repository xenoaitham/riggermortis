#!/usr/bin/env bash
# P1-11 B4: real UI screenshot of the add-on in Blender (windowed mode).
# Needs a reachable X display (DISPLAY=:1 on this box works; xvfb-run -a also
# works but windowed Blender can be slow there). Shows the posed metarig +
# review overlay in a genuine Blender window. The N-panel sidebar TAB can't
# be selected from Python, so the panel's tab may not be the front one — the
# shot is honest about what it shows.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-$REPO/media/ui_screenshot.png}
METARIG_BLEND="$REPO/out/real_rigs/metarig.blend"
PAYLOAD="$REPO/out/payloads/metarig_payload.json"

for f in "$METARIG_BLEND" "$PAYLOAD"; do
  if [ ! -s "$f" ]; then
    echo "missing $f — build it first (see docs/BENCHMARKS.md reproduce block)" >&2
    exit 1
  fi
done

mkdir -p "$(dirname "$OUT")"
LOG=$(mktemp)
trap 'rm -f "$LOG"' EXIT

set +e
ATTEMPT=1
while [ "$ATTEMPT" -le 2 ]; do
  RM_METARIG_BLEND="$METARIG_BLEND" \
  RM_PAYLOAD="$PAYLOAD" \
  RM_CORE_SRC="$REPO/core/src" \
  RM_ADDON_DIR="$REPO/addon" \
  RM_SCREENSHOT_OUT="$OUT" \
    timeout 240 blender --python "$REPO/xtask/ui_screenshot.py" >"$LOG" 2>&1
  BLENDER_EXIT=$?
  grep -q "RM_UI SCREENSHOT DONE" "$LOG" && break
  ATTEMPT=$((ATTEMPT + 1))
done
set -e

# Honest gate: the capture must have reported DONE and the file must exist.
# Blender 4.0 occasionally segfaults during GL teardown AFTER the capture —
# that teardown crash does not invalidate the artifact.
grep -q "RM_UI SCREENSHOT DONE" "$LOG" || { tail -20 "$LOG" >&2; exit 1; }
grep -q "payload applied, worst 0.0" "$LOG" || { tail -20 "$LOG" >&2; exit 1; }
[ -s "$OUT" ] || { echo "screenshot missing" >&2; exit 1; }
if [ "$BLENDER_EXIT" -ne 0 ]; then
  echo "note: blender exited $BLENDER_EXIT after the capture (GL teardown); artifact stands"
fi
echo "P1-11 B4 UI SCREENSHOT: DONE ($OUT)"
