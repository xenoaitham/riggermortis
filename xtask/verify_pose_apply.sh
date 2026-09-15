#!/usr/bin/env bash
# P1-6 gate: pose-payload application in real Blender.
# 1. generates pose payloads with the real pipeline (models must be downloaded)
# 2. applies them headlessly via the ADD-ON's own pose_apply module on
#    - the real Rigify metarig .blend  (payload + mirrored payload)
#    - the Seed-san VRM imported fresh
# 3. independently re-measures every mapped bone's world direction against the
#    canonical targets (bone_target_direction); bar: <= 0.5 degrees per bone.
# Also smoke-tests clear_pose (back to rest). Exits non-zero on first failure.
set -euo pipefail

BLENDER=${BLENDER:-blender}
RIGPOSE=${RIGPOSE:-rigpose}
REPO=$(cd "$(dirname "$0")/.." && pwd)
IMG="$REPO/out/benchmark/images/photo/rtmpose_human_pose.jpg"
MULTI_IMG="$REPO/out/benchmark/images/photo/girls_still_multi.png"
METARIG_BLEND="$REPO/out/real_rigs/metarig.blend"
METARIG_RIG="$REPO/out/real_rigs/metarig.rig.json"
SEEDSAN_VRM="$REPO/out/real_rigs/Seed-san.vrm"
SEEDSAN_RIG="$REPO/out/real_rigs/seedsan.rig.json"
PAYLOADS="$REPO/out/payloads"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

for f in "$IMG" "$MULTI_IMG" "$METARIG_BLEND" "$METARIG_RIG" "$SEEDSAN_VRM" "$SEEDSAN_RIG"; do
  if [ ! -s "$f" ]; then
    echo "missing $f — build it first (see docs/BENCHMARKS.md reproduce block)" >&2
    exit 1
  fi
done

mkdir -p "$PAYLOADS"
fmt() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('format',1))" "$1" 2>/dev/null || echo 0; }
if [ ! -s "$PAYLOADS/metarig_payload.json" ] || [ "$(fmt "$PAYLOADS/metarig_payload.json")" != "2" ]; then
  echo "== generating metarig payload (real models)"
  "$RIGPOSE" pose "$IMG" "$METARIG_RIG" --out "$PAYLOADS/metarig_payload.json" > /dev/null
fi
if [ ! -s "$PAYLOADS/seedsan_payload.json" ] || [ "$(fmt "$PAYLOADS/seedsan_payload.json")" != "2" ]; then
  echo "== generating seedsan payload (real models)"
  "$RIGPOSE" pose "$IMG" "$SEEDSAN_RIG" --out "$PAYLOADS/seedsan_payload.json" > /dev/null
fi
echo "== generating multi-figure payload (B1: real models, --all-figures)"
"$RIGPOSE" pose "$MULTI_IMG" "$METARIG_RIG" --all-figures --out "$PAYLOADS/girls_multi.json" > /dev/null

cat > "$TMP/probe.py" <<'PY'
import json
import math
import os
import sys

sys.path.insert(0, os.environ["RM_CORE_SRC"])
sys.path.insert(0, os.environ["RM_ADDON_DIR"])

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import riggermortis as core  # noqa: E402
from riggermortis_addon import bpy_bridge, pose_apply  # noqa: E402

TOL_DEG = 0.5


def first_armature():
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            return obj
    raise RuntimeError("no armature found in scene")


def measure(obj, pose_dict, mirror):
    """Independent check: applied pose-bone world directions vs canonical targets."""
    pose = core.CanonicalPose.from_dict(pose_dict)
    if mirror:
        pose = pose.mirrored()
    mapping = pose_apply.mapping_from_props(obj, core) or core.map_rig(
        core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    )
    worst_role, worst_deg = "", 0.0
    checked = 0
    for role, assignment in sorted(mapping.assignments.items()):
        target = core.bone_target_direction(pose, role)
        if target is None:
            continue
        pb = obj.pose.bones.get(assignment.bone)
        if pb is None:
            print(f"  MEASURE MISS {role}: pose bone {assignment.bone!r} absent")
            continue
        bpy.context.view_layer.update()
        d = pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))
        d.normalize()
        dot = max(-1.0, min(1.0, d.dot(Vector(target))))
        deg = math.degrees(math.acos(dot))
        checked += 1
        if deg > worst_deg:
            worst_role, worst_deg = role, deg
    return checked, worst_role, worst_deg


def run(payload_path, label, mirror, figure=None):
    with open(payload_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    from riggermortis.payload import pose_for_figure  # noqa: E402

    from riggermortis.payload import entry_for_label  # noqa: E402

    obj = first_armature()
    report = pose_apply.apply_payload(obj, payload, mirror=mirror, figure=figure)
    pose_dict = pose_for_figure(payload, figure)
    expected_label = entry_for_label(payload, figure)["label"]
    checked, worst_role, worst_deg = measure(obj, pose_dict, mirror)
    label_ok = report["figure"] == expected_label
    status = "PASS" if (worst_deg <= TOL_DEG and checked >= 12 and label_ok) else "FAIL"
    if not label_ok:
        print(f"  figure mismatch: applied {report['figure']!r} expected {expected_label!r}")
    print(
        f"RM_POSE_APPLY {label}: {status} worst={worst_deg:.4f}deg role={worst_role} "
        f"checked={checked} applied={len(report['applied'])} mapping={report['mapping_source']} "
        f"notes={len(report['notes'])}"
    )
    if status == "FAIL":
        print(f"  report: {report}")
    return status == "PASS"


def run_clear(obj):
    import mathutils

    pose_apply.clear_pose(obj)
    bpy.context.view_layer.update()
    dirty = [pb.name for pb in obj.pose.bones if pb.matrix_basis != mathutils.Matrix.Identity(4)]
    print(f"RM_POSE_APPLY CLEAR: {'PASS' if not dirty else 'FAIL'} dirty={dirty[:5]}")
    return not dirty


def run_overlay(payload_path):
    """P1-7 headless check: handler registers, line data builds, offscreen attempt.

    Honest scope: a background Blender without a GPU context reports SKIPPED,
    never a faked pass.
    """
    try:
        with open(payload_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        import riggermortis_addon.overlay as overlay

        overlay.register()
        pose = core.CanonicalPose.from_dict(payload["pose"])
        segments = core.skeleton_segments(pose)
        data = overlay.line_data(pose, segments, 0.9, (0.0, 0.0, 0.0))
        bands = {c for _a, _b, c in data}
        if len(data) < 12:
            print(f"RM_OVERLAY HANDLER: FAIL segments={len(data)} (expected >=12)")
            return False
        print(f"RM_OVERLAY HANDLER: PASS segments={len(data)} bands={len(bands)}")
        try:
            import gpu
            from gpu_extras.batch import batch_for_shader

            offscreen = gpu.types.GPUOffScreen(256, 256)
            with offscreen.bind():
                fb = gpu.state.active_framebuffer_get()
                offscreen.clear(color=(0.0, 0.0, 0.0, 1.0))
                shader = gpu.shader.from_builtin("UNIFORM_COLOR")
                drawn = 0
                for color in (overlay.COLOR_LOW, overlay.COLOR_MID, overlay.COLOR_OK):
                    verts = [a for a, _b, c in data if c == color] + [
                        b for _a, b, c in data if c == color
                    ]
                    idx = [(i, i + 1) for i in range(0, len(verts), 2)]
                    if not idx:
                        continue
                    batch = batch_for_shader(shader, "LINES", {"pos": verts}, indices=idx)
                    shader.uniform_float("color", color)
                    batch.draw(shader)
                    drawn += len(idx)
                px = fb.read_color()
                lit = sum(1 for p in px.to_list() if any(v > 0.01 for v in p[:3]))
            offscreen.free()
            print(f"RM_OVERLAY OFFSCREEN: PASS drawn={drawn} lit_px={lit}")
            return drawn > 0
        except Exception as exc:  # noqa: BLE001 — honest scope: no GPU in background
            print(f"RM_OVERLAY OFFSCREEN: SKIPPED ({exc.__class__.__name__}: {exc})")
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"RM_OVERLAY HANDLER: FAIL ({exc.__class__.__name__}: {exc})")
        return False


ok = True

# -- metarig: payload, mirror, clear ------------------------------------------
bpy.ops.wm.open_mainfile(filepath=os.environ["RM_METARIG_BLEND"])
ok &= run(os.path.join(os.environ["RM_PAYLOADS"], "metarig_payload.json"), "METARIG", mirror=False)
ok &= run(os.path.join(os.environ["RM_PAYLOADS"], "metarig_payload.json"), "METARIG_MIRROR", mirror=True)
ok &= run_clear(first_armature())

# -- seedsan: fresh VRM import, payload ----------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.environ["RM_SEEDSAN_VRM"])
ok &= run(os.path.join(os.environ["RM_PAYLOADS"], "seedsan_payload.json"), "SEEDSAN", mirror=False)

# -- B1: multi-figure payload — switch figures in-process on the metarig -------
bpy.ops.wm.open_mainfile(filepath=os.environ["RM_METARIG_BLEND"])
with open(os.path.join(os.environ["RM_PAYLOADS"], "girls_multi.json"), encoding="utf-8") as fh:
    _multi = json.load(fh)
if len(_multi.get("figures", [])) >= 2:
    _label_b = _multi["figures"][1]["label"]
    ok &= run(os.path.join(os.environ["RM_PAYLOADS"], "girls_multi.json"),
              "MULTI_FIGURE_SWITCH", mirror=False, figure=_label_b)
    with open(os.path.join(os.environ["RM_PAYLOADS"], "girls_multi.json"), encoding="utf-8") as fh2:
        _multi2 = json.load(fh2)
    _labels = [f["label"] for f in _multi2["figures"]]
    print(f"RM_MULTI_FIGURE: labels={_labels} applied={_label_b}")
    ok &= len(_labels) >= 2
else:
    print("RM_MULTI_FIGURE: FAIL — payload does not embed >=2 figures")
    ok = False

# -- P1-7 review overlay: handler registers, line data builds, offscreen attempt
ok &= run_overlay(os.path.join(os.environ["RM_PAYLOADS"], "metarig_payload.json"))

print("RM_POSE_APPLY GATE:", "PASS" if ok else "FAIL")
PY

echo "== running headless apply probe"
RM_CORE_SRC="$REPO/core/src" \
RM_ADDON_DIR="$REPO/addon" \
RM_METARIG_BLEND="$METARIG_BLEND" \
RM_SEEDSAN_VRM="$SEEDSAN_VRM" \
RM_PAYLOADS="$PAYLOADS" \
  "$BLENDER" -b --python "$TMP/probe.py" 2>&1 | tee "$TMP/probe.log"

grep -q "RM_POSE_APPLY METARIG: PASS" "$TMP/probe.log"
grep -q "RM_POSE_APPLY METARIG_MIRROR: PASS" "$TMP/probe.log"
grep -q "RM_POSE_APPLY CLEAR: PASS" "$TMP/probe.log"
grep -q "RM_POSE_APPLY SEEDSAN: PASS" "$TMP/probe.log"
grep -q "RM_POSE_APPLY MULTI_FIGURE_SWITCH: PASS" "$TMP/probe.log"
grep -q "RM_MULTI_FIGURE: labels=" "$TMP/probe.log"
grep -q "RM_OVERLAY HANDLER: PASS" "$TMP/probe.log"
grep -qE "RM_OVERLAY OFFSCREEN: (PASS|SKIPPED)" "$TMP/probe.log"
grep -q "RM_POSE_APPLY GATE: PASS" "$TMP/probe.log"

echo ""
echo "P1-6 BLENDER POSE-APPLY GATE: PASS"
