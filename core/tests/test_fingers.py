"""P8-3 finger-chain contract tests (docs/FINGERS.md § As-built design).

Pins: the additive D-021 namespace, the per-finger confidence gate (100%
gated-skip on the occlusion fixtures, ledgered reasons, never guessed),
the declared forward-curl depth rule, the hands-free byte-identity
contract (to_dict omits `hands` when empty), payload/preset round-trips,
and the FK apply path (finger_map fidelity within the 0.5 deg family +
the loud capability line on both no-target sides).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from riggermortis import (
    FINGER_CONF_FLOOR,
    FINGER_SEGMENT_LENGTHS,
    FingerChain,
    apply_canonical_pose,
    finger_parent,
    finger_roles,
    hand_kp_index,
    is_finger_role,
    resolve_hands,
    solve_hand,
    solve_hands,
)
from riggermortis.canonical_pose import CanonicalPose
from riggermortis.errors import PresetError, RiggermortisError
from riggermortis.fk_apply import verify_application
from riggermortis.inference.poses import (
    HAND_KP_COUNT,
    HAND_L_END,
    HAND_L_START,
    HAND_R_END,
    HAND_R_START,
    KEYPOINT_COUNT,
)
from riggermortis.mapper import RigMapping, RoleAssignment
from riggermortis.payload import build_pose_payload
from riggermortis.presets import preset_from_mapping
from riggermortis.types import BoneData, RigData

FINGERS = ("thumb", "index", "middle", "ring", "pinky")
JOINTS = ("mcp", "pip", "dip", "tip")

WRIST = (0.5, 0.0, 0.9)
AX, AY, SCALE = 320.0, 240.0, 400.0


def _project(p3):
    return (AX + p3[0] * SCALE, AY - p3[2] * SCALE)


def _body_pose_stub():
    return CanonicalPose(
        positions={
            "hips": (0.0, 0.0, 0.0),
            "hand.L": WRIST,
            "forearm.L": (WRIST[0] - 0.28, WRIST[1], WRIST[2]),
        },
        flips={},
        confidence=0.8,
        reliable=True,
        scale=SCALE,
        anchor="hips",
        notes=[],
        joint_confidence={},
    )


def _gt_chain(base, splay_deg, curls_deg, lengths, mcp):
    def rot_y(v, deg):
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        return (v[0] * c - v[2] * s, v[1], v[0] * s + v[2] * c)

    def curl(v, deg):
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        return (v[0] * c, -(v[0] * s) + v[1] * c, v[2])

    d = rot_y(base, splay_deg)
    joints = {"mcp": mcp}
    prev = mcp
    for k, name in enumerate(("pip", "dip", "tip")):
        d = curl(d, curls_deg[k])
        prev = tuple(prev[i] + d[i] * lengths[k] for i in range(3))
        joints[name] = prev
    return joints


def _gt_hand(splays, curls, wrist=WRIST):
    """GT hand.L chains + the projected 133-kp arrays (conf 0.9/0.95)."""
    gt = {}
    kps = [(0.0, 0.0)] * KEYPOINT_COUNT
    confs = [0.0] * KEYPOINT_COUNT
    kps[9] = _project(wrist)  # WRIST_L
    confs[9] = 0.95
    for f in FINGERS:
        mcp = (wrist[0] + 0.02, wrist[1], wrist[2] + 0.01 * FINGERS.index(f))
        gj = _gt_chain((1.0, 0.0, 0.0), splays[f], curls[f], FINGER_SEGMENT_LENGTHS[f], mcp)
        gt[f] = gj
        for jname in JOINTS:
            idx = hand_kp_index("hand.L", f, jname)
            kps[idx] = _project(gj[jname])
            confs[idx] = 0.9
    return gt, kps, confs


def _segment_dirs(joints):
    out = []
    for a, b in (("mcp", "pip"), ("pip", "dip"), ("dip", "tip")):
        d = tuple(joints[b][i] - joints[a][i] for i in range(3))
        n = math.sqrt(sum(c * c for c in d))
        out.append(tuple(c / n for c in d))
    return out


# -- namespace ------------------------------------------------------------------


def test_finger_namespace_disjoint_from_frozen_core():
    roles = finger_roles()
    assert len(roles) == 40
    from riggermortis.canonical import ALL_ROLES

    assert not (set(roles) & set(ALL_ROLES))
    assert all(is_finger_role(r) for r in roles)
    assert not any(is_finger_role(r) for r in ALL_ROLES)


def test_finger_topology_parents_chain_to_hand():
    assert finger_parent("hand.L.finger.index.mcp") == "hand.L"
    assert finger_parent("hand.L.finger.index.pip") == "hand.L.finger.index.mcp"
    assert finger_parent("hand.R.finger.pinky.tip") == "hand.R.finger.pinky.dip"
    assert finger_parent("hand.L") is None  # a body role, not a finger role
    assert finger_parent("hips") is None


def test_hand_kp_index_tiles_the_coco_ranges_and_refuses_unknowns():
    idx = [hand_kp_index(h, f, j) for h in ("hand.L", "hand.R") for f in FINGERS for j in JOINTS]
    assert len(idx) == 40 and len(set(idx)) == 40
    assert all(HAND_L_START <= i < HAND_R_END for i in idx)
    assert HAND_L_END - HAND_L_START == HAND_KP_COUNT == HAND_R_END - HAND_R_START
    with pytest.raises(ValueError, match="unknown hand"):
        hand_kp_index("hand.M", "index", "mcp")
    with pytest.raises(ValueError, match="unknown finger"):
        hand_kp_index("hand.L", "thumb2", "mcp")
    with pytest.raises(ValueError, match="unknown joint"):
        hand_kp_index("hand.L", "index", "knuckle")


# -- the solve + gate ------------------------------------------------------------


def test_visible_hand_solves_all_fingers():
    splays = {"thumb": -20.0, "index": -6.0, "middle": 0.0, "ring": 6.0, "pinky": 14.0}
    _gt, kps, confs = _gt_hand(splays, {f: (0.0, 0.0, 0.0) for f in FINGERS})
    solved = solve_hands(kps, confs, _body_pose_stub())
    assert set(solved) == {"hand.L"}
    hand = solved["hand.L"]
    assert set(hand.fingers) == set(FINGERS)
    assert hand.skipped == {}
    for chain in hand.fingers.values():
        assert set(chain.joints) == set(JOINTS)
        assert all(math.isfinite(c) for p in chain.joints.values() for c in p)


def test_occlusion_fixtures_gate_skip_100_percent_with_ledger():
    splays = {"thumb": 0.0, "index": 0.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0}
    _gt, kps, confs = _gt_hand(splays, {f: (0.0, 0.0, 0.0) for f in FINGERS})
    pose = _body_pose_stub()

    behind_back = list(confs)
    for i in range(HAND_L_START, HAND_L_END):
        behind_back[i] = 0.0  # hand-behind-back class: no response
    hs = solve_hand("hand.L", kps, behind_back, pose, AX, AY, SCALE)
    assert hs is not None and hs.fingers == {}
    assert set(hs.skipped) == set(FINGERS)
    assert all("below floor 0.55" in r for r in hs.skipped.values())

    clenched = list(confs)
    for i in range(HAND_L_START + 1, HAND_L_END):
        clenched[i] = FINGER_CONF_FLOOR - 0.05  # kps present, all below floor
    hs2 = solve_hand("hand.L", kps, clenched, pose, AX, AY, SCALE)
    assert hs2 is not None and hs2.fingers == {}
    assert len(hs2.skipped) == 5


def test_partial_gate_skips_only_below_floor_fingers():
    splays = {"thumb": 0.0, "index": 0.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0}
    _gt, kps, confs = _gt_hand(splays, {f: (0.0, 0.0, 0.0) for f in FINGERS})
    confs[hand_kp_index("hand.L", "ring", "dip")] = 0.4  # one joint dips out
    hand = solve_hands(kps, confs, _body_pose_stub())["hand.L"]
    assert "ring" in hand.skipped and set(hand.fingers) == set(FINGERS) - {"ring"}


def test_wrist_below_floor_means_no_entry_absent_reads_clean():
    _gt, kps, confs = _gt_hand({f: 0.0 for f in FINGERS}, {f: (0.0, 0.0, 0.0) for f in FINGERS})
    confs[9] = 0.3  # the anchor itself fails
    assert solve_hands(kps, confs, _body_pose_stub()) == {}


def test_direction_bars_on_prior_consistent_gt():
    all_errs = []
    cases = [
        ({f: 0.0 for f in FINGERS}, {f: (0.0, 0.0, 0.0) for f in FINGERS}),
        ({"thumb": -40.0, "index": -15.0, "middle": 0.0, "ring": 15.0, "pinky": 32.0},
         {f: (0.0, 0.0, 0.0) for f in FINGERS}),
        ({f: -4.0 for f in FINGERS}, {f: (35.0, 40.0, 30.0) for f in FINGERS}),
    ]
    for splays, curls in cases:
        gt, kps, confs = _gt_hand(splays, curls)
        solved = solve_hands(kps, confs, _body_pose_stub())["hand.L"]
        for f in FINGERS:
            sd = _segment_dirs(solved.fingers[f].joints)
            gd = _segment_dirs(gt[f])
            for a, b in zip(sd, gd, strict=True):
                dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b, strict=True))))
                all_errs.append(math.degrees(math.acos(dot)))
    all_errs.sort()
    median = all_errs[len(all_errs) // 2]
    p90 = all_errs[min(int(0.9 * len(all_errs)), len(all_errs) - 1)]
    assert median <= 20.0 and p90 <= 35.0  # Annex A.1 bars [SYNTHETIC]


def test_solve_deterministic_twin():
    _gt, kps, confs = _gt_hand(
        {f: -5.0 for f in FINGERS}, {f: (20.0, 25.0, 15.0) for f in FINGERS}
    )
    assert solve_hands(kps, confs, _body_pose_stub()) == solve_hands(
        kps, confs, _body_pose_stub()
    )


# -- CanonicalPose contract ---------------------------------------------------------


def test_hands_free_to_dict_is_byte_identical_to_pre_p8_3_shape():
    pose = _body_pose_stub()
    d = pose.to_dict()
    assert "hands" not in d  # the omit-when-empty contract
    assert set(d) == {
        "positions", "flips", "confidence", "reliable", "scale",
        "anchor", "notes", "joint_confidence",
    }


def test_hands_round_trip_exact():
    _gt, kps, confs = _gt_hand({f: -5.0 for f in FINGERS}, {f: (15.0, 20.0, 10.0) for f in FINGERS})
    pose = _body_pose_stub()
    pose.hands = solve_hands(kps, confs, pose)
    rebuilt = CanonicalPose.from_dict(pose.to_dict())
    assert rebuilt.to_dict() == pose.to_dict()
    assert set(rebuilt.hands) == {"hand.L"}


def test_from_dict_tolerates_hands_free_payloads():
    pose = _body_pose_stub()
    d = pose.to_dict()
    d["hands"] = {}  # older writers could emit an empty dict — tolerated
    assert CanonicalPose.from_dict(d).hands == {}
    assert "hands" not in CanonicalPose.from_dict(pose.to_dict()).to_dict()


def test_mirrored_swaps_hands_and_negates_x():
    _gt, kps, confs = _gt_hand({f: -5.0 for f in FINGERS}, {f: (15.0, 20.0, 10.0) for f in FINGERS})
    pose = _body_pose_stub()
    pose.hands = solve_hands(kps, confs, pose)
    pose.hands["hand.L"].skipped["pinky"] = "confidence 0.10 below floor 0.55"
    mirror = pose.mirrored()
    assert set(mirror.hands) == {"hand.R"}
    chain = mirror.hands["hand.R"].fingers["thumb"]
    orig = pose.hands["hand.L"].fingers["thumb"]
    assert chain.joints["mcp"][0] == -orig.joints["mcp"][0]
    assert chain.joints["mcp"][1] == orig.joints["mcp"][1]  # depth untouched
    assert mirror.hands["hand.R"].skipped == pose.hands["hand.L"].skipped


def test_hand_and_chain_validation_is_loud():
    pose = _body_pose_stub()
    d = pose.to_dict()
    d["hands"] = {"hand.L": {"fingers": {"claw": {"joints": {}, "confidence": 1.0}}}}
    with pytest.raises(RiggermortisError, match="unknown finger"):
        CanonicalPose.from_dict(d)
    with pytest.raises(RiggermortisError, match="no joints object"):
        FingerChain.from_dict({"confidence": 1.0})
    with pytest.raises(RiggermortisError, match="exactly mcp, pip, dip, tip"):
        FingerChain.from_dict({"joints": {"mcp": [0, 0, 0]}, "confidence": 1.0})
    with pytest.raises(RiggermortisError, match="unknown hand"):
        solve_hand("hand.M", [(0.0, 0.0)] * KEYPOINT_COUNT, [0.0] * KEYPOINT_COUNT, pose, 0, 0, 1)


# -- FK apply ------------------------------------------------------------------------


def _rig_with_fingers():
    """Synthetic rig: the arm chain + one hand.L finger chain (two-pass
    builder discipline: create every bone, then wire parents)."""
    bones: dict[str, BoneData] = {}
    specs = {
        "upper_arm.L": ((0.5, 0.0, 1.0), (0.8, 0.0, 1.0), None),
        "forearm.L": ((0.8, 0.0, 1.0), (1.05, 0.0, 1.0), "upper_arm.L"),
        "hand.L": ((1.05, 0.0, 1.0), (1.15, 0.0, 1.0), "forearm.L"),
        "f_index_1": ((1.15, 0.0, 1.0), (1.18, 0.0, 1.0), "hand.L"),
        "f_index_2": ((1.18, 0.0, 1.0), (1.20, 0.0, 1.0), "f_index_1"),
        "f_index_3": ((1.20, 0.0, 1.0), (1.216, 0.0, 1.0), "f_index_2"),
    }
    for name, (head, tail, parent) in specs.items():
        bones[name] = BoneData(
            name=name, head=head, tail=tail, parent=parent,
        )
    return RigData(name="finger-rig", bones=bones, source="test")


def _mapping(rig, extra_finger=False):
    assignments = {
        "upper_arm.L": RoleAssignment("upper_arm.L", "upper_arm.L", 1.0, "L"),
        "forearm.L": RoleAssignment("forearm.L", "forearm.L", 1.0, "L"),
        "hand.L": RoleAssignment("hand.L", "hand.L", 1.0, "L"),
    }
    return RigMapping(
        rig_name=rig.name, fingerprint=rig.fingerprint(), assignments=assignments
    )


def _pose_with_hands():
    splays = {"thumb": 0.0, "index": 0.0, "middle": 0.0, "ring": 0.0, "pinky": 0.0}
    _gt, kps, confs = _gt_hand(splays, {f: (10.0, 12.0, 8.0) for f in FINGERS})
    pose = _body_pose_stub()
    pose.hands = solve_hands(kps, confs, pose)
    return pose


def test_apply_with_finger_map_binds_finger_chain_within_family_bar():
    rig = _rig_with_fingers()
    pose = _pose_with_hands()
    finger_map = {
        "hand.L.finger.index.mcp": "f_index_1",
        "hand.L.finger.index.pip": "f_index_2",
        "hand.L.finger.index.dip": "f_index_3",
    }
    app = apply_canonical_pose(rig, _mapping(rig), pose, finger_map=finger_map)
    assert not any("fingers not applied" in n for n in app.notes)
    finger_rotations = [r for r in app.rotations if r.role in finger_map]
    assert len(finger_rotations) == 3
    errors = verify_application(rig, app, pose)
    for role in finger_map:
        assert errors[role] <= math.radians(0.5)


def test_no_finger_map_with_hands_carries_the_loud_capability_line():
    rig = _rig_with_fingers()
    pose = _pose_with_hands()
    app = apply_canonical_pose(rig, _mapping(rig), pose)
    line = [n for n in app.notes if "fingers not applied" in n]
    assert len(line) == 1 and "5 finger chain(s) solved" in line[0]
    assert not [r for r in app.rotations if is_finger_role(r.role)]


def test_finger_bindings_without_hands_report_loud_and_apply_nothing():
    rig = _rig_with_fingers()
    pose = _body_pose_stub()  # no hands solved
    finger_map = {"hand.L.finger.index.mcp": "f_index_1"}
    app = apply_canonical_pose(rig, _mapping(rig), pose, finger_map=finger_map)
    assert any("pose carries no hands" in n for n in app.notes)
    assert not [r for r in app.rotations if is_finger_role(r.role)]


def test_tip_binding_and_non_finger_keys_refuse_loudly():
    rig = _rig_with_fingers()
    pose = _pose_with_hands()
    with pytest.raises(ValueError, match="cannot bind"):
        apply_canonical_pose(
            rig, _mapping(rig), pose,
            finger_map={"hand.L.finger.index.tip": "f_index_3"},
        )
    with pytest.raises(ValueError, match="not a finger role"):
        apply_canonical_pose(rig, _mapping(rig), pose, finger_map={"hips": "f_index_1"})


def test_missing_bound_bone_is_skipped_loud():
    rig = _rig_with_fingers()
    pose = _pose_with_hands()
    app = apply_canonical_pose(
        rig, _mapping(rig), pose,
        finger_map={"hand.L.finger.index.mcp": "no_such_bone"},
    )
    assert any("index.mcp" in s and "missing from rig" in s for s in app.skipped)


# -- payload contract ---------------------------------------------------------------


def test_hands_free_payload_has_no_hands_key_and_round_trips():
    rig = _rig_with_fingers()
    pose = _body_pose_stub()
    entry = {
        "figure": {"label": "A", "index": 0, "score": 0.9, "bbox": [0, 0, 10, 10]},
        "pose": pose.to_dict(),
        "rotations": [],
        "skipped": [],
        "notes": [],
    }
    payload = build_pose_payload(
        Path("img.png"), 100, 100, rig, [entry], selected_label="A"
    )
    blob = json.dumps(payload, sort_keys=True)
    assert '"hands"' not in blob
    rebuilt = CanonicalPose.from_dict(payload["pose"])
    assert "hands" not in rebuilt.to_dict()


def test_payload_with_hands_round_trips_through_the_contract():
    rig = _rig_with_fingers()
    pose = _pose_with_hands()
    entry = {
        "figure": {"label": "A", "index": 0, "score": 0.9, "bbox": [0, 0, 10, 10]},
        "pose": pose.to_dict(),
        "rotations": [],
        "skipped": [],
        "notes": [],
    }
    payload = build_pose_payload(
        Path("img.png"), 100, 100, rig, [entry], selected_label="A"
    )
    assert "hands" in json.dumps(payload, sort_keys=True)
    rebuilt = CanonicalPose.from_dict(payload["pose"])
    assert rebuilt.to_dict() == pose.to_dict()


def test_committed_fixture_payload_still_reads_byte_identical():
    fixture = Path(__file__).parent / "fixtures" / "pose_payload_metarig.json"
    if not fixture.exists():
        pytest.skip("committed fixture missing")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    pose = CanonicalPose.from_dict(payload["pose"])
    assert "hands" not in pose.to_dict()  # the fixture predates P8-3: stays clean


# -- preset contract ------------------------------------------------------------------


def test_preset_hands_round_trip_and_omit_when_empty():
    rig = _rig_with_fingers()
    mapping = _mapping(rig)
    bare = preset_from_mapping(rig, mapping)
    assert "hands" not in bare.to_dict()
    bare2 = preset_from_mapping(rig, mapping, hands={})
    assert "hands" not in bare2.to_dict()

    hands = {
        "hand.L.finger.index.mcp": "f_index_1",
        "hand.L.finger.index.pip": "f_index_2",
        "hand.L.finger.index.dip": "f_index_3",
    }
    full = preset_from_mapping(rig, mapping, hands=hands)
    d = full.to_dict()
    assert d["hands"] == hands
    from riggermortis.presets import Preset

    assert Preset.from_dict(d).hands == hands


def test_preset_hands_validation_loud():
    rig = _rig_with_fingers()
    mapping = _mapping(rig)
    from riggermortis.presets import Preset

    with pytest.raises(PresetError, match="not a finger segment role"):
        Preset.from_dict({**preset_from_mapping(rig, mapping).to_dict(),
                          "hands": {"hips": "f_index_1"}})
    with pytest.raises(PresetError, match="cannot bind"):
        Preset.from_dict({**preset_from_mapping(rig, mapping).to_dict(),
                          "hands": {"hand.L.finger.index.tip": "f_index_3"}})
    base = preset_from_mapping(rig, mapping).to_dict()
    with pytest.raises(PresetError, match="bound to multiple finger roles"):
        Preset.from_dict({**base, "hands": {
            "hand.L.finger.index.mcp": "f_index_1",
            "hand.L.finger.index.pip": "f_index_1",
        }})
    with pytest.raises(PresetError, match="already carry a body-role mapping"):
        Preset.from_dict({**base, "hands": {"hand.L.finger.index.mcp": "hand.L"}})


def test_resolve_hands_fingerprint_gate_and_force():
    rig = _rig_with_fingers()
    mapping = _mapping(rig)
    hands = {"hand.L.finger.index.mcp": "f_index_1"}
    preset = preset_from_mapping(rig, mapping, hands=hands)
    assert resolve_hands(preset, rig.fingerprint()) == hands
    with pytest.raises(PresetError, match="does not match this rig"):
        resolve_hands(preset, "deadbeef")
    assert resolve_hands(preset, "deadbeef", force=True) == hands
