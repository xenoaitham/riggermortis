"""The Phase 0 gate: five varied rigs mapped with <=2 corrections each.

A "correction" here is a role the review UI would need the user to reassign:
for the humanoid rigs the mapper must nail every core role outright; for the
deliberately ambiguous quadruped the contract is honest flagging, not magic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from riggermortis.mapper import map_rig  # noqa: E402
from rigs import (  # noqa: E402
    MIXAMO_NAMES,
    mixamo_rig,
    quadruped_rig,
    rigify_rig,
    vrm_rig,
    weird_rig,
)


def _bone(mapping, role):
    a = mapping.assignments.get(role)
    return a.bone if a else None


def test_gate_rigify():
    m = map_rig(rigify_rig())
    assert _bone(m, "hips") == "pelvis"
    assert _bone(m, "spine") == "spine"
    assert _bone(m, "chest") == "spine.001"
    assert _bone(m, "neck") == "neck"
    assert _bone(m, "head") == "head"
    for side in ("L", "R"):
        assert _bone(m, f"upper_arm.{side}") == f"upper_arm.{side}"
        assert _bone(m, f"forearm.{side}") == f"forearm.{side}"
        assert _bone(m, f"hand.{side}") == f"hand.{side}"
        assert _bone(m, f"upper_leg.{side}") == f"thigh.{side}"
        assert _bone(m, f"lower_leg.{side}") == f"shin.{side}"
        assert _bone(m, f"foot.{side}") == f"foot.{side}"
        assert _bone(m, f"toe.{side}") == f"toe.{side}"
        assert _bone(m, f"shoulder.{side}") == f"shoulder.{side}"
    assert m.core_missing() == []
    for a in m.assignments.values():
        if a.role in ("hips", "spine", "chest", "neck", "head") or "." in a.role:
            assert a.confidence >= 0.55, f"{a.role} confidence {a.confidence:.2f} too low"


def test_gate_mixamo():
    m = map_rig(mixamo_rig())
    assert _bone(m, "hips") == MIXAMO_NAMES["hips"]
    assert _bone(m, "spine") == "mixamorig:Spine"
    assert _bone(m, "chest") == "mixamorig:Spine1"
    assert _bone(m, "neck") == "mixamorig:Neck"
    assert _bone(m, "head") == "mixamorig:Head"
    # the trap: Mixamo's LeftLeg is a shin
    assert _bone(m, "lower_leg.L") == "mixamorig:LeftLeg"
    assert _bone(m, "upper_leg.L") == "mixamorig:LeftUpLeg"
    assert _bone(m, "upper_arm.L") == "mixamorig:LeftArm"
    assert _bone(m, "forearm.L") == "mixamorig:LeftForeArm"
    assert _bone(m, "hand.L") == "mixamorig:LeftHand"
    assert _bone(m, "foot.L") == "mixamorig:LeftFoot"
    assert m.core_missing() == []
    assert "mixamorig:Spine2" in m.unmapped_bones  # honestly reported


def test_gate_vrm():
    m = map_rig(vrm_rig())
    assert _bone(m, "hips") == "J_Bip_C_Hips"
    assert _bone(m, "spine") == "J_Bip_C_Spine"
    assert _bone(m, "chest") == "J_Bip_C_Chest"
    assert _bone(m, "head") == "J_Bip_C_Head"
    assert _bone(m, "upper_arm.L") == "J_Bip_L_UpperArm"
    assert _bone(m, "lower_leg.R") == "J_Bip_R_LowerLeg"
    assert _bone(m, "foot.R") == "J_Bip_R_Foot"
    assert m.core_missing() == []


def test_gate_weird_names_geometry_only():
    m = map_rig(weird_rig())
    assert m.core_missing() == [], f"missing: {m.core_missing()}"
    assert _bone(m, "root") == "b00"
    assert _bone(m, "hips") == "b01"
    assert _bone(m, "spine") == "b02"
    assert _bone(m, "chest") == "b03"
    assert _bone(m, "neck") == "b04"
    assert _bone(m, "head") == "b05"
    assert _bone(m, "upper_arm.L") == "b06"
    assert _bone(m, "forearm.L") == "b07"
    assert _bone(m, "hand.L") == "b08"
    assert _bone(m, "upper_arm.R") == "b09"
    assert _bone(m, "upper_leg.L") == "b12"
    assert _bone(m, "lower_leg.L") == "b13"
    assert _bone(m, "foot.L") == "b14"
    assert _bone(m, "toe.L") == "b15"
    assert _bone(m, "upper_leg.R") == "b16"
    for a in m.assignments.values():
        assert a.confidence <= 0.75 + 1e-9, f"{a.role} geometry confidence not capped"


def test_gate_quadruped_flagged_not_faked():
    m = map_rig(quadruped_rig())
    assert _bone(m, "head") == "head"
    assert _bone(m, "neck") == "neck"
    assert _bone(m, "spine") == "spine.01"
    # Four downward chains exist; humanoid mapping must not silently pretend.
    assert len([r for r in m.assignments if r.startswith("upper_leg.")]) == 2
    assert len(m.ambiguities) >= 2
    assert any("quadruped" in n.lower() for n in m.notes), m.notes


def test_gate_determinism_all_five():
    from rigs import all_five

    for name, rig in all_five().items():
        first = json.dumps(map_rig(rig).to_dict(), sort_keys=True)
        second = json.dumps(map_rig(rig).to_dict(), sort_keys=True)
        assert first == second, f"{name} mapping is not deterministic"


def test_confidences_in_range_and_assignments_unique():
    from rigs import all_five

    for rig in all_five().values():
        m = map_rig(rig)
        bones = [a.bone for a in m.assignments.values()]
        assert len(bones) == len(set(bones)), "one bone mapped to two roles"
        for a in m.assignments.values():
            assert 0.0 <= a.confidence <= 1.0
