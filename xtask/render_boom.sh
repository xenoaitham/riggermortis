#!/usr/bin/env bash
# P1-10: the BOOM GIF. Renders the before/after turntables headlessly from the
# real pipeline (metarig + real pose payload), then assembles the GIF.
# Exits non-zero on the first failure. Needs: downloaded models, real rigs.
set -euo pipefail

BLENDER=${BLENDER:-blender}
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-$REPO/media}
IMG="$REPO/out/benchmark/images/photo/rtmpose_human_pose.jpg"
METARIG_BLEND="$REPO/out/real_rigs/metarig.blend"
METARIG_RIG="$REPO/out/real_rigs/metarig.rig.json"
PAYLOAD="$REPO/out/payloads/metarig_payload.json"

for f in "$IMG" "$METARIG_BLEND" "$METARIG_RIG"; do
  if [ ! -s "$f" ]; then
    echo "missing $f — build it first (see docs/BENCHMARKS.md reproduce block)" >&2
    exit 1
  fi
done
mkdir -p "$REPO/out/payloads"
if [ ! -s "$PAYLOAD" ]; then
  echo "== generating pose payload (real models)"
  rigpose pose "$IMG" "$METARIG_RIG" --out "$PAYLOAD" > /dev/null
fi

echo "== rendering boom turntables (24 frames x2, workbench)"
RM_METARIG_BLEND="$METARIG_BLEND" \
RM_PAYLOAD="$PAYLOAD" \
RM_CORE_SRC="$REPO/core/src" \
RM_ADDON_DIR="$REPO/addon" \
  "$BLENDER" -b -P "$REPO/xtask/render_demos.py" -- --demo boom --out "$OUT" 2>&1 | tee /tmp/rm_boom_render.log
grep -q "RM_RENDER BOOM FRAMES DONE" /tmp/rm_boom_render.log
grep -q "payload applied, worst 0.0" /tmp/rm_boom_render.log

echo "== assembling GIF"
python3 "$REPO/xtask/assemble_gif.py" --manifest "$OUT/boom/manifest.json" --out "$OUT/boom.gif"
echo ""
echo "P1-10 BOOM GIF: DONE ($OUT/boom.gif)"
