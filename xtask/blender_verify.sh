#!/usr/bin/env bash
# Phase 0 gate verification against a real local Blender.
# 1. builds a test armature in a fresh .blend (headless)
# 2. extracts it through the bundled bridge script
# 3. maps the extracted rig through the installed `rigpose` CLI (--strict)
# 4. registers the add-on skeleton inside Blender
# 5. 18+ policy enforcement through the REAL add-on preferences flow
#    (P6-4/P6-5: fresh-install OFF, two-toggle enable, verbatim codes)
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

cat > "$TMP/policy_probe.py" <<'PY'
import os
import sys

sys.path.insert(0, os.environ['RM_CORE_SRC'])
sys.path.insert(0, os.environ['RM_ADDON_DIR'])

import addon_utils  # noqa: E402
import bpy  # noqa: E402
import riggermortis  # noqa: E402

# enable the add-on the way the USER does (the checkbox): addon_utils does
# the import, the register() and the preferences entry — no manual shortcuts
print('RM_POLICY ENABLE-ADDON:', addon_utils.enable('riggermortis_addon', default_set=True))
assert 'riggermortis_addon' in bpy.context.preferences.addons

import riggermortis_addon  # noqa: E402
from riggermortis_addon import policy  # noqa: E402

# the REAL AddonPreferences entry — defaults come from the bpy property
# system (both toggles False), not from a stub
prefs = bpy.context.preferences.addons['riggermortis_addon'].preferences
assert (prefs.adult_module_enabled, prefs.adult_module_confirm) == (False, False)

# fresh install: sync derives OFF; fictional_adult refuses, retryably
assert policy.sync_from_preferences() is False
r = policy.check('fictional_adult')
assert r is not None and r.code == riggermortis.ADULT_MODULE_DISABLED and r.retryable
print('RM_POLICY FRESH-OFF: prefs (False, False) -> engine OFF; '
      'fictional_adult -> adult_module_disabled (retryable)')

# one toggle is not enough — the enable needs BOTH (two-toggle contract)
prefs.adult_module_enabled = True
assert policy.sync_from_preferences() is False
print('RM_POLICY ONE-TOGGLE-STILL-OFF: enable without confirm -> engine OFF')

# both toggles -> ON through the documented enable call
prefs.adult_module_confirm = True
assert policy.sync_from_preferences() is True
assert policy.check('fictional_adult') is None
print('RM_POLICY ENABLE-BOTH-TOGGLES: engine ON via enable_adult_module(confirm=True)')

# the hard lines hold even with the module ON (codes verbatim in the report)
r = policy.check('minor')
assert r is not None and r.code == riggermortis.MINOR_CONTENT and not r.retryable
assert '[minor_content_prohibited]' in policy.format_refusal(r)
r = policy.check('real_person')
assert r is not None and r.code == riggermortis.REAL_PERSON_EXPLICIT and not r.retryable
print('RM_POLICY HARD-LINES-HOLD: minor + real_person refuse with '
      'verbatim codes while ON')

# toggles back off -> engine follows, the gate closes again
prefs.adult_module_enabled = False
prefs.adult_module_confirm = False
assert policy.sync_from_preferences() is False
r = policy.check('fictional_adult')
assert r is not None and r.code == riggermortis.ADULT_MODULE_DISABLED
print('RM_POLICY DISABLE-REOFF: toggles off -> engine OFF, gate closed')

print('RM_POLICY: PASS')
PY

echo "== 5/5 18+ policy enforcement through the real add-on (P6-4/P6-5)"
RM_ADDON_DIR="$REPO/addon" RM_CORE_SRC="$REPO/core/src" \
  "$BLENDER" -b --python "$TMP/policy_probe.py" 2>&1 | tee "$TMP/policy.txt" | grep -E "RM_POLICY" || true
for want in ENABLE-ADDON FRESH-OFF ONE-TOGGLE-STILL-OFF ENABLE-BOTH-TOGGLES HARD-LINES-HOLD DISABLE-REOFF; do
  grep -q "RM_POLICY $want" "$TMP/policy.txt" || {
    echo "MISSING RM_POLICY $want" >&2; exit 1; }
done
grep -q "RM_POLICY: PASS" "$TMP/policy.txt"
for want in FRESH-OFF ONE-TOGGLE-STILL-OFF ENABLE-BOTH-TOGGLES HARD-LINES-HOLD DISABLE-REOFF; do
  grep -q "RM_POLICY $want" "$TMP/policy.txt" || {
    echo "MISSING RM_POLICY $want" >&2; exit 1; }
done
grep -q "RM_POLICY: PASS" "$TMP/policy.txt"

echo ""
echo "PHASE 0 BLENDER GATE: PASS"
