"""FK apply engine: canonical pose -> per-bone rotations for any mapped rig.

For every mapped role, the target world direction of its bone is read from
the canonical pose (bone direction = primary-child joint minus role joint).
The rotation that takes the rig bone's REST world direction to that target is
computed as a minimal axis-angle (roll-free — documented v1 simplification),
then expressed in the PARENT SPACE so children inherit: processed top-down,
each local rotation is pre-multiplied by the inverse of the accumulated
ancestor rotation. Unmapped ancestor bones contribute identity (they are
reported, not silently assumed straight).

Pure stdlib math (no Blender, no numpy); the add-on applies the resulting
payload to pose bones via bpy. Ordering is deterministic: chain depth, then
bone name. Zero-length bones and roles without a usable direction are
skipped with reasons — ambiguity is reported, never swallowed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .canonical import ALL_ROLES, PRIMARY_CHILD  # noqa: F401  (re-exported API)
from .canonical_pose import CanonicalPose, Vec3
from .linalg import v_dist, v_sub

Quaternion = tuple[float, float, float, float]  # (w, x, y, z)

# PRIMARY_CHILD lives in canonical.py (shared topology for solver/FK/review)
# and is re-exported here for compatibility with existing importers.


# -- quaternion helpers (stdlib) -------------------------------------------------

def q_identity() -> Quaternion:
    return (1.0, 0.0, 0.0, 0.0)


def q_mul(a: Quaternion, b: Quaternion) -> Quaternion:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def q_conj(q: Quaternion) -> Quaternion:
    return (q[0], -q[1], -q[2], -q[3])


def q_normalize(q: Quaternion) -> Quaternion:
    n = math.sqrt(sum(c * c for c in q))
    if n <= 1e-12:
        return q_identity()
    return (q[0] / n, q[1] / n, q[2] / n, q[3] / n)


def q_rotate(q: Quaternion, v: Vec3) -> Vec3:
    w, x, y, z = q
    # v' = q * (0, v) * conj(q), expanded (no intermediates allocated)
    uvx, uvy, uvz = 2.0 * (y * v[2] - z * v[1]), 2.0 * (z * v[0] - x * v[2]), 2.0 * (x * v[1] - y * v[0])
    return (
        v[0] + w * uvx + (y * uvz - z * uvy),
        v[1] + w * uvy + (z * uvx - x * uvz),
        v[2] + w * uvz + (x * uvy - y * uvx),
    )


def q_from_to(u: Vec3, v: Vec3) -> Quaternion:
    """Minimal rotation taking unit vector u onto unit vector v."""
    d = u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
    if d >= 1.0 - 1e-12:
        return q_identity()
    if d <= -1.0 + 1e-12:
        # Antiparallel: rotate 180 degrees about any perpendicular axis —
        # deterministic pick: the world axis least aligned with u.
        axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        axis = min(axes, key=lambda a: abs(a[0] * u[0] + a[1] * u[1] + a[2] * u[2]))
        return (0.0, axis[0], axis[1], axis[2])
    cx, cy, cz = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    return q_normalize((1.0 + d, cx, cy, cz))


def q_from_axis_angle(axis: Vec3, angle_rad: float) -> Quaternion:
    """Unit quaternion for a rotation by ``angle_rad`` about ``axis``
    (normalized here — the declared face-plan axes are unit, but a caller
    passing scaled axes must not corrupt the result)."""
    n = math.sqrt(sum(c * c for c in axis))
    if n <= 1e-12:
        return q_identity()
    x, y, z = axis[0] / n, axis[1] / n, axis[2] / n
    half = angle_rad / 2.0
    s = math.sin(half)
    return (math.cos(half), x * s, y * s, z * s)


def q_to_axis_angle(q: Quaternion) -> tuple[Vec3, float]:
    w, x, y, z = q_normalize(q)
    sin_half = math.sqrt(x * x + y * y + z * z)
    if sin_half <= 1e-12:
        return ((0.0, 0.0, 1.0), 0.0)
    angle = 2.0 * math.atan2(sin_half, w)
    return ((x / sin_half, y / sin_half, z / sin_half), angle)


def v_norm(a: Vec3) -> Vec3:
    n = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    if n <= 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0] / n, a[1] / n, a[2] / n)


# -- result model ----------------------------------------------------------------

@dataclass
class BoneRotation:
    """One bone's local (parent-space) axis-angle rotation."""

    bone: str
    role: str
    axis: Vec3  # unit axis, parent space
    angle_rad: float
    depth: int  # chain depth in the rig; part of the ordering key

    def to_dict(self) -> dict[str, object]:
        return {
            "bone": self.bone,
            "role": self.role,
            "axis": [round(v, 6) for v in self.axis],
            "angle_rad": round(self.angle_rad, 6),
            "angle_deg": round(math.degrees(self.angle_rad), 3),
            "depth": self.depth,
        }


@dataclass
class PoseApplication:
    """Ordered rotation payload plus honest skip/notes ledgers."""

    rotations: list[BoneRotation] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "rotations": [r.to_dict() for r in self.rotations],
            "skipped": list(self.skipped),
            "notes": list(self.notes),
        }


# -- engine -----------------------------------------------------------------------

def bone_target_direction(pose: CanonicalPose, role: str) -> Vec3 | None:
    """Canonical world direction of the role's bone (toward its chain child).

    Body roles read the frozen PRIMARY_CHILD topology / positions map;
    finger roles (the D-021 namespace, P8-3) read ``pose.hands`` through
    the additive FINGER topology — body behavior is untouched.
    """
    if role not in PRIMARY_CHILD:
        return _finger_target_direction(pose, role)
    child = PRIMARY_CHILD.get(role)
    if child is None or role not in pose.positions or child not in pose.positions:
        return None
    d = v_sub(pose.positions[child], pose.positions[role])
    n = v_dist(pose.positions[child], pose.positions[role])
    if n <= 1e-9:
        return None
    return (d[0] / n, d[1] / n, d[2] / n)


def _finger_target_direction(pose: CanonicalPose, role: str) -> Vec3 | None:
    """Direction of a finger SEGMENT role (mcp/pip/dip — the tip has no
    segment; it is the dip bone's endpoint data)."""
    from .fingers import FINGER_JOINTS, is_finger_role

    if not is_finger_role(role):
        return None
    parts = role.split(".")
    hand_key, finger, joint = f"{parts[0]}.{parts[1]}", parts[3], parts[4]
    idx = FINGER_JOINTS.index(joint)
    if idx >= len(FINGER_JOINTS) - 1:
        return None  # .tip: data only, no bone segment to orient
    hand = pose.hands.get(hand_key)
    if hand is None:
        return None
    chain = hand.fingers.get(finger)
    if chain is None:
        return None
    a = chain.joints[joint]
    b = chain.joints[FINGER_JOINTS[idx + 1]]
    d = v_sub(b, a)
    n = v_dist(b, a)
    if n <= 1e-9:
        return None
    return (d[0] / n, d[1] / n, d[2] / n)


def apply_canonical_pose(
    rig,
    mapping,
    pose: CanonicalPose,
    finger_map: dict[str, str] | None = None,
    face_bones: dict[str, str] | None = None,
    face_shape_keys: set[str] | None = None,
) -> PoseApplication:
    """Compute ordered per-bone rotations applying the pose to a mapped rig.

    ``rig`` is a :class:`riggermortis.types.RigData`, ``mapping`` a
    :class:`riggermortis.mapper.RigMapping` for the same rig. The returned
    rotations are in parent space, ordered by (chain depth, bone name), ready
    for the add-on / CLI / MCP to apply as axis-angle pose rotations.

    ``finger_map`` (P8-3, optional): finger role -> bone name, authored once
    per rig in the preset's ``hands`` bindings. ``None``/empty = no finger
    application; when the pose SOLVED hands and no map is given, the report
    carries the loud capability line — never a silent no-op.

    ``face_bones`` (P8-4, optional): face param -> bone name from the
    preset's ``face_bones`` bindings; bound bones rotate by the DECLARED
    FACE_BONE_PLAN axis-angle (param value x max angle), joining the same
    top-down parent-space pass. ``face_shape_keys`` (P8-4, optional): the
    NAMES of the convention shape keys the caller resolved on the live
    mesh — core accounting only (the add-on applies the values). When the
    pose solved face params and NEITHER class is present, the report
    carries the loud no-facial-targets line — never a silent no-op.
    """
    app = PoseApplication()
    if not pose.reliable:
        app.notes.append(
            f"pose confidence {pose.confidence:.2f} below the reliable bar — "
            "applying anyway; review the result"
        )

    # Role -> bone for mapped roles that have a usable target direction.
    wanted: dict[str, str] = {}
    for role in sorted(mapping.assignments):
        if role not in ALL_ROLES:
            continue
        bone = mapping.assignments[role].bone
        if bone not in rig.bones:
            app.skipped.append(f"{role}: mapped bone {bone!r} missing from rig")
            continue
        target = bone_target_direction(pose, role)
        if target is None:
            app.notes.append(f"{role}: leaf or chain-child unavailable; follows parent")
            continue
        wanted[role] = bone

    # Fingers (additive): validate loudly, join the same top-down pass.
    if finger_map:
        from .fingers import is_finger_role

        for role in sorted(finger_map):
            if not is_finger_role(role):
                raise ValueError(
                    f"finger binding key {role!r} is not a finger role "
                    "(hint: finger roles look like hand.L.finger.index.mcp "
                    "— docs/FINGERS.md, D-021)"
                )
            if role.endswith(".tip"):
                raise ValueError(
                    f"finger role {role!r} cannot bind: the tip is the dip "
                    "bone's endpoint, not a segment "
                    "(hint: bind the mcp/pip/dip segment roles only)"
                )
        if not pose.hands:
            app.notes.append(
                "finger bindings present but the pose carries no hands — "
                "nothing to apply"
            )
        for role in sorted(finger_map):
            bone = finger_map[role]
            if bone not in rig.bones:
                app.skipped.append(f"{role}: bound bone {bone!r} missing from rig")
                continue
            if bone in wanted.values():
                app.skipped.append(
                    f"{role}: bound bone {bone!r} already carries body role "
                    "mapping — a bone implements ONE segment"
                )
                continue
            if bone_target_direction(pose, role) is None:
                continue  # hand/finger unsolved in this pose — ledgered in the pose itself
            wanted[role] = bone
    elif pose.hands:
        n = sum(len(h.fingers) for h in pose.hands.values())
        app.notes.append(
            f"hands: {n} finger chain(s) solved; no finger bindings for this "
            "rig — fingers not applied"
        )

    # Face (additive, P8-4): validate loudly, join the same top-down pass —
    # bound bones take the DECLARED axis-angle instead of a direction target.
    face_wanted: dict[str, str] = {}
    if face_bones:
        from .face import is_face_param

        for param in sorted(face_bones):
            if not is_face_param(param):
                raise ValueError(
                    f"face binding key {param!r} is not a face param "
                    "(hint: params look like jaw.open or brow.raise.L "
                    "— docs/FACE.md, D-022)"
                )
        if pose.face is None:
            app.notes.append(
                "face bindings present but the pose carries no solved face — "
                "nothing to apply"
            )
        for param in sorted(face_bones):
            bone = face_bones[param]
            if bone not in rig.bones:
                app.skipped.append(f"face: {param}: bound bone {bone!r} missing from rig")
                continue
            if bone in wanted.values() or bone in face_wanted.values():
                app.skipped.append(
                    f"face: {param}: bound bone {bone!r} already carries a "
                    "body/finger/face binding — a bone implements ONE target"
                )
                continue
            if pose.face is not None and param not in pose.face.params:
                app.skipped.append(
                    f"face: param {param!r} not solved (ledgered in the pose) — "
                    "bone untouched"
                )
                continue
            face_wanted[param] = bone
    elif pose.face is not None:
        if face_shape_keys:
            app.notes.append(
                f"face: {len(pose.face.params)} expression param(s) solved; "
                f"{len(face_shape_keys)} convention shape key(s) resolved "
                "(values applied by the caller)"
            )
        else:
            app.notes.append(
                f"face: {len(pose.face.params)} expression param(s) solved; "
                "no facial targets for this rig — face not applied"
            )

    if not wanted and not face_wanted:
        app.notes.append("no applicable roles: nothing to rotate")
        return app

    # Top-down order: chain depth, then bone name (deterministic).
    order = sorted(set(wanted.values()) | set(face_wanted.values()),
                   key=lambda b: (rig.chain_depth(b), b))
    role_of_bone = {b: r for r, b in wanted.items()}
    param_of_bone = {b: p for p, b in face_wanted.items()}
    ancestor_rot: dict[str, Quaternion] = {}

    from .face import FACE_BONE_PLAN  # deferred: face is sibling-pure

    for bone in order:
        bdef = rig.bones[bone]
        parent = bdef.parent
        if parent is not None and parent in ancestor_rot:
            anc = ancestor_rot[parent]
        elif parent is not None and parent in rig.bones and parent not in order:
            # Unmapped ancestor between mapped bones: identity, but say so once.
            anc = q_identity()
            app.notes.append(
                f"ancestor bone {parent!r} is unmapped and stays at rest; "
                f"{role_of_bone.get(bone, param_of_bone.get(bone, bone))}'s "
                "target assumes it does not move"
            )
        else:
            anc = q_identity()
        if bone in param_of_bone:
            # Declared face rotation: canonical axis x (param x max angle).
            param = param_of_bone[bone]
            axis_plan, max_deg = FACE_BONE_PLAN[param]
            value = pose.face.params[param] if pose.face is not None else 0.0
            world = q_from_axis_angle(axis_plan, math.radians(max_deg) * value)
            local = q_mul(q_conj(anc), world)
            ancestor_rot[bone] = world
            axis, angle = q_to_axis_angle(local)
            app.rotations.append(
                BoneRotation(
                    bone=bone,
                    role=param,
                    axis=axis,
                    angle_rad=angle,
                    depth=rig.chain_depth(bone),
                )
            )
            continue
        assert bone in role_of_bone  # order is the union of the two maps
        rest = v_norm(v_sub(bdef.tail, bdef.head))
        if math.dist(rest, (0.0, 0.0, 0.0)) <= 1e-9:
            app.skipped.append(f"{role_of_bone[bone]}: zero-length bone {bone!r}")
            continue
        target = bone_target_direction(pose, role_of_bone[bone])
        assert target is not None  # filtered above
        world = q_from_to(rest, target)
        local = q_mul(q_conj(anc), world)
        ancestor_rot[bone] = world
        axis, angle = q_to_axis_angle(local)
        app.rotations.append(
            BoneRotation(
                bone=bone,
                role=role_of_bone[bone],
                axis=axis,
                angle_rad=angle,
                depth=rig.chain_depth(bone),
            )
        )
    app.rotations.sort(key=lambda r: (r.depth, r.bone))
    return app


def verify_application(rig, app: PoseApplication, pose: CanonicalPose) -> dict[str, float]:
    """Kinematic check: simulate FK and report per-role angle error (radians).

    Simulates exactly what Blender will do — accumulate parent-space local
    rotations down each mapped chain and compare resulting bone world
    directions with the canonical targets.
    """
    world: dict[str, Quaternion] = {}
    errors: dict[str, float] = {}
    for rot in app.rotations:
        bdef = rig.bones[rot.bone]
        rest = v_norm(v_sub(bdef.tail, bdef.head))
        parent = bdef.parent
        anc = world.get(parent, q_identity()) if parent else q_identity()
        local = q_normalize(
            (
                math.cos(rot.angle_rad / 2.0),
                rot.axis[0] * math.sin(rot.angle_rad / 2.0),
                rot.axis[1] * math.sin(rot.angle_rad / 2.0),
                rot.axis[2] * math.sin(rot.angle_rad / 2.0),
            )
        )
        w = q_mul(anc, local)
        world[rot.bone] = w
        target = bone_target_direction(pose, rot.role)
        if target is None:
            continue
        achieved = q_rotate(w, rest)
        dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(achieved, target, strict=False))))
        errors[rot.role] = math.acos(dot)
    return errors
