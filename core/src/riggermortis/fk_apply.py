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

from .canonical import ALL_ROLES
from .canonical_pose import CanonicalPose, Vec3
from .linalg import v_dist, v_sub

Quaternion = tuple[float, float, float, float]  # (w, x, y, z)

#: The canonical chain child that defines each role's bone direction. Roles
#: without an entry (hands, toes, head) are leaves — their orientation comes
#: from their parent's rotation; the review overlay can refine later.
PRIMARY_CHILD: dict[str, str] = {
    "hips": "spine",
    "spine": "chest",
    "chest": "neck",
    "neck": "head",
}
for _base, _child in (
    ("shoulder", "upper_arm"),
    ("upper_arm", "forearm"),
    ("forearm", "hand"),
    ("upper_leg", "lower_leg"),
    ("lower_leg", "foot"),
    ("foot", "toe"),
):
    for _side in (".L", ".R"):
        PRIMARY_CHILD[f"{_base}{_side}"] = f"{_child}{_side}"


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
    """Canonical world direction of the role's bone (toward its chain child)."""
    child = PRIMARY_CHILD.get(role)
    if child is None or role not in pose.positions or child not in pose.positions:
        return None
    d = v_sub(pose.positions[child], pose.positions[role])
    n = v_dist(pose.positions[child], pose.positions[role])
    if n <= 1e-9:
        return None
    return (d[0] / n, d[1] / n, d[2] / n)


def apply_canonical_pose(rig, mapping, pose: CanonicalPose) -> PoseApplication:
    """Compute ordered per-bone rotations applying the pose to a mapped rig.

    ``rig`` is a :class:`riggermortis.types.RigData`, ``mapping`` a
    :class:`riggermortis.mapper.RigMapping` for the same rig. The returned
    rotations are in parent space, ordered by (chain depth, bone name), ready
    for the add-on / CLI / MCP to apply as axis-angle pose rotations.
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

    if not wanted:
        app.notes.append("no applicable roles: nothing to rotate")
        return app

    # Top-down order: chain depth, then bone name (deterministic).
    order = sorted(wanted.values(), key=lambda b: (rig.chain_depth(b), b))
    role_of_bone = {b: r for r, b in wanted.items()}
    ancestor_rot: dict[str, Quaternion] = {}

    for bone in order:
        bdef = rig.bones[bone]
        rest = v_norm(v_sub(bdef.tail, bdef.head))
        if math.dist(rest, (0.0, 0.0, 0.0)) <= 1e-9:
            app.skipped.append(f"{role_of_bone[bone]}: zero-length bone {bone!r}")
            continue
        target = bone_target_direction(pose, role_of_bone[bone])
        assert target is not None  # filtered above
        world = q_from_to(rest, target)
        parent = bdef.parent
        if parent is not None and parent in ancestor_rot:
            anc = ancestor_rot[parent]
        elif parent is not None and parent in rig.bones and parent not in order:
            # Unmapped ancestor between mapped bones: identity, but say so once.
            anc = q_identity()
            app.notes.append(
                f"ancestor bone {parent!r} is unmapped and stays at rest; "
                f"{role_of_bone[bone]}'s target assumes it does not move"
            )
        else:
            anc = q_identity()
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
