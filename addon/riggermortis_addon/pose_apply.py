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

PAYLOAD_FORMAT = 3
#: Formats this build reads: 3 (native), 2, and 1 (back-compat, read-only).
READABLE_FORMATS = (1, 2, 3)


def payload_module() -> Any:
    """The core payload contract module (shared with CLI / MCP; D-009)."""
    import riggermortis.payload as payload_mod

    return payload_mod

# alias kept for the original private name
_payload_module = payload_module


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


def resolve_face_shape_keys(obj: Any, pose: Any, core: Any) -> tuple[set[str], list[str]]:
    """Scan the armature's deformed meshes for P8-4 convention shape keys
    (key name == face param name, docs/FACE.md § apply class b).

    Returns (resolved key names, loud report lines). Missing keys are
    reported per solved param — never a silent skip; keys whose param is
    ledgered-not-solved are reported and stay untouched.
    """
    import bpy

    lines: list[str] = []
    if pose.face is None:
        return set(), lines
    available: set[str] = set()
    for mesh in bpy.data.objects:
        if mesh.type != "MESH":
            continue
        for mod in mesh.modifiers:
            if mod.type == "ARMATURE" and mod.object == obj:
                if mesh.data.shape_keys is not None:
                    available |= {kb.name for kb in mesh.data.shape_keys.key_blocks}
                break
    resolved: set[str] = set()
    for param in sorted(available & set(pose.face.params)):
        resolved.add(param)
    for param in sorted(set(pose.face.params) - available):
        lines.append(f"face: no shape key named {param!r} on any deformed mesh — skipped loud")
    for param in sorted(available - set(pose.face.params)):
        lines.append(
            f"face: param {param!r} not solved (ledgered in the pose) — shape key untouched"
        )
    return resolved, lines


def apply_face_shape_keys(obj: Any, pose: Any, core: Any, keys: set[str]) -> list[str]:
    """Set convention shape-key values to the solved params (clamped [0, 1],
    the shape-key native range). Returns the applied key names."""
    import bpy

    applied: list[str] = []
    if pose.face is None or not keys:
        return applied
    for mesh in bpy.data.objects:
        if mesh.type != "MESH":
            continue
        targets = False
        for mod in mesh.modifiers:
            if mod.type == "ARMATURE" and mod.object == obj:
                targets = True
                break
        if not targets or mesh.data.shape_keys is None:
            continue
        for kb in mesh.data.shape_keys.key_blocks:
            if kb.name in keys:
                kb.value = max(0.0, min(1.0, float(pose.face.params.get(kb.name, 0.0))))
                applied.append(kb.name)
    return sorted(set(applied))


def apply_pose_object(
    obj: Any, pose: Any, core: Any, finger_map: dict[str, str] | None = None,
    face_bones: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Write a ``CanonicalPose`` (already mirrored/toggled as needed) to pose bones.

    Shared by payload application and the review flip toggle (P1-11): the FK
    pass, bone-space conversion, and report shape are identical either way.
    ``finger_map`` (P8-3): optional finger role -> bone bindings (the preset's
    ``hands`` bindings); None = no finger application — when the pose solved
    hands, the report carries the loud capability line from core.
    ``face_bones`` (P8-4): optional face param -> bone bindings (the preset's
    ``face_bones``). The SHAPE-KEY class needs no bindings: convention keys
    (name == param name) on the armature's deformed meshes are resolved and
    driven here; missing keys report loud, never silent.
    """
    rig = core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    mapping = mapping_from_props(obj, core)
    mapping_source = "rm_role_* props"
    if mapping is None:
        mapping = core.map_rig(rig)
        mapping_source = "live map_rig"
    core_missing = ", ".join(mapping.core_missing()) if mapping.core_missing() else ""

    shape_keys, shape_key_lines = resolve_face_shape_keys(obj, pose, core)
    application = core.apply_canonical_pose(
        rig, mapping, pose, finger_map=finger_map,
        face_bones=face_bones, face_shape_keys=shape_keys,
    )

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

    shape_keys_applied = apply_face_shape_keys(obj, pose, core, shape_keys)

    errors = core.verify_application(rig, application, pose)
    worst_role, worst_rad = max(errors.items(), key=lambda kv: kv[1]) if errors else ("", 0.0)
    worst_deg = worst_rad * 57.29577951308232

    return {
        "applied": applied,
        "missing_pose_bones": missing,
        "skipped": list(application.skipped),
        "notes": list(application.notes) + shape_key_lines,
        "mapping_source": mapping_source,
        "core_missing": core_missing,
        "confidence": pose.confidence,
        "reliable": pose.reliable,
        "worst_role": worst_role,
        "worst_deg": worst_deg,
        "shape_keys_applied": shape_keys_applied,
    }


def apply_payload(
    obj: Any, payload: dict[str, Any], mirror: bool = False, core: Any = None,
    figure: str | None = None, finger_map: dict[str, str] | None = None,
    face_bones: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Apply a ``rigpose pose`` payload to an armature's pose bones.

    ``figure``: label of the figure to apply (payload v2 carries several when
    written with ``--all-figures``); None = the payload's selected figure.
    ``finger_map`` (P8-3): optional finger role -> bone bindings, resolved
    from a preset's ``hands`` bindings by the caller. ``face_bones`` (P8-4):
    optional face param -> bone bindings from the preset's ``face_bones``;
    the shape-key class needs no bindings (the convention scan is automatic).

    Returns a structured report: applied/missing bones, per-bone FK angle
    errors vs the payload targets (worst included), skipped roles, and notes.
    Raises ``ValueError`` with an actionable message on malformed payloads.
    """
    if obj.type != "ARMATURE":
        raise ValueError(f"{obj.name!r} is not an armature")
    fmt = payload.get("format", 1)
    if fmt not in READABLE_FORMATS:
        raise ValueError(
            f"unsupported pose payload format {fmt!r} "
            f"(hint: this build reads formats {', '.join(map(str, READABLE_FORMATS))}; "
            "regenerate with: rigpose pose <image> <rig.json> --out payload.json)"
        )
    if core is None:
        core = bpy_bridge.import_core()

    payload_mod = _payload_module()
    try:
        pose_dict = payload_mod.pose_for_figure(payload, figure)
    except Exception as exc:  # PayloadError — reworded to the addon's ValueError contract
        raise ValueError(f"{exc} (hint: regenerate with: rigpose pose ...)") from exc
    pose = core.CanonicalPose.from_dict(pose_dict)
    if mirror:
        pose = pose.mirrored()

    report = apply_pose_object(obj, pose, core, finger_map=finger_map, face_bones=face_bones)
    report["mirrored"] = mirror
    applied_label = payload_mod.entry_for_label(payload, figure).get("label", "?")
    report["figure"] = str(applied_label)
    if pose.hands:
        report["hands_solved"] = sum(len(h.fingers) for h in pose.hands.values())
    if pose.face is not None:
        report["face_solved"] = len(pose.face.params)
    return report


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
    import contextlib

    with contextlib.suppress(Exception):  # background/headless runs have no undo stack
        import bpy

        bpy.ops.ed.undo_push()
