"""Bone-name heuristics across rig families."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riggermortis.names import evidence, split_tokens  # noqa: E402


def test_rigify_numbered_spine():
    e = evidence("spine.001")
    assert e.role == "spine"
    assert e.chain_index == 1
    assert e.score >= 0.8


def test_mixamo_trap_leftleg_is_shin():
    assert evidence("mixamorig:LeftLeg").role == "lower_leg.L"
    assert evidence("mixamorig:RightLeg").role == "lower_leg.R"
    assert evidence("mixamorig:LeftUpLeg").role == "upper_leg.L"


def test_mixamo_generic():
    assert evidence("mixamorig:Hips").role == "hips"
    assert evidence("mixamorig:LeftArm").role == "upper_arm.L"
    assert evidence("mixamorig:LeftForeArm").role == "forearm.L"
    assert evidence("mixamorig:LeftToeBase").role == "toe.L"
    assert evidence("mixamorig:Spine2").role == "spine"


def test_vrm_structured_names():
    assert evidence("J_Bip_C_Hips").role == "hips"
    assert evidence("J_Bip_L_UpperArm").role == "upper_arm.L"
    assert evidence("J_Bip_R_LowerLeg").role == "lower_leg.R"
    assert evidence("J_Bip_C_Chest").role == "chest"


def test_unreal_style():
    assert evidence("thigh_l").role == "upper_leg.L"
    assert evidence("calf_r").role == "lower_leg.R"
    assert evidence("upperarm_l").role == "upper_arm.L"


def test_camel_case_without_separators():
    assert evidence("LeftForeArm").role == "forearm.L"
    assert evidence("RightUpLeg").role == "upper_leg.R"


def test_non_pose_bones_are_skipped():
    for name in ("thumb.L", "index_r", "hair_front", "twist_arm.L", "eye.L"):
        e = evidence(name)
        assert e.skip, f"{name} should be skipped"


def test_unknown_names_are_honest():
    e = evidence("b12")
    assert e.role is None
    assert e.role_base is None
    assert e.score == 0.0
    assert not e.skip


def test_def_prefixes_are_stripped():
    assert evidence("DEF-spine").role == "spine"
    assert evidence("ORG-upper_arm.L").role == "upper_arm.L"


def test_split_tokens_variants():
    assert split_tokens("spine.001") == ["spine", "001"]
    assert split_tokens("LeftUpLeg") == ["left", "up", "leg"]
    assert split_tokens("mixamorig:Hips") == ["mixamorig", "hips"]
    assert split_tokens("thigh_l") == ["thigh", "l"]


def test_deterministic():
    for name in ("mixamorig:LeftLeg", "spine.001", "b12", "J_Bip_L_UpperArm"):
        assert evidence(name) == evidence(name)
