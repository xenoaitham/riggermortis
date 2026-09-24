"""Scene camera v0 (P8-1): approximate staging from the reference framing.

Front-prior, closed-form, MEASURED — and honest about all three. The solver
stages a camera whose subject framing matches the reference's subject bbox
(union of the cast figures' detector bboxes), then measures what it staged
by projecting the posed subject through the camera and computing the bbox
IoU against the reference. The Annex A.1 confidence floor is **IoU >= 0.75**:
at/above it the camera stages (created-or-updated ``rm_scene_camera``, made
the scene camera, props ``rm_camera_v0="APPROXIMATE"`` + ``rm_camera_iou``);
below it the operator REFUSES TO STAGE and the scene is untouched — a wrong
silent camera is the failure this module exists to prevent.

Projection model PINNED by the probe (xtask/scene_probe.py, RM_SCENE
CAMERA-PINHOLE err 1.1e-07 on Blender 5.1): for a level camera looking down
-Y (rotation_euler 90/0/180), view depth ``d = cam_y - py``:

    u = 0.5 - (px - cam_x)/d * lens_mm/sensor_w      (viewer-right = -X)
    v = 0.5 + (pz - cam_z)/d * lens_mm/sensor_h      (v-up; image v flips)

with ``sensor_h = sensor_w * res_y/res_x`` (AUTO fit, landscape), and
``world_to_camera_view`` returns these coordinates UNCLAMPED (out-of-frame
points keep going) — reference bboxes from detectors are frame-clamped, so
the solver clamps the reference to [0, 1] before comparing.

Floor derivation (published this session, docs/BENCHMARKS.md SCENE block):
measured on the probe's synthetic two-figure benchmark — the v0-solved
camera lands IoU ~0.97 on a deliberately off-prior reference (35 mm, yawed
12 deg), while degraded cameras measure far lower (distance x1.5 ~0.47,
single-figure framing ~0.13): 0.75 sits inside that gap with margin on both
sides. SYNTHETIC-labeled; the P8-5 GT set re-derives it on real references
(the Annex A.1 re-validation trigger).
"""
from __future__ import annotations

from typing import Any

from . import bpy_bridge

#: The Annex A.1 confidence floor: stage iff subject-bbox IoU >= this.
CAMERA_IOU_FLOOR = 0.75

CAMERA_NAME = "rm_scene_camera"
LENS_MM = 50.0
SENSOR_MM = 36.0

Box = tuple[float, float, float, float]  # normalized frame coords, y-up


def _subject_points(armature_names: list[str]) -> list[Any]:
    """World-space posed joint heads across the cast armatures."""
    import bpy
    from mathutils import Vector

    pts: list[Any] = []
    for name in armature_names:
        obj = bpy.data.objects[name]
        for pb in obj.pose.bones:
            pts.append(obj.matrix_world @ Vector(pb.head))
    return pts


def _bbox_union(boxes: list[Box]) -> Box:
    return (
        min(b[0] for b in boxes), min(b[1] for b in boxes),
        max(b[2] for b in boxes), max(b[3] for b in boxes),
    )


def _iou(a: Box, b: Box) -> float:
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0.0 or iy <= 0.0:
        return 0.0
    inter = ix * iy
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def solve_camera(
    pts: list[Any], ref: Box, res_x: int, res_y: int,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """The closed-form front-prior solve -> (location, euler-degrees).

    Pure function (probe CAMERA-DETERM: two runs identical). Distance from
    the reference width fraction; center matched per the pinned model.
    """
    f = LENS_MM
    sensor_h = SENSOR_MM * res_y / res_x
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    subj_w = max(xs) - min(xs)
    cx, cz = (max(xs) + min(xs)) / 2.0, (max(zs) + min(zs)) / 2.0
    y_mid = (max(ys) + min(ys)) / 2.0
    ref_w = ref[2] - ref[0]
    if ref_w <= 1e-9 or subj_w <= 1e-9:
        raise ValueError(
            "degenerate subject/reference width "
            f"(subject {subj_w:.4f} m, reference fraction {ref_w:.4f})",
        )
    depth = subj_w * f / (SENSOR_MM * ref_w)
    ref_cx, ref_cy = (ref[0] + ref[2]) / 2.0, (ref[1] + ref[3]) / 2.0
    cam_x = cx + (ref_cx - 0.5) * depth * SENSOR_MM / f
    cam_z = cz - (ref_cy - 0.5) * depth * sensor_h / f
    return (cam_x, y_mid + depth, cam_z), (90.0, 0.0, 180.0)


def stage_scene_camera(
    payload: dict[str, Any], assignments: dict[str, str], core: Any = None,
) -> dict[str, Any]:
    """Stage-or-refuse per the floor. Returns a structured report.

    Refusals (loud, scene untouched): no cast armatures, payload figures
    without bboxes or image size, degenerate widths, IoU below the floor.
    Staging: creates-or-updates ``rm_scene_camera`` (deterministic), makes
    it the scene camera, stamps ``rm_camera_v0="APPROXIMATE"`` and the
    measured IoU on the camera, and reports everything it did.
    """
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    if core is None:
        core = bpy_bridge.import_core()

    core.scene_from_payload(payload)  # loud validation before anything touches the scene
    cast_labels = sorted(assignments)
    armatures = sorted(assignments.values())
    missing = [name for name in armatures
               if (o := bpy.data.objects.get(name)) is None or o.type != "ARMATURE"]
    if missing or not cast_labels:
        raise ValueError(
            f"cast armature(s) not found or none cast: {', '.join(missing) or 'no casting'}"
            " (hint: apply the scene first, then stage the camera)",
        )

    image = payload.get("image") or {}
    img_w, img_h = image.get("width"), image.get("height")
    if not isinstance(img_w, int) or not isinstance(img_h, int) or img_w <= 0 or img_h <= 0:
        raise ValueError(
            "payload carries no usable image size "
            "(hint: regenerate with: rigpose pose <image> <rig.json>)",
        )
    entries = {str(e.get("label")): e for e in core.payload.figure_entries(payload)}
    boxes: list[Box] = []
    for label in cast_labels:
        entry = entries.get(label) or {}
        bbox = entry.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(
                f"figure {label!r} carries no detector bbox "
                "(hint: camera v0 frames from the reference's subject boxes)",
            )
        x0, y0, x1, y1 = (float(v) for v in bbox)
        # detector pixels (v-down) -> normalized v-up, clamped to the frame
        boxes.append((
            min(max(x0 / img_w, 0.0), 1.0),
            min(max(1.0 - y1 / img_h, 0.0), 1.0),
            min(max(x1 / img_w, 0.0), 1.0),
            min(max(1.0 - y0 / img_h, 0.0), 1.0),
        ))
    ref = _bbox_union(boxes)

    bpy.context.view_layer.update()
    pts = _subject_points(armatures)
    res_x = int(bpy.context.scene.render.resolution_x)
    res_y = int(bpy.context.scene.render.resolution_y)
    loc, rot_deg = solve_camera(pts, ref, res_x, res_y)

    import math

    cam = bpy.data.objects.get(CAMERA_NAME)
    created = cam is None
    if cam is None or cam.type != "CAMERA":
        cam_data = bpy.data.cameras.new(CAMERA_NAME)
        cam_data.lens = LENS_MM
        cam_data.sensor_width = SENSOR_MM
        cam = bpy.data.objects.new(CAMERA_NAME, cam_data)
        bpy.context.scene.collection.objects.link(cam)
    else:
        cam.data.lens = LENS_MM
        cam.data.sensor_width = SENSOR_MM
    cam.location = Vector(loc)
    cam.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    prev_scene_camera = bpy.context.scene.camera
    bpy.context.scene.camera = cam
    # the measure reads cam.matrix_world — stale until the depsgraph runs
    # (the probe's lesson: place, UPDATE, then measure)
    bpy.context.view_layer.update()

    # MEASURE what we staged — the floor gate reads the measured frame, never
    # the solver's intent.
    got_x, got_y = [], []
    for p in pts:
        co = world_to_camera_view(bpy.context.scene, cam, p)
        got_x.append(co.x)
        got_y.append(co.y)
    got = (min(got_x), min(got_y), max(got_x), max(got_y))
    iou = _iou(got, ref)

    if iou < CAMERA_IOU_FLOOR:
        # refuse-to-stage: undo the staging (restore/delete), leave no camera
        bpy.context.scene.camera = prev_scene_camera
        if created:
            bpy.data.objects.remove(cam)
            cam_data = bpy.data.cameras.get(CAMERA_NAME)
            if cam_data is not None and cam_data.users == 0:
                bpy.data.cameras.remove(cam_data)
        report = {
            "staged": False,
            "reason": "below the confidence floor",
            "iou": round(iou, 4),
            "floor": CAMERA_IOU_FLOOR,
            "reference_bbox": [round(v, 4) for v in ref],
            "measured_bbox": [round(v, 4) for v in got],
            "hint": "move the rigs toward the reference framing, re-crop the "
                    "reference, or frame the camera manually (camera v0 is "
                    "APPROXIMATE by design; the measured solve is P8-5)",
        }
        return report

    cam["rm_camera_v0"] = "APPROXIMATE"
    cam["rm_camera_iou"] = round(iou, 4)
    return {
        "staged": True,
        "camera": CAMERA_NAME,
        "created": created,
        "scene_camera_set": True,
        "lens_mm": LENS_MM,
        "iou": round(iou, 4),
        "floor": CAMERA_IOU_FLOOR,
        "reference_bbox": [round(v, 4) for v in ref],
        "measured_bbox": [round(v, 4) for v in got],
        "label": "APPROXIMATE (front-prior bbox solve; the measured solve is P8-5)",
    }
