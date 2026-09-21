"""P4-8 manga builder — "Paper Dart", a 6-page wordless manga + 3-style hero.

Runs INSIDE Blender (spawned by ``xtask/manga_build.sh`` — D-009: the spawn
and every artifact MOVE live in shell glue, never in a ``.py``; this script
only renders/creates files under the one OUT_DIR it is given, exactly like
``style_probe.py``). Deterministic, asset-free, CI-safe: the character is a
code-built mannequin (canonical-lexicon rig + joined rigid-part mesh), the
prop is a grey paper dart, the poses are hand-authored canonical positions
built by small transforms of a neutral dict, and every beat bakes through
the CERTIFIED ``bake_action`` transport (the P2-3/P3-7/P4-7 gate path).

The per-panel ``frame`` field (P4-8, docs/STYLE.md) carries the story:
each panel names the scene frame (== beat number) to render; all motion
(an armature bake + the dart's object keyframes + the rig's root-height
keys) lives in the scene, so one ``frame_set(n)`` moves everything.

Modes: ``sheet`` renders the pose contact sheet (the visual-check loop),
``pages`` renders the 6 story pages + hero + the parse-back-verified PDF,
``all`` does both. The shell glue copies the checked artifacts into
``docs/manga/``.

Usage: blender -b --python xtask/manga_build.py -- OUT_DIR [sheet|pages|all]
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "addon"))

PAGES_DIR = REPO / "xtask" / "manga_pages"
STORY_PAGES = [f"manga_dart_p{i}" for i in range(1, 7)]
HERO_PAGE = "manga_dart_hero"

# -- canonical-space helpers -------------------------------------------------
# Character faces -Y, character-left = +X, hips anchored at the origin (the
# payload/pose convention). Positions are role JOINT positions in canonical
# units (the _anim_pose layout proven through bake_action in the style gate).


def _neutral() -> dict[str, tuple[float, float, float]]:
    pos = {
        "hips": (0.0, 0.0, 0.0),
        "spine": (0.0, 0.0, 0.09),
        "chest": (0.0, 0.0, 0.26),
        "neck": (0.0, 0.0, 0.45),
        "head": (0.0, 0.0, 0.56),
    }
    for side, sx in (("L", 1.0), ("R", -1.0)):
        pos[f"shoulder.{side}"] = (0.08 * sx, 0.0, 0.45)
        pos[f"upper_arm.{side}"] = (0.15 * sx, 0.0, 0.45)
        pos[f"forearm.{side}"] = (0.47 * sx, 0.0, 0.45)
        pos[f"hand.{side}"] = (0.75 * sx, 0.0, 0.45)
        pos[f"upper_leg.{side}"] = (0.09 * sx, 0.0, 0.0)
        pos[f"lower_leg.{side}"] = (0.09 * sx, 0.0, -0.44)
        pos[f"foot.{side}"] = (0.09 * sx, 0.0, -0.88)
    return pos


def _rx(p: tuple[float, float, float], pivot: tuple[float, float, float], a: float) -> tuple[float, float, float]:
    c, s = math.cos(a), math.sin(a)
    y, z = p[1] - pivot[1], p[2] - pivot[2]
    return (p[0], pivot[1] + c * y - s * z, pivot[2] + s * y + c * z)


def _ry(p: tuple[float, float, float], pivot: tuple[float, float, float], a: float) -> tuple[float, float, float]:
    c, s = math.cos(a), math.sin(a)
    x, z = p[0] - pivot[0], p[2] - pivot[2]
    return (pivot[0] + c * x + s * z, p[1], pivot[2] - s * x + c * z)


def _rz(p: tuple[float, float, float], pivot: tuple[float, float, float], a: float) -> tuple[float, float, float]:
    c, s = math.cos(a), math.sin(a)
    x, y = p[0] - pivot[0], p[1] - pivot[1]
    return (pivot[0] + c * x - s * y, pivot[1] + s * x + c * y, p[2])


def _chain(pos: dict[str, tuple[float, float, float]], roles: list[str], pivot: str, fn: Any, *args: Any) -> None:
    """Rotate every role in ``roles`` about the pivot role's CURRENT position."""
    base = pos[pivot]
    for role in roles:
        pos[role] = fn(pos[role], base, *args)


def _norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(x * x for x in v))
    return (v[0] / length, v[1] / length, v[2] / length)


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _rodriguez(
    p: tuple[float, float, float],
    pivot: tuple[float, float, float],
    axis: tuple[float, float, float],
    a: float,
) -> tuple[float, float, float]:
    """Rotate ``p`` about ``pivot`` around the unit ``axis`` by ``a`` radians."""
    c, s = math.cos(a), math.sin(a)
    v = (p[0] - pivot[0], p[1] - pivot[1], p[2] - pivot[2])
    cr = _cross(axis, v)
    dot = axis[0] * v[0] + axis[1] * v[1] + axis[2] * v[2]
    return (
        pivot[0] + v[0] * c + cr[0] * s + axis[0] * dot * (1 - c),
        pivot[1] + v[1] * c + cr[1] * s + axis[1] * dot * (1 - c),
        pivot[2] + v[2] * c + cr[2] * s + axis[2] * dot * (1 - c),
    )


_TORSO = [
    "spine", "chest", "neck", "head",
    "shoulder.L", "upper_arm.L", "forearm.L", "hand.L",
    "shoulder.R", "upper_arm.R", "forearm.R", "hand.R",
]


def _sys_core() -> None:
    p = str(REPO / "core" / "src")
    if p not in sys.path:
        sys.path.insert(0, p)


def build_pose(**kw: float) -> Any:
    """A CanonicalPose from small authored joint angles (degrees).

    Signs: ``torso_fwd`` + leans toward -Y; ``head_pitch`` + looks down;
    ``sh_y`` + hangs the arm down (90 = straight down), - lifts overhead;
    ``sh_z`` + swings the arm forward (-Y); ``elbow`` + bends forward;
    ``hip`` + swings the thigh forward; ``knee`` + bends the shank back;
    ``ankle`` + pitches the toes down. All pure math on a neutral dict —
    same input, same pose, always.
    """
    pos = _neutral()
    d = math.radians
    fwd = kw.get("torso_fwd", 0.0)
    if fwd:
        _chain(pos, _TORSO, "hips", _rx, d(fwd))
    hp = kw.get("head_pitch", 0.0)
    if hp:
        _chain(pos, ["head"], "neck", _rx, d(hp))
    for side, sx in (("L", 1.0), ("R", -1.0)):
        s = side.lower()
        y = kw.get(f"{s}_sh_y", 90.0)  # arms hang by default
        z = kw.get(f"{s}_sh_z", 0.0)
        el = kw.get(f"{s}_elbow", 0.0)
        arm = [f"upper_arm.{side}", f"forearm.{side}", f"hand.{side}"]
        _chain(pos, arm, f"upper_arm.{side}", _ry, d(y * sx))
        _chain(pos, arm, f"upper_arm.{side}", _rz, d(z * sx))
        # Elbow: fold the hand toward forward-UP (a raised arm's hand comes
        # up toward the face, a hanging arm's comes forward) — the bend axis
        # is perpendicular to the current forearm direction and the pull.
        fdir = _norm(
            (
                pos[f"hand.{side}"][0] - pos[f"forearm.{side}"][0],
                pos[f"hand.{side}"][1] - pos[f"forearm.{side}"][1],
                pos[f"hand.{side}"][2] - pos[f"forearm.{side}"][2],
            )
        )
        axis = _norm(_cross(fdir, (0.0, -0.45, 0.89)))
        _chain(pos, [f"hand.{side}"], f"forearm.{side}", _rodriguez, axis, d(el))
        hip = kw.get(f"{s}_hip", 0.0)
        knee = kw.get(f"{s}_knee", 0.0)
        ankle = kw.get(f"{s}_ankle", 0.0)
        _chain(pos, [f"lower_leg.{side}", f"foot.{side}"], f"upper_leg.{side}", _rx, d(-hip))
        _chain(pos, [f"foot.{side}"], f"lower_leg.{side}", _rx, d(knee))
        _chain(pos, [f"foot.{side}"], f"foot.{side}", _rx, d(ankle))
    _sys_core()
    import riggermortis as core

    return core.CanonicalPose(
        positions=pos,
        flips={},
        confidence=1.0,
        reliable=True,
        scale=30.0,
        anchor="hips",
    )


# -- the board: 20 beats (frame == beat number) ------------------------------
# pose = build_pose kwargs; dart = (mode, vec, euler_deg) with mode
# "world" | "hand.R" | "hands_mid"; drop = rig root height (meters).

BEATS: list[dict[str, Any]] = [
    {  # b1 FIND — wide establishing: the dart lies ahead-right
        "cam": "rm_cam_p1_wide", "drop": 0.0,
        "pose": {"head_pitch": 14, "l_sh_y": 86, "r_sh_y": 86, "l_elbow": 4, "r_elbow": 4},
        "dart": ("world", (0.32, -0.55, -0.885), (4, 0, 28)),
    },
    {  # b2 — notices it fully, torso leans
        "cam": "rm_cam_p1_med", "drop": 0.0,
        "pose": {"torso_fwd": 5, "head_pitch": 22, "l_sh_y": 86, "r_sh_y": 86},
        "dart": ("world", (0.32, -0.55, -0.885), (4, 0, 28)),
    },
    {  # b3 — crouch + reach (shallow bend: 0.44*cos40 + 0.44*cos30 -> drop ~0.16)
        "cam": "rm_cam_p1_close", "drop": -0.16,
        "pose": {"l_hip": 40, "l_knee": 70, "l_ankle": -30, "r_hip": 38, "r_knee": 74,
                 "r_ankle": -32, "head_pitch": 26, "l_sh_y": 84, "r_sh_y": 30,
                 "r_sh_z": 42, "r_elbow": 14},
        "dart": ("world", (0.32, -0.55, -0.885), (4, 0, 28)),
    },
    {  # b4 TAKE — the dart comes up in the right hand (drop: 0.44*cos56 +
        # 0.44*cos42 ~= 0.57 -> ~0.31)
        "cam": "rm_cam_p2_med", "drop": -0.31,
        "pose": {"l_hip": 56, "l_knee": 98, "l_ankle": -42, "r_hip": 54, "r_knee": 102,
                 "r_ankle": -44, "head_pitch": 20, "l_sh_y": 82, "r_sh_y": 12,
                 "r_sh_z": 50, "r_elbow": 18},
        "dart": ("hand.R", (0.0, -0.03, -0.055), (10, 0, 24)),
    },
    {  # b5 — holds it up before the face
        "cam": "rm_cam_p2_close", "drop": 0.0,
        "pose": {"head_pitch": 24, "l_sh_y": 88, "r_sh_y": 40, "r_sh_z": 80, "r_elbow": 95},
        "dart": ("hand.R", (0.0, -0.12, 0.03), (18, 0, 12)),
    },
    {  # b6 — head up, dart to the chest (resolve)
        "cam": "rm_cam_p2_chest", "drop": 0.0,
        "pose": {"torso_fwd": -4, "head_pitch": -8, "l_sh_y": 88, "r_sh_y": 40,
                 "r_sh_z": 30, "r_elbow": 116},
        "dart": ("hand.R", (0.02, -0.05, 0.02), (6, 0, 30)),
    },
    {  # b7 THROW — wind-up
        "cam": "rm_cam_p3_wind", "drop": 0.0,
        "pose": {"torso_fwd": 6, "head_pitch": 4, "l_sh_y": 70, "l_sh_z": 32, "l_elbow": 12,
                 "r_sh_y": 74, "r_sh_z": -68, "r_elbow": 26},
        "dart": ("hand.R", (0.0, 0.06, 0.02), (-38, 0, 40)),
    },
    {  # b8 — release, the dart just past the fingertips
        "cam": "rm_cam_p3_rel", "drop": 0.0,
        "pose": {"torso_fwd": 9, "head_pitch": 6, "l_sh_y": 76, "l_sh_z": -22, "l_elbow": 10,
                 "r_sh_y": 60, "r_sh_z": 92, "r_elbow": 8},
        "dart": ("hand.R", (0.0, -0.24, 0.07), (24, 0, -6)),
    },
    {  # b9 — it SOARS; the mannequin points, tiny under a big sky
        "cam": "rm_cam_p3_sky", "drop": 0.0,
        "pose": {"head_pitch": -20, "l_sh_y": 60, "l_sh_z": 24, "r_sh_y": 46,
                 "r_sh_z": 68, "r_elbow": 6},
        "dart": ("world", (0.36, -3.40, 1.70), (30, 0, 14)),
    },
    {  # b10 CRASH — the dive, seen high and wide
        "cam": "rm_cam_p4_dive", "drop": 0.0,
        "pose": {"head_pitch": -6, "l_sh_y": 62, "l_sh_z": 26, "r_sh_y": 58, "r_sh_z": 30,
                 "l_elbow": 14, "r_elbow": 14},
        "dart": ("world", (0.46, -1.95, 0.55), (-58, 0, 32)),
    },
    {  # b11 — runs toward it
        "cam": "rm_cam_p4_run", "drop": -0.02,
        "pose": {"torso_fwd": 12, "head_pitch": 12, "l_hip": 52, "l_knee": 34,
                 "r_hip": -38, "r_knee": 62, "l_sh_y": 72, "l_sh_z": 44, "l_elbow": 58,
                 "r_sh_y": 74, "r_sh_z": -38, "r_elbow": 52},
        "dart": ("world", (0.48, -1.35, 0.12), (-72, 0, 26)),
    },
    {  # b12 — frozen stare at the crash (ANIME beat + the empty bubble)
        "cam": "rm_cam_p4_close", "drop": -0.04,
        "pose": {"torso_fwd": 8, "head_pitch": 18, "l_sh_y": 74, "l_sh_z": 16, "l_elbow": 22,
                 "r_sh_y": 76, "r_sh_z": 18, "r_elbow": 22, "l_hip": 18, "l_knee": 10},
        "dart": ("world", (0.50, -1.00, -0.79), (-80, 0, 20)),
    },
    {  # b13 — slumped over it
        "cam": "rm_cam_p4_slump", "drop": -0.05,
        "pose": {"torso_fwd": 15, "head_pitch": 30, "l_sh_y": 84, "r_sh_y": 84,
                 "l_elbow": 8, "r_elbow": 8},
        "dart": ("world", (0.50, -1.00, -0.79), (-80, 0, 20)),
    },
    {  # b14 REPAIR — crouched, both hands at the dart (drop ~0.28)
        "cam": "rm_cam_p5_hands", "drop": -0.28,
        "pose": {"l_hip": 54, "l_knee": 94, "l_ankle": -40, "r_hip": 52, "r_knee": 98,
                 "r_ankle": -42, "head_pitch": 32, "l_sh_y": 36, "l_sh_z": 48,
                 "l_elbow": 34, "r_sh_y": 34, "r_sh_z": 46, "r_elbow": 36},
        "dart": ("world", (0.42, -0.92, -0.865), (-2, 0, 32)),
    },
    {  # b15 — lifts the mended dart overhead
        "cam": "rm_cam_p5_lift", "drop": 0.0,
        "pose": {"torso_fwd": -5, "head_pitch": -24, "l_sh_y": -96, "l_sh_z": 14,
                 "l_elbow": 8, "r_sh_y": -96, "r_sh_z": -14, "r_elbow": 8},
        "dart": ("hands_mid", (0.0, -0.04, 0.16), (58, 0, 0)),
    },
    {  # b16 — the second wind-up
        "cam": "rm_cam_p5_wind", "drop": 0.0,
        "pose": {"torso_fwd": 7, "head_pitch": 6, "l_sh_y": 72, "l_sh_z": 26, "l_elbow": 14,
                 "r_sh_y": 72, "r_sh_z": -74, "r_elbow": 34},
        "dart": ("hand.R", (0.0, 0.07, 0.03), (-44, 0, 42)),
    },
    {  # b17 SOAR — the second release, thrown higher
        "cam": "rm_cam_p6_rel", "drop": 0.0,
        "pose": {"torso_fwd": 7, "head_pitch": 0, "l_sh_y": 76, "l_sh_z": -20, "l_elbow": 10,
                 "r_sh_y": 58, "r_sh_z": 98, "r_elbow": 6},
        "dart": ("hand.R", (0.0, -0.30, 0.24), (38, 0, -10)),
    },
    {  # b18 — the SKY panel: the dart climbs steeply
        "cam": "rm_cam_p6_sky", "drop": 0.0,
        "pose": {"head_pitch": -26, "l_sh_y": 86, "r_sh_y": 40, "r_sh_z": 58, "r_elbow": 118},
        "dart": ("world", (0.16, -2.60, 2.30), (46, 0, -8)),
    },
    {  # b19 — THE JUMP (the hero beat): both arms up, feet off the ground
        "cam": "rm_cam_hero", "drop": 0.22,
        "pose": {"head_pitch": -14, "l_sh_y": -112, "l_sh_z": 26, "l_elbow": 8,
                 "r_sh_y": -112, "r_sh_z": -26, "r_elbow": 8,
                 "l_hip": 26, "l_knee": 46, "r_hip": 16, "r_knee": 32},
        "dart": ("world", (0.30, -4.60, 3.40), (42, 0, -6)),
    },
    {  # b20 — waving after it, the dart a speck in the corner of the sky
        "cam": "rm_cam_p6_final", "drop": 0.0,
        "pose": {"torso_fwd": -2, "head_pitch": -8, "l_sh_y": 86, "r_sh_y": -132,
                 "r_sh_z": -18, "r_elbow": 26},
        "dart": ("world", (0.52, -7.60, 4.30), (40, 0, -10)),
    },
]

CAMERAS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "rm_cam_p1_wide": ((1.65, -4.60, 1.30), (0.18, -0.65, 0.22)),
    "rm_cam_p1_med": ((0.75, -2.00, 1.00), (0.10, -0.50, 0.55)),
    "rm_cam_p1_close": ((1.35, -2.55, 1.00), (0.18, -0.58, 0.38)),
    "rm_cam_p2_med": ((1.05, -2.40, 1.05), (0.05, -0.35, 0.50)),
    "rm_cam_p2_close": ((0.45, -1.75, 1.02), (0.02, -0.18, 0.72)),
    "rm_cam_p2_chest": ((0.75, -2.30, 1.05), (0.00, -0.30, 0.52)),
    "rm_cam_p3_wind": ((0.95, -2.60, 1.15), (-0.12, -0.20, 0.62)),
    "rm_cam_p3_rel": ((-0.95, -2.45, 1.10), (0.06, -0.52, 0.62)),
    "rm_cam_p3_sky": ((0.60, -7.50, 0.70), (0.20, -2.20, 1.35)),
    "rm_cam_p4_dive": ((2.15, -3.95, 2.55), (0.42, -1.55, 0.45)),
    "rm_cam_p4_run": ((-1.00, -2.75, 1.00), (0.10, -0.70, 0.45)),
    "rm_cam_p4_close": ((1.60, -0.90, 0.55), (0.35, -0.95, -0.10)),
    "rm_cam_p4_slump": ((1.70, -2.20, 1.05), (0.30, -0.80, 0.30)),
    "rm_cam_p5_hands": ((0.70, -2.00, 0.85), (0.28, -0.80, 0.48)),
    "rm_cam_p5_lift": ((0.40, -2.20, 0.50), (0.00, -0.12, 0.90)),
    "rm_cam_p5_wind": ((-0.90, -2.45, 1.15), (0.06, -0.28, 0.62)),
    "rm_cam_p6_rel": ((1.30, -4.00, 1.10), (0.15, -0.55, 0.68)),
    "rm_cam_p6_sky": ((-0.30, -1.70, 0.30), (0.16, -2.20, 1.55)),
    "rm_cam_hero": ((0.95, -3.60, 1.15), (0.00, -0.28, 0.68)),
    "rm_cam_p6_final": ((1.40, -6.00, 1.60), (0.12, -1.30, 1.35)),
}


# -- scene construction -------------------------------------------------------

def _unlit_material(name: str, rgb: tuple[float, float, float]) -> Any:
    import bpy

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1.0)
    em.inputs["Strength"].default_value = 1.0
    out = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def _group(obj: Any, group_name: str) -> None:
    vg = obj.vertex_groups.new(name=group_name)
    vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")


def _part(primitive: str, vg: str, **kw: Any) -> Any:
    import bpy

    getattr(bpy.ops.mesh, primitive)(**kw)
    obj = bpy.context.object
    _group(obj, vg)
    return obj


def build_mannequin(rig: Any) -> Any:
    """Rigid primitive parts joined into ONE mesh (per-bone vertex groups)."""
    import bpy

    parts: list[Any] = []
    parts.append(_part("primitive_cube_add", "hips", size=1.0, location=(0, 0, 0.02)))
    parts[-1].scale = (0.24, 0.15, 0.13)
    parts.append(_part("primitive_cube_add", "spine", size=1.0, location=(0, 0, 0.17)))
    parts[-1].scale = (0.21, 0.13, 0.18)
    parts.append(_part("primitive_cube_add", "chest", size=1.0, location=(0, 0, 0.35)))
    parts[-1].scale = (0.27, 0.145, 0.19)
    parts.append(_part("primitive_uv_sphere_add", "head", segments=32, ring_count=16,
                       radius=0.115, location=(0, -0.015, 0.655)))
    for side, sx in (("L", 1.0), ("R", -1.0)):
        parts.append(_part("primitive_uv_sphere_add", f"upper_arm.{side}", segments=24,
                           ring_count=12, radius=0.062, location=(0.15 * sx, 0, 0.45)))
        parts.append(_part("primitive_cylinder_add", f"upper_arm.{side}", vertices=20,
                           radius=0.044, depth=0.32, location=(0.31 * sx, 0, 0.45),
                           rotation=(0, math.pi / 2, 0)))
        parts.append(_part("primitive_cylinder_add", f"forearm.{side}", vertices=20,
                           radius=0.038, depth=0.28, location=(0.61 * sx, 0, 0.45),
                           rotation=(0, math.pi / 2, 0)))
        parts.append(_part("primitive_uv_sphere_add", f"hand.{side}", segments=20,
                           ring_count=10, radius=0.055, location=(0.79 * sx, 0, 0.45)))
        parts.append(_part("primitive_cylinder_add", f"upper_leg.{side}", vertices=20,
                           radius=0.056, depth=0.44, location=(0.09 * sx, 0, -0.22)))
        parts.append(_part("primitive_cylinder_add", f"lower_leg.{side}", vertices=20,
                           radius=0.045, depth=0.44, location=(0.09 * sx, 0, -0.66)))
        parts.append(_part("primitive_cube_add", f"foot.{side}", size=1.0,
                           location=(0.09 * sx, -0.05, -0.90)))
        parts[-1].scale = (0.10, 0.21, 0.055)
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = "rm_mannequin"
    mod = body.modifiers.new("rm_arm", "ARMATURE")
    mod.object = rig
    return body


def build_eyes(rig: Any) -> Any:
    """Two dark dots bone-parented to ``head`` (they ride every head tilt)."""
    import bpy

    made = []
    for sx in (1.0, -1.0):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.020,
                                             location=(0.044 * sx, -0.112, 0.678))
        made.append(bpy.context.object)
    for obj in made:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = made[-1]
    bpy.ops.object.join()
    eyes = bpy.context.object
    eyes.name = "rm_eyes"
    eyes.data.materials.append(_unlit_material("rm_eye_ink", (0.03, 0.03, 0.03)))
    eyes.parent = rig
    eyes.parent_type = "BONE"
    eyes.parent_bone = "head"
    bpy.context.view_layer.update()
    pb = rig.pose.bones["head"]
    eyes.matrix_basis = pb.matrix.inverted() @ eyes.matrix_world
    eyes.location = (0.0, 0.0, 0.0)
    return eyes


def build_dart() -> Any:
    """A folded-paper dart: 5 verts, 4 triangles, flat grey (no line art —
    the single LineArt build belongs to the protagonist; the grey value
    carries the silhouette on the light sky)."""
    import bpy

    mesh = bpy.data.meshes.new("rm_dart")
    verts = [
        (0.0, -0.18, 0.0),       # nose
        (0.0, 0.09, 0.045),      # tail top
        (0.075, 0.10, -0.015),   # tail left
        (-0.075, 0.10, -0.015),  # tail right
        (0.0, 0.05, -0.030),     # keel
    ]
    faces = [(0, 2, 1), (0, 1, 3), (0, 4, 2), (0, 3, 4)]
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new("rm_dart", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(_unlit_material("rm_dart_paper", (0.42, 0.42, 0.43)))
    return obj


def build_rig() -> Any:
    """Humanoid armature with canonical-lexicon bone names (live map_rig
    maps 1:1; bake_action is the certified transport, unchanged)."""
    import bpy

    bpy.ops.object.armature_add(location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = "rm_rig"
    bpy.ops.object.mode_set(mode="EDIT")
    bones = rig.data.edit_bones
    bones.remove(bones[0])

    def bone(name: str, parent: str | None, head: tuple[float, ...], tail: tuple[float, ...]) -> None:
        b = bones.new(name)
        b.head, b.tail = head, tail
        b.parent = bones[parent] if parent else None

    bone("hips", None, (0, 0, 0.0), (0, 0, 0.09))
    bone("spine", "hips", (0, 0, 0.09), (0, 0, 0.26))
    bone("chest", "spine", (0, 0, 0.26), (0, 0, 0.45))
    bone("neck", "chest", (0, 0, 0.45), (0, 0, 0.56))
    bone("head", "neck", (0, 0, 0.56), (0, 0, 0.72))
    for side, sx in (("L", 1.0), ("R", -1.0)):
        bone(f"shoulder.{side}", "chest", (0.04 * sx, 0, 0.45), (0.14 * sx, 0, 0.45))
        bone(f"upper_arm.{side}", f"shoulder.{side}", (0.15 * sx, 0, 0.45), (0.47 * sx, 0, 0.45))
        bone(f"forearm.{side}", f"upper_arm.{side}", (0.47 * sx, 0, 0.45), (0.75 * sx, 0, 0.45))
        bone(f"hand.{side}", f"forearm.{side}", (0.75 * sx, 0, 0.45), (0.86 * sx, 0, 0.45))
        bone(f"upper_leg.{side}", "hips", (0.09 * sx, 0, 0.0), (0.09 * sx, 0, -0.44))
        bone(f"lower_leg.{side}", f"upper_leg.{side}", (0.09 * sx, 0, -0.44), (0.09 * sx, 0, -0.88))
        bone(f"foot.{side}", f"lower_leg.{side}", (0.09 * sx, 0, -0.88), (0.09 * sx, -0.14, -0.90))
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def build_world_and_ground() -> None:
    import bpy

    world = bpy.data.worlds.new("rm_world")
    world.use_nodes = False
    world.color = (0.855, 0.855, 0.835)
    bpy.context.scene.world = world
    bpy.ops.mesh.primitive_plane_add(size=24.0, location=(0, 0, -0.93))
    ground = bpy.context.object
    ground.name = "rm_ground"
    ground.data.materials.append(_unlit_material("rm_ground_fill", (0.90, 0.895, 0.878)))


def build_cameras() -> None:
    import bpy
    from mathutils import Vector

    for name, (loc, aim) in CAMERAS.items():
        data = bpy.data.cameras.new(name)
        data.lens = 35  # wide enough that the ~1.6-unit figure fits the
        # wide panels' narrow vertical field (50mm cropped heads/darts)
        obj = bpy.data.objects.new(name, data)
        obj.location = loc
        obj.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        bpy.context.collection.objects.link(obj)


def build_scene() -> tuple[Any, Any, Any, Any, Any]:
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_world_and_ground()
    rig = build_rig()
    body = build_mannequin(rig)
    eyes = build_eyes(rig)
    dart = build_dart()
    build_cameras()
    scene = bpy.context.scene
    scene.camera = bpy.data.objects["rm_cam_p1_wide"]
    scene.render.resolution_x, scene.render.resolution_y = 480, 360
    scene.render.image_settings.file_format = "PNG"
    scene.frame_start, scene.frame_end = 1, len(BEATS)
    engines = [
        e.identifier
        for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    ]
    scene.render.engine = (
        "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    )
    return scene, rig, body, eyes, dart


# -- motion: bake + dart/root keys -------------------------------------------

def bake_and_key(scene: Any, rig: Any, dart: Any) -> dict[str, Any]:
    """20 canonical poses through the CERTIFIED bake; the dart and the rig's
    root height are keyed by THIS driver at the same frames (object-level
    fcurves — one frame_set(n) moves the whole scene deterministically)."""
    import bpy
    from riggermortis_addon import bake as bake_mod

    _sys_core()
    import riggermortis as core

    frames = [
        core.ActionFrame(frame=i, pose=build_pose(**beat["pose"]))
        for i, beat in enumerate(BEATS)
    ]
    report = bake_mod.bake_action(rig, frames, core, name="rm_dart_bake")
    if report["baked_frames"] != list(range(1, len(BEATS) + 1)):
        raise AssertionError(f"bake report frames {report['baked_frames']}")

    for i, beat in enumerate(BEATS):
        rig.location = (0.0, 0.0, float(beat["drop"]))
        rig.keyframe_insert("location", frame=i + 1)

    for i, beat in enumerate(BEATS):
        scene.frame_set(i + 1)
        bpy.context.view_layer.update()
        mode, vec, rot = beat["dart"]
        if mode == "world":
            dart.location = vec
        else:
            if mode == "hand.R":
                anchor = rig.pose.bones["hand.R"].matrix.to_translation()
            elif mode == "hands_mid":
                a = rig.pose.bones["hand.L"].matrix.to_translation()
                b = rig.pose.bones["hand.R"].matrix.to_translation()
                anchor = (a + b) / 2.0
            else:
                raise ValueError(f"unknown dart mode {mode!r}")
            dart.location = (anchor[0] + vec[0], anchor[1] + vec[1], anchor[2] + vec[2])
        dart.rotation_euler = tuple(math.radians(a) for a in rot)
        dart.keyframe_insert("location", frame=i + 1)
        dart.keyframe_insert("rotation_euler", frame=i + 1)
    scene.frame_set(1)
    return report


# -- base look (persistent-style semantics: re-apply before every page) ------

def base_look(scene: Any, body: Any, preset_name: str = "manga") -> None:
    from riggermortis_addon import style

    # The page-identity view contract (Standard + dither 0) for the PANEL
    # renders too: the default AgX compressed the light sky/ground into a
    # heavy dark grey — the manga page reads white only under Standard,
    # the same transform the page assembly stages.
    scene.view_settings.view_transform = "Standard"
    scene.render.dither_intensity = 0.0
    preset = style.load_preset(preset_name)
    body.data.materials.clear()
    style.build_toon_material(body, preset)
    if preset.get("lineart") is not None:
        style.build_lineart(body, preset)
    else:
        style.remove_lineart()
    if preset.get("tones") is not None:
        style.build_screentones(scene, preset)
    else:
        style.remove_screentones(scene)


# -- modes --------------------------------------------------------------------

def render_sheet(scene: Any, body: Any, out_dir: Path) -> int:
    """The pose contact sheet: every beat through its own camera (the
    visual-check loop; inspection artifact, git-ignored). The BASE LOOK is
    applied first — an unstyled mannequin has no emission/ink and renders
    as a flat near-black mass (the sheet must preview the real look)."""
    import bpy

    base_look(scene, body)
    sheet = out_dir / "sheet"
    sheet.mkdir(parents=True, exist_ok=True)
    r = scene.render
    staged = (scene.camera, r.resolution_x, r.resolution_y, r.filepath)
    try:
        for i, beat in enumerate(BEATS):
            scene.frame_set(i + 1)
            scene.camera = bpy.data.objects[beat["cam"]]
            r.resolution_x, r.resolution_y = 480, 360
            r.filepath = str(sheet / f"beat_{i + 1:02d}.png")
            bpy.ops.render.render(write_still=True)
    finally:
        scene.camera, r.resolution_x, r.resolution_y, r.filepath = staged
    scene.frame_set(1)
    print(f"RM_MANGA SHEET rendered={len(BEATS)} dir={sheet}", flush=True)
    return 0


def render_pages(scene: Any, body: Any, out_dir: Path) -> list[Path]:
    """The 6 story pages + hero: base look -> bubbles -> panels -> graph ->
    page render -> remove_page (the page graph must never leak into the
    next page's panel renders)."""
    from riggermortis_addon import bubbles, pages

    panel_root = out_dir / "panels"
    page_dir = out_dir / "pages"
    panel_root.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)
    done: list[Path] = []
    for name in STORY_PAGES + [HERO_PAGE]:
        page = pages.load_page(str(PAGES_DIR / f"{name}.json"))
        base_look(scene, body)
        report = pages.render_panels(scene, page, panel_root / name, subject=body)
        bubble_files = None
        if pages.page_bubble_count(page):
            entries = bubbles.render_bubbles(scene, page, panel_root / name)["bubbles"]
            bubble_files = [e["file"] for e in entries]
        graph = pages.build_page_graph(
            scene, page, [f["file"] for f in report["panels"]], bubble_files
        )
        out_path = page_dir / f"{name}.png"
        pages.render_page(scene, page, out_path)
        pages.remove_page(scene)
        done.append(out_path)
        print(
            f"RM_MANGA PAGE {name}: PASS panels={len(report['panels'])} "
            f"bubbles={pages.page_bubble_count(page)} size={graph['size']} "
            f"file={out_path.name}",
            flush=True,
        )
    return done


def assemble_pdf(page_files: list[Path], out_dir: Path) -> None:
    """PDF via the pure-stdlib writer + in-process parse-back (the same
    writer the EXPORT gate proves; the shell glue copies the checked file
    into docs/manga/)."""
    _sys_core()
    from riggermortis import pagedoc

    story = [p for p in page_files if p.stem != HERO_PAGE]
    pdf_path = out_dir / "paper_dart.pdf"
    pagedoc.write_pdf(story, pdf_path, title="Paper Dart - a wordless manga (GENERATED)")
    parsed = pagedoc.read_pdf_pages(pdf_path)
    if len(parsed) != len(story):
        raise AssertionError(f"pdf pages {len(parsed)} != {len(story)}")
    for entry in parsed:
        want = (int(entry["image_width"]), int(entry["image_height"]))
        if want != (1200, 1800):
            raise AssertionError(f"pdf page size {want}")
    print(f"RM_MANGA PDF: PASS pages={len(parsed)} file={pdf_path.name}", flush=True)


def main() -> int:
    argv = sys.argv
    if "--" not in argv or len(argv) - argv.index("--") < 2:
        print("RM_MANGA FAIL: expected -- OUT_DIR [sheet|pages|all]")
        return 2
    rest = argv[argv.index("--") + 1:]
    out_dir = Path(rest[0]).resolve()
    mode = rest[1] if len(rest) > 1 else "all"
    if mode not in ("sheet", "pages", "all"):
        print(f"RM_MANGA FAIL: unknown mode {mode!r} (hint: sheet|pages|all)")
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    scene, rig, body, eyes, dart = build_scene()
    bake_and_key(scene, rig, dart)
    print(f"RM_MANGA SCENE: OK beats={len(BEATS)} cameras={len(CAMERAS)}", flush=True)

    if mode in ("sheet", "all"):
        render_sheet(scene, body, out_dir)
    if mode in ("pages", "all"):
        page_files = render_pages(scene, body, out_dir)
        assemble_pdf(page_files, out_dir)
    print("RM_MANGA BUILD OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
