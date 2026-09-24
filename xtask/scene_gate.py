"""P8-1 scene gate probe (run INSIDE Blender, headless) — the RM_SCENE rows.

Uses the REAL gate assets (the multi-figure payload the gate generates from
the benchmark image with real models) and the REAL add-on machinery:

1. CASTING — core casting-validation refusals fire (uncast, double-cast,
   unknown armature) before any pose is written.
2. APPLY2 — the session executor's apply_scene action drives ONE payload
   into TWO rigs in one action; every mapped bone re-measured vs the
   canonical targets per figure (bar: the 0.5 deg family).
3. V2-BACKCOMPAT — the same content shaped as a format-2 payload dict
   applies byte-identical pose-bone rotations through the v3 code (the
   additive-contract pin; the file-IO half of the session action is already
   covered by APPLY2, so this row isolates the FORMAT difference).
4. CAMERA-REFUSE — staging from a single-figure casting against the
   two-figure reference framing measures below the 0.75 floor and stages
   NOTHING (no camera object left in the scene).
5. CAMERA-STAGE — the full two-figure casting clears the floor; the staged
   camera carries rm_camera_v0 = "APPROXIMATE" + the measured IoU.

Usage: blender -b --python xtask/scene_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR, RM_SCENE_MULTI (payload path).
Prints RM_SCENE lines; exit 0 only if every row PASSes.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["RM_CORE_SRC"])
sys.path.insert(0, os.environ["RM_ADDON_DIR"])

import bpy  # noqa: E402
import riggermortis as core  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402
from riggermortis_addon import scene_apply, scene_camera  # noqa: E402
from riggermortis_addon import session as rm_session  # noqa: E402

TOL_DEG = 0.5
FLOOR = scene_camera.CAMERA_IOU_FLOOR

OK = True


def env_path(name: str) -> Path:
    """Resolve a REQUIRED env path to an existing file (validated, absolute)."""
    raw = os.environ.get(name, "")
    if not raw:
        raise SystemExit(f"RM_SCENE GATE: FAIL ({name} not set)")
    path = Path(raw).resolve()
    if not path.is_file():
        raise SystemExit(f"RM_SCENE GATE: FAIL ({name} not a file: {raw!r})")
    return path


def check(label: str, ok: bool, detail: str = "") -> None:
    global OK
    if not ok:
        OK = False
    print(f"RM_SCENE {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")


def build_rig(name: str, x_off: float, z_rot_deg: float, scale: float):
    """Canonical-layout rig with role props (the probe/gate rig family)."""
    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.mode_set(mode="EDIT")
    bones = obj.data.edit_bones
    bones.remove(bones[0])

    def add(bn, parent, head, tail):
        b = bones.new(bn)
        b.head, b.tail = head, tail
        b.parent = bones[parent] if parent else None

    add("pelvis", None, (0, 0, 0.98), (0, 0, 1.06))
    add("spine", "pelvis", (0, 0, 1.06), (0, 0, 1.22))
    add("spine.001", "spine", (0, 0, 1.22), (0, 0, 1.40))
    add("neck", "spine.001", (0, 0, 1.40), (0, 0, 1.50))
    add("head", "neck", (0, 0, 1.50), (0, 0, 1.70))
    add("shoulder.L", "spine.001", (0.03, 0, 1.44), (0.14, 0, 1.46))
    add("upper_arm.L", "shoulder.L", (0.16, 0, 1.45), (0.46, 0, 1.45))
    add("forearm.L", "upper_arm.L", (0.46, 0, 1.45), (0.72, 0, 1.45))
    add("hand.L", "forearm.L", (0.72, 0, 1.45), (0.82, 0, 1.45))
    add("shoulder.R", "spine.001", (-0.03, 0, 1.44), (-0.14, 0, 1.46))
    add("upper_arm.R", "shoulder.R", (-0.16, 0, 1.45), (-0.46, 0, 1.45))
    add("forearm.R", "upper_arm.R", (-0.46, 0, 1.45), (-0.72, 0, 1.45))
    add("hand.R", "forearm.R", (-0.72, 0, 1.45), (-0.82, 0, 1.45))
    add("thigh.L", "pelvis", (0.09, 0, 0.98), (0.09, 0, 0.52))
    add("shin.L", "thigh.L", (0.09, 0, 0.52), (0.09, 0, 0.10))
    add("foot.L", "shin.L", (0.09, 0, 0.10), (0.09, -0.14, 0.02))
    add("thigh.R", "pelvis", (-0.09, 0, 0.98), (-0.09, 0, 0.52))
    add("shin.R", "thigh.R", (-0.09, 0, 0.52), (-0.09, 0, 0.10))
    add("foot.R", "shin.R", (-0.09, 0, 0.10), (-0.09, -0.14, 0.02))
    bpy.ops.object.mode_set(mode="OBJECT")

    obj.location = (x_off, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, math.radians(z_rot_deg))
    obj.scale = (scale, scale, scale)
    role_of = {
        "pelvis": "hips", "spine": "spine", "spine.001": "chest", "neck": "neck",
        "head": "head",
        "shoulder.L": "shoulder.L", "upper_arm.L": "upper_arm.L",
        "forearm.L": "forearm.L", "hand.L": "hand.L",
        "shoulder.R": "shoulder.R", "upper_arm.R": "upper_arm.R",
        "forearm.R": "forearm.R", "hand.R": "hand.R",
        "thigh.L": "upper_leg.L", "shin.L": "lower_leg.L", "foot.L": "foot.L",
        "thigh.R": "upper_leg.R", "shin.R": "lower_leg.R", "foot.R": "foot.R",
    }
    for bone, role in sorted(role_of.items()):
        obj[f"rm_role_{role}"] = bone
    return obj


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def armature(name: str):
    return bpy.data.objects[name]


def all_quats() -> dict:
    out = {}
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        for pb in obj.pose.bones:
            aa = pb.rotation_axis_angle
            out[f"{obj.name}/{pb.name}"] = tuple(Quaternion(aa[1:4], aa[0]))
    return out


def worst_fk_deg(obj, pose_dict: dict) -> tuple[float, str]:
    """Worst mapped-bone direction error vs the pose's canonical targets."""
    pose = core.CanonicalPose.from_dict(pose_dict)
    worst, worst_role = 0.0, ""
    for role in sorted(core.ALL_ROLES):
        target = core.bone_target_direction(pose, role)
        bone = obj.get(f"rm_role_{role}")
        if target is None or not bone:
            continue
        pb = obj.pose.bones.get(str(bone))
        if pb is None:
            continue
        d = pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))
        d.normalize()
        dot = max(-1.0, min(1.0, d.dot(Vector(target))))
        deg = math.degrees(math.acos(dot))
        if deg > worst:
            worst, worst_role = deg, role
    return worst, worst_role


def apply_scene_action(payload_path: Path, assignments: dict) -> dict:
    """The REAL session executor path (the apply_scene action, minus only
    the socket hop — which session-verify already covers generically)."""
    result = rm_session.execute_action({
        "kind": "apply_scene",
        "params": {
            "payload_path": str(payload_path),
            "assignments": assignments,
        },
    })
    if not result.get("ok"):
        raise RuntimeError(f"apply_scene executor error: {result.get('error')}")
    return result["report"]


def main() -> int:
    global OK
    multi = env_path("RM_SCENE_MULTI")
    with open(multi, encoding="utf-8") as fh:
        payload = json.load(fh)
    entries = [e for e in payload["figures"] if e.get("bbox")]
    if len(entries) < 2:
        print("RM_SCENE GATE: FAIL (multi-figure payload has <2 figures with bboxes)")
        return 1
    label_a, label_b = str(entries[0]["label"]), str(entries[1]["label"])

    # -- 1. CASTING refusals fire before any pose is written -------------------
    scene = core.scene_from_payload(payload)
    rigs = ["RM_RigA", "RM_RigB", "RM_RigC"]
    refused = 0
    cases = (
        ({label_a: "RM_RigA", "figure 99": "RM_RigA"}, "unknown figure"),
        ({label_a: "RM_RigA", label_b: "RM_RigA"}, "multiple figures"),
        ({label_a: "RM_RigX", label_b: "RM_RigB"}, "not in the scene"),
    )
    for i, (assignments, needle) in enumerate(cases):
        try:
            core.validate_casting(scene, assignments, rigs)
            check(f"CASTING-{i}", False, f"no refusal for {needle!r}")
        except core.SceneError as exc:
            if needle in str(exc):
                refused += 1
            else:
                check(f"CASTING-{i}", False, f"wrong refusal: {exc}")
    subset = core.validate_casting(scene, {label_a: "RM_RigA"}, rigs)
    subset_ok = list(subset) == [label_a]  # subset-casting is valid by design
    check("CASTING", refused == 3 and subset_ok,
          f"refusals={refused}/3 subset_ok={subset_ok}")

    # -- 2. APPLY2: the session executor's apply_scene, two rigs, one action ---
    fresh_scene()
    build_rig("RM_RigA", 0.0, 0.0, 1.0)
    build_rig("RM_RigB", 2.5, 12.0, 1.05)
    report = apply_scene_action(multi, {label_a: "RM_RigA", label_b: "RM_RigB"})
    bpy.context.view_layer.update()
    pose_by_label = {str(e["label"]): e["pose"] for e in entries}
    wa, ra = worst_fk_deg(armature("RM_RigA"), pose_by_label[label_a])
    wb, rb = worst_fk_deg(armature("RM_RigB"), pose_by_label[label_b])
    pins = report["pins"]
    check("APPLY2",
          wa <= TOL_DEG and wb <= TOL_DEG and report["figures_applied"] == 2,
          f"{label_a} {wa:.4f}deg ({ra}) {label_b} {wb:.4f}deg ({rb}) "
          f"pins={len(pins)} carried-not-enforced")

    # -- 3. V2-BACKCOMPAT: format-2 twin applies byte-identically --------------
    q_v3 = all_quats()
    fresh_scene()
    build_rig("RM_RigA", 0.0, 0.0, 1.0)
    build_rig("RM_RigB", 2.5, 12.0, 1.05)
    scene_apply.apply_scene_payload(
        {**payload, "format": 2},
        {label_a: "RM_RigA", label_b: "RM_RigB"}, core=core,
    )
    q_v2 = all_quats()
    same = q_v3 == q_v2 and len(q_v3) > 0
    check("V2-BACKCOMPAT", same, f"identical={q_v3 == q_v2} bones={len(q_v3)}")

    # -- 4. CAMERA rows: the scene layout must MATCH the reference's framing
    # (the honest real-world condition: the payload comes FROM the reference
    # being posed). Rig separation is derived from the POSED subject's measured
    # aspect so the union matches the reference bbox aspect; the render
    # resolution matches the reference aspect so fractions compare.
    fresh_scene()
    scene_cfg = bpy.context.scene
    scene_cfg.render.resolution_x = 1280
    scene_cfg.render.resolution_y = 720  # 16:9, the reference image's aspect
    build_rig("RM_RigA", 0.0, 0.0, 1.0)
    build_rig("RM_RigB", 3.0, 12.0, 1.05)
    apply_scene_action(multi, {label_a: "RM_RigA", label_b: "RM_RigB"})
    bpy.context.view_layer.update()
    bx0, by0, bx1, by1 = entries[0]["bbox"]
    cx0, cy0, cx1, cy1 = entries[1]["bbox"]
    ref_px_w = max(bx1, cx1) - min(bx0, cx0)
    ref_px_h = max(by1, cy1) - min(by0, cy0)
    rig_a = armature("RM_RigA")

    def _world_xz_span(obj) -> tuple[float, float]:
        from mathutils import Vector

        xs = [(obj.matrix_world @ Vector(pb.head)).x for pb in obj.pose.bones]
        zs = [(obj.matrix_world @ Vector(pb.head)).z for pb in obj.pose.bones]
        return max(xs) - min(xs), max(zs) - min(zs)

    w_one, h_posed = _world_xz_span(rig_a)
    ref_ar = ref_px_w / ref_px_h  # the reference union's world aspect target

    def _union_ar() -> float:
        xs, zs = [], []
        for name in ("RM_RigA", "RM_RigB"):
            obj = armature(name)
            for pb in obj.pose.bones:
                p = obj.matrix_world @ Vector(pb.head)
                xs.append(p.x)
                zs.append(p.z)
        return (max(xs) - min(xs)) / (max(zs) - min(zs)), (max(zs) - min(zs))

    # deterministic fixture construction: move the rigs until the posed union's
    # aspect matches the reference bbox aspect (an artist sliding rigs together)
    sep = h_posed * ref_ar - w_one
    for _ in range(6):
        rig_a.location.x = -sep / 2.0
        armature("RM_RigB").location.x = sep / 2.0
        bpy.context.view_layer.update()
        ar, _h = _union_ar()
        if abs(ar - ref_ar) < 0.02:
            break
        sep *= ref_ar / ar
    bpy.context.view_layer.update()

    # 4a. REFUSE: a reference framing that does not match this scene (the
    # single-figure payload's tall-narrow bbox) must not stage anything.
    single = env_path("RM_SCENE_SINGLE")
    with open(single, encoding="utf-8") as fh:
        payload_single = json.load(fh)
    refuse = scene_camera.stage_scene_camera(
        payload_single, {label_a: "RM_RigA"}, core=core,
    )
    left_no_camera = bpy.data.objects.get(scene_camera.CAMERA_NAME) is None
    check("CAMERA-REFUSE",
          not refuse["staged"] and refuse["iou"] < FLOOR and left_no_camera,
          f"iou={refuse['iou']:.4f} < floor={FLOOR} nothing_staged={left_no_camera}")

    # 4b. STAGE: the matching reference clears the floor; the camera carries
    # the APPROXIMATE label + the measured IoU.
    bpy.context.view_layer.update()
    staged = scene_camera.stage_scene_camera(
        payload, {label_a: "RM_RigA", label_b: "RM_RigB"}, core=core,
    )
    cam = bpy.data.objects.get(scene_camera.CAMERA_NAME)
    labeled = cam is not None and cam.get("rm_camera_v0") == "APPROXIMATE"
    is_scene_camera = bpy.context.scene.camera == cam
    check("CAMERA-STAGE",
          staged["staged"] and staged["iou"] >= FLOOR and labeled and is_scene_camera,
          f"iou={staged['iou']:.4f} floor={FLOOR} camera={staged.get('camera')} "
          f"approx_labeled={labeled} scene_camera={is_scene_camera} "
          f"ref={staged.get('reference_bbox')} got={staged.get('measured_bbox')}")

    print(f"RM_SCENE GATE: {'PASS' if OK else 'FAIL'}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
