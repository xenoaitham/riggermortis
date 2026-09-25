"""P8-4 face contract tests: the D-022 namespace, the solve gates, the
payload/round-trip contracts, and the FK apply path (docs/FACE.md is the
design of record; the probe earned the constants — never re-declare here).
"""
from __future__ import annotations

import json
import math

import pytest

from riggermortis import (
    FACE_PARAMS,
    FacePose,
    RigData,
    apply_canonical_pose,
    face_bone_rotations,
    face_kp_index,
    is_face_param,
    preset_from_mapping,
    resolve_face,
    solve_face,
)
from riggermortis.canonical_pose import CanonicalPose
from riggermortis.errors import PresetError, RiggermortisError
from riggermortis.inference.poses import (
    FACE_END,
    FACE_START,
    KEYPOINT_COUNT,
)
from riggermortis.mapper import RigMapping, RoleAssignment
from riggermortis.types import BoneData

# -- GT face fixture (the probe's generator, test-owned minimal copy) -------------

CX, CY, SCALE = 320.0, 240.0, 400.0
_EYE_W = 0.30
_PRIOR_EYE_H = 0.28 * _EYE_W
_NOSE_Y = 0.45
_MOUTH_Y = _NOSE_Y + 0.40  # PRIOR_CORNER_DROP


def _put(face, confs, rel, x, y, conf=0.9):
    face[rel] = (CX + x * SCALE, CY + y * SCALE)
    confs[FACE_START + rel] = conf


def gt_face(brow=None, blink=None, jaw=0.0, smile=None, pout=0.0, cheek=None):
    brow, blink, smile, cheek = brow or {}, blink or {}, smile or {}, cheek or {}
    face: list[tuple[float, float] | None] = [None] * 68
    confs = [0.0] * KEYPOINT_COUNT
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        cx_eye = 0.5 * sgn
        h = _PRIOR_EYE_H * (1.0 - blink.get(side, 0.0))
        e_lo = 42 if side == "L" else 36  # measured side map: .L = band B
        _put(face, confs, e_lo + 0, cx_eye - 0.15 * sgn, 0.0)
        _put(face, confs, e_lo + 1, cx_eye - 0.075 * sgn, -h / 2.0)
        _put(face, confs, e_lo + 2, cx_eye + 0.075 * sgn, -h / 2.0)
        _put(face, confs, e_lo + 3, cx_eye + 0.15 * sgn, 0.0)
        _put(face, confs, e_lo + 4, cx_eye + 0.075 * sgn, h / 2.0)
        _put(face, confs, e_lo + 5, cx_eye - 0.075 * sgn, h / 2.0)
        b_lo = 22 if side == "L" else 17
        brow_y = -(0.30 + brow.get(side, 0.0) * 0.15)
        for i in range(5):
            _put(face, confs, b_lo + i, cx_eye - 0.15 * sgn + 0.075 * sgn * i, brow_y)
        ll_lo, ll_hi = (46, 48) if side == "L" else (40, 42)
        lid_y = h / 2.0
        _put(face, confs, ll_lo, cx_eye + 0.075 * sgn, lid_y)
        _put(face, confs, ll_hi - 1, cx_eye - 0.075 * sgn, lid_y)
        _put(face, confs, 35 if side == "L" else 31, cx_eye,
             lid_y + (0.72 - cheek.get(side, 0.0) * 0.10))
    nose_lift = 0.3 * 0.10 * (cheek.get("L", 0.0) + cheek.get("R", 0.0)) / 2.0
    _put(face, confs, 33, 0.0, _NOSE_Y - nose_lift)
    w = 0.83 - pout * 0.25
    c_l_y = _MOUTH_Y - smile.get("L", 0.0) * 0.12
    c_r_y = _MOUTH_Y - smile.get("R", 0.0) * 0.12
    _put(face, confs, 54, w / 2.0, c_l_y)  # corner .L = image-right (measured map)
    _put(face, confs, 48, -w / 2.0, c_r_y)
    _put(face, confs, 51, 0.0, _MOUTH_Y - 0.05)
    _put(face, confs, 57, 0.0, _MOUTH_Y - 0.05 + 0.02 + jaw * 0.55)
    for rel in range(17):
        _put(face, confs, rel, -0.6 + 1.2 * rel / 16.0, _MOUTH_Y + 0.45)
    for rel in range(27, 31):
        _put(face, confs, rel, 0.0, 0.10 + 0.10 * (rel - 27))
    for rel in (32, 34):
        _put(face, confs, rel, -0.1 + 0.1 * (rel - 32), _NOSE_Y - nose_lift)
    for rel in range(49, 54):
        if face[rel] is None:  # never overwrite consumed points (51 is one)
            _put(face, confs, rel, -w / 2.0 + w * (rel - 48) / 6.0, _MOUTH_Y - 0.05)
    for rel in range(55, 60):
        if face[rel] is None:  # 57 is consumed (the jaw lower lip)
            _put(face, confs, rel, -w / 2.0 + w * (rel - 54) / 6.0, c_l_y + 0.03)
    for rel in range(60, 68):
        if face[rel] is None:
            _put(face, confs, rel, -0.3 + 0.086 * (rel - 60), _MOUTH_Y + 0.02)
    kps: list[tuple[float, float]] = [(0.0, 0.0)] * KEYPOINT_COUNT
    for rel in range(68):
        kps[FACE_START + rel] = face[rel]  # type: ignore[index]
    return kps, confs


# -- namespace + layout ------------------------------------------------------------

def test_face_namespace_is_exactly_the_ten_params():
    assert len(FACE_PARAMS) == 10
    assert len(set(FACE_PARAMS)) == 10
    for p in FACE_PARAMS:
        assert is_face_param(p)
    assert not is_face_param("head")
    assert not is_face_param("hand.L.finger.index.mcp")


def test_face_kp_index_tiles_the_face_partition_and_refuses_unknowns():
    used = [face_kp_index(s, "eye", i) for s in ("L", "R") for i in range(6)]
    used += [face_kp_index(s, "brow", i) for s in ("L", "R") for i in range(5)]
    used += [face_kp_index(s, "lower_lid", i) for s in ("L", "R") for i in range(2)]
    used += [face_kp_index(s, "corner") for s in ("L", "R")]
    used += [face_kp_index(s, "wing") for s in ("L", "R")]
    used += [face_kp_index("L", "nose_bottom")]
    used += [FACE_START + 51, FACE_START + 57]  # outer lip centers (jaw.open)
    assert all(FACE_START <= i < FACE_END for i in used)
    assert len(set(used)) == 29
    with pytest.raises(ValueError):
        face_kp_index("Q", "eye")
    with pytest.raises(ValueError):
        face_kp_index("L", "jaw")
    with pytest.raises(ValueError):
        face_kp_index("L", "eye", 9)


# -- the solve ----------------------------------------------------------------------

def test_neutral_solves_zero_params_with_full_ledger():
    kps, confs = gt_face()
    face = solve_face(kps, confs)
    assert face is not None
    assert face.params == {}
    assert len(face.skipped) == 10
    assert all("below activation floor" in r for r in face.skipped.values())
    assert face.iod_conf > 0.5


def test_expression_params_solve_exactly_on_prior_consistent_gt():
    kps, confs = gt_face(
        brow={"L": 0.8, "R": 0.4}, blink={"L": 1.0}, jaw=0.5,
        smile={"R": 0.9}, pout=0.6, cheek={"L": 0.7},
    )
    face = solve_face(kps, confs)
    assert face is not None
    for name, expected in (
        ("brow.raise.L", 0.8), ("brow.raise.R", 0.4), ("blink.L", 1.0),
        ("jaw.open", pytest.approx(0.5, abs=1e-6)),
        # smile.R reads 0.9 minus the GT's honest nose-lift cross-talk
        # (a cheek raise lifts the nose bottom 0.3x the wing rise —
        # docs/FACE.md amendment A4's second-order term): 0.9 - 0.0105/0.12
        ("smile.R", pytest.approx(0.9 - (0.3 * 0.10 * 0.35) / 0.12, abs=1e-6)),
        ("pout", pytest.approx(0.6, abs=1e-6)), ("cheek.L", pytest.approx(0.7, abs=1e-6)),
    ):
        assert face.params[name] == expected, name
    # every param not authored sits at/below the activation floor
    assert "smile.L" not in face.params and "cheek.R" not in face.params
    assert "blink.R" not in face.params


def test_occlusion_gate_conf_zero_face_has_no_entry():
    kps, _c = gt_face()
    face = solve_face(kps, [0.0] * KEYPOINT_COUNT)
    assert face is None  # absent reads clean, never guessed


def test_partial_face_gates_exactly_the_starved_params():
    kps, confs = gt_face(smile={"L": 1.0, "R": 1.0})
    for i in range(5):  # brow band B (the .L side) starves
        confs[FACE_START + 22 + i] = 0.3
    face = solve_face(kps, confs)
    assert face is not None
    assert "brow.raise.L" in face.skipped
    assert "below floor 0.55" in face.skipped["brow.raise.L"]
    assert face.params["smile.L"] == pytest.approx(1.0, abs=1e-6)
    assert face.params["smile.R"] == pytest.approx(1.0, abs=1e-6)


def test_iod_anchor_below_floor_means_no_entry_even_with_other_kps():
    kps, confs = gt_face(jaw=1.0)
    confs[FACE_START + 36] = 0.1  # one IOD corner dies -> no scale, no solve
    assert solve_face(kps, confs) is None


def test_solve_is_deterministic_twin():
    kps, confs = gt_face(cheek={"L": 0.7, "R": 0.7})
    assert solve_face(kps, confs) == solve_face(kps, confs)


def test_solve_refuses_wrong_array_lengths():
    with pytest.raises(RiggermortisError):
        solve_face([(0.0, 0.0)] * 10, [0.9] * 10)


def _gt_params(kw: dict) -> dict[str, float]:
    """The state's authored GT param values (the probe's state() mapping)."""
    return {
        **{f"brow.raise.{s}": kw.get("brow", {}).get(s, 0.0) for s in ("L", "R")},  # type: ignore[union-attr]
        **{f"blink.{s}": kw.get("blink", {}).get(s, 0.0) for s in ("L", "R")},  # type: ignore[union-attr]
        **{f"smile.{s}": kw.get("smile", {}).get(s, 0.0) for s in ("L", "R")},  # type: ignore[union-attr]
        **{f"cheek.{s}": kw.get("cheek", {}).get(s, 0.0) for s in ("L", "R")},  # type: ignore[union-attr]
        "jaw.open": float(kw.get("jaw", 0.0)),
        "pout": float(kw.get("pout", 0.0)),
    }


def test_monotonicity_with_reach_over_the_ten_expression_benchmark():
    states = {
        "neutral": {},
        "brows_raise": {"brow": {"L": 0.8, "R": 0.8}},
        "brow_raise_L": {"brow": {"L": 0.8}},
        "blink_both": {"blink": {"L": 1.0, "R": 1.0}},
        "blink_L": {"blink": {"L": 1.0}},
        "jaw_open": {"jaw": 1.0},
        "smile": {"smile": {"L": 1.0, "R": 1.0}},
        "smile_L": {"smile": {"L": 1.0}},
        "pout": {"pout": 1.0},
        "cheeks": {"cheek": {"L": 0.7, "R": 0.7}},
    }
    solved: dict[str, dict[str, float]] = {}
    for name, kw in states.items():
        face = solve_face(*gt_face(**kw))
        solved[name] = dict(face.params) if face else {}
    for param in FACE_PARAMS:
        gt = {name: _gt_params(kw)[param] for name, kw in states.items()}
        order = sorted(gt, key=lambda n: (gt[n], n))
        seq = [solved[n].get(param, 0.0) for n in order]
        viol = sum(1 for a, b in zip(seq, seq[1:], strict=False) if a - b > 0.05)
        assert viol <= 1, f"{param}: {viol} violations over {seq}"
        gt_max = max(gt.values())
        if gt_max > 0:
            reach = max(
                solved[n].get(param, 0.0) for n in gt if gt[n] == gt_max
            ) / gt_max
            assert reach >= 0.5, f"{param} reach {reach:.2f}"


# -- payload contracts ---------------------------------------------------------------

def test_face_free_to_dict_is_byte_identical():
    pose = CanonicalPose(
        positions={"hips": (0.0, 0.0, 0.0)}, flips={}, confidence=0.9,
        reliable=True, scale=400.0, anchor="hips",
    )
    a = pose.to_dict()
    assert "face" not in a and "hands" not in a
    pose.face = None
    assert pose.to_dict() == a


def test_face_round_trip_exact():
    kps, confs = gt_face(smile={"L": 1.0}, jaw=0.4)
    face = solve_face(kps, confs)
    assert face is not None
    pose = CanonicalPose(
        positions={"hips": (0.0, 0.0, 0.0)}, flips={}, confidence=0.9,
        reliable=True, scale=400.0, anchor="hips", face=face,
    )
    rt = CanonicalPose.from_dict(json.loads(json.dumps(pose.to_dict())))
    assert rt.face is not None
    # both sides serialize through the same 4-decimal rounding: compare the
    # serialized forms (the payload contract), not raw float identity
    assert rt.face.to_dict() == face.to_dict()


def test_from_dict_tolerates_face_free_payloads():
    d = {
        "positions": {"hips": [0.0, 0.0, 0.0]}, "flips": {}, "confidence": 0.9,
        "reliable": True, "scale": 400.0, "anchor": "hips",
    }
    pose = CanonicalPose.from_dict(d)
    assert pose.face is None


def test_face_pose_validation_is_loud():
    with pytest.raises(RiggermortisError):
        FacePose.from_dict({"params": {"brow.raise.Q": 0.5}})
    with pytest.raises(RiggermortisError):
        FacePose.from_dict({"params": {"jaw.open": 1.5}})
    with pytest.raises(RiggermortisError):
        FacePose.from_dict(["not", "an", "object"])


def test_mirrored_swaps_face_sides():
    face = FacePose(params={"brow.raise.L": 0.8, "jaw.open": 0.5},
                    skipped={"blink.L": "below activation floor 0.08 (value 0.0000)"},
                    iod_conf=0.9)
    pose = CanonicalPose(
        positions={"hips": (0.0, 0.0, 0.0)}, flips={}, confidence=0.9,
        reliable=True, scale=400.0, anchor="hips", face=face,
    )
    m = pose.mirrored()
    assert m.face is not None
    assert m.face.params == {"brow.raise.R": 0.8, "jaw.open": 0.5}
    assert "blink.R" in m.face.skipped
    # mirror commute: mirrored twice is the original
    mm = m.mirrored()
    assert mm.face is not None and mm.face.params == face.params


# -- apply: bones + shape-key accounting ---------------------------------------------

def _tiny_rig_and_mapping(face_bone: str = "jaw", jaw_parent: str = "head"):
    """neck + head + face bone; the body mapping binds neck (direction to
    head exists) while head is a leaf (target None -> unbound, noted)."""
    bones = {
        "neck": BoneData(name="neck", parent=None, head=(0.0, 0.0, 1.3), tail=(0.0, 0.0, 1.5)),
        "head": BoneData(name="head", parent="neck", head=(0.0, 0.0, 1.5), tail=(0.0, 0.0, 1.7)),
        face_bone: BoneData(name=face_bone, parent=jaw_parent,
                            head=(0.0, -0.05, 1.45), tail=(0.05, -0.05, 1.45)),
    }
    rig = RigData(name="tiny", bones=bones, metadata={})
    mapping = RigMapping(
        rig_name="tiny", fingerprint="fp", notes=[],
        assignments={
            "neck": RoleAssignment(role="neck", bone="neck", confidence=1.0, side="C"),
            "head": RoleAssignment(role="head", bone="head", confidence=1.0, side="C"),
        },
    )
    return rig, mapping


def _tiny_pose(face=None):
    return CanonicalPose(
        positions={"neck": (0.0, 0.0, 1.3), "head": (0.0, 0.0, 1.5)},
        flips={}, confidence=1.0, reliable=True, scale=400.0,
        anchor="hips", face=face,
    )


def test_face_bone_bindings_apply_declared_axis_angle():
    rig, mapping = _tiny_rig_and_mapping()
    kps, confs = gt_face(jaw=1.0)
    face = solve_face(kps, confs)
    assert face is not None and "jaw.open" in face.params
    pose = _tiny_pose(face)
    app = apply_canonical_pose(rig, mapping, pose, face_bones={"jaw.open": "jaw"})
    jaw_rot = [r for r in app.rotations if r.role == "jaw.open"]
    assert len(jaw_rot) == 1
    expected = math.radians(25.0) * face.params["jaw.open"]
    assert jaw_rot[0].angle_rad == pytest.approx(expected, abs=1e-6)


def test_face_bone_rotation_helper_matches_the_plan():
    kps, confs = gt_face(brow={"L": 0.8})
    face = solve_face(kps, confs)
    assert face is not None
    rots = face_bone_rotations(face, {"brow.raise.L": "brow.L"})
    assert len(rots) == 1
    assert rots[0].bone == "brow.L"
    assert rots[0].angle_rad == pytest.approx(math.radians(20.0) * 0.8, abs=1e-9)


def test_ledgered_param_bound_bone_is_skipped_loud_not_guessed():
    rig, mapping = _tiny_rig_and_mapping()
    kps, confs = gt_face()  # neutral: every param ledgered
    face = solve_face(kps, confs)
    assert face is not None and face.params == {}
    pose = _tiny_pose(face)
    app = apply_canonical_pose(rig, mapping, pose, face_bones={"jaw.open": "jaw"})
    assert not [r for r in app.rotations if r.role == "jaw.open"]
    assert any("not solved (ledgered in the pose)" in s for s in app.skipped)


def test_unknown_face_binding_key_refuses_loud():
    rig, mapping = _tiny_rig_and_mapping()
    pose = _tiny_pose()
    with pytest.raises(ValueError, match="not a face param"):
        apply_canonical_pose(rig, mapping, pose, face_bones={"wink.L": "jaw"})


def test_no_facial_targets_line_is_loud_and_verbatim():
    rig, mapping = _tiny_rig_and_mapping()
    kps, confs = gt_face(jaw=0.6)
    face = solve_face(kps, confs)
    assert face is not None and face.params
    pose = _tiny_pose(face)
    app = apply_canonical_pose(rig, mapping, pose)
    lines = [n for n in app.notes if "no facial targets for this rig" in n]
    assert len(lines) == 1
    assert f"face: {len(face.params)} expression param(s) solved" in lines[0]


def test_shape_keys_resolved_means_no_no_target_line():
    rig, mapping = _tiny_rig_and_mapping()
    kps, confs = gt_face(jaw=0.6)
    face = solve_face(kps, confs)
    pose = _tiny_pose(face)
    app = apply_canonical_pose(rig, mapping, pose, face_shape_keys={"jaw.open"})
    assert not [n for n in app.notes if "no facial targets" in n]
    assert any("convention shape key(s) resolved" in n for n in app.notes)


def test_double_bound_face_bone_is_refused_loud():
    rig, mapping = _tiny_rig_and_mapping()
    kps, confs = gt_face(jaw=0.6)
    face = solve_face(kps, confs)
    pose = _tiny_pose(face)
    app = apply_canonical_pose(
        rig, mapping, pose, face_bones={"jaw.open": "neck"}  # neck carries the body role (bound: neck->head direction)
    )
    assert any("already carries a" in s and "ONE target" in s for s in app.skipped)


# -- preset face_bones ----------------------------------------------------------------

def test_preset_face_bones_round_trip_and_omit_when_empty():
    from riggermortis.presets import Preset

    bones = {
        "head": BoneData(name="head", parent=None, head=(0.0, 0.0, 1.5), tail=(0.0, 0.0, 1.7)),
        "jaw": BoneData(name="jaw", parent="head", head=(0.0, -0.05, 1.45), tail=(0.05, -0.05, 1.45)),
    }
    rig = RigData(name="tiny", bones=bones, metadata={})
    mapping = RigMapping(
        rig_name="tiny", fingerprint=rig.fingerprint(), notes=[],
        assignments={"head": RoleAssignment(role="head", bone="head", confidence=1.0, side="C")},
    )
    preset = preset_from_mapping(rig, mapping, face_bones={"jaw.open": "jaw"})
    d = preset.to_dict()
    assert d["face_bones"] == {"jaw.open": "jaw"}
    bare = preset_from_mapping(rig, mapping).to_dict()
    assert "face_bones" not in bare
    rt = Preset.from_dict(json.loads(json.dumps(d)))
    assert rt.face_bones == {"jaw.open": "jaw"}


def test_preset_face_bones_validation_loud():
    from riggermortis.presets import Preset

    with pytest.raises(PresetError, match="not a face param"):
        Preset.from_dict({
            "format": 2, "rig_name": "r", "fingerprint": "fp", "core_version": "0",
            "mapping": {}, "face_bones": {"wink.L": "jaw"},
        })
    with pytest.raises(PresetError, match="bound to multiple face params"):
        Preset.from_dict({
            "format": 2, "rig_name": "r", "fingerprint": "fp", "core_version": "0",
            "mapping": {}, "face_bones": {"jaw.open": "jaw", "smile.L": "jaw"},
        })
    with pytest.raises(PresetError, match="already carry"):
        Preset.from_dict({
            "format": 2, "rig_name": "r", "fingerprint": "fp", "core_version": "0",
            "mapping": {"head": "jaw"}, "face_bones": {"jaw.open": "jaw"},
        })


def test_resolve_face_fingerprint_gate_and_force():
    from riggermortis.presets import Preset

    preset = Preset(
        format=2, rig_name="r", fingerprint="aaa", core_version="0",
        mapping={}, face_bones={"jaw.open": "jaw"},
    )
    assert resolve_face(preset, "aaa") == {"jaw.open": "jaw"}
    from riggermortis.errors import PresetError as PE
    with pytest.raises(PE, match="does not match this rig"):
        resolve_face(preset, "bbb")
    assert resolve_face(preset, "bbb", force=True) == {"jaw.open": "jaw"}
