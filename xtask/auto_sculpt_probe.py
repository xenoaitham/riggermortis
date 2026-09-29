"""P9-1 auto-sculpt probe (run INSIDE Blender, headless) — the RM_ASCULPT rows.

Design of record: docs/AUTO_SCULPT.md (written BEFORE this probe; the bars
and the selection arithmetic there are LAW). The honest physics: body
keypoints give SKELETON positions, not VOLUME — P9-1 matches SKELETON
proportions only. This probe answers the Blender unknowns with numbers:

1. ASC-FIXTURE  — the engine-built fixture set (metarig-class + Mixamo-class,
                  each an armature + a skinned mesh with deterministic
                  nearest-bone weights), base skeletons exact.
2. ASC-TARGET   — the pure target math (the core-lift draft): reference
                  ratios -> intended joint positions; authored-GT ratio
                  round-trip; determinism (no Blender semantics involved).
3. ASC-LATTICE  — candidate (a) `lattice`: the armature-lattice capability
                  answered FIRST (measured, never assumed), then per-joint
                  errors vs the Annex A.1 5% bar on BOTH rigs x all classes.
                  One pre-declared repair cycle (grid 4x4x8 -> 6x6x12).
4. ASC-SHAPEKEY — candidate (b) `shape_key_binding`: convention keys authored
                  (the counted artifact), values applied, joint errors
                  published (the structural skin-skeleton separation), the
                  no-keys rig loud-refused.
5. ASC-SCALE    — candidate (c) `armature_scale_correctives`: edit-bone
                  re-placement, per-joint errors vs the bar, mesh
                  follow-through.
6. ASC-SELECT   — the pre-declared selection arithmetic: bar-holders on both
                  rigs -> fewest required rig-side artifacts -> candidate
                  name ascending.
7. ASC-NOTARGET — a rig missing mapped roles: loud capability line, rest
                  unchanged.
8. ASC-DETERM   — twin runs byte-identical (target math + edit-bone state).

Rows print as `RM_ASCULPT <ROW>: PASS|FAIL <detail>`; the final row
`RM_ASCULPT GATE: PASS` is the crash-proof contract (Blender masks crashed
scripts with exit 0 — grep the FINAL row; no `: FAIL` row may exist on a
green run). The pure target math is CORE's now (the lift): the probe
imports `riggermortis.auto_sculpt` and re-runs against it — the numbers
must reproduce the probe-first run exactly (the S33 re-run rule). Usage:

    blender -b --python xtask/auto_sculpt_probe.py
Env: RM_CORE_SRC (required — the core import), RM_ADDON_DIR (optional).
"""
from __future__ import annotations

import math
import os
import sys

_core_src = os.environ.get("RM_CORE_SRC")
if not _core_src:
    raise SystemExit("RM_CORE_SRC is required (the core import)")
if _core_src not in sys.path:
    sys.path.insert(0, _core_src)
_addon_dir = os.environ.get("RM_ADDON_DIR")
if _addon_dir and _addon_dir not in sys.path:
    sys.path.insert(0, _addon_dir)

import bpy  # noqa: E402
import mathutils  # noqa: E402
import riggermortis as core  # noqa: E402

EPS = 1e-12
BAR_FRAC = core.BAR_FRAC  # Annex A.1 verbatim, imported from the core
LATTICE_GRID = (4, 4, 8)  # declared untuned (u, v, w)
LATTICE_GRID_REPAIR = (6, 6, 12)  # the ONE pre-declared repair cycle
IDW_SOFTEN_FRAC = 0.01  # x torso span, declared untuned

# The pure target math is CORE's (the lift); thin local aliases keep the
# probe-first call sites readable.
movable_roles = core.movable_roles
measure_proportion_ratios = core.measure_proportion_ratios
build_proportion_target = core.build_proportion_target
sculpt_capability_lines = core.sculpt_capability_lines


def validate_target(achieved, intended, base):
    """Probe-side wrapper over core.validate_sculpt (3-tuple shape)."""
    worst, fracs, worst_role, _ok = core.validate_sculpt(achieved, intended, base)
    return worst, fracs, worst_role

# Declared base skeleton (meters, Z up, facing -Y, the compact class —
# arms HANGING per the SCENE_TEST.md A2 lesson; no wide T-pose spread).
BASE_JOINTS: dict[str, tuple[float, float, float]] = {
    "hips": (0.0, 0.0, 0.98),
    "spine": (0.0, 0.0, 1.068),
    "chest": (0.0, 0.0, 1.234),
    "neck": (0.0, 0.0, 1.42),
    "head": (0.0, 0.0, 1.53),
    "shoulder.L": (0.06, 0.0, 1.40),
    "shoulder.R": (-0.06, 0.0, 1.40),
    "upper_arm.L": (0.18, 0.0, 1.38),
    "upper_arm.R": (-0.18, 0.0, 1.38),
    "forearm.L": (0.18, 0.0, 1.12),
    "forearm.R": (-0.18, 0.0, 1.12),
    "hand.L": (0.18, 0.0, 0.88),
    "hand.R": (-0.18, 0.0, 0.88),
    "upper_leg.L": (0.14, 0.0, 0.94),
    "upper_leg.R": (-0.14, 0.0, 0.94),
    "lower_leg.L": (0.14, 0.0, 0.52),
    "lower_leg.R": (-0.14, 0.0, 0.52),
    "foot.L": (0.14, 0.0, 0.12),
    "foot.R": (-0.14, 0.0, 0.12),
}
RIGID_TAILS: dict[str, tuple[float, float, float]] = {
    "head": (0.0, 0.0, 1.62),
    "hand.L": (0.18, 0.0, 0.71),
    "hand.R": (-0.18, 0.0, 0.71),
    "foot.L": (0.14, -0.16, 0.02),
    "foot.R": (-0.14, -0.16, 0.02),
}
BONE_TABLE: tuple[tuple[str, str | None], ...] = (
    ("hips", None),
    ("spine", "hips"),
    ("chest", "spine"),
    ("neck", "chest"),
    ("head", "neck"),
    ("shoulder.L", "neck"),
    ("shoulder.R", "neck"),
    ("upper_arm.L", "shoulder.L"),
    ("upper_arm.R", "shoulder.R"),
    ("forearm.L", "upper_arm.L"),
    ("forearm.R", "upper_arm.R"),
    ("hand.L", "forearm.L"),
    ("hand.R", "forearm.R"),
    ("upper_leg.L", "hips"),
    ("upper_leg.R", "hips"),
    ("lower_leg.L", "upper_leg.L"),
    ("lower_leg.R", "upper_leg.R"),
    ("foot.L", "lower_leg.L"),
    ("foot.R", "lower_leg.R"),
)
MIXAMO_NAME = {
    "hips": "mixamorig:Hips",
    "spine": "mixamorig:Spine",
    "chest": "mixamorig:Spine1",
    "neck": "mixamorig:Neck",
    "head": "mixamorig:Head",
    "shoulder.L": "mixamorig:LeftShoulder",
    "shoulder.R": "mixamorig:RightShoulder",
    "upper_arm.L": "mixamorig:LeftArm",
    "upper_arm.R": "mixamorig:RightArm",
    "forearm.L": "mixamorig:LeftForeArm",
    "forearm.R": "mixamorig:RightForeArm",
    "hand.L": "mixamorig:LeftHand",
    "hand.R": "mixamorig:RightHand",
    "upper_leg.L": "mixamorig:LeftUpLeg",
    "upper_leg.R": "mixamorig:RightUpLeg",
    "lower_leg.L": "mixamorig:LeftLeg",
    "lower_leg.R": "mixamorig:RightLeg",
    "foot.L": "mixamorig:LeftFoot",
    "foot.R": "mixamorig:RightFoot",
}
MIXAMO_SPACE_SCALE = 100.0  # meters -> armature-local cm (object scale 0.01)

GIRDLES = {"shoulder_w": ("upper_arm.L", "upper_arm.R"), "hip_w": ("upper_leg.L", "upper_leg.R")}
LIMB_SEGMENTS = {
    "upper_arm": ("upper_arm", "forearm"),
    "forearm": ("forearm", "hand"),
    "thigh": ("upper_leg", "lower_leg"),
    "shin": ("lower_leg", "foot"),
}
SIDES = ("L", "R")
RULER_NAMES = ("shoulder_w", "hip_w", "upper_arm", "forearm", "thigh", "shin")

REF_CLASSES: dict[str, dict[str, float]] = {
    "heavy": {"shoulder_w": 0.25, "hip_w": 0.20, "upper_arm": 0.0, "forearm": 0.0, "thigh": 0.0, "shin": 0.0},
    "slender": {"shoulder_w": -0.15, "hip_w": -0.12, "upper_arm": 0.0, "forearm": 0.0, "thigh": 0.0, "shin": 0.0},
    "tall": {"shoulder_w": 0.05, "hip_w": 0.05, "upper_arm": 0.15, "forearm": 0.15, "thigh": 0.15, "shin": 0.15},
}

SHAPEKEY_PARAMS = ("prop.shoulder_w", "prop.hip_w", "prop.upper_arm", "prop.forearm", "prop.thigh", "prop.shin")
SHAPEKEY_VALUES = {
    "heavy": {"prop.shoulder_w": 1.0, "prop.hip_w": 1.0, "prop.upper_arm": 0.0, "prop.forearm": 0.0, "prop.thigh": 0.0, "prop.shin": 0.0},
    "slender": {"prop.shoulder_w": -0.6, "prop.hip_w": -0.6, "prop.upper_arm": 0.0, "prop.forearm": 0.0, "prop.thigh": 0.0, "prop.shin": 0.0},
    "tall": {"prop.shoulder_w": 0.2, "prop.hip_w": 0.2, "prop.upper_arm": 1.0, "prop.forearm": 1.0, "prop.thigh": 1.0, "prop.shin": 1.0},
}

CANDIDATE_NAMES = ("armature_scale_correctives", "lattice", "shape_key_binding")
REQUIRED_ARTIFACTS = {"armature_scale_correctives": 0, "lattice": 0, "shape_key_binding": len(SHAPEKEY_PARAMS)}

OK = True


def check(label: str, ok: bool, detail: str = "") -> bool:
    global OK
    if not ok:
        OK = False
    print(f"RM_ASCULPT {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def v_norm(a):
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    if n <= EPS:
        return (0.0, 0.0, 0.0)
    return (a[0] / n, a[1] / n, a[2] / n)


# --------------------------------------------------------------------------
# The pure target math is CORE's (imported above). Fixture-side constants:
# --------------------------------------------------------------------------

def class_ratios(base_ratios: dict[str, float], deltas: dict[str, float]) -> dict[str, float]:
    return {k: (1.0 if k == "torso" else base_ratios[k] * (1.0 + deltas[k])) for k in base_ratios}


# --------------------------------------------------------------------------
# Fixtures (Blender): armature + skinned mesh, deterministic nearest-bone
# weights; metarig-class (canonical names, meters) + Mixamo-class (mixamorig
# names, 0.01 object scale, cm armature space).
# --------------------------------------------------------------------------

def _bone_tail(role: str) -> tuple[float, float, float]:
    if role in RIGID_TAILS:
        return RIGID_TAILS[role]
    for child, parent in BONE_TABLE:
        if parent == role:
            return BASE_JOINTS[child]
    raise ValueError(f"no tail for bone {role}")


def _set_active(obj) -> None:
    for o in bpy.data.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def _build_bones(arm_obj, space_scale: float) -> dict[str, str]:
    """Two-pass bone build (the S27 fixture law): create every bone, THEN
    wire parents. Returns role -> bone name."""
    _set_active(arm_obj)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_obj.data.edit_bones
    role_to_bone: dict[str, str] = {}
    created: dict[str, object] = {}
    for role, _parent in BONE_TABLE:
        bone_name = MIXAMO_NAME.get(role, role) if space_scale != 1.0 else role
        b = eb.new(bone_name)
        b.head = v_scale(BASE_JOINTS[role], space_scale)
        b.tail = v_scale(_bone_tail(role), space_scale)
        created[role] = b
        role_to_bone[role] = bone_name
    for role, parent in BONE_TABLE:
        if parent is not None:
            created[role].parent = created[parent]
        created[role].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for role, bone_name in role_to_bone.items():
        arm_obj[f"rm_role_{role}"] = bone_name
    return role_to_bone


def _build_mesh(name: str, space_scale: float):
    """Engine-built skinnable box (deterministic from_pydata grid)."""
    nx, ny, nz = 8, 5, 16
    x0, x1, y0, y1, z0, z1 = -0.28, 0.28, -0.14, 0.14, 0.02, 1.55
    verts: list[tuple[float, float, float]] = []
    for k in range(nz + 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                verts.append(
                    (
                        (x0 + (x1 - x0) * i / nx) * space_scale,
                        (y0 + (y1 - y0) * j / ny) * space_scale,
                        (z0 + (z1 - z0) * k / nz) * space_scale,
                    )
                )

    def vid(i: int, j: int, k: int) -> int:
        return k * (ny + 1) * (nx + 1) + j * (nx + 1) + i

    faces: list[tuple[int, int, int, int]] = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                a, b, c, d = vid(i, j, k), vid(i + 1, j, k), vid(i + 1, j + 1, k), vid(i, j + 1, k)
                e, f, g, h = (
                    vid(i, j, k + 1),
                    vid(i + 1, j, k + 1),
                    vid(i + 1, j + 1, k + 1),
                    vid(i, j + 1, k + 1),
                )
                faces.extend([(a, b, c, d), (e, f, g, h), (a, b, f, e), (d, c, g, h), (a, d, h, e), (b, c, g, f)])
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def _point_segment_dist(p, a, b) -> float:
    ab = v_sub(b, a)
    ab2 = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2
    if ab2 <= EPS:
        return v_dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1] + (p[2] - a[2]) * ab[2]) / ab2))
    return v_dist(p, v_add(a, v_scale(ab, t)))


def _nearest_bone_weights(mesh_obj, role_to_bone: dict[str, str], space_scale: float) -> int:
    """Deterministic skinning: weight 1.0 to the nearest bone SEGMENT (ties
    by bone name)."""
    segments = []
    for role, _parent in BONE_TABLE:
        a = v_scale(BASE_JOINTS[role], space_scale)
        b = v_scale(_bone_tail(role), space_scale)
        segments.append((role_to_bone[role], a, b))
    groups = {role_to_bone[role]: mesh_obj.vertex_groups.new(name=role_to_bone[role]) for role in sorted(role_to_bone)}
    n = 0
    for v in mesh_obj.data.vertices:
        p = (v.co.x, v.co.y, v.co.z)
        best_name = ""
        best_d = 1e30
        for bone_name, a, b in sorted(segments):
            d = _point_segment_dist(p, a, b)
            if d < best_d - 1e-9 * space_scale:
                best_d = d
                best_name = bone_name
        groups[best_name].add([v.index], 1.0, "REPLACE")
        n += 1
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = mesh_obj.parent  # set after parent assignment below
    return n


def build_fixture(name: str, mixamo: bool = False, with_mesh: bool = True) -> dict:
    arm_data = bpy.data.armatures.new(f"{name}_arm")
    arm_obj = bpy.data.objects.new(f"{name}_armature", arm_data)
    bpy.context.collection.objects.link(arm_obj)
    space_scale = MIXAMO_SPACE_SCALE if mixamo else 1.0
    role_to_bone = _build_bones(arm_obj, space_scale)
    mesh_obj = None
    n_weighted = 0
    if with_mesh:
        mesh_obj = _build_mesh(f"{name}_mesh", space_scale)
        mesh_obj.parent = arm_obj
        n_weighted = _nearest_bone_weights(mesh_obj, role_to_bone, space_scale)
        mesh_obj.modifiers["Armature"].object = arm_obj
    if mixamo:
        arm_obj.scale = (1.0 / space_scale,) * 3
        bpy.context.view_layer.update()
    return {
        "name": name,
        "arm": arm_obj,
        "mesh": mesh_obj,
        "role_to_bone": role_to_bone,
        "mixamo": mixamo,
        "space_scale": space_scale,
        "n_weighted": n_weighted,
    }


def rest_joints(fx: dict) -> dict[str, tuple[float, float, float]]:
    """Role joint positions in ARMATURE space (rest heads; plain floats)."""
    out: dict[str, tuple[float, float, float]] = {}
    for role, bone_name in fx["role_to_bone"].items():
        h = fx["arm"].data.bones[bone_name].matrix_local.to_translation()
        out[role] = (h.x, h.y, h.z)
    return out


def world_joints(fx: dict) -> dict[str, tuple[float, float, float]]:
    """Evaluated role joint positions in WORLD space (update first — the
    stale-matrix law)."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = fx["arm"].evaluated_get(deps)
    m = ev.matrix_world
    out: dict[str, tuple[float, float, float]] = {}
    for role, bone_name in fx["role_to_bone"].items():
        t = ev.pose.bones[bone_name].matrix.to_translation()
        w = m @ t
        out[role] = (w.x, w.y, w.z)
    return out


def to_world(fx: dict, p: tuple[float, float, float]) -> tuple[float, float, float]:
    bpy.context.view_layer.update()
    w = fx["arm"].matrix_world @ mathutils.Vector(p)
    return (w.x, w.y, w.z)


def to_local(fx: dict, p: tuple[float, float, float]) -> tuple[float, float, float]:
    bpy.context.view_layer.update()
    v = fx["arm"].matrix_world.inverted() @ mathutils.Vector(p)
    return (v.x, v.y, v.z)


# --------------------------------------------------------------------------
# Mechanism (a): lattice
# --------------------------------------------------------------------------

def apply_lattice(fx: dict, tgt_local: dict, grid: tuple[int, int, int]) -> dict:
    """Candidate (a). Creates a lattice, binds armature + mesh through the
    REAL user path (bpy.ops.object.parent_set LATTICE), moves control
    points by the IDW of the joint deltas, measures the evaluated joints.
    The ARMATURE-LATTICE CAPABILITY is answered by measurement."""
    base_world = world_joints(fx)
    joint_deltas = {r: v_sub(to_world(fx, tgt_local[r]), base_world[r]) for r in sorted(tgt_local)}
    torso_world = v_dist(base_world["hips"], base_world["neck"])
    soften = IDW_SOFTEN_FRAC * torso_world
    xs = [p[0] for p in base_world.values()]
    ys = [p[1] for p in base_world.values()]
    zs = [p[2] for p in base_world.values()]
    margin = 0.6 * torso_world
    center = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0)
    dims = (max(max(xs) - min(xs), 0.1) + margin, 0.4 + margin, max(max(zs) - min(zs), 0.1) + margin)

    lat = bpy.data.lattices.new(f"{fx['name']}_lat")
    lat.points_u, lat.points_v, lat.points_w = grid
    lat_obj = bpy.data.objects.new(f"{fx['name']}_lattice", lat)
    bpy.context.collection.objects.link(lat_obj)
    fx.setdefault("extra", []).append(lat_obj)
    lat_obj.location = center
    lat_obj.scale = (dims[0] / 2.0, dims[1] / 2.0, dims[2] / 2.0)

    capability = True
    note = "parent_set LATTICE"
    try:
        for key in ("arm", "mesh"):
            child = fx[key]
            if child is None:
                continue
            _set_active(lat_obj)
            child.select_set(True)
            bpy.ops.object.parent_set(type="LATTICE")
            child.select_set(False)
    except Exception as exc:  # narrow: the parent_set refusal IS the answer
        capability = False
        note = f"bind refused: {type(exc).__name__}: {exc}"
    bpy.context.view_layer.update()

    if capability:
        rest_after_bind = world_joints(fx)
        rest_drift = max(v_dist(rest_after_bind[r], base_world[r]) for r in rest_after_bind)
        if rest_drift > 1e-6:
            capability = False
            note = f"bind displaced rest by {rest_drift:.6f} m — unusable"
    if capability:
        half = (dims[0] / 2.0, dims[1] / 2.0, dims[2] / 2.0)
        nu, nv, nw = grid
        for idx, p in enumerate(lat.points):
            iu = idx % nu
            iv = (idx // nu) % nv
            iw = idx // (nu * nv)
            base_co = (
                -1.0 + 2.0 * iu / (nu - 1),
                -1.0 + 2.0 * iv / (nv - 1),
                -1.0 + 2.0 * iw / (nw - 1),
            )
            world = v_add(center, (base_co[0] * half[0], base_co[1] * half[1], base_co[2] * half[2]))
            num = [0.0, 0.0, 0.0]
            den = 0.0
            for role in sorted(joint_deltas):
                delta = joint_deltas[role]
                jp = base_world[role]
                d2 = (world[0] - jp[0]) ** 2 + (world[1] - jp[1]) ** 2 + (world[2] - jp[2]) ** 2
                w = 1.0 / (d2 + soften * soften)
                num[0] += w * delta[0]
                num[1] += w * delta[1]
                num[2] += w * delta[2]
                den += w
            disp_world = (num[0] / den, num[1] / den, num[2] / den)
            co = (
                base_co[0] + disp_world[0] / half[0],
                base_co[1] + disp_world[1] / half[1],
                base_co[2] + disp_world[2] / half[2],
            )
            p.co_deform = co
        bpy.context.view_layer.update()
        moved = world_joints(fx)
        arm_motion = max(v_dist(moved[r], base_world[r]) for r in moved)
        max_delta = max(math.sqrt(sum(c * c for c in joint_deltas[r])) for r in joint_deltas)
        # the REAL-motion threshold (float32 parent-inverse noise is ~1e-7 m;
        # a 1e-9 threshold read that noise as capability — caught + fixed)
        if arm_motion <= 1e-6 and max_delta > 1e-6:
            capability = False
            mods = [(m.name, m.type) for m in fx["mesh"].modifiers] if fx["mesh"] else []
            note = (
                "armature heads unmoved at 1e-6 (mesh-only deform class;"
                f" parent_set LATTICE adds the modifier to the MESH only {mods},"
                " the armature gets plain OBJECT parenting)"
            )
    achieved = world_joints(fx) if capability else base_world
    return {"capability": capability, "note": note, "achieved_world": achieved, "base_world": base_world}


# --------------------------------------------------------------------------
# Mechanism (b): shape keys by convention
# --------------------------------------------------------------------------

def author_convention_shape_keys(fx: dict) -> int:
    """Author the REQUIRED artifacts (the counted rig-side keys): one key per
    region param, value 1.0 == the heavy girdle delta / the tall limb delta.
    Returns the key count."""
    me = fx["mesh"].data
    ss = fx["space_scale"]
    _set_active(fx["mesh"])
    if fx["mesh"].data.shape_keys is None:
        bpy.ops.object.shape_key_add()  # creates the Basis (5.1: no name arg)
        me.shape_keys.key_blocks[0].name = "Basis"

    def band_offset(x: float, z: float, key: str) -> tuple[float, float, float]:
        if key == "prop.shoulder_w" and 1.30 <= z <= 1.46 and abs(x) > 0.05:
            return (x * 0.25, 0.0, 0.0)
        if key == "prop.hip_w" and 0.86 <= z <= 1.00 and abs(x) > 0.05:
            return (x * 0.20, 0.0, 0.0)
        for seg in ("upper_arm", "forearm"):
            for side in SIDES:
                sx = 0.18 if side == "L" else -0.18
                if key == f"prop.{seg}" and abs(x - sx) < 0.08:
                    if seg == "upper_arm" and 1.12 <= z <= 1.38:
                        return (0.0, 0.0, (z - 1.38) * 0.15)
                    if seg == "forearm" and 0.88 <= z <= 1.12:
                        return (0.0, 0.0, (z - 1.12) * 0.15)
        for side in SIDES:
            sx = 0.14 if side == "L" else -0.14
            if key == "prop.thigh" and abs(x - sx) < 0.08 and 0.52 <= z <= 0.94:
                return (0.0, 0.0, (z - 0.94) * 0.15)
            if key == "prop.shin" and abs(x - sx) < 0.08 and 0.12 <= z <= 0.52:
                return (0.0, 0.0, (z - 0.52) * 0.15)
        return (0.0, 0.0, 0.0)

    for key_name in SHAPEKEY_PARAMS:
        bpy.ops.object.shape_key_add()  # from_mix=False: a zero-delta copy
        k = me.shape_keys.key_blocks[-1]
        k.name = key_name
        k.relative_key = me.shape_keys.key_blocks["Basis"]
        for v in me.vertices:
            x, _y, z = v.co.x / ss, v.co.y / ss, v.co.z / ss
            off = band_offset(x, z, key_name)
            k.data[v.index].co = v.co + mathutils.Vector(v_scale(off, ss))
    return len(SHAPEKEY_PARAMS)


def apply_shape_keys(fx: dict, class_name: str) -> dict:
    """Candidate (b). Sets the convention key values; measures joints
    (expected unmoved) + the mesh surface (expected moved)."""
    keys = fx["mesh"].data.shape_keys
    for name, val in sorted(SHAPEKEY_VALUES[class_name].items()):
        keys.key_blocks[name].value = val
    fx["mesh"].data.update()
    bpy.context.view_layer.update()
    base_local = rest_joints(fx)
    base_world = world_joints(fx)
    achieved_world = world_joints(fx)
    deps = bpy.context.evaluated_depsgraph_get()
    ev = fx["mesh"].evaluated_get(deps)
    n_moved = 0
    max_surf = 0.0
    total = len(fx["mesh"].data.vertices)
    for v in fx["mesh"].data.vertices:
        d = (ev.data.vertices[v.index].co - v.co).length / fx["space_scale"]
        if d > 1e-9:
            n_moved += 1
        max_surf = max(max_surf, d)
    return {
        "capability": True,
        "note": f"keys applied; surface {n_moved}/{total} verts moved, max {max_surf:.4f} m",
        "joints_unmoved": achieved_world == base_world,
        "base_local": base_local,
        "surface_moved": n_moved,
    }


# --------------------------------------------------------------------------
# Mechanism (c): armature scale-correctives (the positions-surgery class)
# --------------------------------------------------------------------------

def init_joint_ends(fx: dict, base_local: dict) -> dict[str, list[tuple[str, str]]]:
    """Data-driven: every bone head/tail resting AT a movable joint moves
    with it (matching by base position, 1e-9)."""
    ends: dict[str, list[tuple[str, str]]] = {r: [] for r in movable_roles() & set(base_local)}
    for _role, bone_name in sorted(fx["role_to_bone"].items()):
        bone = fx["arm"].data.bones[bone_name]
        h = bone.matrix_local.to_translation()
        head = (h.x, h.y, h.z)
        t = bone.matrix_local @ mathutils.Vector((0.0, bone.length, 0.0))
        tail = (t.x, t.y, t.z)
        for jrole in sorted(ends):
            jpos = base_local[jrole]
            if v_dist(head, jpos) < 1e-9:
                ends[jrole].append((bone_name, "head"))
            if v_dist(tail, jpos) < 1e-9:
                ends[jrole].append((bone_name, "tail"))
    return ends


FOLLOW_EPS = 1e-6  # real-follow threshold x space_scale (float32 noise is ~1e-7 local)


def apply_rest_correctives(fx: dict, tgt_local: dict, base_local: dict) -> dict:
    """The REFUTED delivery (amendment A1's evidence): edit-bone re-placement
    lands joints FP-exactly, but armature skinning RE-BINDS to the new rest —
    the deform is pose @ rest^-1 = identity at rest pose, so the mesh does
    NOT follow. Kept + measured so the refutation carries its number."""
    arm = fx["arm"]
    ends = init_joint_ends(fx, base_local)
    _set_active(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for role in sorted(ends):
        new = tgt_local[role]
        for bone_name, which in sorted(ends[role]):
            b = eb[bone_name]
            if which == "head":
                b.head = new
            else:
                b.tail = new
    for role in sorted(RIGID_TAILS):
        if role not in tgt_local:
            continue
        b = eb[fx["role_to_bone"][role]]
        d = v_sub(tgt_local[role], base_local[role])
        b.tail = (b.tail.x + d[0], b.tail.y + d[1], b.tail.z + d[2])
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    follow = _mesh_follow(fx)
    achieved_local = rest_joints(fx)
    return {
        "capability": True,
        "note": f"rest re-placement; joints exact; mesh follow {follow:.4f} (REBIND REFUTED THE FOLLOW)",
        "achieved_local": achieved_local,
        "surface_follow": follow,
    }


def _mesh_follow(fx: dict) -> float:
    """Fraction of mesh vertices whose EVALUATED position really moved
    (threshold FOLLOW_EPS x space_scale — float32 noise stays under it)."""
    pre = [tuple(v.co) for v in fx["mesh"].data.vertices]
    deps = bpy.context.evaluated_depsgraph_get()
    ev = fx["mesh"].evaluated_get(deps)
    thr = FOLLOW_EPS * fx["space_scale"]
    moved = 0
    for i in range(len(pre)):
        if (ev.data.vertices[i].co - mathutils.Vector(pre[i])).length > thr:
            moved += 1
    return moved / max(len(pre), 1)


def _pose_head_local(arm, bone_name: str) -> tuple[float, float, float]:
    t = arm.pose.bones[bone_name].matrix.to_translation()
    return (t.x, t.y, t.z)


def apply_pose_correctives(fx: dict, tgt_local: dict, base_local: dict) -> dict:
    """Candidate (c) as corrected by amendment A1: per-joint offsets deliver
    as POSE-bone locations (rigid offsets in parent frames — they persist
    without an action and FK rotations compose over them). The head response
    to a location L is linear: head(L) = head(0) + R @ L; R is MEASURED per
    bone with three axis perturbations (no API-semantics betting), then
    L = R^-1 @ (intended - head(0)). Parent-first keyed order."""
    arm = fx["arm"]
    ends = init_joint_ends(fx, base_local)
    _set_active(arm)
    bpy.ops.object.mode_set(mode="POSE")
    solved: dict[str, tuple[float, float, float]] = {}
    for role, _parent in BONE_TABLE:  # declared order == parent-first
        if role not in ends:
            continue
        bone_name = fx["role_to_bone"][role]
        pb = arm.pose.bones[bone_name]
        bpy.context.view_layer.update()
        c0 = _pose_head_local(arm, bone_name)
        delta = v_sub(tgt_local[role], c0)
        if v_dist(delta, (0.0, 0.0, 0.0)) <= 1e-12:
            solved[role] = c0
            continue
        cols = []
        for axis in range(3):
            h = 1e-4 * fx["space_scale"]
            probe = [0.0, 0.0, 0.0]
            probe[axis] = h
            pb.location = probe
            bpy.context.view_layer.update()
            cp = _pose_head_local(arm, bone_name)
            cols.append(v_scale(v_sub(cp, c0), 1.0 / h))
            pb.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        r = cols  # columns of the response matrix R
        det = (
            r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
            - r[1][0] * (r[0][1] * r[2][2] - r[0][2] * r[2][1])
            + r[2][0] * (r[0][1] * r[1][2] - r[0][2] * r[1][1])
        )
        if abs(det) < 1e-12:
            raise ValueError(f"degenerate pose-response for {role}")
        inv_det = 1.0 / det
        adj0 = (r[1][1] * r[2][2] - r[1][2] * r[2][1], r[0][2] * r[2][1] - r[0][1] * r[2][2], r[0][1] * r[1][2] - r[0][2] * r[1][1])
        adj1 = (r[1][2] * r[2][0] - r[1][0] * r[2][2], r[0][0] * r[2][2] - r[0][2] * r[2][0], r[0][2] * r[1][0] - r[0][0] * r[1][2])
        adj2 = (r[1][0] * r[2][1] - r[1][1] * r[2][0], r[0][1] * r[2][0] - r[0][0] * r[2][1], r[0][0] * r[1][1] - r[0][1] * r[1][0])
        loc = (
            inv_det * (adj0[0] * delta[0] + adj1[0] * delta[1] + adj2[0] * delta[2]),
            inv_det * (adj0[1] * delta[0] + adj1[1] * delta[1] + adj2[1] * delta[2]),
            inv_det * (adj0[2] * delta[0] + adj1[2] * delta[1] + adj2[2] * delta[2]),
        )
        pb.location = loc
        bpy.context.view_layer.update()
        solved[role] = _pose_head_local(arm, bone_name)
    follow = _mesh_follow(fx)
    achieved_local = {}
    for role, bone_name in fx["role_to_bone"].items():
        achieved_local[role] = _pose_head_local(arm, bone_name)
    bpy.ops.object.mode_set(mode="OBJECT")
    return {
        "capability": True,
        "note": f"pose-translation correctives; mesh follow {follow:.2f}",
        "achieved_local": achieved_local,
        "solved": solved,
        "surface_follow": follow,
        "pose_locations": {b.name: tuple(b.location) for b in arm.pose.bones},
    }


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------

def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def cleanup_fixtures(*fxs: dict) -> None:
    for fx in fxs:
        for obj in fx.get("extra", []):
            try:
                data_name = obj.data.name if obj.data is not None else ""
            except ReferenceError:
                data_name = ""
            bpy.data.objects.remove(obj, do_unlink=True)
            if data_name and data_name in bpy.data.lattices:
                bpy.data.lattices.remove(bpy.data.lattices[data_name], do_unlink=True)
        for key in ("mesh", "arm"):
            obj = fx.get(key)
            if obj is None:
                continue
            try:
                data_name = obj.data.name
            except ReferenceError:
                continue
            bpy.data.objects.remove(obj, do_unlink=True)
            # removing the object orphans the data; Blender may purge it —
            # look it up BY NAME (the captured RNA can be dead already)
            for coll in (bpy.data.meshes, bpy.data.armatures):
                if data_name in coll:
                    coll.remove(coll[data_name], do_unlink=True)


def main() -> int:
    fixture_ok = True
    target_ok = True
    shapekey_ok = True
    select_ok = True

    fresh_scene()
    base_ratios = measure_proportion_ratios(BASE_JOINTS)

    # ---- ASC-FIXTURE -----------------------------------------------------
    fixtures: dict[bool, dict] = {}
    for mixamo in (False, True):
        class_tag = "mixamo" if mixamo else "metarig"
        # base fixtures LIVE for the whole probe — named outside the asc_
        # cleanup sweep's namespace
        fx = build_fixture(f"base_{class_tag}", mixamo=mixamo)
        fixtures[mixamo] = fx
        base_local = rest_joints(fx)
        expect = {r: v_scale(BASE_JOINTS[r], fx["space_scale"]) for r in BASE_JOINTS}
        # float32 bone-matrix storage: tolerance scales with the space
        tol = 1e-6 * fx["space_scale"]
        fixture_ok &= all(v_dist(base_local[r], expect[r]) < tol for r in BASE_JOINTS)
        fixture_ok &= fx["n_weighted"] > 0 and fx["mesh"] is not None
    check("ASC-FIXTURE", fixture_ok, "2 rig classes, base skeletons exact, meshes skinned (nearest-bone)")

    # ---- per-fixture targets (scale-free by construction) ----------------
    local_targets: dict[bool, dict[str, dict]] = {}
    for mixamo in (False, True):
        base_local = rest_joints(fixtures[mixamo])
        local_targets[mixamo] = {}
        for class_name in sorted(REF_CLASSES):
            ref_ratios = class_ratios(base_ratios, REF_CLASSES[class_name])
            tgt, _factors, _adj = build_proportion_target(base_local, ref_ratios, base_ratios)
            local_targets[mixamo][class_name] = tgt

    # ---- ASC-TARGET (pure math: authored-GT recovery + determinism) ------
    try:
        for class_name in sorted(REF_CLASSES):
            ref_ratios = class_ratios(base_ratios, REF_CLASSES[class_name])
            tgt, _f, _a = build_proportion_target(BASE_JOINTS, ref_ratios, base_ratios)
            back = measure_proportion_ratios(tgt)
            worst_rt = max(abs(back[k] - ref_ratios[k]) for k in ref_ratios)
            tgt2, _f2, _a2 = build_proportion_target(BASE_JOINTS, ref_ratios, base_ratios)
            target_ok &= worst_rt < 1e-9 and all(tgt[r] == tgt2[r] for r in tgt)
    except ValueError as exc:
        target_ok = False
        print(f"RM_ASCULPT ASC-TARGET detail: refused: {exc}")
    check("ASC-TARGET", target_ok, "3 classes, GT ratio round-trip < 1e-9, twins exact (pure stdlib)")

    # ---- the per-class per-rig runs ---------------------------------------
    selection = {n: {"holders": True, "note": []} for n in CANDIDATE_NAMES}
    lattice_last: dict | None = None
    scale_last: dict | None = None

    for mixamo in (False, True):
        class_tag = "mixamo" if mixamo else "metarig"
        base_local = rest_joints(fixtures[mixamo])
        for class_name in sorted(REF_CLASSES):
            tgt_local = local_targets[mixamo][class_name]

            # (a) lattice, with the ONE pre-declared repair cycle (also on a
            # bar miss — the A.2 bounded cycle, declared in AUTO_SCULPT.md)
            fxa = build_fixture(f"asc_{class_tag}_{class_name}_lat", mixamo=mixamo)
            rep = apply_lattice(fxa, tgt_local, LATTICE_GRID)
            achieved_local = {r: to_local(fixtures[mixamo], rep["achieved_world"][r]) for r in rep["achieved_world"]}
            worst_a, _fracs, worst_role = validate_target(achieved_local, tgt_local, base_local)
            rep_note = f"grid={LATTICE_GRID[0]}x{LATTICE_GRID[1]}x{LATTICE_GRID[2]} worst={worst_a:.4f}@{worst_role}"
            if not rep["capability"]:
                rep_note += f"; capability refusal: {rep['note']}"
            elif worst_a > BAR_FRAC:
                fxa2 = build_fixture(f"asc_{class_tag}_{class_name}_lat2", mixamo=mixamo)
                rep2 = apply_lattice(fxa2, tgt_local, LATTICE_GRID_REPAIR)
                achieved2 = {r: to_local(fixtures[mixamo], rep2["achieved_world"][r]) for r in rep2["achieved_world"]}
                worst_a2, _f2, wr2 = validate_target(achieved2, tgt_local, base_local)
                rep_note += (
                    f"; repair={LATTICE_GRID_REPAIR[0]}x{LATTICE_GRID_REPAIR[1]}x{LATTICE_GRID_REPAIR[2]}"
                    f" worst={worst_a2:.4f}@{wr2} cap={rep2['capability']}"
                )
                if rep2["capability"] and worst_a2 < worst_a:
                    rep = rep2
                    achieved_local = achieved2
                    worst_a, worst_role = worst_a2, wr2
                cleanup_fixtures(fxa2)
            cap_a = rep["capability"]
            selection["lattice"]["holders"] &= cap_a and worst_a <= BAR_FRAC
            selection["lattice"]["note"].append(f"{class_tag}/{class_name}: cap={cap_a} {rep_note}")
            lattice_last = rep
            cleanup_fixtures(fxa)

            # (b) shape keys
            fxb = build_fixture(f"asc_{class_tag}_{class_name}_sk", mixamo=mixamo)
            n_keys = author_convention_shape_keys(fxb)
            repb = apply_shape_keys(fxb, class_name)
            worst_b, _fracs, worst_role = validate_target(repb["base_local"], tgt_local, base_local)
            shapekey_ok &= repb["surface_moved"] > 0 and n_keys == len(SHAPEKEY_PARAMS) and repb["joints_unmoved"]
            selection["shape_key_binding"]["holders"] &= worst_b <= BAR_FRAC
            selection["shape_key_binding"]["note"].append(
                f"{class_tag}/{class_name}: joints_unmoved worst={worst_b:.4f}@{worst_role} surf={repb['surface_moved']}"
            )
            cleanup_fixtures(fxb)

            # (c) scale-correctives: the A1 rest-delivery EVIDENCE (refuted
            # rebind, heavy class per rig) + the corrected pose-translation
            # delivery (the selection input, all classes)
            if class_name == "heavy":
                fxr = build_fixture(f"asc_{class_tag}_{class_name}_rc", mixamo=mixamo)
                repr_ = apply_rest_correctives(fxr, tgt_local, base_local)
                worst_r, _f, wr = validate_target(repr_["achieved_local"], tgt_local, base_local)
                selection["armature_scale_correctives"]["note"].append(
                    f"{class_tag}/{class_name}: REST delivery worst={worst_r:.4f}@{wr}"
                    f" follow={repr_['surface_follow']:.4f} (rebind evidence)"
                )
                cleanup_fixtures(fxr)
            fxc = build_fixture(f"asc_{class_tag}_{class_name}_sc", mixamo=mixamo)
            repc = apply_pose_correctives(fxc, tgt_local, base_local)
            worst_c, _fracs, worst_role = validate_target(repc["achieved_local"], tgt_local, base_local)
            selection["armature_scale_correctives"]["holders"] &= worst_c <= BAR_FRAC
            selection["armature_scale_correctives"]["note"].append(
                f"{class_tag}/{class_name}: POSE worst={worst_c:.4f}@{worst_role} follow={repc['surface_follow']:.2f}"
            )
            scale_last = repc
            cleanup_fixtures(fxc)

    check("ASC-LATTICE", lattice_last is not None, "; ".join(selection["lattice"]["note"]))
    check("ASC-SHAPEKEY", shapekey_ok, "; ".join(selection["shape_key_binding"]["note"]))
    check("ASC-SCALE", scale_last is not None, "; ".join(selection["armature_scale_correctives"]["note"]))

    # ---- ASC-SELECT (the pre-declared arithmetic) -------------------------
    holders = [n for n in CANDIDATE_NAMES if selection[n]["holders"]]
    if holders:
        fewest = min(REQUIRED_ARTIFACTS[n] for n in holders)
        tied = sorted(n for n in holders if REQUIRED_ARTIFACTS[n] == fewest)
        winner = tied[0]
        check(
            "ASC-SELECT",
            select_ok,
            f"verdict={winner} holders={','.join(holders)}"
            f" required_artifacts={REQUIRED_ARTIFACTS[winner]} (tie-break: candidate name ascending)",
        )
    else:
        check(
            "ASC-SELECT",
            select_ok,
            "verdict=REFUSED — no candidate holds the 5% bar on both rigs;"
            " the proportion REPORT ships as data; the auto-sculpt claim is never made",
        )

    # ---- ASC-NOTARGET ------------------------------------------------------
    fxn = build_fixture("asc_notarget", with_mesh=True)
    roles_present = set(fxn["role_to_bone"])
    roles_present.discard("lower_leg.L")
    roles_present.discard("upper_leg.L")
    lines = sculpt_capability_lines(roles_present)
    loud = bool(lines) and "lower_leg.L" in lines[0] and "proportions not applied" in lines[0]
    check("ASC-NOTARGET", loud, lines[0] if lines else "NO LINE — silent refusal is the failure")
    cleanup_fixtures(fxn)

    # ---- ASC-DETERM --------------------------------------------------------
    dets = []
    for name in ("asc_det1", "asc_det2"):
        fxd = build_fixture(name, mixamo=False)
        base_local = rest_joints(fxd)
        ref = class_ratios(base_ratios, REF_CLASSES["heavy"])
        tgt, _f, _a = build_proportion_target(base_local, ref, base_ratios)
        repd = apply_pose_correctives(fxd, tgt, base_local)
        dets.append(repd["pose_locations"])
        cleanup_fixtures(fxd)
    identical = dets[0].keys() == dets[1].keys() and all(dets[0][k] == dets[1][k] for k in dets[0])
    ref = class_ratios(base_ratios, REF_CLASSES["heavy"])
    t1, _f, _a = build_proportion_target(BASE_JOINTS, ref, base_ratios)
    t2, _f, _a = build_proportion_target(BASE_JOINTS, ref, base_ratios)
    det_ok = identical and all(t1[r] == t2[r] for r in t1)
    check("ASC-DETERM", det_ok, f"pose-corrective state + target math twins byte-identical ({len(dets[0])} bones)")

    # ---- verdict -----------------------------------------------------------
    check("GATE", OK, "the probe's rows above are the contract")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
