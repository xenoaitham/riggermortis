"""P8-1 capability probe: the Blender-side unknowns for scenes + camera v0.

The design page (docs/SCENES.md) commits to a build only after these are
answered by DOING them in THIS Blender, headless:

1. MULTI-RIG-RECOMPUTE — ONE multi-figure payload drives TWO different
   armatures in one scene through the real ``apply_payload`` recompute path
   (D-009); per-figure FK fidelity vs the canonical targets (bar: the 0.5
   deg family). Confirms no shared-state leak between applies.
2. ORDER-AND-CLEANUP — A-then-B vs B-then-A lands identical pose-bone
   rotations (exact float equality); a second full apply is idempotent;
   clearing one rig leaves the other untouched.
3. CAMERA-MECHANICS — ``world_to_camera_view`` works headless and matches
   hand-derived pinhole coordinates (bar 1e-4); the frame-convention y-flip
   (detector image v-down vs projection v-up) is pinned; the candidate v0
   solver (front prior, closed-form distance/center from the reference
   bbox) stages a camera whose measured subject-bbox IoU vs the reference
   clears the 0.75 floor on a NON-trivial reference (hand camera yawed off
   front, different lens); degraded cameras (distance x1.5, single-figure
   framing) measure strictly worse — the floor separates the classes;
   the solve is deterministic (two runs identical).

Prints RM_SCENE lines; exit 0 only if every answer is yes.
Usage: blender -b --python xtask/scene_probe.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "core" / "src"))
sys.path.insert(0, str(REPO / "addon"))

import bpy  # noqa: E402 — probe runs inside Blender
import riggermortis as core  # noqa: E402
from mathutils import Vector  # noqa: E402
from riggermortis.canonical import rest_skeleton  # noqa: E402
from riggermortis.payload import build_pose_payload  # noqa: E402

FK_BAR_DEG = 0.5
PROJ_BAR = 1e-4
IOU_FLOOR = 0.75  # Annex A.1 — the same floor the v0 button will gate on
RES_X, RES_Y = 640, 480
LENS_MM = 50.0
SENSOR_MM = 36.0

OK = True


def check(label: str, ok: bool, detail: str = "") -> bool:
    global OK
    if not ok:
        OK = False
    print(f"RM_SCENE {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


# --- synthetic scene ----------------------------------------------------------

def build_rig(name: str, x_off: float, z_rot_deg: float, scale: float) -> bpy.types.Object:
    """A canonical-layout armature (the session-gate rig family), offset,
    turned, and scaled — DIFFERENT world placement per figure, same role
    names so ``rm_role_*`` props map it without the live mapper."""

    bpy.ops.object.armature_add(location=(0, 0, 0))
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.mode_set(mode="EDIT")
    bones = obj.data.edit_bones
    bones.remove(bones[0])

    def add(bn: str, parent: str, head: tuple[float, float, float],
            tail: tuple[float, float, float]) -> None:
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
    # role props (the mapped path the apply uses; no live-map fallback needed)
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
    bpy.context.view_layer.update()
    return obj


def author_pose(kind: str) -> core.CanonicalPose:
    """A hand-authored canonical pose (positions only carry the FK solve).

    kind 'stand': near-rest, arms lowered. kind 'crouch': hips dropped,
    one arm raised — the two figures must be VISIBLY different so a
    mis-assignment cannot pass the FK re-measure.
    """
    rest = rest_skeleton(1.0)
    pos = {r: tuple(v[0]) for r, v in rest.items()}
    flips = {"forearm.L": -1, "forearm.R": -1, "lower_leg.L": 1, "lower_leg.R": 1}
    if kind == "stand":
        for side in ("L", "R"):
            sx = 1.0 if side == "L" else -1.0
            pos[f"upper_arm.{side}"] = (sx * 0.28, 0.0, rest["chest"][0][2] - 0.02)
            pos[f"forearm.{side}"] = (sx * 0.30, -0.05, pos[f"upper_arm.{side}"][2] - 0.30)
            pos[f"hand.{side}"] = (sx * 0.31, -0.08, pos[f"forearm.{side}"][2] - 0.26)
    elif kind == "crouch":
        pos["hips"] = (0.0, 0.0, 0.55)
        pos["upper_leg.L"] = (0.10, -0.22, 0.52)
        pos["lower_leg.L"] = (0.10, -0.30, 0.24)
        pos["foot.L"] = (0.10, -0.44, 0.05)
        pos["upper_leg.R"] = (-0.10, 0.10, 0.52)
        pos["lower_leg.R"] = (-0.10, -0.02, 0.22)
        pos["foot.R"] = (-0.10, -0.16, 0.04)
        drop = 0.55 - 0.935  # hips drop vs the rest height (0.55 hip band)
        for r in ("spine", "chest", "neck", "head"):
            pos[r] = (pos[r][0], pos[r][1], pos[r][2] + drop)
        pos["upper_arm.L"] = (0.22, -0.10, pos["chest"][2] + 0.16)
        pos["forearm.L"] = (0.26, -0.22, pos["upper_arm.L"][2] + 0.26)
        pos["hand.L"] = (0.28, -0.30, pos["forearm.L"][2] + 0.24)
        pos["upper_arm.R"] = (-0.28, 0.0, pos["chest"][2] - 0.02)
        pos["forearm.R"] = (-0.30, -0.05, pos["upper_arm.R"][2] - 0.30)
        pos["hand.R"] = (-0.31, -0.08, pos["forearm.R"][2] - 0.26)
    else:
        raise ValueError(kind)
    return core.CanonicalPose(
        positions=pos, flips=flips, confidence=0.9, reliable=True, scale=1.0,
        anchor="hips", notes=[f"scene_probe authored pose {kind}"],
        joint_confidence={r: 0.9 for r in pos},
    )


def build_two_figure_payload() -> dict:
    """Contract-shaped v2 multi-figure payload (rotations computed against
    rig A's data — the addon recompute path never reads them, matching the
    real --all-figures flow)."""
    pose_a, pose_b = author_pose("stand"), author_pose("crouch")
    bones: dict = {}
    for bn, pr, h, t in [
        ("pelvis", None, (0, 0, 0.98), (0, 0, 1.06)),
        ("spine", "pelvis", (0, 0, 1.06), (0, 0, 1.22)),
        ("spine.001", "spine", (0, 0, 1.22), (0, 0, 1.40)),
        ("neck", "spine.001", (0, 0, 1.40), (0, 0, 1.50)),
        ("head", "neck", (0, 0, 1.50), (0, 0, 1.70)),
    ]:
        bones[bn] = core.BoneData(name=bn, parent=pr, head=h, tail=t)
    rig = core.RigData(name="probe", bones=bones)
    mapping = core.map_rig(rig)
    entries = []
    for label, pose in (("figure A", pose_a), ("figure B", pose_b)):
        app = core.apply_canonical_pose(rig, mapping, pose)
        entries.append({
            "figure": {"label": label, "index": len(entries), "score": 0.9,
                       "bbox": [10.0, 20.0, 300.0, 460.0]},
            "pose": pose.to_dict(),
            "rotations": [
                {"bone": r.bone, "axis": list(r.axis), "angle_rad": r.angle_rad}
                for r in app.rotations
            ],
            "skipped": list(app.skipped),
            "notes": list(app.notes),
        })
    return build_pose_payload(
        Path("/tmp/scene_probe_reference.png"), RES_X, RES_Y, rig, entries,
        "figure A",
    )


# --- apply + re-eval instrument (the RM_BAKE pattern, static) ------------------

def apply_via_pose_apply(obj, payload: dict, label: str) -> dict:
    """The REAL add-on apply path (the same function the Apply Pose operator
    and the session executor call)."""
    from riggermortis_addon import pose_apply

    return pose_apply.apply_payload(obj, payload, mirror=False, figure=label)


def worst_fk_deg(obj, pose: core.CanonicalPose) -> tuple[float, str]:
    """Worst angle between each mapped pose bone's Y and its canonical target."""
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


def scene_quats() -> dict[str, tuple[float, ...]]:
    """Every pose bone's rotation quaternion, for byte-exact comparisons."""
    out: dict[str, tuple[float, ...]] = {}
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        for pb in obj.pose.bones:
            q = pb.rotation_quaternion if pb.rotation_mode == "QUATERNION" else None
            if q is None:
                aa = pb.rotation_axis_angle
                q = __import__("mathutils").Quaternion(aa[1:4], aa[0])
            out[f"{obj.name}/{pb.name}"] = tuple(q)
    return out


def fresh_scene() -> tuple:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    rig_a = build_rig("RM_RigA", 0.0, 0.0, 1.0)
    rig_b = build_rig("RM_RigB", 2.5, 12.0, 1.05)
    return scene, rig_a, rig_b


# --- camera mechanics -----------------------------------------------------------

def subject_points() -> list[Vector]:
    """World-space posed joint heads across every armature (the subject)."""
    pts: list[Vector] = []
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        for pb in obj.pose.bones:
            pts.append(obj.matrix_world @ Vector(pb.head))
    return pts


def add_camera(name: str, loc: tuple[float, float, float],
               rot_deg: tuple[float, float, float], lens: float):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_data.sensor_width = SENSOR_MM
    cam = bpy.data.objects.new(name, cam_data)
    cam.location = loc
    cam.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    bpy.context.scene.collection.objects.link(cam)
    return cam


def project_bbox(cam, pts: list[Vector]) -> tuple[float, float, float, float]:
    """Frame-space (normalized, y-UP world_to_camera_view convention) bbox."""
    from bpy_extras.object_utils import world_to_camera_view

    scene = bpy.context.scene
    xs, ys = [], []
    for p in pts:
        co = world_to_camera_view(scene, cam, p)
        xs.append(co.x)
        ys.append(co.y)
    return min(xs), min(ys), max(xs), max(ys)


def iou(a: tuple[float, float, float, float],
        b: tuple[float, float, float, float]) -> float:
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0.0 or iy <= 0.0:
        return 0.0
    inter = ix * iy
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def bbox_to_ref(ref_bbox_px: tuple[float, float, float, float],
                img_w: int, img_h: int) -> tuple[float, float, float, float]:
    """Detector pixel bbox (v-down) -> normalized frame coords (v-up)."""
    x0, y0, x1, y1 = ref_bbox_px
    return (x0 / img_w, 1.0 - y1 / img_h, x1 / img_w, 1.0 - y0 / img_h)


def solve_v0_camera(pts: list[Vector], ref: tuple[float, float, float, float]):
    """The candidate v0 solver (docs/SCENES.md § Camera v0): front prior
    (camera on +Y looking -Y), 50 mm, closed-form distance from the width
    fraction + center match. Returns (loc, rot_deg) for the staged camera.

    Projection model (PINNED by CAMERA-PINHOLE, measured against
    world_to_camera_view in THIS Blender): for a level camera looking down
    -Y, a point at view depth d = cam_y - py projects to
      u = 0.5 - (px - cam_x)/d * f/sensor_w        (viewer-right = -X)
      v = 0.5 + (pz - cam_z)/d * f/sensor_h        (v-up convention)
    with sensor_h = sensor_w * res_y/res_x (AUTO fit, landscape). NOTE the
    full-sensor denominators: the first draft used f/(sensor/2) and landed
    2x off — the probe's hand-derived check caught it.
    """
    f = LENS_MM
    sensor_h = SENSOR_MM * RES_Y / RES_X
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    subj_w = max(xs) - min(xs)
    cx, cz = (max(xs) + min(xs)) / 2.0, (max(zs) + min(zs)) / 2.0
    y_mid = (max(ys) + min(ys)) / 2.0
    ref_w = ref[2] - ref[0]
    ref_cx, ref_cy = (ref[0] + ref[2]) / 2.0, (ref[1] + ref[3]) / 2.0
    depth = subj_w * f / (SENSOR_MM * ref_w)
    cam_x = cx + (ref_cx - 0.5) * depth * SENSOR_MM / f
    cam_z = cz - (ref_cy - 0.5) * depth * sensor_h / f
    return (cam_x, y_mid + depth, cam_z), (90.0, 0.0, 180.0)


# --- main -----------------------------------------------------------------------

def main() -> int:
    global OK
    payload = build_two_figure_payload()

    # -- 1. MULTI-RIG-RECOMPUTE ------------------------------------------------
    scene, rig_a, rig_b = fresh_scene()
    rep_a = apply_via_pose_apply(rig_a, payload, "figure A")
    rep_b = apply_via_pose_apply(rig_b, payload, "figure B")
    bpy.context.view_layer.update()
    wa, ra = worst_fk_deg(rig_a, core.CanonicalPose.from_dict(
        payload["figures"][0]["pose"]))
    wb, rb = worst_fk_deg(rig_b, core.CanonicalPose.from_dict(
        payload["figures"][1]["pose"]))
    check("MULTI-RIG-RECOMPUTE",
          wa <= FK_BAR_DEG and wb <= FK_BAR_DEG
          and rep_a["worst_deg"] <= FK_BAR_DEG and rep_b["worst_deg"] <= FK_BAR_DEG,
          f"A {wa:.4f}deg ({ra}) B {wb:.4f}deg ({rb})")

    # -- 2. ORDER-AND-CLEANUP ---------------------------------------------------
    q_ab = scene_quats()
    fresh_scene()
    apply_via_pose_apply(bpy.data.objects["RM_RigB"], payload, "figure B")
    apply_via_pose_apply(bpy.data.objects["RM_RigA"], payload, "figure A")
    bpy.context.view_layer.update()
    q_ba = scene_quats()
    order_ok = q_ab == q_ba
    check("ORDER", order_ok,
          f"identical={order_ok} bones={len(q_ab)}")

    apply_via_pose_apply(bpy.data.objects["RM_RigA"], payload, "figure A")
    apply_via_pose_apply(bpy.data.objects["RM_RigB"], payload, "figure B")
    bpy.context.view_layer.update()
    q_again = scene_quats()
    check("IDEMPOTENT", q_again == q_ab, f"identical={q_again == q_ab}")

    from riggermortis_addon import pose_apply as pa_mod
    pa_mod.clear_pose(bpy.data.objects["RM_RigB"])
    bpy.context.view_layer.update()
    q_clear = scene_quats()
    untouched = all(q_clear[k] == q_ab[k] for k in q_ab if k.startswith("RM_RigA/"))
    cleared = all(
        tuple(__import__("mathutils").Quaternion((1, 0, 0, 0))) == q_clear[k]
        for k in q_clear if k.startswith("RM_RigB/")
    )
    check("CLEANUP", untouched and cleared,
          f"other_rig_untouched={untouched} cleared_to_rest={cleared}")

    # -- 3. CAMERA-MECHANICS -----------------------------------------------------
    scene, rig_a, rig_b = fresh_scene()
    apply_via_pose_apply(rig_a, payload, "figure A")
    apply_via_pose_apply(rig_b, payload, "figure B")
    bpy.context.view_layer.update()
    pts = subject_points()

    # 3a. pinhole identity: a KNOWN camera + KNOWN points vs hand-derived coords.
    probe_cam = add_camera("RM_ProbeCam", (0.0, 4.0, 1.0), (90.0, 0.0, 180.0), LENS_MM)
    bpy.context.view_layer.update()
    p = Vector((0.3, 2.0, 1.4))  # off-axis point, inside the frustum
    co = project_bbox(probe_cam, [p])[0:2]
    # hand-derived (probe-measured model): u = 0.5 - dx/depth * f/sensor_w;
    # v = 0.5 + dz/depth * f/sensor_h (sensor_h = sensor_w * res_y/res_x).
    u_expect = 0.5 - (0.3 - 0.0) / 2.0 * (LENS_MM / SENSOR_MM)
    v_expect = 0.5 + (1.4 - 1.0) / 2.0 * (LENS_MM / (SENSOR_MM * RES_Y / RES_X))
    err = max(abs(co[0] - u_expect), abs(co[1] - v_expect))
    check("CAMERA-PINHOLE", err <= PROJ_BAR,
          f"measured=({co[0]:.6f},{co[1]:.6f}) expected=({u_expect:.6f},{v_expect:.6f}) err={err:.2e}")

    # 3b. y-flip convention pin: a point ABOVE the camera axis must project to
    # v-up > 0.5, i.e. detector image v (v-down) < 0.5.
    hi = project_bbox(probe_cam, [Vector((0.0, 3.0, 2.0))])
    check("CAMERA-YFLIP", hi[1] > 0.5, f"v_up={hi[1]:.4f} (>0.5 means v-down flip is real)")

    # 3c. the reference framing: a HAND camera deliberately off the v0 prior
    # (35 mm, yawed 12 deg, slightly low) — its subject bbox is the "reference"
    # the v0 solver must match from the bbox alone.
    ref_cam = add_camera("RM_RefCam", (0.9, 4.6, 0.82), (90.0, 0.0, 168.0), 35.0)
    bpy.context.view_layer.update()
    ref = project_bbox(ref_cam, pts)
    ref_px = (ref[0] * RES_X, (1.0 - ref[3]) * RES_Y,
              ref[2] * RES_X, (1.0 - ref[1]) * RES_Y)  # detector-pixel shape
    ref_norm = bbox_to_ref(ref_px, RES_X, RES_Y)

    # 3d. the v0 solve stages a camera that clears the floor on that reference.
    loc, rot = solve_v0_camera(pts, ref_norm)
    v0_cam = add_camera("RM_V0Cam", loc, rot, LENS_MM)
    bpy.context.view_layer.update()
    got = project_bbox(v0_cam, pts)
    iou_v0 = iou(got, ref_norm)
    check("CAMERA-SOLVE", iou_v0 >= IOU_FLOOR,
          f"iou={iou_v0:.4f} floor={IOU_FLOOR} ref={tuple(round(v, 3) for v in ref_norm)} got={tuple(round(v, 3) for v in got)}")

    # 3e. degraded cameras measure strictly worse — the floor separates.
    loc_bad = (loc[0], loc[1] * 1.5, loc[2])
    bad_cam = add_camera("RM_BadCam", loc_bad, rot, LENS_MM)
    bpy.context.view_layer.update()
    iou_dist = iou(project_bbox(bad_cam, pts), ref_norm)
    pts_a = [p for p in pts if p.x < 1.5]  # figure A alone framed
    loc_one, _ = solve_v0_camera(pts_a, ref_norm)
    one_cam = add_camera("RM_OneCam", loc_one, rot, LENS_MM)
    bpy.context.view_layer.update()
    iou_one = iou(project_bbox(one_cam, pts_a), ref_norm)
    check("CAMERA-FLOOR",
          iou_dist < iou_v0 and iou_one < IOU_FLOOR,
          f"distance_x1.5 iou={iou_dist:.4f} (<solved {iou_v0:.4f}); "
          f"single-figure iou={iou_one:.4f} (<floor {IOU_FLOOR})")

    # 3f. determinism: the solve is a pure function of (pts, ref).
    loc2, rot2 = solve_v0_camera(pts, ref_norm)
    check("CAMERA-DETERM", loc == loc2 and rot == rot2,
          f"identical={loc == loc2 and rot == rot2}")

    print(f"RM_SCENE: {'PASS' if OK else 'FAIL'}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
