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
XBOT_GLB="$REPO/out/real_rigs/Xbot.glb"
XBOT_RIG="$REPO/out/real_rigs/xbot.rig.json"
PAYLOADS="$REPO/out/payloads"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

for f in "$IMG" "$MULTI_IMG" "$METARIG_BLEND" "$METARIG_RIG" "$SEEDSAN_VRM" \
         "$SEEDSAN_RIG" "$XBOT_GLB" "$XBOT_RIG"; do
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
if [ ! -s "$PAYLOADS/xbot_payload.json" ] || [ "$(fmt "$PAYLOADS/xbot_payload.json")" != "2" ]; then
  echo "== generating xbot payload (real models; P2-8a tail probe)"
  "$RIGPOSE" pose "$IMG" "$XBOT_RIG" --out "$PAYLOADS/xbot_payload.json" > /dev/null
fi

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

# -- P1-11 B2: review interactivity — pick ray + flip toggle re-applied --------
def run_review(payload_path):
    try:
        with open(payload_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        pose = core.CanonicalPose.from_dict(payload["pose"])
        points = core.joint_points(pose, origin=(0.0, 0.0, 0.0), scale=1.0)
        target = "lower_leg.L" if "lower_leg.L" in points else None
        if target is None:
            print("RM_REVIEW PICK: SKIP (no lower_leg.L in payload pose)")
            return True
        p = points[target]
        role = core.pick_joint(points, (p[0], p[1] + 5.0, p[2]), (0.0, -1.0, 0.0), radius=0.25)
        pick_ok = role == target
        print(f"RM_REVIEW PICK: {'PASS' if pick_ok else 'FAIL'} picked={role} expected={target}")
        toggled = pose.toggled("lower_leg.L")
        toggle_ok = (
            toggled is not pose
            and toggled.joint_confidence["lower_leg.L"] == 1.0
            and abs(toggled.positions["foot.L"][1] - pose.positions["foot.L"][1]) > 1e-6
        )
        print(f"RM_REVIEW TOGGLE: {'PASS' if toggle_ok else 'FAIL'}")
        report = pose_apply.apply_pose_object(first_armature(), toggled, core)
        apply_ok = report["worst_deg"] <= TOL_DEG and len(report["applied"]) >= 12
        print(
            f"RM_REVIEW TOGGLE_APPLY: {'PASS' if apply_ok else 'FAIL'} "
            f"worst={report['worst_deg']:.4f}deg applied={len(report['applied'])}"
        )
        return pick_ok and toggle_ok and apply_ok
    except Exception as exc:  # noqa: BLE001
        print(f"RM_REVIEW B2: FAIL ({exc.__class__.__name__}: {exc})")
        return False


ok &= run_review(os.path.join(os.environ["RM_PAYLOADS"], "metarig_payload.json"))

# -- P2-3: 2-frame action bake — key two poses, re-evaluate BOTH from the curves
def run_bake(payload_path):
    """Bake frame 1 = payload pose, frame 2 = mirrored pose into a new action,
    then re-measure each frame's bone world directions from the fcurve
    evaluation (scene.frame_set), bar <= 0.5 deg per bone per frame."""
    try:
        with open(payload_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        import riggermortis_addon.bake as bake  # noqa: E402

        pose_a = core.CanonicalPose.from_dict(payload["pose"])
        pose_b = pose_a.mirrored()
        frames = [
            core.ActionFrame(frame=0, pose=pose_a),
            core.ActionFrame(frame=1, pose=pose_b),
        ]
        obj = first_armature()
        report = bake.bake_action(obj, frames, core, name="rm_bake_gate")
        baked_ok = report["baked_frames"] == [1, 2] and report["keys"] >= 24
        print(
            f"RM_BAKE BAKE: {'PASS' if baked_ok else 'FAIL'} "
            f"frames={report['baked_frames']} keys={report['keys']} "
            f"worst={report['worst_deg']:.4f}deg mapping={report['mapping_source']}"
        )
        evals = []
        for frame_no, mirror in ((1, False), (2, True)):
            bpy.context.scene.frame_set(frame_no)
            checked, worst_role, worst_deg = measure(obj, payload["pose"], mirror)
            evals.append((frame_no, checked, worst_role, worst_deg))
        eval_ok = all(w <= TOL_DEG and c >= 12 for _f, c, _r, w in evals)
        detail = " ".join(
            f"f{f}:worst={w:.4f}deg({r}) checked={c}" for f, c, r, w in evals
        )
        print(f"RM_BAKE EVAL: {'PASS' if eval_ok else 'FAIL'} {detail}")
        obj.animation_data_clear()
        bpy.data.actions.remove(bpy.data.actions[report["action"]])
        return baked_ok and eval_ok
    except Exception as exc:  # noqa: BLE001
        print(f"RM_BAKE: FAIL ({exc.__class__.__name__}: {exc})")
        return False


ok &= run_bake(os.path.join(os.environ["RM_PAYLOADS"], "metarig_payload.json"))

# -- P2-5: foot-lock bake — locked ankle stays planted across the interval ------
def run_foot_lock():
    """Synthetic planted-foot action (canonical units): detect -> core lock ->
    bake with contacts on the metarig. The ankle bone's world position across
    the locked interval must drift <= 0.01 m, and the UNLOCKED bake of the raw
    frames must drift more (otherwise the lock does nothing in rig space)."""
    try:
        import riggermortis_addon.bake as bake
        from riggermortis_addon import pose_apply

        def probe_pose(i):
            positions = {
                "spine": (0.0, 0.0, 0.09), "chest": (0.0, 0.0, 0.26),
                "neck": (0.0, 0.0, 0.45), "head": (0.0, 0.0, 0.56),
                "shoulder.L": (0.13, 0.0, 0.45), "shoulder.R": (-0.13, 0.0, 0.45),
                "upper_arm.L": (0.26, 0.0, 0.45), "upper_arm.R": (-0.26, 0.0, 0.45),
                "forearm.L": (0.58, 0.0, 0.45), "forearm.R": (-0.58, 0.0, 0.45),
                "hand.L": (0.86, 0.0, 0.45), "hand.R": (-0.86, 0.0, 0.45),
            }
            sway = 0.004 * math.sin(0.7 * i)
            positions["hips"] = (sway, 0.0, 0.0)
            for sign in (-1.0, 1.0):
                side = ".L" if sign < 0 else ".R"
                hip = (sign * 0.08 + sway, 0.0, 0.0)
                positions[f"upper_leg{side}"] = hip
                if side == ".L":  # planted, drifting 0.004 u/frame (the artifact)
                    ankle = (-0.11 + 0.004 * i, 0.0, -1.0)
                else:  # swinging arc
                    t = min(1.0, (i + 1) / 11.0)
                    ankle = (0.11 - 0.02 * i, 0.0, -1.0 + 0.3 * math.sin(math.pi * t))
                knee = ((hip[0] + ankle[0]) / 2.0, -0.08, (hip[2] + ankle[2]) / 2.0)
                positions[f"lower_leg{side}"] = knee
                positions[f"foot{side}"] = ankle
                positions[f"toe{side}"] = (ankle[0], ankle[1] - 0.12, ankle[2])
            return core.CanonicalPose(
                positions=positions, flips={}, confidence=0.9, reliable=True,
                scale=30.0, anchor="hips",
            )

        frames = [core.ActionFrame(frame=i, pose=probe_pose(i)) for i in range(10)]
        action = core.action_from_poses([(f.frame, f.pose) for f in frames])
        report = core.detect_contacts(frames)
        l_ivs = [iv for iv in report.intervals if iv.foot == "foot.L"]
        if not l_ivs:
            print("RM_FOOT_LOCK LOCK: FAIL — detector found no foot.L contact")
            return False
        locked, lock = core.lock_feet(action, report)

        bpy.ops.wm.open_mainfile(filepath=os.environ["RM_METARIG_BLEND"])
        obj = first_armature()
        mapping = pose_apply.mapping_from_props(obj, core) or core.map_rig(
            core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
        )
        ankle_bone = mapping.assignments["foot.L"].bone

        def drift(report_frames):
            points = []
            for f in report_frames:
                bpy.context.scene.frame_set(f + 1)
                bpy.context.view_layer.update()
                points.append(obj.pose.bones[ankle_bone].matrix.to_translation())
            return max(
                (math.dist(a, b) for i, a in enumerate(points) for b in points[i + 1:]),
                default=0.0,
            )

        def clean(up):
            obj.animation_data_clear()
            act = bpy.data.actions.get(up["action"])
            if act is not None:
                bpy.data.actions.remove(act)

        contact_frames = [
            f for iv in l_ivs for f in range(iv.start, iv.end + 1)
        ]
        before = bake.bake_action(obj, frames, core, name="rm_lock_before")
        drift_before = drift(contact_frames)
        clean(before)
        after = bake.bake_action(
            obj, locked.frames, core, name="rm_lock_after", contacts=report
        )
        drift_after = drift(contact_frames)
        clean(after)

        bar = 0.01
        passed = drift_after <= bar and drift_after < drift_before
        print(
            f"RM_FOOT_LOCK BEFORE: unlocked ankle drift={drift_before:.4f}m "
            f"across {len(contact_frames)} contact frame(s)"
        )
        print(
            f"RM_FOOT_LOCK LOCK: {'PASS' if passed else 'FAIL'} "
            f"locked_drift={drift_after:.4f}m unlocked={drift_before:.4f}m "
            f"bar={bar:.4f}m lock_dev={after['lock_dev_deg']:.2f}deg "
            f"locked_frames={after['locked_frames']} "
            f"knee_cost={max(lock.max_knee_shift.values(), default=0.0):.4f}u"
        )
        return passed
    except Exception as exc:  # noqa: BLE001
        print(f"RM_FOOT_LOCK: FAIL ({exc.__class__.__name__}: {exc})")
        return False


ok &= run_foot_lock()

# -- P2-8a: glTF tail normalization — garbage tails ladder posed children -----
def run_xbot_tails():
    """On Xbot.glb (D-015: glTF-synthesized tails ~100x garbage) applying the
    standing-photo payload throws the EVALUATED ankle ~1.5 m above its rest
    height — children ladder through the garbage tails. With the add-on's
    conditional repair (absurd-ratio rule, lockstep with xtask/walk_media.py)
    applied BEFORE posing, the same payload's evaluated ankle lift lands
    INSIDE the measured sane-rig band: the certified rigs lifting the same
    canonical pose measure 0.2464 m (seedsan) and 0.3214 m (metarig); the
    repaired Xbot lands at 0.2817 m while the raw one is at 1.5177 m. Bars:
    fixed lift in [0.15, 0.40] m (sane band + margin), raw > 1.0 m and
    > 3x fixed. Also proves the sane-rig no-op: the metarig repairs 0 bones
    (co-located-child bones give no tail evidence and are skipped)."""
    try:
        from riggermortis.payload import pose_for_figure  # noqa: E402
        from riggermortis_addon import tails  # noqa: E402

        with open(os.path.join(os.environ["RM_PAYLOADS"], "xbot_payload.json"),
                  encoding="utf-8") as fh:
            payload = json.load(fh)

        def fresh_xbot():
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.gltf(filepath=os.environ["RM_XBOT_GLB"])
            obj = first_armature()
            mapping = pose_apply.mapping_from_props(obj, core) or core.map_rig(
                core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
            )
            return obj, mapping.assignments["foot.L"].bone

        def ankle_lift(obj, ankle):
            """Evaluated ankle world Z after apply vs its rest Z (the payload
            pose is upright — a sane evaluated rig keeps the lift in the
            measured sane band; garbage tails throw the foot into the air)."""
            rest_z = (obj.matrix_world @ obj.data.bones[ankle].head_local).z
            pose_apply.apply_payload(obj, payload)
            bpy.context.view_layer.update()
            applied_z = (
                obj.matrix_world @ obj.pose.bones[ankle].matrix.to_translation()
            ).z
            return applied_z - rest_z

        obj, ankle = fresh_xbot()
        raw_lift = ankle_lift(obj, ankle)

        obj, ankle = fresh_xbot()
        repaired = tails.normalize_imported_tails(obj)
        fixed_lift = ankle_lift(obj, ankle)

        # Sane-rig no-op: the Blender-native metarig must repair 0 bones.
        bpy.ops.wm.open_mainfile(filepath=os.environ["RM_METARIG_BLEND"])
        sane_repaired = tails.normalize_imported_tails(first_armature())

        noop_ok = sane_repaired == 0
        fixed_ok = repaired > 0 and 0.15 <= fixed_lift <= 0.40
        contrast_ok = raw_lift > 1.0 and raw_lift > 3.0 * fixed_lift
        passed = noop_ok and fixed_ok and contrast_ok
        print(
            f"RM_TAILS XBOT: {'PASS' if passed else 'FAIL'} "
            f"raw_lift={raw_lift:.4f}m fixed_lift={fixed_lift:.4f}m "
            f"repaired={repaired} "
            f"bars: fixed in [0.15,0.40]m (sane band 0.246-0.321 measured), "
            f"raw>1.0m and >3x fixed"
        )
        print(
            f"RM_TAILS METARIG_NOOP: {'PASS' if noop_ok else 'FAIL'} "
            f"(sane rig repaired {sane_repaired} bones — must be 0)"
        )
        return passed
    except Exception as exc:  # noqa: BLE001
        print(f"RM_TAILS: FAIL ({exc.__class__.__name__}: {exc})")
        return False


ok &= run_xbot_tails()

print("RM_POSE_APPLY GATE:", "PASS" if ok else "FAIL")
PY

echo "== running headless apply probe"
RM_CORE_SRC="$REPO/core/src" \
RM_ADDON_DIR="$REPO/addon" \
RM_METARIG_BLEND="$METARIG_BLEND" \
RM_SEEDSAN_VRM="$SEEDSAN_VRM" \
RM_XBOT_GLB="$XBOT_GLB" \
RM_PAYLOADS="$PAYLOADS" \
  "$BLENDER" -b --python "$TMP/probe.py" 2>&1 | tee "$TMP/probe.log"

grep -q "RM_POSE_APPLY METARIG: PASS" "$TMP/probe.log"
grep -q "RM_POSE_APPLY METARIG_MIRROR: PASS" "$TMP/probe.log"
grep -q "RM_POSE_APPLY CLEAR: PASS" "$TMP/probe.log"
grep -q "RM_POSE_APPLY SEEDSAN: PASS" "$TMP/probe.log"
grep -q "RM_POSE_APPLY MULTI_FIGURE_SWITCH: PASS" "$TMP/probe.log"
grep -q "RM_MULTI_FIGURE: labels=" "$TMP/probe.log"
grep -q "RM_REVIEW PICK: PASS" "$TMP/probe.log"
grep -q "RM_REVIEW TOGGLE: PASS" "$TMP/probe.log"
grep -q "RM_REVIEW TOGGLE_APPLY: PASS" "$TMP/probe.log"
grep -q "RM_BAKE BAKE: PASS" "$TMP/probe.log"
grep -q "RM_BAKE EVAL: PASS" "$TMP/probe.log"
grep -q "RM_FOOT_LOCK BEFORE: " "$TMP/probe.log"
grep -q "RM_FOOT_LOCK LOCK: PASS" "$TMP/probe.log"
grep -q "RM_TAILS XBOT: PASS" "$TMP/probe.log"
grep -q "RM_TAILS METARIG_NOOP: PASS" "$TMP/probe.log"
grep -q "RM_OVERLAY HANDLER: PASS" "$TMP/probe.log"
grep -qE "RM_OVERLAY OFFSCREEN: (PASS|SKIPPED)" "$TMP/probe.log"
grep -q "RM_POSE_APPLY GATE: PASS" "$TMP/probe.log"

echo ""
echo "P1-6 BLENDER POSE-APPLY GATE: PASS"
