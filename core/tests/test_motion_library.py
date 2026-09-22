"""P6-2 tests: motion-library clip conversion (docs/MOTION_LIBRARY.md).

The converter is deliberately BLIND to Blender: its input is the sampled
clip JSON the shell-glue sampler writes (the probe's recipe). These tests
pin the conversion contract (hips anchoring, rest-span scale, measured
flips, loud validation, honest ledgers) and the certified-composition
contract on a clip-sourced action (detect finds the known plants, the
foot lock zeroes the slide, nothing mutates its input).
"""
from __future__ import annotations

import copy
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis import ALL_ROLES  # noqa: E402
from riggermortis.action import CanonicalAction, condition_action  # noqa: E402
from riggermortis.canonical_pose import TORSO_SPAN  # noqa: E402
from riggermortis.contacts import (  # noqa: E402
    detect_contacts,
    foot_slide,
    lock_feet,
)
from riggermortis.errors import MotionError  # noqa: E402
from riggermortis.motion import (  # noqa: E402
    MotionClip,
    action_from_clip,
    pose_from_sample,
)

SCALE_REF = 0.42
FACTOR = TORSO_SPAN / SCALE_REF  # canonical units per source meter

HIPS = (0.0, 0.0, 1.0)
LEG_L = {
    "upper_leg.L": (0.09, 0.0, 0.92),
    "lower_leg.L": (0.09, 0.0, 0.50),
    "foot.L": (0.09, 0.0, 0.08),
}
LEG_R = {
    "upper_leg.R": (-0.09, 0.0, 0.92),
    "lower_leg.R": (-0.09, 0.0, 0.50),
    "foot.R": (-0.09, 0.0, 0.08),
}


def _clip(**overrides: object) -> MotionClip:
    base: dict[str, object] = {
        "format": 1,
        "fps": 24.0,
        "scale_ref": SCALE_REF,
        "frames": [
            {"frame": 1, "positions": {"hips": list(HIPS), **{k: list(v) for k, v in LEG_L.items()}}}
        ],
        "source": "test",
        "notes": ["synthetic test clip"],
    }
    base.update(overrides)
    return MotionClip.from_dict(base)  # type: ignore[arg-type]


def test_from_dict_roundtrip_is_byte_identical() -> None:
    clip = _clip()
    d = clip.to_dict()
    again = MotionClip.from_dict(copy.deepcopy(d)).to_dict()
    assert again == d


def test_hips_anchoring_drops_world_translation() -> None:
    shifted = {
        "hips": [HIPS[0] + 5.0, HIPS[1] - 3.0, HIPS[2] + 2.0],
        **{k: [v[0] + 5.0, v[1] - 3.0, v[2] + 2.0] for k, v in LEG_L.items()},
    }
    a = action_from_clip(_clip()).frames[0].pose
    b = action_from_clip(
        _clip(frames=[{"frame": 1, "positions": shifted}])
    ).frames[0].pose
    assert set(b.positions) == set(a.positions)
    for role, p in a.positions.items():
        assert b.positions[role] == pytest.approx(p, abs=1e-12)


def test_scale_invariance_two_rig_sizes_same_canonical_shape() -> None:
    big = {
        "hips": [v * 2.0 for v in HIPS],
        **{k: [v * 2.0 for v in p] for k, p in LEG_L.items()},
    }
    a = action_from_clip(_clip()).frames[0].pose
    b = action_from_clip(
        _clip(scale_ref=SCALE_REF * 2.0, frames=[{"frame": 1, "positions": big}])
    ).frames[0].pose
    assert b.positions == a.positions


@pytest.mark.parametrize(
    "mutation",
    [
        {"format": 2},
        {"unexpected_field": 1},
        {"fps": 0.0},
        {"fps": -1.0},
        {"scale_ref": 0.0},
        {"scale_ref": -0.42},
        {"frames": []},
        {"fps": "fast"},
        {
            "frames": [
                {"frame": 2, "positions": {"hips": [0.0, 0.0, 1.0]}},
                {"frame": 1, "positions": {"hips": [0.0, 0.0, 1.0]}},
            ]
        },
        {"frames": [{"frame": 1, "positions": {"hips": [0.0, 0.0]}}]},
        {"frames": [{"frame": 1, "positions": {"hips": [0.0, 0.0, float("nan")]}}]},
        {"frames": [{"frame": 1, "positions": {"not_a_role": [0.0, 0.0, 0.0]}}]},
        {"frames": [{"frame": 1, "positions": {"hips": [0.0, 0.0, 1.0]}, "extra": 1}]},
        {"frames": [{"frame": True, "positions": {"hips": [0.0, 0.0, 1.0]}}]},
        {"notes": "not-a-list"},
        {"source_fingerprint": 42},
    ],
)
def test_loud_validation_refusals_carry_hints(mutation: dict[str, object]) -> None:
    raw: dict[str, object] = {
        "format": 1,
        "fps": 24.0,
        "scale_ref": SCALE_REF,
        "frames": [{"frame": 1, "positions": {"hips": [0.0, 0.0, 1.0]}}],
    }
    raw.update(mutation)
    with pytest.raises(MotionError) as excinfo:
        MotionClip.from_dict(raw)
    assert "hint:" in str(excinfo.value)


def test_missing_roles_ledgered_never_guessed() -> None:
    action = action_from_clip(_clip())  # leg-only: 20 canonical roles absent
    pose = action.frames[0].pose
    assert "hips" in pose.positions and "foot.L" in pose.positions
    assert "head" not in pose.positions
    ledger = [n for n in action.notes if "absent from the clip" in n]
    assert len(ledger) == 1
    assert "head" in ledger[0] and "shoulder.L" in ledger[0]
    assert pose.positions.keys() <= set(ALL_ROLES)


def test_flips_are_measured_not_guessed() -> None:
    forward = {  # hand FORWARD of the elbow (character faces -Y)
        "hips": list(HIPS),
        "upper_arm.L": [0.05, 0.0, 1.42],
        "forearm.L": [0.25, 0.0, 1.42],
        "hand.L": [0.45, -0.05, 1.42],
    }
    backward = dict(forward)
    backward["hand.L"] = [0.45, 0.05, 1.42]
    pose_f = pose_from_sample(forward, SCALE_REF)
    pose_b = pose_from_sample(backward, SCALE_REF)
    assert pose_f.flips["forearm.L"] == -1
    assert pose_b.flips["forearm.L"] == 1
    # straight segment: no forward bias -> +1, review's immaterial auto-pass
    straight = dict(forward)
    straight["hand.L"] = [0.45, 0.0, 1.42]
    assert pose_from_sample(straight, SCALE_REF).flips["forearm.L"] == 1
    # a distal pair whose child is absent carries NO flip key
    lone = {"hips": list(HIPS), "forearm.L": [0.25, 0.0, 1.42]}
    assert "forearm.L" not in pose_from_sample(lone, SCALE_REF).flips


def test_provenance_metadata_distinguishes_clips_from_solves() -> None:
    pose = action_from_clip(_clip()).frames[0].pose
    assert pose.confidence == 1.0 and pose.reliable and pose.anchor == "hips"
    assert pose.joint_confidence == {r: 1.0 for r in ("hips", *LEG_L)}
    assert pose.scale == pytest.approx(SCALE_REF / TORSO_SPAN)
    assert any("measured from 3D clip" in n for n in pose.notes)
    action = action_from_clip(_clip())
    assert any("source=test" in n and "fps=24" in n for n in action.notes)
    assert action.rig_fingerprint is None  # the clip carried no fingerprint


def test_clip_with_fingerprint_carries_it_through() -> None:
    clip = _clip(source_fingerprint="deadbeef")
    assert action_from_clip(clip).rig_fingerprint == "deadbeef"


def test_action_from_clip_never_mutates_the_clip() -> None:
    clip = _clip()
    before = clip.to_dict()
    action_from_clip(clip)
    assert clip.to_dict() == before


def test_load_refuses_missing_and_torn_files(tmp_path: Path) -> None:
    with pytest.raises(MotionError) as missing:
        MotionClip.load(tmp_path / "nope.json")
    assert "hint:" in str(missing.value)
    torn = tmp_path / "torn.json"
    torn.write_text('{"format": 1, "fps":', encoding="utf-8")
    with pytest.raises(MotionError) as bad:
        MotionClip.load(torn)
    assert "not valid JSON" in str(bad.value)


# -- the certified composition on a clip-sourced action -------------------------
#
# A 70-frame SLIDING walk authored in source meters (stance feet drift
# +0.003 m/frame = the classic mocap foot-slide), converted through
# action_from_clip, then run through the certified stages. The composition
# must treat it exactly like a video-path action: detect finds the plants,
# the lock zeroes the slide, nothing mutates its input.

GROUND_M = 0.08
H_MAX_M = 0.35
DRIFT_M = 0.003
PHASES_L = [("stance", 0, 9), ("swing", 10, 23), ("stance", 24, 39),
            ("swing", 40, 53), ("stance", 54, 69)]
PHASES_R = [("swing", 0, 13), ("stance", 14, 29), ("swing", 30, 43),
            ("stance", 44, 59), ("swing", 60, 69)]


def _foot_track(phases: list[tuple[str, int, int]], sign: float) -> dict[int, tuple[float, float, float]]:
    out: dict[int, tuple[float, float, float]] = {}
    for kind, start, end in phases:
        for i in range(start, end + 1):
            if kind == "stance":
                out[i] = (sign * 0.09 + DRIFT_M * (i - start), 0.0, GROUND_M)
            else:
                span = end - start + 2
                t = (i - start + 1) / span
                out[i] = (
                    sign * 0.09,
                    0.0,
                    GROUND_M + H_MAX_M * math.sin(math.pi * t),
                )
    return out


def _walk_clip() -> MotionClip:
    left, right = _foot_track(PHASES_L, -1.0), _foot_track(PHASES_R, 1.0)
    frames = []
    for i in sorted(set(left) | set(right)):
        positions = {"hips": list(HIPS)}
        positions.update({k: list(v) for k, v in LEG_L.items() if k != "foot.L"})
        positions.update({k: list(v) for k, v in LEG_R.items() if k != "foot.R"})
        positions["foot.L"] = list(left[i])
        positions["foot.R"] = list(right[i])
        frames.append({"frame": i, "positions": positions})
    return _clip(frames=frames)  # type: ignore[arg-type]


def test_certified_composition_contract_holds_on_a_clip_action() -> None:
    action = action_from_clip(_walk_clip())
    assert len(action.frames) == 70 and not action.failed

    report = detect_contacts(action.frames)
    left = [iv for iv in report.intervals if iv.foot == "foot.L"]
    right = [iv for iv in report.intervals if iv.foot == "foot.R"]
    assert len(left) == 3 and len(right) == 2  # the phase structure survived
    assert (left[0].foot, left[0].start, left[0].end) == ("foot.L", 1, 9)

    slide_before = foot_slide(action.frames, report)
    assert slide_before.total > 0.05  # the slide is real and measured

    frozen = copy.deepcopy(action.frames)
    locked, lock_report = lock_feet(action, report)
    assert [af.frame for af in action.frames] == [af.frame for af in frozen]
    assert all(
        af.pose.positions == fr.pose.positions
        for af, fr in zip(action.frames, frozen, strict=True)
    )  # the input action is never mutated
    assert lock_report.slide_before is not None
    assert lock_report.slide_after is not None
    assert lock_report.slide_before.total == pytest.approx(slide_before.total)
    assert lock_report.slide_after.total == pytest.approx(0.0, abs=1e-12)
    assert lock_report.slide_after.total * 5 <= lock_report.slide_before.total

    conditioned = condition_action(action, min_cutoff=None, tolerance=None)
    assert [af.frame for af in conditioned.frames] == [af.frame for af in action.frames]
    assert detect_contacts(conditioned.frames).in_contact == report.in_contact


def test_clip_frame_indices_survive_into_the_action() -> None:
    clip = _walk_clip()
    action: CanonicalAction = action_from_clip(clip)
    assert [af.frame for af in action.frames] == sorted(
        cf.frame for cf in clip.frames
    )  # the clip's own 1:1 indices, never renumbered
