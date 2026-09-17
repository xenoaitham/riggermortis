#!/usr/bin/env bash
# Style gate (P4-1 toon materials + P4-2 line art): presets -> deterministic
# builds (+ EEVEE pixels when the box has a GPU context — a headless CPU-only
# environment reports RM_STYLE RENDER SKIPPED honestly and the graph/stroke
# checks still gate).
#
# Self-contained (no models, no local rigs). NOT wired into ci.yml yet:
# apt Blender 4.0.2 in CI would exercise only the SKIPPED path — wire it in
# deliberately once the EEVEE-on-CI question is decided (D-014 revisit
# trigger, one documented commit).
#
# Run: make style-verify   (or: BLENDER=... PY=... bash xtask/style_verify.sh)
set -euo pipefail

BLENDER=${BLENDER:-blender}
REPO=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

"$BLENDER" -b --python "$REPO/xtask/style_probe.py" -- "$TMP" \
  > "$TMP/probe.log" 2>&1 || { cat "$TMP/probe.log" >&2; exit 1; }

grep -q "RM_STYLE PRESETS: anime, manga, western" "$TMP/probe.log"
grep -q "RM_STYLE ANIME GRAPH: PASS" "$TMP/probe.log"
grep -q "RM_STYLE MANGA GRAPH: PASS" "$TMP/probe.log"
grep -q "RM_STYLE WESTERN GRAPH: PASS" "$TMP/probe.log"
grep -q "RM_STYLE ANIME LINEART: PASS" "$TMP/probe.log"
grep -q "RM_STYLE MANGA LINEART: PASS" "$TMP/probe.log"
grep -q "RM_STYLE WESTERN LINEART: PASS" "$TMP/probe.log"
grep -q "RM_STYLE PROBE OK" "$TMP/probe.log"
grep "RM_STYLE" "$TMP/probe.log" | sed 's/^/   /'

if grep -q "RM_STYLE PROBE OK rendered=\[" "$TMP/probe.log"; then
  for f in "$TMP"/style_*.png; do
    if [ ! -s "$f" ]; then
      echo "error: style render missing: $f" >&2
      exit 1
    fi
  done
  echo "   ok: EEVEE frames rendered on this box (kept in $TMP for inspection)"
else
  echo "   ok: no GPU context — renders honestly SKIPPED, graph checks gate"
fi

echo ""
echo "STYLE GATE (P4-1 materials + P4-2 line art): PASS"
