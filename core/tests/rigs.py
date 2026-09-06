"""Synthetic test rigs: the five families the Phase 0 gate requires.

Rigify-style, Mixamo-style, VRM-style, an opaque custom rig (``b00`` names,
geometry-only mapping), and a deliberately ambiguous quadruped. All
coordinates are meters in Blender world convention: Z up, facing -Y,
character-left = +X.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riggermortis.types import BoneData, RigData  # noqa: E402

Vec = tuple[float, float, float]


def _add(rig: RigData, name: str, parent: str | None, head: Vec, tail: Vec) -> None:
    rig.bones[name] = BoneData(name=name, parent=parent, head=head, tail=tail)


def _humanoid_joints() -> dict[str, tuple[Vec, Vec]]:
    """Canonical humanoid joint table (~1.70 m, T-pose)."""
    j: dict[str, tuple[Vec, Vec]] = {
        "hips": ((0.0, 0.0, 0.98), (0.0, 0.0, 1.06)),
        "spine": ((0.0, 0.0, 1.06), (0.0, 0.0, 1.22)),
        "chest": ((0.0, 0.0, 1.22), (0.0, 0.0, 1.40)),
        "neck": ((0.0, 0.0, 1.40), (0.0, 0.0, 1.50)),
        "head": ((0.0, 0.0, 1.50), (0.0, 0.0, 1.70)),
    }
    for side, sx in (("L", 1.0), ("R", -1.0)):
        j[f"shoulder.{side}"] = ((0.03 * sx, 0.0, 1.44), (0.14 * sx, 0.0, 1.46))
        j[f"upper_arm.{side}"] = ((0.16 * sx, 0.0, 1.45), (0.46 * sx, 0.0, 1.45))
        j[f"forearm.{side}"] = ((0.46 * sx, 0.0, 1.45), (0.72 * sx, 0.0, 1.45))
        j[f"hand.{side}"] = ((0.72 * sx, 0.0, 1.45), (0.82 * sx, 0.0, 1.45))
        j[f"upper_leg.{side}"] = ((0.10 * sx, 0.0, 0.98), (0.11 * sx, 0.0, 0.52))
        j[f"lower_leg.{side}"] = ((0.11 * sx, 0.0, 0.52), (0.11 * sx, 0.0, 0.09))
        j[f"foot.{side}"] = ((0.11 * sx, 0.01, 0.09), (0.11 * sx, -0.13, 0.05))
        j[f"toe.{side}"] = ((0.11 * sx, -0.13, 0.05), (0.11 * sx, -0.24, 0.05))
    return j


_CANON_PARENTS: dict[str, str | None] = {
    "hips": None, "spine": "hips", "chest": "spine", "neck": "chest", "head": "neck",
}
for _side in ("L", "R"):
    _CANON_PARENTS[f"shoulder.{_side}"] = "chest"
    _CANON_PARENTS[f"upper_arm.{_side}"] = f"shoulder.{_side}"
    _CANON_PARENTS[f"forearm.{_side}"] = f"upper_arm.{_side}"
    _CANON_PARENTS[f"hand.{_side}"] = f"forearm.{_side}"
    _CANON_PARENTS[f"upper_leg.{_side}"] = "hips"
    _CANON_PARENTS[f"lower_leg.{_side}"] = f"upper_leg.{_side}"
    _CANON_PARENTS[f"foot.{_side}"] = f"lower_leg.{_side}"
    _CANON_PARENTS[f"toe.{_side}"] = f"foot.{_side}"


def _named_humanoid(name_map: dict[str, str], rig_name: str) -> RigData:
    rig = RigData(name=rig_name, bones={})
    for role, (head, tail) in _humanoid_joints().items():
        canon_parent = _CANON_PARENTS[role]
        parent = name_map[canon_parent] if canon_parent is not None else None
        _add(rig, name_map[role], parent, head, tail)
    return rig


def rigify_rig() -> RigData:
    """Rigify-style names, including the numbered spine chain."""
    names = {
        "hips": "pelvis", "spine": "spine", "chest": "spine.001",
        "neck": "neck", "head": "head",
    }
    for role in _humanoid_joints():
        if role not in names:
            names[role] = role  # arm/foot chains keep canonical names
    names["upper_leg.L"], names["upper_leg.R"] = "thigh.L", "thigh.R"
    names["lower_leg.L"], names["lower_leg.R"] = "shin.L", "shin.R"
    return _named_humanoid(names, "rigify_meta")


MIXAMO_NAMES = {
    "hips": "mixamorig:Hips", "spine": "mixamorig:Spine", "chest": "mixamorig:Spine1",
    "neck": "mixamorig:Neck", "head": "mixamorig:Head",
    "shoulder.L": "mixamorig:LeftShoulder", "shoulder.R": "mixamorig:RightShoulder",
    "upper_arm.L": "mixamorig:LeftArm", "upper_arm.R": "mixamorig:RightArm",
    "forearm.L": "mixamorig:LeftForeArm", "forearm.R": "mixamorig:RightForeArm",
    "hand.L": "mixamorig:LeftHand", "hand.R": "mixamorig:RightHand",
    "upper_leg.L": "mixamorig:LeftUpLeg", "upper_leg.R": "mixamorig:RightUpLeg",
    "lower_leg.L": "mixamorig:LeftLeg", "lower_leg.R": "mixamorig:RightLeg",
    "foot.L": "mixamorig:LeftFoot", "foot.R": "mixamorig:RightFoot",
    "toe.L": "mixamorig:LeftToeBase", "toe.R": "mixamorig:RightToeBase",
}


def mixamo_rig() -> RigData:
    """Mixamo-style rig: the lying ``LeftLeg``-is-a-shin trap, plus an extra Spine2."""
    rig = _named_humanoid(MIXAMO_NAMES, "mixamo_char")
    # Spine2 sits between Spine1 and Neck; expect it to surface as unmapped.
    _add(rig, "mixamorig:Spine2", "mixamorig:Spine1", (0.0, 0.0, 1.40), (0.0, 0.0, 1.52))
    _add(rig, "mixamorig:Neck", "mixamorig:Spine2", (0.0, 0.0, 1.52), (0.0, 0.0, 1.62))
    _add(rig, "mixamorig:Head", "mixamorig:Neck", (0.0, 0.0, 1.62), (0.0, 0.0, 1.82))
    return rig


VRM_NAMES = {
    "hips": "J_Bip_C_Hips", "spine": "J_Bip_C_Spine", "chest": "J_Bip_C_Chest",
    "neck": "J_Bip_C_Neck", "head": "J_Bip_C_Head",
    "shoulder.L": "J_Bip_L_Shoulder", "shoulder.R": "J_Bip_R_Shoulder",
    "upper_arm.L": "J_Bip_L_UpperArm", "upper_arm.R": "J_Bip_R_UpperArm",
    "forearm.L": "J_Bip_L_LowerArm", "forearm.R": "J_Bip_R_LowerArm",
    "hand.L": "J_Bip_L_Hand", "hand.R": "J_Bip_R_Hand",
    "upper_leg.L": "J_Bip_L_UpperLeg", "upper_leg.R": "J_Bip_R_UpperLeg",
    "lower_leg.L": "J_Bip_L_LowerLeg", "lower_leg.R": "J_Bip_R_LowerLeg",
    "foot.L": "J_Bip_L_Foot", "foot.R": "J_Bip_R_Foot",
    "toe.L": "J_Bip_L_ToeBase", "toe.R": "J_Bip_R_ToeBase",
}


def vrm_rig() -> RigData:
    return _named_humanoid(dict(VRM_NAMES), "vrm_avatar")


def weird_rig() -> RigData:
    """Opaque ``b00`` names on a clean humanoid: geometry must carry the mapping."""
    rig = RigData(name="game_char_final_v2", bones={})
    _add(rig, "b00", None, (0.0, 0.0, 0.90), (0.0, 0.0, 0.98))
    _add(rig, "b01", "b00", (0.0, 0.0, 0.98), (0.0, 0.0, 1.06))
    _add(rig, "b02", "b01", (0.0, 0.0, 1.06), (0.0, 0.0, 1.22))
    _add(rig, "b03", "b02", (0.0, 0.0, 1.22), (0.0, 0.0, 1.40))
    _add(rig, "b04", "b03", (0.0, 0.0, 1.40), (0.0, 0.0, 1.50))
    _add(rig, "b05", "b04", (0.0, 0.0, 1.50), (0.0, 0.0, 1.70))
    for side, sx, off in (("L", 1.0, 0), ("R", -1.0, 3)):
        a, f, h = 6 + off, 7 + off, 8 + off
        _add(rig, f"b{a:02d}", "b03", (0.16 * sx, 0.0, 1.45), (0.46 * sx, 0.0, 1.45))
        _add(rig, f"b{f:02d}", f"b{a:02d}", (0.46 * sx, 0.0, 1.45), (0.72 * sx, 0.0, 1.45))
        _add(rig, f"b{h:02d}", f"b{f:02d}", (0.72 * sx, 0.0, 1.45), (0.82 * sx, 0.0, 1.45))
        t, s, ft, to = (12, 13, 14, 15) if side == "L" else (16, 17, 18, 19)
        _add(rig, f"b{t:02d}", "b01", (0.10 * sx, 0.0, 0.98), (0.11 * sx, 0.0, 0.52))
        _add(rig, f"b{s:02d}", f"b{t:02d}", (0.11 * sx, 0.0, 0.52), (0.11 * sx, 0.0, 0.09))
        _add(rig, f"b{ft:02d}", f"b{s:02d}", (0.11 * sx, 0.01, 0.09), (0.11 * sx, -0.13, 0.05))
        _add(rig, f"b{to:02d}", f"b{ft:02d}", (0.11 * sx, -0.13, 0.05), (0.11 * sx, -0.24, 0.05))
    return rig


def quadruped_rig() -> RigData:
    """Deliberately ambiguous quadruped: four downward limb chains, horizontal spine."""
    rig = RigData(name="quad_creature", bones={})
    _add(rig, "q_root", None, (0.0, 0.30, 0.55), (0.0, 0.15, 0.58))
    _add(rig, "spine.01", "q_root", (0.0, 0.15, 0.58), (0.0, 0.00, 0.60))
    _add(rig, "spine.02", "spine.01", (0.0, 0.00, 0.60), (0.0, -0.15, 0.58))
    _add(rig, "spine.03", "spine.02", (0.0, -0.15, 0.58), (0.0, -0.30, 0.55))
    _add(rig, "neck", "spine.01", (0.0, 0.15, 0.58), (0.0, 0.25, 0.70))
    _add(rig, "head", "neck", (0.0, 0.25, 0.70), (0.0, 0.38, 0.72))
    _add(rig, "tail.01", "spine.03", (0.0, -0.30, 0.55), (0.0, -0.45, 0.60))
    for side, sx in (("L", 1.0), ("R", -1.0)):
        for prefix, parent, y, top_z in (
            ("F", "spine.01", 0.10, 0.58),
            ("B", "spine.03", -0.28, 0.55),
        ):
            _add(rig, f"leg{prefix}{side}", parent,
                 (0.12 * sx, y, top_z), (0.14 * sx, y, top_z - 0.30))
            _add(rig, f"shin{prefix}{side}", f"leg{prefix}{side}",
                 (0.14 * sx, y, top_z - 0.30), (0.14 * sx, y, top_z - 0.56))
            _add(rig, f"paw{prefix}{side}", f"shin{prefix}{side}",
                 (0.14 * sx, y, top_z - 0.56), (0.14 * sx, y - 0.06, top_z - 0.56))
    return rig


def all_five() -> dict[str, RigData]:
    return {
        "rigify": rigify_rig(),
        "mixamo": mixamo_rig(),
        "vrm": vrm_rig(),
        "weird": weird_rig(),
        "quadruped": quadruped_rig(),
    }
