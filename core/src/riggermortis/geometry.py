"""Geometry analysis: bone directions, chain topology, proportion priors.

Geometry does two jobs in the mapper: it validates/corrects name-based
assignments (a "LeftLeg" that points sideways is suspect) and it carries the
mapping for rigs with opaque names, where the skeleton's shape is all we have.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .canonical import RoleDef
from .linalg import Vec3, v_dot, v_len, v_norm, v_sub
from .types import RigData

DEFAULT_HIP_HEIGHT_FRAC = 0.55


@dataclass
class BoneFeatures:
    name: str
    parent: str | None
    direction: Vec3  # unit; zero vector for zero-length bones
    length: float
    length_frac: float  # length / hip height
    head_z: float
    tail_z: float
    head_z_frac: float  # head height / rig height
    tail_z_frac: float
    depth: int
    n_children: int
    is_leaf: bool
    x_offset: float  # head x relative to the rig's x center


@dataclass
class RigFeatures:
    height: float
    hip_height: float
    x_center: float
    bones: dict[str, BoneFeatures] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)


def analyze(rig: RigData, hip_height_frac: float = DEFAULT_HIP_HEIGHT_FRAC) -> RigFeatures:
    points = [p for b in rig.bones.values() for p in (b.head, b.tail)]
    z_min = min(p[2] for p in points)
    z_max = max(p[2] for p in points)
    height = max(z_max - z_min, 1e-6)
    x_center = sum(p[0] for p in points) / len(points)
    feats = RigFeatures(height=height, hip_height=height * hip_height_frac, x_center=x_center)

    depths: dict[str, int] = {}

    def depth_of(name: str, guard: frozenset[str] = frozenset()) -> int:
        if name in depths:
            return depths[name]
        bone = rig.bones[name]
        if bone.parent is None or bone.parent not in rig.bones or bone.parent in guard:
            depths[name] = 0
            return 0
        d = 1 + depth_of(bone.parent, guard | {name})
        depths[name] = d
        return d

    for name in rig.sorted_bone_names():
        b = rig.bones[name]
        vec = v_sub(b.tail, b.head)
        length = v_len(vec)
        children = rig.children(name)
        feats.bones[name] = BoneFeatures(
            name=name,
            parent=b.parent,
            direction=v_norm(vec),
            length=length,
            length_frac=length / feats.hip_height,
            head_z=b.head[2],
            tail_z=b.tail[2],
            head_z_frac=(b.head[2] - z_min) / height,
            tail_z_frac=(b.tail[2] - z_min) / height,
            depth=depth_of(name),
            n_children=len(children),
            is_leaf=len(children) == 0,
            x_offset=b.head[0] - x_center,
        )
    feats.children = {name: rig.children(name) for name in rig.sorted_bone_names()}
    return feats


def direction_agreement(d: Vec3, target: Vec3) -> float:
    dot = v_dot(d, target)
    return (dot + 1.0) / 2.0


def length_agreement(length_frac: float, role: RoleDef, sigma: float = 0.45) -> float:
    if role.length_ratio <= 0:
        return 0.5
    ratio = max(length_frac / role.length_ratio, 1e-6)
    return math.exp(-0.5 * (math.log(ratio) / sigma) ** 2)


def height_agreement(z_frac: float, role: RoleDef, falloff: float = 0.15) -> float:
    if role.height_band is None:
        return 0.5
    lo, hi = role.height_band
    if lo <= z_frac <= hi:
        return 1.0
    dist = lo - z_frac if z_frac < lo else z_frac - hi
    return max(0.0, 1.0 - dist / falloff)


def geometry_score(bf: BoneFeatures, role: RoleDef) -> float:
    """How well a bone's shape matches a canonical role, in 0..1.

    Zero-direction roles (root) score a neutral 0.5.
    """
    if role.role == "root":
        return 0.5
    zero_len = bf.length <= 1e-9
    dir_score = 0.5 if zero_len else direction_agreement(bf.direction, role.direction)
    len_score = length_agreement(bf.length_frac, role)
    h_score = height_agreement(bf.head_z_frac, role)
    return 0.4 * dir_score + 0.3 * len_score + 0.3 * h_score


def side_sign(bf: BoneFeatures) -> str:
    """Character-left (+X) / right (-X) / center by x offset."""
    if bf.x_offset > 0.01:
        return "L"
    if bf.x_offset < -0.01:
        return "R"
    return "C"


def branch_nodes(rig: RigData) -> list[str]:
    return sorted(name for name in rig.sorted_bone_names() if len(rig.children(name)) >= 2)


def upward_chain(rig: RigData, feats: RigFeatures, start: str) -> list[str]:
    """Walk upward from ``start`` through single-child parents with up-pointing bones."""
    chain = [start]
    cur = start
    while True:
        bone = rig.bones[cur]
        parent = bone.parent
        if parent is None or parent not in rig.bones:
            break
        pf = feats.bones[parent]
        if pf.direction[2] < 0.5 or feats.children[parent] != [cur]:
            break
        chain.append(parent)
        cur = parent
    return chain  # bottom -> top
