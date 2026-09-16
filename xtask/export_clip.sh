#!/usr/bin/env bash
# P2-7 gate: animation export round-trip in real Blender.
# 1. builds the proven test armature (same layout as blender_verify.sh)
# 2. bakes a 2-frame canonical action (pose A + mirror) through the ADD-ON's
#    own bake path (riggermortis_addon.bake)
# 3. exports FBX + glTF via Blender's BUILTIN exporters (D-009: the spawn
#    lives in this shell script; no Python here spawns anything)
# 4. round-trips BOTH files in a fresh scene: skeleton survives (bone count +
#    mapping resolves), animation survives (action + fcurves cover the baked
#    frames), and per-frame pose fidelity is re-measured against the canonical
#    targets (same independent measure as verify_pose_apply.sh).
# Exits non-zero on first failure. Self-contained: no models, no local assets.
set -euo pipefail

BLENDER=${BLENDER:-blender}
REPO=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

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
from riggermortis_addon import bake as bake_mod  # noqa: E402

TOL_DEG = 2.0  # file-format round-trip bar (resampling + axis/unit conversion;
               # the in-process apply bar is 0.5 deg — verify_pose_apply.sh)


def build_rig():
    """The blender_verify.sh layout: maps 19/22 strict on every Blender tried."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bones = obj.data.edit_bones
    bones.remove(bones[0])

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
    return obj


def canonical_pose(i):
    """A leg-and-torso pose that changes between frame 0 and 1."""
    positions = {
        "spine": (0.0, 0.0, 0.09), "chest": (0.0, 0.0, 0.26),
        "neck": (0.0, 0.0, 0.45), "head": (0.0, 0.0, 0.56),
        "shoulder.L": (0.13, 0.0, 0.45), "shoulder.R": (-0.13, 0.0, 0.45),
        "upper_arm.L": (0.26, 0.0, 0.45 + 0.02 * i),
        "upper_arm.R": (-0.26, 0.0, 0.45),
        "forearm.L": (0.58, 0.0, 0.45), "forearm.R": (-0.58, 0.0, 0.45),
        "hand.L": (0.86, 0.0, 0.45), "hand.R": (-0.86, 0.0, 0.45),
        "hips": (0.0, 0.0, 0.0),
    }
    for sign in (-1.0, 1.0):
        side = ".L" if sign < 0 else ".R"
        hip = (sign * 0.08, 0.0, 0.0)
        positions[f"upper_leg{side}"] = hip
        knee_z = -0.5 - 0.06 * i * (1 if side == ".L" else 0)
        knee = ((hip[0] + sign * 0.11) / 2.0, -0.08, (0.0 + knee_z) / 2.0)
        ankle = (sign * 0.11 + 0.01 * i, -0.04, knee_z)
        positions[f"lower_leg{side}"] = knee
        positions[f"foot{side}"] = ankle
        positions[f"toe{side}"] = (ankle[0], ankle[1] - 0.12, ankle[2] - 0.05)
    return core.CanonicalPose(
        positions=positions, flips={}, confidence=0.9, reliable=True,
        scale=30.0, anchor="hips",
    )


def fcurve_count(act):
    """Action fcurve count across Blender APIs (4.x legacy / 5.x slotted)."""
    try:
        return len(act.fcurves)  # Blender <= 4.x
    except AttributeError:
        n = 0
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    n += len(bag.fcurves)
        return n


def first_armature():
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            return obj
    raise RuntimeError("no armature found in scene")


def measure(pose, mirror):
    """Independent pose check of the CURRENT armature vs canonical targets."""
    if mirror:
        pose = pose.mirrored()
    from riggermortis_addon import bpy_bridge, pose_apply

    obj = first_armature()
    mapping = pose_apply.mapping_from_props(obj, core) or core.map_rig(
        core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    )
    worst_role, worst_deg, checked = "", 0.0, 0
    for role, assignment in sorted(mapping.assignments.items()):
        target = core.bone_target_direction(pose, role)
        if target is None:
            continue
        pb = obj.pose.bones.get(assignment.bone)
        if pb is None:
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


def export_and_roundtrip(ext):
    """Bake once, export once, re-import in a fresh scene, verify.

    Returns "pass", "skip", or raises. A SKIP is honest and loud: it fires
    only when THIS Blender build lacks a dependency the exporter needs
    (apt Blender 4.x ships no numpy; its glTF exporter imports it). A gate
    where every format skipped is a FAIL.
    """
    obj = build_rig()
    pose_a = canonical_pose(0)
    pose_b = canonical_pose(1).mirrored()
    frames = [
        core.ActionFrame(frame=0, pose=pose_a),
        core.ActionFrame(frame=1, pose=pose_b),
    ]
    report = bake_mod.bake_action(obj, frames, core, name="rm_export_bake")
    baked_ok = report["baked_frames"] == [1, 2] and report["keys"] >= 24
    n_bones_source = len(obj.data.bones)  # stale after the scene switch below
    print(
        f"RM_EXPORT BAKE: {'PASS' if baked_ok else 'FAIL'} "
        f"frames={report['baked_frames']} keys={report['keys']} "
        f"worst={report['worst_deg']:.4f}deg"
    )
    if not baked_ok:
        return "fail"

    dir = os.environ["RM_EXPORT_DIR"]
    out = os.path.join(dir, f"clip.{ext}")
    try:
        if ext == "gltf":
            bpy.ops.export_scene.gltf(filepath=out, export_format='GLTF_SEPARATE')
        else:
            bpy.ops.export_scene.fbx(
                filepath=out, add_leaf_bones=False,
                object_types={'ARMATURE'},
            )
    except ModuleNotFoundError as exc:
        print(
            f"RM_EXPORT {ext.upper()}: SKIPPED (this Blender build lacks a "
            f"batteries module the exporter needs: {exc}) — honest skip, "
            "not a pass"
        )
        return "skip"
    if not os.path.getsize(out) > 0:
        print(f"RM_EXPORT {ext.upper()}: FAIL — empty file")
        return "fail"

    bpy.ops.wm.read_factory_settings(use_empty=True)
    if ext == "gltf":
        bpy.ops.import_scene.gltf(filepath=out)
    else:
        bpy.ops.import_scene.fbx(filepath=out)

    imported = first_armature()
    bone_count_ok = len(imported.data.bones) == n_bones_source
    ad = imported.animation_data
    act = ad.action if ad is not None else None
    n_curves = fcurve_count(act) if act is not None else 0
    frame_ok = act is not None and act.frame_range[0] <= 1 and act.frame_range[1] >= 2
    print(
        f"RM_EXPORT {ext.upper()} STRUCT: "
        f"{'PASS' if bone_count_ok and frame_ok else 'FAIL'} "
        f"bones={len(imported.data.bones)} fcurves={n_curves} "
        f"range={tuple(act.frame_range) if act is not None else None}"
    )

    evals = []
    for frame_no, mirror in ((1, False), (2, True)):
        bpy.context.scene.frame_set(frame_no)
        checked, worst_role, worst_deg = measure(canonical_pose(frame_no - 1), mirror)
        evals.append((frame_no, checked, worst_role, worst_deg))
    pose_ok = all(c >= 8 and w <= TOL_DEG for _f, c, _r, w in evals)
    detail = " ".join(
        f"f{f}:worst={w:.4f}deg({r}) checked={c}" for f, c, r, w in evals
    )
    print(f"RM_EXPORT {ext.upper()} POSE: {'PASS' if pose_ok else 'FAIL'} {detail}")
    return "pass" if (bone_count_ok and frame_ok and pose_ok) else "fail"


results = {}
for ext in ("gltf", "fbx"):
    results[ext] = export_and_roundtrip(ext)

verified = [e for e, r in results.items() if r == "pass"]
skipped = [e for e, r in results.items() if r == "skip"]
ok = bool(verified) and "fail" not in results.values()
print(
    f"RM_EXPORT GATE: {'PASS' if ok else 'FAIL'} "
    f"verified={','.join(verified) or 'none'} skipped={','.join(skipped) or 'none'} "
    "(a skip is honest: this Blender build lacks the exporter's dependency; "
    "a gate where EVERY format skipped is a FAIL)"
)
PY

echo "== running export round-trip probe"
RM_CORE_SRC="$REPO/core/src" \
RM_ADDON_DIR="$REPO/addon" \
RM_EXPORT_DIR="$TMP" \
  "$BLENDER" -b --python "$TMP/probe.py" 2>&1 | tee "$TMP/probe.log"

# The bake always runs; each format either round-trips (files exist, lines
# PASS) or is honestly SKIPPED (dependency missing in this Blender build).
# The gate FAILS unless at least ONE format is fully round-tripped.
grep -q "RM_EXPORT BAKE: PASS" "$TMP/probe.log"
grep -qE "RM_EXPORT GATE: PASS verified=(gltf|fbx)" "$TMP/probe.log"

echo ""
echo "P2-7 EXPORT ROUND-TRIP GATE: PASS"
