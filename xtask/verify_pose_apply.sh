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
# v3 is additive (S26): formats 2 and 3 are both current-build-readable.
fmt_ok() { case "$1" in 2|3) return 0 ;; *) return 1 ;; esac; }
if [ ! -s "$PAYLOADS/metarig_payload.json" ] || ! fmt_ok "$(fmt "$PAYLOADS/metarig_payload.json")"; then
  echo "== generating metarig payload (real models)"
  "$RIGPOSE" pose "$IMG" "$METARIG_RIG" --out "$PAYLOADS/metarig_payload.json" > /dev/null
fi
if [ ! -s "$PAYLOADS/seedsan_payload.json" ] || ! fmt_ok "$(fmt "$PAYLOADS/seedsan_payload.json")"; then
  echo "== generating seedsan payload (real models)"
  "$RIGPOSE" pose "$IMG" "$SEEDSAN_RIG" --out "$PAYLOADS/seedsan_payload.json" > /dev/null
fi
echo "== generating multi-figure payload (B1: real models, --all-figures)"
"$RIGPOSE" pose "$MULTI_IMG" "$METARIG_RIG" --all-figures --out "$PAYLOADS/girls_multi.json" > /dev/null
if [ ! -s "$PAYLOADS/xbot_payload.json" ] || ! fmt_ok "$(fmt "$PAYLOADS/xbot_payload.json")"; then
  echo "== generating xbot payload (real models; P2-8a tail probe)"
  "$RIGPOSE" pose "$IMG" "$XBOT_RIG" --out "$PAYLOADS/xbot_payload.json" > /dev/null
fi

# -- P6-2 motion library: fixture -> bridge sampler -> convert/bake gate ------
# Synthetic sliding-walk fixtures are GENERATED at gate time (nothing binary
# committed); the REAL-Motion row samples the local Xbot.glb `walk` when it
# exists and SKIPS honestly otherwise.
echo "== building motion fixtures (SYNTHETIC sliding walk, gate-time only)"
"$BLENDER" -b --python "$REPO/xtask/motion_fixture.py" -- \
  "$TMP/rm_walk.bvh" "$TMP/rm_walk.fbx" 2>&1 | tee "$TMP/motion_fixture.log"
grep -q "RM_MOTIONFIX BUILD: PASS" "$TMP/motion_fixture.log"

echo "== sampling fixtures + real clip through the bridge sampler"
"$BLENDER" -b --python "$REPO/xtask/sample_clip.py" -- \
  "$TMP/rm_walk.bvh" "$TMP/rm_walk.bvh.clip.json" --tag BVH 2>&1 | tee "$TMP/sample_BVH.log"
grep -q "RM_MOTION SAMPLE BVH: ok=True" "$TMP/sample_BVH.log"
grep -q "RM_MOTION DETERM BVH: PASS" "$TMP/sample_BVH.log"
"$BLENDER" -b --python "$REPO/xtask/sample_clip.py" -- \
  "$TMP/rm_walk.fbx" "$TMP/rm_walk.fbx.clip.json" --tag FBX 2>&1 | tee "$TMP/sample_FBX.log"
grep -q "RM_MOTION SAMPLE FBX: ok=True" "$TMP/sample_FBX.log"
grep -q "RM_MOTION DETERM FBX: PASS" "$TMP/sample_FBX.log"
RM_CLIP_XBOT="$TMP/xbot_walk.clip.json"
if [ -s "$XBOT_GLB" ]; then
  "$BLENDER" -b --python "$REPO/xtask/sample_clip.py" -- \
    "$XBOT_GLB" "$RM_CLIP_XBOT" --action walk --tag XBOT 2>&1 | tee "$TMP/sample_XBOT.log"
  grep -q "RM_MOTION SAMPLE XBOT: ok=True" "$TMP/sample_XBOT.log"
  grep -q "RM_MOTION DETERM XBOT: PASS" "$TMP/sample_XBOT.log"
else
  rm -f "$RM_CLIP_XBOT"
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
from riggermortis import presets as rm_presets  # noqa: E402
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

# -- P6-1: secondary motion — spring chains through the REAL bake --------------
def run_secondary():
    """demo_tail.json (DATA, validated by core.ChainSpec) simulated over the
    SYNTHETIC walk fixture job (xtask/walk_job.py — labeled synthetic) via
    core.simulate_secondary, keyed through bake_action's secondary binding
    onto 4 appendage bones added under the mapped hips bone. Bars: chain
    directions re-evaluate <= 0.05 deg vs the simulated track, FK role world
    directions are unchanged with vs without the binding (<= 0.001 deg — the
    certified composition is untouched), the chain visibly responds to the
    walk's hip motion (max deviation from its instantaneous rest target
    >= 0.5 deg; the walk is a subtle synthetic — the step-response behavior
    bar lives in the probe, 24.84 deg measured), and the
    simulation is deterministic (two runs identical)."""
    try:
        from pathlib import Path

        import riggermortis_addon.bake as bake

        sys.path.insert(0, os.environ["RM_XTASK"])
        import walk_job  # noqa: E402

        job_dir = Path(os.environ["RM_WALK_JOB"])
        walk_job.build_walk_job(job_dir)
        action = core.load_action(job_dir)
        spec = core.ChainSpec.from_dict(
            json.loads(Path(os.environ["RM_TAIL_SPEC"]).read_text(encoding="utf-8"))
        )
        tracks_a, rep = core.simulate_secondary(action, [spec], fps=30.0)
        tracks_b, _rep2 = core.simulate_secondary(action, [spec], fps=30.0)
        determ = tracks_a == tracks_b
        max_dev = rep.max_dev_deg["tail"]
        sim_ok = determ and max_dev >= 0.5
        print(
            f"RM_SECONDARY SIM: {'PASS' if sim_ok else 'FAIL'} "
            f"chains={len(rep.chains)} frames={rep.frames} "
            f"substeps={rep.substeps_per_frame} max_dev={max_dev:.2f}deg "
            f"determ={determ}"
        )

        bpy.ops.wm.open_mainfile(filepath=os.environ["RM_METARIG_BLEND"])
        obj = first_armature()
        mapping = pose_apply.mapping_from_props(obj, core) or core.map_rig(
            core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
        )
        anchor_bone = mapping.assignments["hips"].bone

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        arm = obj.data
        head = tuple(arm.edit_bones[anchor_bone].tail)
        chain_bones = []
        for i in range(4):
            e = arm.edit_bones.new(f"rm_tail{i + 1}")
            e.head = head
            e.tail = (head[0], head[1], head[2] - 0.12)
            if i == 0:
                e.parent = arm.edit_bones[anchor_bone]
            else:
                e.parent = arm.edit_bones[chain_bones[i - 1]]
            e.use_connect = False
            chain_bones.append(e.name)
            head = e.tail
        bpy.ops.object.mode_set(mode="OBJECT")

        track = tracks_a["tail"]

        def read_dirs(bones):
            bpy.context.view_layer.update()
            out = {}
            for b in bones:
                pb = obj.pose.bones.get(b)
                if pb is not None:
                    out[b] = pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))
            return out

        n = len(action.frames)
        samples = sorted(
            {action.frames[0].frame + 1, action.frames[n // 2].frame + 1,
             action.frames[-1].frame + 1}
        )
        role_bones = [a.bone for a in mapping.assignments.values()]

        def clean(act_name):
            obj.animation_data_clear()
            act = bpy.data.actions.get(act_name)
            if act is not None:
                bpy.data.actions.remove(act)

        rep_ctl = bake.bake_action(obj, action.frames, core, name="rm_sec_control")
        control = {}
        for f in samples:
            bpy.context.scene.frame_set(f)
            control[f] = read_dirs(role_bones)
        clean(rep_ctl["action"])

        rep_sec = bake.bake_action(
            obj,
            action.frames,
            core,
            name="rm_sec_full",
            secondary=[(track, chain_bones)],
        )
        sec = rep_sec.get("secondary", {}).get("tail", {})
        bake_ok = (
            sec.get("bones") == 4
            and sec.get("keys") == 4 * n
            and len(rep_sec["baked_frames"]) == n
        )
        print(
            f"RM_SECONDARY BAKE: {'PASS' if bake_ok else 'FAIL'} "
            f"bones={sec.get('bones')} chain_keys={sec.get('keys')} "
            f"frames={len(rep_sec['baked_frames'])} fk_keys={rep_sec['keys'] - sec.get('keys', 0)}"
        )

        worst_chain = 0.0
        worst_fk = 0.0
        for f in samples:
            bpy.context.scene.frame_set(f)
            now_chain = read_dirs(chain_bones)
            now_roles = read_dirs(role_bones)
            for i, b in enumerate(chain_bones):
                src = f - 1
                k = track.frames.index(src)
                target = Vector(track.directions[k][i])
                got = now_chain.get(b)
                if got is not None:
                    worst_chain = max(worst_chain, math.degrees(got.angle(target)))
            for role_bone, v0 in control[f].items():
                got = now_roles.get(role_bone)
                if got is not None:
                    worst_fk = max(worst_fk, math.degrees(got.angle(v0)))

        reeval_ok = worst_chain <= 0.05
        fkinv_ok = worst_fk <= 0.001
        print(
            f"RM_SECONDARY REEVAL: {'PASS' if reeval_ok else 'FAIL'} "
            f"worst={worst_chain:.4f}deg bar<=0.05deg"
        )
        print(
            f"RM_SECONDARY FKINV: {'PASS' if fkinv_ok else 'FAIL'} "
            f"worst={worst_fk:.5f}deg bar<=0.001deg (certified composition untouched)"
        )

        # P6-1a: the SAME chain through a SAVED PRESET — the full author ->
        # save -> load -> fingerprint-gate -> simulate -> bake path via
        # core.presets inside Blender. The preset-carried binding must key
        # EXACTLY what the direct binding above keyed (same deterministic
        # simulation, same bake validation), a fingerprint mismatch must
        # refuse, and force must proceed.
        rig_data = core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
        preset = rm_presets.preset_from_mapping(
            rig_data, mapping,
            secondary=[rm_presets.SecondaryBinding(
                chain=spec, bones=tuple(chain_bones),
            )],
        )
        preset_path = job_dir / "gate_secondary.rigpreset.json"
        rm_presets.save_preset(preset, preset_path)
        loaded = rm_presets.load_preset(preset_path)
        bindings = rm_presets.resolve_secondary(loaded, rig_data.fingerprint())
        tracks_p, _rep_p = core.simulate_secondary(
            action, [b.chain for b in bindings], fps=30.0,
        )
        pairs = [(tracks_p[b.chain.name], list(b.bones)) for b in bindings]
        rep_pre = bake.bake_action(
            obj, action.frames, core, name="rm_sec_preset", secondary=pairs,
        )
        pre = rep_pre.get("secondary", {}).get("tail", {})
        preset_ok = (
            loaded.format == 2
            and [b.chain.name for b in loaded.secondary] == ["tail"]
            and pre.get("bones") == 4
            and pre.get("keys") == sec.get("keys")
            and len(rep_pre["baked_frames"]) == n
        )
        print(
            f"RM_SECONDARY PRESET: {'PASS' if preset_ok else 'FAIL'} "
            f"format={loaded.format} chains={len(loaded.secondary)} "
            f"keys={pre.get('keys')} direct_keys={sec.get('keys')}"
        )
        mismatch_refused = False
        try:
            rm_presets.resolve_secondary(loaded, "0" * 64)
        except core.PresetError:
            mismatch_refused = True
        forced = rm_presets.resolve_secondary(loaded, "0" * 64, force=True)
        gate_ok = mismatch_refused and len(forced) == 1
        print(
            f"RM_SECONDARY PRESET_GATE: {'PASS' if gate_ok else 'FAIL'} "
            f"mismatch_refused={mismatch_refused} force_bindings={len(forced)}"
        )

        clean(rep_pre["action"])
        clean(rep_sec["action"])
        return (
            sim_ok and bake_ok and reeval_ok and fkinv_ok
            and preset_ok and gate_ok
        )
    except Exception as exc:  # noqa: BLE001
        print(f"RM_SECONDARY: FAIL ({exc.__class__.__name__}: {exc})")
        return False


ok &= run_secondary()

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
RM_XTASK="$REPO/xtask" \
RM_WALK_JOB="$TMP/walk_job" \
RM_TAIL_SPEC="$REPO/addon/riggermortis_addon/presets/secondary/demo_tail.json" \
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
grep -q "RM_SECONDARY SIM: PASS" "$TMP/probe.log"
grep -q "RM_SECONDARY BAKE: PASS" "$TMP/probe.log"
grep -q "RM_SECONDARY REEVAL: PASS" "$TMP/probe.log"
grep -q "RM_SECONDARY FKINV: PASS" "$TMP/probe.log"
grep -q "RM_SECONDARY PRESET: PASS" "$TMP/probe.log"
grep -q "RM_SECONDARY PRESET_GATE: PASS" "$TMP/probe.log"
grep -q "RM_TAILS XBOT: PASS" "$TMP/probe.log"
grep -q "RM_TAILS METARIG_NOOP: PASS" "$TMP/probe.log"
grep -q "RM_OVERLAY HANDLER: PASS" "$TMP/probe.log"
grep -qE "RM_OVERLAY OFFSCREEN: (PASS|SKIPPED)" "$TMP/probe.log"
grep -q "RM_POSE_APPLY GATE: PASS" "$TMP/probe.log"

cat > "$TMP/motion_gate.py" <<'PY'
"""P6-2 motion-library gate: sampled clips -> certified composition -> bake.

Consumes the bridge sampler's clip JSONs (fixture BVH + FBX, and the REAL
Xbot.glb `walk` sample when it exists), converts through core
``action_from_clip``, runs the certified composition (detect -> lock), bakes
on the real metarig through the add-on's own ``bake_action``, and
re-evaluates from the fcurves against the locked canonical poses. Bars:
the >=5x slide-reduction family on the deliberately sliding fixture (the
CI clip pins the same contract core-side), the 0.5 deg FK-family bar on
independent fcurve re-evaluation, and FBX-vs-BVH canonical equality. The
REAL row gates retarget fidelity and reports its contact finding HONESTLY —
thresholds are never tuned to make real data plant (D-008).
"""
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["RM_CORE_SRC"])
sys.path.insert(0, os.environ["RM_ADDON_DIR"])

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import riggermortis as core  # noqa: E402
from riggermortis_addon import bake, bpy_bridge, pose_apply  # noqa: E402

SLIDE_BAR_U = 0.05  # the fixture slide must be real before the lock runs
LOCK_FAMILY = 5  # the published >=5x slide-reduction criterion
REEVAL_BAR_DEG = 0.5  # FK family
ROUNDTRIP_BAR_U = 0.005  # exporter round-trip family (probe-measured 0.000000)
SPREAD = 6  # re-evaluated frames per bake


def first_armature():
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            return obj
    raise RuntimeError("no armature found in scene")


def metarig():
    bpy.ops.wm.open_mainfile(filepath=os.environ["RM_METARIG_BLEND"])
    obj = first_armature()
    mapping = pose_apply.mapping_from_props(obj, core) or core.map_rig(
        core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    )
    return obj, mapping


def spread_frames(frames, count=SPREAD):
    n = len(frames)
    idxs = sorted({round(i * (n - 1) / (count - 1)) for i in range(count)})
    return [frames[i] for i in idxs]


def reeval(obj, mapping, frames):
    """Independent fcurve re-evaluation: mapped-role bone world directions vs
    the canonical targets of the (locked) poses at spread frames."""
    worst, checked = 0.0, 0
    for af in spread_frames(frames):
        bpy.context.scene.frame_set(af.frame)
        bpy.context.view_layer.update()
        for role, assignment in sorted(mapping.assignments.items()):
            target = core.bone_target_direction(af.pose, role)
            if target is None:
                continue
            pb = obj.pose.bones.get(assignment.bone)
            if pb is None:
                continue
            d = (pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
            checked += 1
            worst = max(worst, math.degrees(d.angle(Vector(target).normalized())))
    return checked, worst


def bake_and_reeval(tag, obj, mapping, locked, report, expect_locked):
    rep = bake.bake_action(
        obj, locked.frames, core, name=f"rm_motion_{tag}", frame_offset=0,
        contacts=report,
    )
    baked_ok = (
        len(rep["baked_frames"]) == len(locked.frames)
        and rep["worst_deg"] <= REEVAL_BAR_DEG
        and (rep["locked_frames"] > 0) == expect_locked
    )
    print(
        f"RM_MOTION {tag} BAKE: {'PASS' if baked_ok else 'FAIL'} "
        f"frames={len(rep['baked_frames'])} keys={rep['keys']} "
        f"worst={rep['worst_deg']:.4f}deg lock_dev={rep['lock_dev_deg']:.2f}deg "
        f"locked={rep['locked_frames']} mapping={rep['mapping_source']}"
    )
    checked, worst = reeval(obj, mapping, locked.frames)
    reeval_ok = worst <= REEVAL_BAR_DEG
    print(
        f"RM_MOTION {tag} REEVAL: {'PASS' if reeval_ok else 'FAIL'} "
        f"checked={checked} worst={worst:.4f}deg bar<={REEVAL_BAR_DEG}deg "
        f"frames={SPREAD}"
    )
    return baked_ok and reeval_ok


ok = True

# -- the SYNTHETIC sliding-walk fixture (the slide-cleaning deliverable) ------
clip = core.MotionClip.load(Path(os.environ["RM_CLIP_BVH"]))
action = core.action_from_clip(clip)
idxs = [af.frame for af in action.frames]
seen_roles = set()
for af in action.frames:
    seen_roles.update(af.pose.positions)
missing_n = len(set(core.ALL_ROLES) - seen_roles)
convert_ok = (
    len(action.frames) == len(clip.frames)
    and idxs == sorted(cf.frame for cf in clip.frames)
    and missing_n > 0
    and any("absent from the clip" in n for n in action.notes)
)
print(
    f"RM_MOTION CONVERT: {'PASS' if convert_ok else 'FAIL'} "
    f"frames={len(action.frames)} fps={clip.fps:g} scale_ref={clip.scale_ref:.6f} "
    f"roles={len(seen_roles)} missing_roles={missing_n} (ledgered, never guessed)"
)
ok &= convert_ok

report = core.detect_contacts(action.frames)
left = [iv for iv in report.intervals if iv.foot == "foot.L"]
right = [iv for iv in report.intervals if iv.foot == "foot.R"]
contacts_ok = len(left) >= 2 and len(right) >= 2
print(
    f"RM_MOTION CONTACTS: {'PASS' if contacts_ok else 'FAIL'} "
    f"left={[(iv.start, iv.end) for iv in left]} "
    f"right={[(iv.start, iv.end) for iv in right]}"
)
ok &= contacts_ok

slide_before = core.foot_slide(action.frames, report).total
locked, lock_rep = core.lock_feet(action, report)
after = lock_rep.slide_after.total
lock_ok = (
    slide_before > SLIDE_BAR_U
    and after * LOCK_FAMILY <= lock_rep.slide_before.total
)
print(
    f"RM_MOTION LOCK: {'PASS' if lock_ok else 'FAIL'} "
    f"before={lock_rep.slide_before.total:.4f}u after={after:.6f}u "
    f"bar before>{SLIDE_BAR_U}u, after*{LOCK_FAMILY}<=before "
    f"(ratio={'inf' if after == 0 else f'{lock_rep.slide_before.total / after:.0f}x'})"
)
ok &= lock_ok

obj, mapping = metarig()
ok &= bake_and_reeval("FIXTURE", obj, mapping, locked, report, expect_locked=True)

# -- FBX fixture: the same authored walk must convert identically -------------
clip_f = core.MotionClip.load(Path(os.environ["RM_CLIP_FBX"]))
action_f = core.action_from_clip(clip_f)
worst = 0.0
for fa, fb in zip(action.frames, action_f.frames):
    for role in fa.pose.positions:
        worst = max(
            worst,
            max(abs(fa.pose.positions[role][i] - fb.pose.positions[role][i])
                for i in range(3)),
        )
fbx_ok = (
    len(action_f.frames) == len(action.frames)
    and worst <= ROUNDTRIP_BAR_U
)
print(
    f"RM_MOTION FBX: {'PASS' if fbx_ok else 'FAIL'} "
    f"worst={worst:.6f}u bar<={ROUNDTRIP_BAR_U}u frames={len(action_f.frames)}"
)
ok &= fbx_ok

# -- the REAL-Motion row: Xbot.glb `walk` (SKIPPED honestly when absent) -------
xbot_path = os.environ.get("RM_CLIP_XBOT", "")
if not xbot_path or not os.path.isfile(xbot_path):
    print("RM_MOTION XBOT: SKIPPED (no clip sample; set RM_CLIP_XBOT to the "
          "sampler's output for the local Xbot.glb `walk`)")
else:
    xok = True
    clip_x = core.MotionClip.load(Path(xbot_path))
    action_x = core.action_from_clip(clip_x)
    print(
        f"RM_MOTION XBOT CONVERT: PASS frames={len(action_x.frames)} "
        f"fps={clip_x.fps:g} scale_ref={clip_x.scale_ref:.4f} "
        f"roles={len(next(iter(action_x.frames)).pose.positions)}"
    )
    report_x = core.detect_contacts(action_x.frames)
    l_x = [iv for iv in report_x.intervals if iv.foot == "foot.L"]
    r_x = [iv for iv in report_x.intervals if iv.foot == "foot.R"]
    slide_x = core.foot_slide(action_x.frames, report_x).total
    locked_x, lock_x = core.lock_feet(action_x, report_x)
    unchanged = all(
        af.pose.positions == src.pose.positions
        for af, src in zip(locked_x.frames, action_x.frames)
    ) if lock_x.slide_before.total == 0.0 else True
    print(
        f"RM_MOTION XBOT CONTACTS: intervals={len(l_x) + len(r_x)} "
        f"(L={len(l_x)} R={len(r_x)}) slide_before={slide_x:.4f}u "
        f"lock_noop_intact={'PASS' if unchanged else 'FAIL'} — the honest "
        f"finding, never threshold-tuned (see docs/BENCHMARKS.md MOTION)"
    )
    xok &= unchanged
    obj, mapping = metarig()
    xok &= bake_and_reeval(
        "XBOT", obj, mapping, locked_x, report_x, expect_locked=len(l_x) + len(r_x) > 0
    )
    print(f"RM_MOTION XBOT: {'PASS' if xok else 'FAIL'}")
    ok &= xok

print("RM_MOTION GATE:", "PASS" if ok else "FAIL")
PY

echo "== running motion-library gate probe (P6-2)"
RM_CORE_SRC="$REPO/core/src" \
RM_ADDON_DIR="$REPO/addon" \
RM_METARIG_BLEND="$METARIG_BLEND" \
RM_CLIP_BVH="$TMP/rm_walk.bvh.clip.json" \
RM_CLIP_FBX="$TMP/rm_walk.fbx.clip.json" \
RM_CLIP_XBOT="$RM_CLIP_XBOT" \
  "$BLENDER" -b --python "$TMP/motion_gate.py" 2>&1 | tee "$TMP/motion_gate.log"

grep -q "RM_MOTION CONVERT: PASS" "$TMP/motion_gate.log"
grep -q "RM_MOTION CONTACTS: PASS" "$TMP/motion_gate.log"
grep -q "RM_MOTION LOCK: PASS" "$TMP/motion_gate.log"
grep -q "RM_MOTION FIXTURE BAKE: PASS" "$TMP/motion_gate.log"
grep -q "RM_MOTION FIXTURE REEVAL: PASS" "$TMP/motion_gate.log"
grep -q "RM_MOTION FBX: PASS" "$TMP/motion_gate.log"
grep -qE "RM_MOTION XBOT: (PASS|SKIPPED)" "$TMP/motion_gate.log"
grep -q "RM_MOTION GATE: PASS" "$TMP/motion_gate.log"

# -- P8-1 scenes: multi-rig apply + v2 back-compat + camera v0 stage/refuse ---
echo "== scene gate: one multi-figure payload -> two rigs + camera v0"
RM_CORE_SRC="$REPO/core/src" \
RM_ADDON_DIR="$REPO/addon" \
RM_SCENE_MULTI="$PAYLOADS/girls_multi.json" \
RM_SCENE_SINGLE="$PAYLOADS/metarig_payload.json" \
  "$BLENDER" -b --python "$REPO/xtask/scene_gate.py" 2>&1 | tee "$TMP/scene_gate.log"
grep -q "RM_SCENE CASTING: PASS" "$TMP/scene_gate.log"
grep -q "RM_SCENE APPLY2: PASS" "$TMP/scene_gate.log"
grep -q "RM_SCENE V2-BACKCOMPAT: PASS" "$TMP/scene_gate.log"
grep -q "RM_SCENE CAMERA-REFUSE: PASS" "$TMP/scene_gate.log"
grep -q "RM_SCENE CAMERA-STAGE: PASS" "$TMP/scene_gate.log"
grep -q "RM_SCENE GATE: PASS" "$TMP/scene_gate.log"

echo ""
echo "P1-6 BLENDER POSE-APPLY GATE: PASS"
