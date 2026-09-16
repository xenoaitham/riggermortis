"""Action baking (P2-3): a canonical action -> keyframed pose rotations.

Per kept frame the bake recomputes the FK rotations from that frame's
``CanonicalPose`` (the exact math of :func:`pose_apply.apply_pose_object`,
including the ``B = M⁻¹LM`` bone-space conversion verified to <=0.5° by
``xtask/verify_pose_apply.sh``), writes them to the pose bones, and inserts a
rotation keyframe at the frame's Blender frame number (source index + offset).

Rig data and the role mapping are computed ONCE up front — a long bake must
not re-map the rig per frame. Bones a frame's application does not mention
(partial observation) keep their previous key — the honest constant
interpolation, never a fabricated in-between.

Root motion is deliberately NOT baked: the single-view solve is hip-anchored
per frame (D-008), so the action carries no world translation — any root
keys would be fabricated data, violating the honesty rule. P2-6's hip
stabilization is the place to revisit.

The bake writes into a NEW action (never the user's active one) and returns
a structured report; ``verify_application`` runs per frame and the worst
per-frame FK error travels in the report.
"""
from __future__ import annotations

from typing import Any

from . import bpy_bridge

_RAD_TO_DEG = 57.29577951308232


def bake_action(
    obj: Any,
    frames: Any,  # iterable of riggermortis ActionFrame
    core: Any,
    *,
    name: str = "rm_bake",
    frame_offset: int = 1,
) -> dict[str, Any]:
    """Bake ``frames`` (ActionFrame list) onto ``obj`` as a new keyframed action.

    ``frame_offset`` maps source frame index -> Blender frame number; the
    default 1 makes source frame 0 play at Blender frame 1. Play the result
    at the source video's frame rate for true timing.
    """
    if obj.type != "ARMATURE":
        raise ValueError(f"{obj.name!r} is not an armature")
    frames = list(frames)
    if not frames:
        raise ValueError(
            "no frames to bake (hint: the canonical action is empty — check "
            "its failure ledger; failed frames are never fabricated)"
        )

    rig = core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    # Lazy imports (bpy, mathutils, pose_apply) follow the addon convention:
    # modules import Blender-side dependencies inside functions so the package
    # imports cleanly outside Blender (see bpy_bridge.CORE_MISSING_HINT).
    from .pose_apply import mapping_from_props

    mapping = mapping_from_props(obj, core)
    mapping_source = "rm_role_* props"
    if mapping is None:
        mapping = core.map_rig(rig)
        mapping_source = "live map_rig"

    import bpy
    from mathutils import Matrix, Vector

    action = bpy.data.actions.new(name)
    obj.animation_data_create()
    obj.animation_data.action = action

    baked: list[int] = []
    keys = 0
    worst_role = ""
    worst_rad = 0.0
    skipped: set[str] = set()

    for af in frames:
        frame_no = af.frame + frame_offset
        application = core.apply_canonical_pose(rig, mapping, af.pose)
        skipped.update(application.skipped)
        for rot in application.rotations:
            pb = obj.pose.bones.get(rot.bone)
            if pb is None:
                continue
            rest = pb.bone.matrix_local.to_3x3()
            world = Matrix.Rotation(float(rot.angle_rad), 3, Vector(rot.axis))
            basis = rest.inverted() @ world @ rest
            axis, angle = basis.to_quaternion().to_axis_angle()
            if pb.rotation_mode != "AXIS_ANGLE":
                pb.rotation_mode = "AXIS_ANGLE"
            pb.rotation_axis_angle = (angle, axis.x, axis.y, axis.z)
            pb.keyframe_insert(data_path="rotation_axis_angle", frame=frame_no)
            keys += 1
        errors = core.verify_application(rig, application, af.pose)
        for role, rad in errors.items():
            if rad > worst_rad:
                worst_role, worst_rad = role, rad
        baked.append(frame_no)

    return {
        "action": action.name,
        "baked_frames": baked,
        "keys": keys,
        "worst_role": worst_role,
        "worst_deg": worst_rad * _RAD_TO_DEG,
        "skipped": sorted(skipped),
        "mapping_source": mapping_source,
        "notes": [
            (
                "rotations only — no root motion (single-view solve is "
                "hip-anchored; baking world translation would be fabricated)"
            ),
        ],
    }
