"""P8-5 camera gate (run INSIDE Blender, headless) — the RM_CAM rows.

The sibling of scene_gate/couple_gate/finger_gate/face_gate (the Mimosa
new-file rule). Rows:

1. CAM-MODEL  — the declared composed yaw+pitch projection vs Blender's
                own world_to_camera_view over a yawed+pitched grid
                (err <= 1e-4): a sign flip dies HERE.
2. CAM-GT     — the tier-1 GT sweep re-run through the CORE solve inside
                Blender: the Annex bars (yaw 7.5 / pitch 5 / distance 12%).
3. CAM-STAGE  — the REAL addon staging path (camera_stage.
                stage_scene_camera_measured): canonical-exact fixture rig
                + a detector-shaped payload, the pose applied through the
                REAL apply, the camera staged, MEASURED-labeled, framing
                IoU >= the 0.75 floor, scene camera set.
4. CAM-REFUSE — a degraded payload through the same path refuses LOUD
                (below the confidence floor / pose-class) and stages
                NOTHING.
5. CAM-TWIN   — twin staging byte-identical (camera transforms + report).

Usage: blender -b --python xtask/camera_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR.
Prints RM_CAM lines; exit 0 only if every row PASSes.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.environ["RM_CORE_SRC"])
sys.path.insert(0, os.environ["RM_ADDON_DIR"])

import bpy  # noqa: E402
import riggermortis as core  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from riggermortis_addon import camera_stage, pose_apply  # noqa: E402

LENS_MM = 50.0
SENSOR_W_MM = 36.0
IMG_W, IMG_H = 640, 960

OK = True


def check(label: str, ok: bool, detail: str = "") -> None:
    global OK
    if not ok:
        OK = False
    print(f"RM_CAM {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")


def _project(points, cam, target, img_w=IMG_W, img_h=IMG_H):
    """The declared composed yaw+pitch pinhole model (docs/CAMERA.md)."""
    fw = [t - c for t, c in zip(target, cam, strict=True)]
    ln = math.sqrt(sum(v * v for v in fw))
    fw = [v / ln for v in fw]
    up_w = (0.0, 0.0, 1.0)
    # right = fw x up_w (the v0-pinned viewer-right = -X at the level
    # front; the up_w x fw order mirrors u — A10, caught by CAM-MODEL)
    right = (
        fw[1] * up_w[2] - fw[2] * up_w[1],
        fw[2] * up_w[0] - fw[0] * up_w[2],
        fw[0] * up_w[1] - fw[1] * up_w[0],
    )
    rl = math.sqrt(sum(v * v for v in right))
    right = [v / rl for v in right]
    # up = right x fw (screen-up = world +Z at the level front, v0-pinned)
    up_c = (
        right[1] * fw[2] - right[2] * fw[1],
        right[2] * fw[0] - right[0] * fw[2],
        right[0] * fw[1] - right[1] * fw[0],
    )
    # AUTO fit, GENERAL (A11): the sensor's LONG edge fits the render's
    # LONG side — landscape: 36 x (36*h/w); portrait: (36*w/h) x 36
    if img_w >= img_h:
        sw = SENSOR_W_MM
        sh = SENSOR_W_MM * img_h / img_w
    else:
        sw = SENSOR_W_MM * img_w / img_h
        sh = SENSOR_W_MM
    out = []
    for p in points:
        rel = [p[i] - cam[i] for i in range(3)]
        d = sum(rel[i] * fw[i] for i in range(3))
        ru = sum(rel[i] * right[i] for i in range(3))
        rv = sum(rel[i] * up_c[i] for i in range(3))
        # A10: `right` IS the screen-right axis -> plus sign
        out.append((0.5 + ru / d * LENS_MM / sw,
                    0.5 + rv / d * LENS_MM / sh))
    return out


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def build_rig(name: str):
    """Canonical-layout rig with role props (TWO-PASS: create every bone,
    then wire parents — the S27 fixture law)."""
    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.mode_set(mode="EDIT")
    bones = obj.data.edit_bones
    bones.remove(bones[0])

    def add(bn, parent, head, tail):
        b = bones.new(bn)
        b.head, b.tail = head, tail
        created[bn] = b

    created: dict = {}
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
    for bn, par in (
        ("spine", "pelvis"), ("spine.001", "spine"), ("neck", "spine.001"),
        ("head", "neck"),
        ("shoulder.L", "spine.001"), ("upper_arm.L", "shoulder.L"),
        ("forearm.L", "upper_arm.L"), ("hand.L", "forearm.L"),
        ("shoulder.R", "spine.001"), ("upper_arm.R", "shoulder.R"),
        ("forearm.R", "upper_arm.R"), ("hand.R", "forearm.R"),
        ("thigh.L", "pelvis"), ("shin.L", "thigh.L"), ("foot.L", "shin.L"),
        ("thigh.R", "pelvis"), ("shin.R", "thigh.R"), ("foot.R", "shin.R"),
    ):
        created[bn].parent = created[par]
    bpy.ops.object.mode_set(mode="OBJECT")
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


def gt_payload(yaw_deg: float, dist: float, elev: float):
    """A detector-shaped v3 payload from the projected rest fixture: the
    REAL observations+pose solve feed the pose dict, exactly what the CLI
    would write for such a detection."""
    from riggermortis.canonical import rest_skeleton
    from riggermortis.canonical_pose import (
        observations_from_keypoints,
        solve_pose,
    )
    from riggermortis.inference.poses import (
        ANKLE_L,
        ANKLE_R,
        BIG_TOE_L,
        BIG_TOE_R,
        ELBOW_L,
        ELBOW_R,
        HIP_L,
        HIP_R,
        KEYPOINT_COUNT,
        KNEE_L,
        KNEE_R,
        NOSE,
        SHOULDER_L,
        SHOULDER_R,
        WRIST_L,
        WRIST_R,
    )

    rest = rest_skeleton(2.0, hip_height_frac=0.5)
    pts = {r: tuple(float(v) for v in hv[0]) for r, hv in rest.items()}
    keep = (
        "hips", "spine", "chest", "neck", "head",
        "shoulder.L", "upper_arm.L", "forearm.L", "hand.L",
        "shoulder.R", "upper_arm.R", "forearm.R", "hand.R",
        "upper_leg.L", "lower_leg.L", "foot.L", "toe.L",
        "upper_leg.R", "lower_leg.R", "foot.R", "toe.R",
    )
    pts = {r: pts[r] for r in keep}
    zs = [p[2] for p in pts.values()]
    target = (0.0, 0.0, (max(zs) + min(zs)) / 2.0)
    y = math.radians(yaw_deg)
    cam = (
        target[0] - dist * math.sin(y),
        target[1] - dist * math.cos(y),
        target[2] + elev,
    )
    kp_map = {
        NOSE: "head", SHOULDER_L: "upper_arm.L", SHOULDER_R: "upper_arm.R",
        ELBOW_L: "forearm.L", ELBOW_R: "forearm.R", WRIST_L: "hand.L",
        WRIST_R: "hand.R", HIP_L: "upper_leg.L", HIP_R: "upper_leg.R",
        KNEE_L: "lower_leg.L", KNEE_R: "lower_leg.R", ANKLE_L: "foot.L",
        ANKLE_R: "foot.R", BIG_TOE_L: "toe.L", BIG_TOE_R: "toe.R",
    }
    roles = sorted(set(kp_map.values()))
    world = [pts[r] for r in roles] + [
        (pts["head"][0], pts["head"][1] - 0.10, pts["head"][2])
    ]
    proj = _project(world, cam, target)
    kps = [(0.0, 0.0)] * KEYPOINT_COUNT
    # map roles back through the FIRST kp index of each role
    role_idx: dict[str, int] = {}
    for idx, role in kp_map.items():
        role_idx.setdefault(role, idx)
    for i, r in enumerate(roles):
        u, v = proj[i]
        kps[role_idx[r]] = (u * IMG_W, (1.0 - v) * IMG_H)
    # the nose kp carries the declared forward offset (the yaw signal)
    u, v = proj[-1]
    kps[NOSE] = (u * IMG_W, (1.0 - v) * IMG_H)
    confs = [1.0 if kps[i] != (0.0, 0.0) else 0.0 for i in range(KEYPOINT_COUNT)]
    obs = observations_from_keypoints(kps, confs)
    pose = solve_pose(obs)
    px = [kps[i] for i in range(KEYPOINT_COUNT) if confs[i] > 0.0]
    bbox = [
        min(p[0] for p in px), min(p[1] for p in px),
        max(p[0] for p in px), max(p[1] for p in px),
    ]
    return {
        "format": 3,
        "name": f"cam_gt_y{int(yaw_deg)}",
        "image": {"path": "synthetic", "width": IMG_W, "height": IMG_H},
        "figures": [
            {"label": "A", "bbox": bbox, "score": 0.99, "pose": pose.to_dict()}
        ],
        "pins": [],
    }, cam, target, pts



def _aim_quat(location: Vector, target: Vector):
    """The camera rotation FROM THE MODEL BASIS (docs/CAMERA.md): screen
    right = fw x world-up, screen-up = right x fw — the v0-pinned
    convention, no track_quat ambiguity (CAM-MODEL proves the match)."""
    fw = (target - location).normalized()
    right = fw.cross(Vector((0.0, 0.0, 1.0))).normalized()
    up = right.cross(fw).normalized()
    m = Matrix((right, up, -fw)).transposed()
    return m.to_quaternion()


def main() -> int:
    fresh_scene()

    # 1. CAM-MODEL — the composed projection vs Blender, yawed+pitched grid.
    from riggermortis.canonical import rest_skeleton

    rest = rest_skeleton(2.0, hip_height_frac=0.5)
    pts = [tuple(float(v) for v in hv[0]) for r, hv in sorted(rest.items())]
    target = (0.0, 0.0, 0.8)
    cam_data = bpy.data.cameras.new("rm_model_cam")
    cam_data.lens = LENS_MM
    cam_data.sensor_width = SENSOR_W_MM
    cam = bpy.data.objects.new("rm_model_cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    bpy.context.scene.render.resolution_x = IMG_W
    bpy.context.scene.render.resolution_y = IMG_H
    err_max = 0.0
    for yaw in (-40.0, 0.0, 40.0):
        for elev in (-1.0, 0.0, 1.0):
            y = math.radians(yaw)
            loc = Vector((
                -4.0 * math.sin(y), -4.0 * math.cos(y), target[2] + elev,
            ))
            cam.location = loc
            cam.rotation_mode = "QUATERNION"
            cam.rotation_quaternion = _aim_quat(loc, Vector(target))
            bpy.context.view_layer.update()
            mine = _project(pts, tuple(loc), target, IMG_W, IMG_H)
            for p, (u, v) in zip(pts, mine, strict=True):
                co = bpy_extras_object_utils_world_to_camera_view(p)
                err_max = max(err_max, abs(co.x - u), abs(co.y - v))
    check(
        "CAM-MODEL", err_max <= 1e-4,
        f"composed model vs world_to_camera_view max err {err_max:.2e} "
        f"(bar 1e-4) over 9 yawed+pitched cameras (a sign flip dies here)",
    )

    # 2. CAM-GT — the tier-1 sweep through the CORE solve, the Annex bars.
    yaw_errs, pit_errs, dist_errs = [], [], []
    for yaw_gt in (-40.0, -20.0, 0.0, 20.0, 40.0):
        for dist in (2.6, 4.0, 6.0):
            for elev in (-1.0, -0.35, 0.0, 0.35, 1.0):
                payload, _cam, _t, _pts = gt_payload(yaw_gt, dist, elev)
                pose_d = payload["figures"][0]["pose"]
                res = core.solve_camera_figure(
                    {r: tuple(p) for r, p in pose_d["positions"].items()},
                    {r: float(c) for r, c in pose_d["joint_confidence"].items()},
                    float(pose_d["scale"]),
                    tuple(float(v) for v in payload["figures"][0]["bbox"]),
                    IMG_W, IMG_H,
                )
                assert res.ok, (yaw_gt, dist, elev, res.reason)
                yaw_errs.append(abs(res.yaw_deg - yaw_gt))
                pit_errs.append(abs(res.pitch_deg - math.degrees(math.atan2(-elev, dist))))
                dist_errs.append(abs(res.distance / dist - 1.0))
    mae = lambda v: sum(v) / len(v)  # noqa: E731
    check(
        "CAM-GT",
        mae(yaw_errs) <= 7.5 and mae(pit_errs) <= 5.0 and mae(dist_errs) <= 0.12,
        f"n={len(yaw_errs)} [SYNTHETIC, prior-consistent GT]: yaw MAE "
        f"{mae(yaw_errs):.2f} (bar 7.5), pitch MAE {mae(pit_errs):.2f} "
        f"(bar 5), distance MAE {mae(dist_errs) * 100:.2f}% (bar 12)",
    )

    # 3. CAM-STAGE — the REAL addon staging path.
    fresh_scene()
    rig = build_rig("rig_a")
    payload, gt_cam, gt_target, _fix = gt_payload(20.0, 4.0, 0.5)
    report_apply = pose_apply.apply_payload(rig, payload, figure="A")
    assert report_apply.get("applied"), report_apply
    report = camera_stage.stage_scene_camera_measured(payload, {"A": "rig_a"})
    staged_ok = (
        report.get("staged")
        and report.get("mode") == "MEASURED"
        and float(report.get("iou", 0.0)) >= 0.75
        and bpy.context.scene.camera is not None
        and bpy.data.objects.get("rm_scene_camera") is not None
        and bpy.data.objects["rm_scene_camera"].get("rm_camera_solve") == "MEASURED"
    )
    check(
        "CAM-STAGE", staged_ok,
        f"staged MEASURED (yaw {report['params']['yaw_deg']:.2f} pitch "
        f"{report['params']['pitch_deg']:.2f} dist "
        f"{report['params']['distance']:.3f}) IoU {report['iou']:.4f} >= 0.75, "
        f"conf {report['confidence']:.2f}, scene camera set, props stamped",
    )

    # 4. CAM-REFUSE — a degraded payload refuses LOUD, stages nothing.
    fresh_scene()
    build_rig("rig_b")
    payload_ok, _c, _t, _p = gt_payload(0.0, 4.0, 0.0)
    starved = json_deep_copy(payload_ok)
    pose_d = starved["figures"][0]["pose"]
    pose_d["joint_confidence"]["upper_arm.R"] = 0.3
    report_ref = camera_stage.stage_scene_camera_measured(starved, {"A": "rig_b"})
    no_camera = bpy.data.objects.get("rm_scene_camera") is None
    ref_ok = (
        not report_ref.get("staged")
        and bool(report_ref.get("reason"))
        and no_camera
    )
    check(
        "CAM-REFUSE", ref_ok,
        f"degraded payload refused loud: '{str(report_ref.get('reason'))[:70]}' "
        "— no camera object left in the scene",
    )

    # 5. CAM-TWIN — twin staging byte-identical.
    fresh_scene()
    rig3 = build_rig("rig_c")
    payload_t, _c, _t, _p = gt_payload(-15.0, 3.5, 0.0)
    pose_apply.apply_payload(rig3, payload_t, figure="A")
    rep_a = camera_stage.stage_scene_camera_measured(payload_t, {"A": "rig_c"})
    loc_a = tuple(bpy.data.objects["rm_scene_camera"].location) if rep_a.get("staged") else None
    fresh_scene()
    rig4 = build_rig("rig_c")
    pose_apply.apply_payload(rig4, payload_t, figure="A")
    rep_b = camera_stage.stage_scene_camera_measured(payload_t, {"A": "rig_c"})
    cam_b = bpy.data.objects.get("rm_scene_camera")
    loc_b = tuple(cam_b.location) if cam_b else None
    twin_ok = (
        rep_a.get("staged") and rep_b.get("staged")
        and rep_a.get("iou") == rep_b.get("iou")
        and rep_a.get("params") == rep_b.get("params")
        and loc_a is not None and loc_a == loc_b
    )
    check(
        "CAM-TWIN", twin_ok,
        f"twin staging byte-identical (iou {rep_a.get('iou')}=="
        f"{rep_b.get('iou')}, params equal, camera location equal)",
    )

    passed = OK
    print(f"RM_CAM GATE: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def bpy_extras_object_utils_world_to_camera_view(point):
    from bpy_extras.object_utils import world_to_camera_view

    scene = bpy.context.scene
    return world_to_camera_view(scene, scene.camera, Vector(point))


def _rest_pts():
    from riggermortis.canonical import rest_skeleton

    rest = rest_skeleton(2.0, hip_height_frac=0.5)
    return {r: tuple(float(v) for v in hv[0]) for r, hv in rest.items()}


def json_deep_copy(obj):
    import json

    return json.loads(json.dumps(obj))


if __name__ == "__main__":
    raise SystemExit(main())
