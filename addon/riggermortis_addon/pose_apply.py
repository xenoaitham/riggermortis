"""Pose-payload application: payload JSON -> pose-bone rotations (D-009).

The payload (written by ``rigpose pose``) carries the solved canonical pose
plus parent-space/world-frame rotations. Blender's ``pose_bone`` rotations live
in the bone's LOCAL rest space (bone Y along the bone, roll included), so a
payload rotation ``L`` (a pure rotation in armature space) must be conjugated
by the bone's rest matrix before it can be stored:

    B = M⁻¹ @ L @ M        M = pose_bone.bone.matrix_local (rest, armature space)

Derivation: with ``W`` the bone's accumulated world-frame rotation relative to
rest and ``W_p`` the parent's, Blender gives ``W = W_p @ (M @ B @ M⁻¹)`` while
the payload satisfies ``W = W_p @ L`` — hence ``B = M⁻¹ @ L @ M``. The
conversion is verified headlessly to <=0.5° per bone by
``xtask/verify_pose_apply.sh`` on the real metarig and Seed-san rigs.

Application recomputes rotations from the payload's pose in-process (stdlib
core) so the mirror toggle and manual ``rm_role_*`` remaps stay correct; the
payload's own ``rotations`` remain the headless/CLI/MCP consumer format.
Ambiguity is reported, never swallowed: every skip and note lands in the
returned report.
"""
from __future__ import annotations

from typing import Any

from . import bpy_bridge

PAYLOAD_FORMAT = 1


def mapping_from_props(obj: Any, core: Any) -> Any | None:
    """Role->bone mapping from ``rm_role_*`` custom props (Inspect & Map).

    Returns None when no props exist, so the caller can fall back to a live
    ``map_rig``. Partial prop sets are used as-is: unassigned roles are then
    reported by the FK engine's notes instead of silently guessed.
    """
    assignments: dict[str, Any] = {}
    for role in core.ALL_ROLES:
        bone = obj.get(f"rm_role_{role}")
        if bone and bone in obj.data.bones:
            assignments[role] = core.RoleAssignment(
                role=role, bone=str(bone), confidence=1.0, side=core.side_of(role)
            )
    if not assignments:
        return None
    return core.RigMapping(
        rig_name=obj.name,
        fingerprint=core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj)).fingerprint(),
        assignments=assignments,
    )


def _bone_local_basis(pb: Any, world_axis: Any, world_angle: float) -> Any:
    """Conjugate a payload (armature-space) rotation into the bone's local space."""
    from mathutils import Matrix, Vector

    rest = pb.bone.matrix_local.to_3x3()
    world = Matrix.Rotation(float(world_angle), 3, Vector(world_axis))
    return rest.inverted() @ world @ rest


def apply_payload(
    obj: Any, payload: dict[str, Any], mirror: bool = False, core: Any = None
) -> dict[str, Any]:
    """Apply a ``rigpose pose`` payload to an armature's pose bones.

    Returns a structured report: applied/missing bones, per-bone FK angle
    errors vs the payload targets (worst included), skipped roles, and notes.
    Raises ``ValueError`` with an actionable message on malformed payloads.
    """
    if obj.type != "ARMATURE":
        raise ValueError(f"{obj.name!r} is not an armature")
    if payload.get("format") != PAYLOAD_FORMAT:
        raise ValueError(
            f"unsupported pose payload format {payload.get('format')!r} "
            f"(hint: this build reads format {PAYLOAD_FORMAT}; "
            "regenerate with: rigpose pose <image> <rig.json> --out payload.json)"
        )
    if "pose" not in payload:
        raise ValueError(
            "payload has no 'pose' section "
            "(hint: regenerate with: rigpose pose <image> <rig.json> --out payload.json)"
        )
    if core is None:
        core = bpy_bridge.import_core()

    pose = core.CanonicalPose.from_dict(payload["pose"])
    if mirror:
        pose = pose.mirrored()

    rig = core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    mapping = mapping_from_props(obj, core)
    mapping_source = "rm_role_* props"
    if mapping is None:
        mapping = core.map_rig(rig)
        mapping_source = "live map_rig"
    if mapping.core_missing():
        core_missing = ", ".join(mapping.core_missing())
    else:
        core_missing = ""

    application = core.apply_canonical_pose(rig, mapping, pose)

    applied: list[str] = []
    missing: list[str] = []
    for rot in application.rotations:
        pb = obj.pose.bones.get(rot.bone)
        if pb is None:
            missing.append(rot.bone)
            continue
        basis = _bone_local_basis(pb, rot.axis, rot.angle_rad)
        axis, angle = basis.to_quaternion().to_axis_angle()
        if pb.rotation_mode != "AXIS_ANGLE":
            pb.rotation_mode = "AXIS_ANGLE"
        pb.rotation_axis_angle = (angle, axis.x, axis.y, axis.z)
        applied.append(rot.bone)

    errors = core.verify_application(rig, application, pose)
    worst_role, worst_rad = max(errors.items(), key=lambda kv: kv[1]) if errors else ("", 0.0)
    worst_deg = worst_rad * 57.29577951308232

    return {
        "applied": applied,
        "missing_pose_bones": missing,
        "skipped": list(application.skipped),
        "notes": list(application.notes),
        "mapping_source": mapping_source,
        "core_missing": core_missing,
        "mirrored": mirror,
        "confidence": pose.confidence,
        "reliable": pose.reliable,
        "worst_role": worst_role,
        "worst_deg": worst_deg,
    }


def clear_pose(obj: Any) -> str:
    """Restore every pose bone to rest (identity basis) — undo-able via the operator."""
    from mathutils import Matrix

    count = 0
    for pb in obj.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
        count += 1
    return f"restored {count} bone(s) to rest"


def push_undo() -> None:
    """Best-effort undo push; background mode has no undo context."""
    try:
        import bpy

        bpy.ops.ed.undo_push()
    except Exception:  # noqa: BLE001 — background/headless runs have no undo stack
        pass
