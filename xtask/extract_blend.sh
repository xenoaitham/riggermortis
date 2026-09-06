#!/usr/bin/env bash
# Convert a .blend to riggermortis rig JSON using the user's local Blender.
# Usage: extract_blend.sh model.blend out.rig.json [armature-name]
#
# The core library is deliberately process-free; all Blender process interop
# lives in edge scripts like this one. Everything stays local.
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "usage: $0 <model.blend> <out.rig.json> [armature-name]" >&2
    exit 64
fi

BLEND=$1
OUT=$2
RIG=${3:-}
REPO=$(cd "$(dirname "$0")/.." && pwd)
SCRIPT="$REPO/core/src/riggermortis/bridge/blender_extract.py"
BLENDER=${BLENDER:-blender}

if [ ! -f "$BLEND" ]; then
    echo "error: no such file: $BLEND" >&2
    exit 66
fi

"$BLENDER" -b "$BLEND" -P "$SCRIPT" -- --out "$OUT" ${RIG:+--rig "$RIG"}
echo "wrote $OUT"
