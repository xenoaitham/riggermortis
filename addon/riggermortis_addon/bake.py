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

Foot contact lock (P2-5, optional ``contacts``): when a ContactReport is
passed, every frame inside one of its contact intervals pins each planted
foot's leg chain (both feet on double-support frames) to its interval-start
WORLD pose:

- thigh + shin are re-solved per frame by a small 2-bone correction so the
  ANKLE (foot-bone head) stays at its captured world position — hips motion
  is compensated instead of dragging the foot. The knee keeps the computed
  bend direction (closest-to-provisional pole, deterministic); an unreachable
  target is clamped along hip->ankle and counted in ``lock_clamped`` (FK
  bones cannot stretch);
- the foot bone's world transform (position + orientation) is held at its
  captured plant pose, so the foot itself neither pivots nor drifts.

All three leg roles must be mapped; a frame missing one degrades that frame
to plain computed keys. This is a deliberate deviation from the source pose:
FK fidelity (``worst_deg``) is verified on the UNLOCKED application, and the
held-vs-computed deviation is reported separately as ``lock_dev_deg``.
Core-side pinning (``contacts.lock_feet``) fixes the canonical action itself;
this bake freeze is the rig-space half of the lock. All matrices are composed
locally from the keyed bases and rest matrices (``W = P @ (Mp⁻¹ Mb) @ B``,
identity verified to 0.000000 on the real metarig) — reading ``pb.matrix``
back mid-bake is unreliable once an action is assigned (stale evaluated
state).

Root motion is deliberately NOT baked: the single-view solve is hip-anchored
per frame (D-008), so the action carries no world translation — any root
keys would be fabricated data, violating the honesty rule. P2-6's hip
stabilization is the place to revisit.

The bake writes into a NEW action (never the user's active one) and returns
a structured report; ``verify_application`` runs per frame and the worst
per-frame FK error travels in the report.
"""
from __future__ import annotations

import math
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
    contacts: Any = None,  # riggermortis ContactReport (P2-5 foot lock)
    secondary: Any = None,  # list of (SecondaryTrack, [bone names]) (P6-1)
) -> dict[str, Any]:
    """Bake ``frames`` (ActionFrame list) onto ``obj`` as a new keyframed action.

    ``frame_offset`` maps source frame index -> Blender frame number; the
    default 1 makes source frame 0 play at Blender frame 1. Play the result
    at the source video's frame rate for true timing. ``contacts`` (optional
    ContactReport) pins each planted foot's world pose across its contact
    intervals — see the module docstring.

    ``secondary`` (optional, P6-1): list of ``(track, bone_names)`` pairs
    where each ``track`` is a ``core.secondary.SecondaryTrack`` (spring-chain
    simulation output, docs/SECONDARY_MOTION.md) and ``bone_names`` lists the
    rig's appendage bones implementing the chain, parent-first, with
    ``bones[0]`` parented under the anchor role's mapped bone. These keys are
    written AFTER the FK roles of the same frame — the certified composition
    is untouched; appendage bones only. Frames absent from a track keep the
    previous chain key (constant interpolation, like FK).
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

    _Y = Vector((0.0, 1.0, 0.0))

    # P6-1: validate the secondary bindings up front (loud, actionable).
    # Chain bones are appendage bones ONLY — double-keying a role bone would
    # let the chain overwrite the certified FK keys.
    sec_bindings: list[tuple[str, dict[int, Any], list[str]]] = []
    sec_report: dict[str, dict[str, int]] = {}
    if secondary is not None:
        mapped_bones = {a.bone for a in mapping.assignments.values()}
        for track, bones in secondary:
            bones = list(bones)
            if not track.directions:
                raise ValueError(
                    f"secondary chain {track.name!r}: the track has no "
                    "frames (hint: the simulation never started — check the "
                    "action's anchor role coverage)"
                )
            if len(bones) != len(track.directions[0]):
                raise ValueError(
                    f"secondary chain {track.name!r}: {len(bones)} bone(s) "
                    f"for {len(track.directions[0])} link(s) (hint: the "
                    "binding must list exactly one bone per chain link)"
                )
            missing = [b for b in bones if b not in obj.pose.bones]
            if missing:
                raise ValueError(
                    f"secondary chain {track.name!r}: bones not on this "
                    f"armature: {', '.join(missing)}"
                )
            overlap = sorted(set(bones) & mapped_bones)
            if overlap:
                raise ValueError(
                    f"secondary chain {track.name!r}: bones are role-mapped "
                    f"(FK owns them): {', '.join(overlap)} (hint: chains key "
                    "appendage bones only, never canonical roles)"
                )
            anchor_assignment = mapping.assignments.get(track.anchor_role)
            if anchor_assignment is None:
                raise ValueError(
                    f"secondary chain {track.name!r}: anchor role "
                    f"{track.anchor_role!r} is not mapped on this rig"
                )
            first = obj.pose.bones[bones[0]]
            if first.parent is None or first.parent.name != anchor_assignment.bone:
                raise ValueError(
                    f"secondary chain {track.name!r}: bone {bones[0]!r} must "
                    f"be parented under {anchor_assignment.bone!r} (the "
                    f"{track.anchor_role} anchor) — the composition walks the "
                    "rig's own hierarchy"
                )
            for i, b in enumerate(bones[1:], start=1):
                pb = obj.pose.bones[b]
                if pb.parent is None or pb.parent.name != bones[i - 1]:
                    raise ValueError(
                        f"secondary chain {track.name!r}: bone {b!r} must be "
                        f"parented to {bones[i - 1]!r} (bindings are "
                        "parent-first along the chain)"
                    )
            by_frame = dict(zip(track.frames, track.directions, strict=True))
            sec_bindings.append((track.name, by_frame, bones))
            sec_report[track.name] = {"bones": len(bones), "keys": 0}

    # P2-5: source frame -> locked (foot role, interval index) list. BOTH
    # feet on double-support frames — a single (foot, idx) per frame would
    # silently unpin the other planted leg (caught by the P2-8 walk media
    # pipeline, where stance phases overlap).
    lock_at: dict[int, list[tuple[str, int]]] = {}
    if contacts is not None:
        for idx, interval in enumerate(contacts.intervals):
            for f in range(interval.start, interval.end + 1):
                lock_at.setdefault(f, []).append((interval.foot, idx))

    # Armature-space world matrix per bone, composed from the keyed bases and
    # carried across frames: W = P @ (Mp⁻¹ Mb) @ B equals exactly what the
    # fcurves evaluate to. Bones with no key yet sit at rest; bones absent
    # from a frame keep their previous world (constant interpolation).
    world_t: dict[str, Matrix] = {}
    # Per (foot, interval) plant capture: W per chain role, the ankle target,
    # and thigh/shin rest lengths for the 2-bone solve.
    world0: dict[tuple[str, int], dict[str, Any]] = {}

    action = bpy.data.actions.new(name)
    obj.animation_data_create()
    obj.animation_data.action = action

    baked: list[int] = []
    keys = 0
    locked_frames = 0
    lock_clamped = 0
    lock_dev_rad = 0.0
    worst_role = ""
    worst_rad = 0.0
    skipped: set[str] = set()

    def _chain_len(side: str, parent_base: str, child_base: str) -> float | None:
        """Rest segment length as the ACTUAL head-to-head distance between the
        two chain bones. NOT Bone.length: glTF-imported rigs (VRM/Mixamo glb)
        synthesize bone tails whose length is a convention — on the Mixamo glb
        it is ~100x the true segment, which poisoned the 2-bone solve (P2-8
        third-rig catch; metarig/seedsan tails happen to be sane)."""
        pa = mapping.assignments.get(parent_base + side)
        ca = mapping.assignments.get(child_base + side)
        if pa is None or ca is None:
            return None
        p_bone = obj.pose.bones.get(pa.bone)
        c_bone = obj.pose.bones.get(ca.bone)
        if p_bone is None or c_bone is None:
            return None
        return (c_bone.bone.head_local - p_bone.bone.head_local).length

    def _key(pb: Any, basis: Any, frame_no: int) -> None:
        axis, angle = basis.to_quaternion().to_axis_angle()
        if pb.rotation_mode != "AXIS_ANGLE":
            pb.rotation_mode = "AXIS_ANGLE"
        pb.rotation_axis_angle = (angle, axis.x, axis.y, axis.z)
        pb.keyframe_insert(data_path="rotation_axis_angle", frame=frame_no)

    def _compose(pb: Any, basis4: Any) -> Any:
        """World matrix of ``pb`` under ``basis4``: W = P @ (Mp⁻¹ Mb) @ B."""
        mb = pb.bone.matrix_local
        if pb.parent is None:
            return mb @ basis4
        mp = pb.parent.bone.matrix_local
        p_w = world_t.get(pb.parent.name, mp)  # unkeyed parent: at rest
        return p_w @ (mp.inverted() @ mb) @ basis4

    def _to_basis(pb: Any, w: Any) -> Any:
        """Inverse of _compose: the basis realizing world matrix ``w``."""
        mb = pb.bone.matrix_local
        if pb.parent is None:
            return mb.inverted() @ w
        mp = pb.parent.bone.matrix_local
        p_w = world_t.get(pb.parent.name, mp)
        return mb.inverted() @ mp @ p_w.inverted() @ w

    def _head(pb: Any) -> Any:
        """World position of the bone's head (independent of its own basis)."""
        mb = pb.bone.matrix_local
        if pb.parent is None:
            return mb.to_translation()
        mp = pb.parent.bone.matrix_local
        p_w = world_t.get(pb.parent.name, mp)
        return (p_w @ (mp.inverted() @ mb)).to_translation()

    def _aligned_world(pb: Any, head: Any, direction: Any) -> Any:
        """World matrix: head at ``head``, bone Y along ``direction``."""
        rest3 = pb.bone.matrix_local.to_3x3()
        q = (rest3 @ _Y).rotation_difference(direction)
        return Matrix.Translation(head) @ (q.to_matrix().to_4x4() @ rest3.to_4x4())

    def _solve_knee(head: Any, a0: Any, k_prov: Any, l1: float, l2: float) -> Any:
        """Knee placing the ankle at ``a0``: reachable point closest to the
        provisional ``k_prov`` (keeps the bend); unreachable targets are
        clamped along hip->ankle (counted). Returns (knee, clamped)."""
        d_vec = a0 - head
        d = d_vec.length
        clamped = 0
        ceil = (l1 + l2) * (1.0 - 1e-6)
        floor = max(abs(l1 - l2) * (1.0 + 1e-6), 1e-9)
        if d > ceil:
            a0 = head + d_vec * (ceil / d)
            d = ceil
            clamped = 1
        elif d < floor:
            if d > 1e-12:
                a0 = head + d_vec * (floor / d)
            else:
                a0 = head + Vector((0.0, 0.0, -floor))
            d = floor
            clamped = 1
        axis = (a0 - head) / d
        along = (l1 * l1 - l2 * l2 + d * d) / (2.0 * d)
        r = math.sqrt(max(l1 * l1 - along * along, 0.0))
        plane = head + axis * along
        pole = k_prov - plane
        pole = pole - axis * pole.dot(axis)
        if pole.length <= 1e-9:
            for fallback in (Vector((0.0, -1.0, 0.0)), Vector((0.0, 0.0, 1.0)),
                             Vector((1.0, 0.0, 0.0))):
                pole = fallback - axis * fallback.dot(axis)
                if pole.length > 1e-9:
                    break
        return plane + pole.normalized() * r, clamped

    for af in frames:
        frame_no = af.frame + frame_offset
        application = core.apply_canonical_pose(rig, mapping, af.pose)
        skipped.update(application.skipped)
        # FK fidelity is verified on the UNLOCKED application; the freeze is a
        # deliberate deviation and reports separately as lock_dev_deg.
        errors = core.verify_application(rig, application, af.pose)
        for role, rad in errors.items():
            if rad > worst_rad:
                worst_role, worst_rad = role, rad

        lock = lock_at.get(af.frame, ())
        roles_present = {rot.role for rot in application.rotations}
        caps: dict[str, dict[str, Any]] = {}
        for foot_role, idx in lock:
            side2 = foot_role[-2:]
            if all(
                f"{b}{side2}" in roles_present
                for b in ("upper_leg", "lower_leg", "foot")
            ):
                caps[side2] = world0.setdefault(
                    (foot_role, idx), {"W": {}, "A0": None, "l1": None, "l2": None}
                )
        pinned_any = False
        solved_knee: dict[str, Any] = {}  # per side: thigh solve -> shin reuse

        for rot in application.rotations:  # depth order: parents first
            pb = obj.pose.bones.get(rot.bone)
            if pb is None:
                continue
            mb = pb.bone.matrix_local
            rest3 = mb.to_3x3()
            world = Matrix.Rotation(float(rot.angle_rad), 3, Vector(rot.axis))
            final_basis = rest3.inverted() @ world @ rest3
            computed_q = final_basis.to_quaternion()
            final_world: Any = None
            base = rot.role.rsplit(".", 1)[0]
            side = rot.role[-2:] if rot.role.endswith((".L", ".R")) else ""
            cap = caps.get(side) if side else None
            is_chain = cap is not None and base in core.LOCK_CHAIN_BASES

            if is_chain:
                w0 = cap["W"].get(rot.role)
                if w0 is None:
                    # First locked frame of the interval: capture this
                    # frame's computed plant pose (parents key first, so
                    # their composed worlds are current). Keys stay computed.
                    w0 = _compose(pb, final_basis.to_4x4())
                    cap["W"][rot.role] = w0
                    if base == "foot":
                        cap["A0"] = w0.to_translation()
                    elif base == "lower_leg":
                        cap["l2"] = _chain_len(side, "lower_leg", "foot")
                    elif base == "upper_leg":
                        cap["l1"] = _chain_len(side, "upper_leg", "lower_leg")
                    pinned_any = True
                elif base == "upper_leg" and cap["l1"] is not None and cap["l2"] is not None:
                    k_prov_w = _compose(pb, final_basis.to_4x4())
                    k_prov = (
                        k_prov_w.to_3x3() @ Vector((0.0, cap["l1"], 0.0))
                        + k_prov_w.to_translation()
                    )
                    knee, clamped = _solve_knee(
                        _head(pb), cap["A0"], k_prov, cap["l1"], cap["l2"],
                    )
                    lock_clamped += clamped
                    solved_knee[side] = knee
                    dir_v = knee - _head(pb)
                    if dir_v.length > 1e-9:
                        final_world = _aligned_world(
                            pb, _head(pb), dir_v.normalized()
                        )
                        final_basis = _to_basis(pb, final_world).to_3x3()
                elif base == "lower_leg" and solved_knee.get(side) is not None:
                    a0 = cap["A0"]
                    dir_v = a0 - solved_knee[side]
                    if dir_v.length > 1e-9:
                        final_world = _aligned_world(
                            pb, solved_knee[side], dir_v.normalized()
                        )
                        final_basis = _to_basis(pb, final_world).to_3x3()
                elif base == "foot":
                    final_world = w0
                    final_basis = _to_basis(pb, w0).to_3x3()

                if final_world is not None:
                    pinned_any = True
                    q2 = final_basis.to_quaternion()
                    dot = max(-1.0, min(1.0, abs(computed_q.dot(q2))))
                    lock_dev_rad = max(lock_dev_rad, 2.0 * math.acos(dot))

            if final_world is None:
                final_world = _compose(pb, final_basis.to_4x4())
            _key(pb, final_basis, frame_no)
            keys += 1
            world_t[pb.name] = final_world

        # P6-1: secondary chains ride AFTER the FK roles of the same frame —
        # the certified composition is untouched; appendage bones only.
        for chain_name, by_frame, bones in sec_bindings:
            dirs = by_frame.get(af.frame)
            if dirs is None:
                continue  # chain not started at this frame: keep prior key
            for i, bone_name in enumerate(bones):
                pb = obj.pose.bones[bone_name]
                target = Vector(dirs[i])
                if target.length < 1e-9:
                    continue
                w = _aligned_world(pb, _head(pb), target)
                _key(pb, _to_basis(pb, w).to_3x3(), frame_no)
                keys += 1
                sec_report[chain_name]["keys"] += 1
                world_t[bone_name] = w

        if pinned_any:
            locked_frames += 1
        baked.append(frame_no)

    notes = [
        (
            "rotations only — no root motion (single-view solve is "
            "hip-anchored; baking world translation would be fabricated)"
        ),
    ]
    if contacts is not None:
        notes.append(
            "contacts lock: planted legs pinned to the interval-start world "
            "pose (2-bone ankle pin + held foot transform); deviation from "
            "the source pose = lock_dev_deg"
        )
        if locked_frames == 0:
            notes.append(
                "contacts lock: no baked frame fell inside a contact interval"
            )
    if sec_bindings:
        notes.append(
            "secondary motion: spring-chain tracks keyed onto appendage "
            "bones after the FK roles (docs/SECONDARY_MOTION.md; constants "
            "order-of-magnitude, declared untuned per D-008)"
        )

    return {
        "action": action.name,
        "baked_frames": baked,
        "keys": keys,
        "locked_frames": locked_frames,
        "lock_dev_deg": lock_dev_rad * _RAD_TO_DEG,
        "lock_clamped": lock_clamped,
        "worst_role": worst_role,
        "worst_deg": worst_rad * _RAD_TO_DEG,
        "skipped": sorted(skipped),
        "mapping_source": mapping_source,
        "secondary": {k: dict(v) for k, v in sorted(sec_report.items())},
        "notes": notes,
    }
