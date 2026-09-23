#!/usr/bin/env python
"""P6-2 fixture builder: a SYNTHETIC sliding-walk clip as BVH + FBX.

Run inside Blender (shell glue spawns it — D-009):

    blender -b --python xtask/motion_fixture.py -- out.bvh out.fbx

Builds the probe's BVH-conventional humanoid (``xtask/motion_probe.py``'s
``build_humanoid`` extended with hands + toes so the converter sees 19
canonical roles) and keys a 49-frame walk whose STANCE legs rotate slowly
about the hip while rigid — the ankle traces a shallow arc instead of
staying planted, which is exactly the classic mocap foot-slide artifact the
certified composition exists to clean. Swing legs flex the knee (the foot
lifts clear of the ground). Nothing here is real motion: the clip is a
labeled synthetic gate fixture, generated at gate time, never committed.

Design numbers (chosen from the contact detector's documented thresholds,
NOT fitted — D-008 discipline):
- stance sweep +-5 deg over 12 frames on a 0.84 m hip->ankle radius
  = 0.0134 m/frame ankle drift = 0.0143 canonical u/frame (detector
  enter_speed bar 0.02 u/frame — contact-classified while visibly sliding);
  the stance leg is RIGID (knee joint 0) so the drift is exactly the arc;
- stance total slide ~0.157 u per interval (the lock has something to zero);
- swing knee flexion 50 deg lifts the ankle to ~0.23 m (detector exit_height
  0.20 u — clearly airborne).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from mathutils import Matrix

FPS = 24
N_FRAMES = 49  # two 24-frame cycles + the wrap frame (f49 == f1 pose)
STANCE = 12  # frames per stance/swing half-cycle
SWEEP_DEG = 5.0  # +-5 deg stance rotation (the slide)
KNEE_DEG = 50.0  # swing knee flexion peak (the lift)

# parent chain for the mini humanoid (parent-first build order)
PARENTS = {
    "Hips": None,
    "Spine": "Hips",
    "Spine1": "Spine",
    "Neck": "Spine1",
    "Head": "Neck",
    "LeftArm": "Spine1",
    "LeftForeArm": "LeftArm",
    "LeftHand": "LeftForeArm",
    "RightArm": "Spine1",
    "RightForeArm": "RightArm",
    "RightHand": "RightForeArm",
    "LeftUpLeg": "Hips",
    "LeftLeg": "LeftUpLeg",
    "LeftFoot": "LeftLeg",
    "LeftToeBase": "LeftFoot",
    "RightUpLeg": "Hips",
    "RightLeg": "RightUpLeg",
    "RightFoot": "RightLeg",
    "RightToeBase": "RightFoot",
}
ORDER = list(PARENTS)

# rest heads (meters, Z-up, facing -Y) — the probe's humanoid plus hands/toes
REST_HEADS = {
    "Hips": (0.0, 0.0, 1.0),
    "Spine": (0.0, 0.0, 1.12),
    "Spine1": (0.0, 0.0, 1.30),
    "Neck": (0.0, 0.0, 1.48),
    "Head": (0.0, 0.0, 1.56),
    "LeftArm": (0.05, 0.0, 1.42),
    "LeftForeArm": (0.25, 0.0, 1.42),
    "LeftHand": (0.45, 0.0, 1.42),
    "RightArm": (-0.05, 0.0, 1.42),
    "RightForeArm": (-0.25, 0.0, 1.42),
    "RightHand": (-0.45, 0.0, 1.42),
    "LeftUpLeg": (0.09, 0.0, 0.92),
    "LeftLeg": (0.09, 0.0, 0.50),
    "LeftFoot": (0.09, 0.0, 0.08),
    "LeftToeBase": (0.09, -0.12, 0.02),
    "RightUpLeg": (-0.09, 0.0, 0.92),
    "RightLeg": (-0.09, 0.0, 0.50),
    "RightFoot": (-0.09, 0.0, 0.08),
    "RightToeBase": (-0.09, -0.12, 0.02),
}
REST_TAILS = {
    "Head": (0.0, 0.0, 1.72),
    "LeftHand": (0.58, 0.0, 1.42),
    "RightHand": (-0.58, 0.0, 1.42),
    "LeftToeBase": (0.09, -0.24, 0.02),
    "RightToeBase": (-0.09, -0.24, 0.02),
}
LEGS = ("UpLeg", "Leg", "Foot")


def build_humanoid(name):
    """Fresh armature with BVH-conventional names, QUATERNION pose bones."""
    arm = bpy.data.armatures.new(name)  # type: ignore[name-defined]
    obj = bpy.data.objects.new(name, arm)  # type: ignore[name-defined]
    bpy.context.scene.collection.objects.link(obj)  # type: ignore[name-defined]
    bpy.context.view_layer.objects.active = obj  # type: ignore[name-defined]
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    made = {}
    for bname in ORDER:
        e = arm.edit_bones.new(bname)
        e.head = REST_HEADS[bname]
        child = next((c for c in ORDER if PARENTS[c] == bname), None)
        if child:
            e.tail = REST_HEADS[child]
        elif bname in REST_TAILS:
            e.tail = REST_TAILS[bname]
        else:
            h = REST_HEADS[bname]
            e.tail = (h[0], h[1], h[2] + 0.1)
        made[bname] = e
    for bname in ORDER:
        if PARENTS[bname] is not None:
            made[bname].parent = made[PARENTS[bname]]
            made[bname].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in obj.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return obj


def _conj_basis_quat(obj, bname, angle_rad):
    """Armature-space X-axis rotation carried by the bone's basis: q =
    rest^-1 @ R @ rest (the rest-conjugate trick — rotation about the bone
    head along the WORLD X axis regardless of the bone's roll convention)."""
    rest = obj.data.bones[bname].matrix_local.to_3x3()
    rot = rest.inverted() @ Matrix.Rotation(angle_rad, 3, "X") @ rest
    return rot.to_quaternion()


def leg_angles(frame):
    """(l_thigh_deg, l_knee_deg, r_thigh_deg, r_knee_deg) at a 1-based frame.

    Left stance 1..12 / swing 13..24 (cycle repeats; f49 wraps to the f1
    stance-start pose); Right runs the OPPOSITE phase — it swings while the
    left stands. All transitions are C1 (each phase's t runs 0..1 with
    matching end angles), so no per-frame angular jumps.
    """
    f = (frame - 1) % (2 * STANCE) + 1  # 1..24 within the cycle
    if f <= STANCE:  # left stance / right swing
        l_thigh = SWEEP_DEG - 2.0 * SWEEP_DEG * ((f - 1) / (STANCE - 1))
        l_knee = 0.0
        t_sw = f / STANCE
        r_thigh = -SWEEP_DEG + 2.0 * SWEEP_DEG * t_sw
        r_knee = KNEE_DEG * math.sin(math.pi * t_sw)
    else:  # left swing / right stance
        t_sw = (f - STANCE) / STANCE
        l_thigh = -SWEEP_DEG + 2.0 * SWEEP_DEG * t_sw
        l_knee = KNEE_DEG * math.sin(math.pi * t_sw)
        r_thigh = SWEEP_DEG - 2.0 * SWEEP_DEG * ((f - STANCE - 1) / (STANCE - 1))
        r_knee = 0.0
    return l_thigh, l_knee, r_thigh, r_knee


def key_walk(obj):
    """Key the sliding walk: per-frame quaternion keys on the 6 leg bones
    (rigid stance arc + flexing swing knee; hands/arms/toes ride their
    parents). Hips location is a constant channel (explicit no root motion)."""
    scene = bpy.context.scene  # type: ignore[name-defined]
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, N_FRAMES
    ad = obj.animation_data_create()
    ad.action = bpy.data.actions.new("rm_motion_fixture_walk")  # type: ignore[name-defined]
    for side in ("Left", "Right"):
        for seg in LEGS:
            pb = obj.pose.bones[f"{side}{seg}"]
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pb.keyframe_insert("rotation_quaternion", frame=1)
    hips = obj.pose.bones["Hips"]
    hips.location = (0.0, 0.0, 0.0)
    hips.keyframe_insert("location", frame=1)
    for pb in (obj.pose.bones["LeftArm"], obj.pose.bones["RightArm"]):
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.keyframe_insert("rotation_quaternion", frame=1)
    for frame in range(1, N_FRAMES + 1):
        thigh_l, knee_l, thigh_r, knee_r = leg_angles(frame)
        for side, thigh, knee in (("Left", thigh_l, knee_l), ("Right", thigh_r, knee_r)):
            # keys are JOINT angles (each bone's basis rotates it about its
            # OWN head in the parent-posed frame — measured on the first
            # build): stance knee 0 keeps the leg RIGID about the hip (the
            # slide arc); the swing knee flexion lifts the foot
            for seg, deg in (("UpLeg", thigh), ("Leg", knee), ("Foot", knee)):
                bname = f"{side}{seg}"
                pb = obj.pose.bones[bname]
                pb.rotation_quaternion = _conj_basis_quat(obj, bname, math.radians(deg))
                pb.keyframe_insert("rotation_quaternion", frame=frame)
    scene.frame_set(1)
    bpy.context.view_layer.update()  # type: ignore[name-defined]


def export_bvh(obj, path):
    bpy.context.view_layer.objects.active = obj  # type: ignore[name-defined]
    obj.select_set(True)
    # the 5.1 BVH exporter has NO axis params (writes Blender world axes
    # as-is) — the importer side must pin axis_forward='Y', axis_up='Z'
    # (the measured contract, xtask/motion_probe.py)
    return bpy.ops.export_anim.bvh(  # type: ignore[name-defined]
        filepath=str(path), frame_start=1, frame_end=N_FRAMES, rotate_mode="XYZ"
    )


def export_fbx(obj, path):
    bpy.context.view_layer.objects.active = obj  # type: ignore[name-defined]
    obj.select_set(True)
    return bpy.ops.export_scene.fbx(  # type: ignore[name-defined]
        filepath=str(path), add_leaf_bones=False
    )


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2:
        print(
            "usage: motion_fixture.py <out.bvh> <out.fbx>",
            file=sys.stderr,
        )
        return 64
    bvh_path, fbx_path = Path(argv[0]), Path(argv[1])
    # factory-EMPTY scene (the probe's wipe_scene pattern): the default
    # startup light would ride the FBX export and Blender 5.1.0's bundled
    # FBX importer then CRASHES on it (lamp.cycles.cast_shadow is gone
    # upstream — a fixture scene carries only the armature)
    bpy.ops.wm.read_factory_settings(use_empty=True)  # type: ignore[name-defined]
    obj = build_humanoid("rm_motion_fixture")
    key_walk(obj)
    r1 = export_bvh(obj, bvh_path)
    r2 = export_fbx(obj, fbx_path)
    ok = "FINISHED" in r1 and "FINISHED" in r2 and bvh_path.is_file() and fbx_path.is_file()
    print(
        f"RM_MOTIONFIX BUILD: {'PASS' if ok else 'FAIL'} bones={len(obj.data.bones)} "
        f"frames={N_FRAMES} fps={FPS} bvh={bvh_path} fbx={fbx_path} "
        f"(SYNTHETIC sliding-walk fixture — stance sweep ±{SWEEP_DEG:g} deg, "
        f"swing knee {KNEE_DEG:g} deg)"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    import bpy  # type: ignore[name-defined]

    sys.exit(main())
