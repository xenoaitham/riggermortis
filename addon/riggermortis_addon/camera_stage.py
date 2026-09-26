"""Measured scene-camera staging (P8-5) — the additive sibling of the v0
stager in :mod:`.scene_camera`.

v0's code and contract are untouched (the RM_SCENE CAMERA-* rows keep
exercising them); this module stages from the MEASURED solve
(core.camera: yaw/pitch/distance/height fitted from the body kps, the
canonical skeleton as the ruler — docs/CAMERA.md). The stage gate is BOTH
floors: the solve's confidence (>= CAMERA_CONF_FLOOR 0.55, reused from
core) AND the measured framing IoU (>= CAMERA_IOU_FLOOR 0.75, the Annex
A.1 bar, measured by projecting the posed subject through the staged
camera — the v0 machinery). Either failing refuses LOUD and the scene is
untouched: a wrong silent camera is the trust-killer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import bpy_bridge

if TYPE_CHECKING:  # the annotations only; runtime imports stay in-function
    from mathutils import Vector
from .scene_camera import (
    CAMERA_IOU_FLOOR,
    CAMERA_NAME,
    LENS_MM,
    SENSOR_MM,
    _bbox_union,
    _iou,
    _subject_points,
)

#: The solve-confidence floor (the CONVENTIONS bar, reused from core).
CAMERA_CONF_FLOOR = 0.55


def _reference_box(payload: dict, entries: dict, cast_labels: list[str]) -> tuple:
    """The reference subject box: union of the cast figures' bboxes
    (detector pixels, v-down) normalized to v-up frame coords + clamped —
    the v0 measurement convention, verbatim."""
    image = payload.get("image") or {}
    img_w, img_h = image.get("width"), image.get("height")
    if not isinstance(img_w, int) or not isinstance(img_h, int) or img_w <= 0 or img_h <= 0:
        raise ValueError(
            "payload carries no usable image size "
            "(hint: regenerate with: rigpose pose <image> <rig.json>)"
        )
    boxes: list[tuple] = []
    for label in cast_labels:
        entry = entries.get(label) or {}
        bbox = entry.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(
                f"figure {label!r} carries no detector bbox "
                "(hint: the camera stages from the reference's subject boxes)"
            )
        x0, y0, x1, y1 = (float(v) for v in bbox)
        boxes.append((
            min(max(x0 / img_w, 0.0), 1.0),
            min(max(1.0 - y1 / img_h, 0.0), 1.0),
            min(max(x1 / img_w, 0.0), 1.0),
            min(max(1.0 - y0 / img_h, 0.0), 1.0),
        ))
    return _bbox_union(boxes)


def _figure_solves(payload: dict, entries: dict, cast_labels: list[str], core: Any):
    """The pure per-figure solves off the payload's own fields (no bpy)."""
    img = payload.get("image") or {}
    solves = []
    for label in cast_labels:
        pose_dict = (entries.get(label) or {}).get("pose") or {}
        positions = {
            str(r): (float(p[0]), float(p[1]), float(p[2]))
            for r, p in pose_dict.get("positions", {}).items()
        }
        joint_conf = {
            str(r): float(c) for r, c in pose_dict.get("joint_confidence", {}).items()
        }
        scale = float(pose_dict.get("scale", 0.0))
        bbox = tuple(float(v) for v in (entries.get(label, {}).get("bbox") or [0.0] * 4))
        solves.append((
            label,
            core.solve_camera_figure(
                positions, joint_conf, scale, bbox,
                int(img.get("width", 0)), int(img.get("height", 0)),
            ),
        ))
    return solves



def _aim_quat(location: Vector, target: Vector):
    """The camera rotation FROM THE MODEL BASIS (docs/CAMERA.md): screen
    right = fw x world-up, screen-up = right x fw — the v0-pinned
    convention, no track_quat ambiguity (the gate's CAM-MODEL row proves
    the model matches world_to_camera_view to 1e-4 under this basis)."""
    from mathutils import Matrix, Vector

    fw = (target - location).normalized()
    right = fw.cross(Vector((0.0, 0.0, 1.0))).normalized()
    up = right.cross(fw).normalized()
    m = Matrix((right, up, -fw)).transposed()
    return m.to_quaternion()


def stage_scene_camera_measured(
    payload: dict[str, Any], assignments: dict[str, str], core: Any = None,
) -> dict[str, Any]:
    """Stage-or-refuse from the MEASURED solve. Returns a structured report.

    Flow (docs/CAMERA.md § The addon staging composition): the pure core
    solve runs per cast figure -> the confidence-weighted consensus ->
    the camera is built from the POSED rigs' measured world geometry
    (target, scale, facing) -> placed, updated, MEASURED by projecting the
    posed subject -> BOTH floors -> stage with MEASURED props, or refuse
    with nothing in the scene.
    """
    import math

    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    if core is None:
        core = bpy_bridge.import_core()

    core.scene_from_payload(payload)  # loud validation before anything touches the scene
    cast_labels = sorted(assignments)
    armatures = sorted(set(assignments.values()))
    missing = [name for name in armatures
               if (o := bpy.data.objects.get(name)) is None or o.type != "ARMATURE"]
    if missing or not cast_labels:
        raise ValueError(
            f"cast armature(s) not found or none cast: {', '.join(missing) or 'no casting'}"
            " (hint: apply the scene first, then stage the camera)"
        )

    entries = {str(e.get("label")): e for e in core.payload.figure_entries(payload)}
    ref = _reference_box(payload, entries, cast_labels)
    figure_solves = _figure_solves(payload, entries, cast_labels, core)
    consensus = core.consensus_camera(figure_solves)
    figures_report = {label: s.to_dict() for label, s in figure_solves}
    if not consensus.get("ok"):
        return {
            "staged": False,
            "mode": "MEASURED",
            "reason": str(consensus.get("reason")),
            "figures": figures_report,
            "hint": "the measured solve refused every cast figure (see reasons)",
        }
    if float(consensus.get("confidence", 0.0)) < CAMERA_CONF_FLOOR:
        return {
            "staged": False,
            "mode": "MEASURED",
            "reason": (
                f"below the confidence floor: solve confidence "
                f"{float(consensus['confidence']):.2f} < {CAMERA_CONF_FLOOR}"
            ),
            "consensus": consensus,
            "figures": figures_report,
            "hint": "a low-confidence camera is refused, never staged "
                    "(move the rigs / re-frame the reference / stage manually)",
        }

    # the framing only transfers when the scene's aspect matches the
    # reference's (the sensor AUTO-fits the long side): set the render res
    # to the reference dims for the measurement, restore on refuse
    img = payload.get("image") or {}
    scene = bpy.context.scene
    prev_res = (scene.render.resolution_x, scene.render.resolution_y)
    scene.render.resolution_x = int(img.get("width", prev_res[0]))
    scene.render.resolution_y = int(img.get("height", prev_res[1]))

    # world geometry, MEASURED from the posed rigs (the coupling-pass class)
    bpy.context.view_layer.update()
    pts = _subject_points(armatures)
    if not pts:
        raise ValueError("cast armatures expose no pose bones to frame")
    xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
    target = Vector((
        (max(xs) + min(xs)) / 2.0,
        (max(ys) + min(ys)) / 2.0,
        (max(zs) + min(zs)) / 2.0,
    ))
    z_low = min(zs)
    # world scale: the posed rigs' torso span / the canonical 0.45 (the
    # coupling placement's s); fallback = the subject's z extent / R_STAND
    torso = 0.0
    for name in armatures:
        obj = bpy.data.objects[name]
        role_of = {str(key): val for key, val in obj.items() if str(key).startswith("rm_role_")}
        hips_b = role_of.get("rm_role_hips")
        neck_b = role_of.get("rm_role_neck")
        if hips_b and neck_b and hips_b in obj.pose.bones and neck_b in obj.pose.bones:
            ph = obj.matrix_world @ Vector(obj.pose.bones[hips_b].head)
            pn = obj.matrix_world @ Vector(obj.pose.bones[neck_b].head)
            torso = max(torso, (ph - pn).length)
    if torso > 1e-6:
        s = torso / 0.45
    else:
        s = (max(zs) - min(zs)) / core.camera.R_STAND
    # the rigs' world facing: canonical -Y through the first armature's
    # world rotation (the upright-rig class the staging declares)
    rig = bpy.data.objects[armatures[0]]
    facing = (rig.matrix_world.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
    yaw = math.radians(float(consensus["yaw_deg"]))
    dist = float(consensus["distance"]) * s
    # yaw > 0 = the camera views the subject's RIGHT flank (docs/CAMERA.md):
    # rotate the facing ray by -yaw about world Z
    cam_dir_xy = Vector((
        facing.x * math.cos(yaw) + facing.y * math.sin(yaw),
        -facing.x * math.sin(yaw) + facing.y * math.cos(yaw),
    ))
    location = Vector((
        target.x + cam_dir_xy.x * dist,
        target.y + cam_dir_xy.y * dist,
        z_low + float(consensus["height"]) * s,
    ))

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
    cam.location = location
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = _aim_quat(location, target)
    prev_scene_camera = bpy.context.scene.camera
    bpy.context.scene.camera = cam
    bpy.context.view_layer.update()  # place, UPDATE, then measure (the v0 lesson)

    got_x, got_y = [], []
    for p in pts:
        co = world_to_camera_view(bpy.context.scene, cam, p)
        got_x.append(co.x)
        got_y.append(co.y)
    got = (min(got_x), min(got_y), max(got_x), max(got_y))
    iou = _iou(got, ref)

    if iou < CAMERA_IOU_FLOOR:
        scene.render.resolution_x, scene.render.resolution_y = prev_res
        bpy.context.scene.camera = prev_scene_camera
        if created:
            bpy.data.objects.remove(cam)
            cam_data = bpy.data.cameras.get(CAMERA_NAME)
            if cam_data is not None and cam_data.users == 0:
                bpy.data.cameras.remove(cam_data)
        return {
            "staged": False,
            "mode": "MEASURED",
            "reason": "below the framing confidence floor",
            "iou": round(iou, 4),
            "floor": CAMERA_IOU_FLOOR,
            "solve_confidence": consensus.get("confidence"),
            "consensus": consensus,
            "reference_bbox": [round(v, 4) for v in ref],
            "measured_bbox": [round(v, 4) for v in got],
            "hint": "the solve's framing missed the reference box "
                    "(move the rigs / re-crop the reference / stage manually)",
        }

    cam["rm_camera_solve"] = "MEASURED"
    cam["rm_camera_conf"] = round(float(consensus["confidence"]), 4)
    cam["rm_camera_iou"] = round(iou, 4)
    cam["rm_camera_params"] = (
        f"yaw {float(consensus['yaw_deg']):.2f} pitch "
        f"{float(consensus['pitch_deg']):.2f} dist {float(consensus['distance']):.4f} "
        f"height {float(consensus['height']):.4f} (canonical units)"
    )
    return {
        "staged": True,
        "mode": "MEASURED",
        "camera": CAMERA_NAME,
        "created": created,
        "scene_camera_set": True,
        "lens_mm": LENS_MM,
        "iou": round(iou, 4),
        "floor": CAMERA_IOU_FLOOR,
        "confidence": round(float(consensus["confidence"]), 4),
        "params": consensus,
        "figures": figures_report,
        "reference_bbox": [round(v, 4) for v in ref],
        "measured_bbox": [round(v, 4) for v in got],
        "label": "MEASURED (P8-5 solve: yaw/pitch/distance/height from body kps)",
    }
