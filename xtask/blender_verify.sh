#!/usr/bin/env bash
# Phase 0 gate verification against a real local Blender.
# 1. builds a test armature in a fresh .blend (headless)
# 2. extracts it through the bundled bridge script
# 3. maps the extracted rig through the installed `rigpose` CLI (--strict)
# 4. registers the add-on skeleton inside Blender
# Exits non-zero on the first failure. Run `make install` first.
set -euo pipefail

BLENDER=${BLENDER:-blender}
RIGPOSE=${RIGPOSE:-rigpose}
REPO=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

BLEND="$TMP/rm_gate.blend"
JSON="$TMP/rm_gate.rig.json"

cat > "$TMP/make_blend.py" <<'PY'
import bpy
import os

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.object.armature_add(location=(0, 0, 0))
obj = bpy.context.object
bpy.ops.object.mode_set(mode='EDIT')
bones = obj.data.edit_bones
bones.remove(bones[0])  # drop the default 'Bone' created by armature_add

def add(name, parent, head, tail):
    b = bones.new(name)
    b.head, b.tail = head, tail
    b.parent = bones[parent] if parent else None

add('pelvis', None, (0, 0, 0.98), (0, 0, 1.06))
add('spine', 'pelvis', (0, 0, 1.06), (0, 0, 1.22))
add('spine.001', 'spine', (0, 0, 1.22), (0, 0, 1.40))
add('neck', 'spine.001', (0, 0, 1.40), (0, 0, 1.50))
add('head', 'neck', (0, 0, 1.50), (0, 0, 1.70))
add('shoulder.L', 'spine.001', (0.03, 0, 1.44), (0.14, 0, 1.46))
add('upper_arm.L', 'shoulder.L', (0.16, 0, 1.45), (0.46, 0, 1.45))
add('forearm.L', 'upper_arm.L', (0.46, 0, 1.45), (0.72, 0, 1.45))
add('hand.L', 'forearm.L', (0.72, 0, 1.45), (0.82, 0, 1.45))
add('shoulder.R', 'spine.001', (-0.03, 0, 1.44), (-0.14, 0, 1.46))
add('upper_arm.R', 'shoulder.R', (-0.16, 0, 1.45), (-0.46, 0, 1.45))
add('forearm.R', 'upper_arm.R', (-0.46, 0, 1.45), (-0.72, 0, 1.45))
add('hand.R', 'forearm.R', (-0.72, 0, 1.45), (-0.82, 0, 1.45))
add('thigh.L', 'pelvis', (0.10, 0, 0.98), (0.11, 0, 0.52))
add('shin.L', 'thigh.L', (0.11, 0, 0.52), (0.11, 0, 0.09))
add('foot.L', 'shin.L', (0.11, 0.01, 0.09), (0.11, -0.13, 0.05))
add('thigh.R', 'pelvis', (-0.10, 0, 0.98), (-0.11, 0, 0.52))
add('shin.R', 'thigh.R', (-0.11, 0, 0.52), (-0.11, 0, 0.09))
add('foot.R', 'shin.R', (-0.11, 0.01, 0.09), (-0.11, -0.13, 0.05))
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_as_mainfile(filepath=os.environ['RM_BLEND_OUT'])
print('BLEND_SAVED')
PY

cat > "$TMP/register_addon.py" <<'PY'
import os
import sys

sys.path.insert(0, os.environ['RM_ADDON_DIR'])
import riggermortis_addon

riggermortis_addon.register()
assert riggermortis_addon.bl_info['name'] == 'Riggermortis'
print('RM_ADDON_OK')
PY

echo "== 1/4 building test .blend"
RM_BLEND_OUT="$BLEND" "$BLENDER" -b --python "$TMP/make_blend.py" 2>&1 | grep -q BLEND_SAVED

echo "== 2/4 extracting rig JSON via bridge"
"$BLENDER" -b "$BLEND" -P "$REPO/core/src/riggermortis/bridge/blender_extract.py" -- --out "$JSON" > /dev/null
test -s "$JSON"

echo "== 3/4 mapping extracted rig (strict)"
"$RIGPOSE" map "$JSON" --strict | tee "$TMP/map.txt"
grep -q 'thigh.L' "$TMP/map.txt"
grep -q 'roles assigned' "$TMP/map.txt"

echo "== 4/4 registering add-on skeleton in Blender"
RM_ADDON_DIR="$REPO/addon" "$BLENDER" -b --python "$TMP/register_addon.py" 2>&1 | grep -q RM_ADDON_OK

echo ""
echo "PHASE 0 BLENDER GATE: PASS"
