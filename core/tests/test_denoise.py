"""P2-6 tests: hip stabilization + the denoise composition.

CI-safe: synthetic actions only (stdlib, no models). The artifact model is
the documented one — per-frame scale breathing (bob + detector noise
modulating the torso span) and anchor translation wobble — NOT fitted to any
fixture (D-008); assertions are comparative (after < before), never
threshold-tuned.
"""
from __future__ import annotations

import copy
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis.action import (  # noqa: E402
    action_from_poses,
    condition_action,
    stabilize_hips,
)
from riggermortis.canonical_pose import CanonicalPose  # noqa: E402
from riggermortis.contacts import (  # noqa: E402
    attach_contacts,
    detect_contacts,
    foot_slide,
    lock_feet,
)

BASE_SCALE = 30.0

#: Static standing skeleton, canonical units, both feet planted at z = -0.9.
BASE_POSITIONS: dict[str, tuple[float, float, float]] = {
    "hips": (0.0, 0.0, 0.0),
    "spine": (0.0, 0.0, 0.09),
    "chest": (0.0, 0.0, 0.26),
    "neck": (0.0, 0.0, 0.45),
    "head": (0.0, 0.0, 0.56),
    "upper_arm.L": (0.26, 0.0, 0.45),
    "upper_arm.R": (-0.26, 0.0, 0.45),
    "upper_leg.L": (0.09, 0.0, 0.0),
    "upper_leg.R": (-0.09, 0.0, 0.0),
    "lower_leg.L": (0.10, -0.02, -0.45),
    "lower_leg.R": (-0.10, -0.02, -0.45),
    "foot.L": (0.11, -0.04, -0.90),
    "foot.R": (-0.11, -0.04, -0.90),
}


def _pose(
    *,
    scale: float = BASE_SCALE,
    shift: tuple[float, float, float] = (0.0, 0.0, 0.0),
    drop: tuple[str, ...] = (),
) -> CanonicalPose:
    positions = {
        role: (p[0] + shift[0], p[1] + shift[1], p[2] + shift[2])
        for role, p in BASE_POSITIONS.items()
        if role not in drop
    }
    return CanonicalPose(
        positions=positions,
        flips={},
        confidence=0.9,
        reliable=True,
        scale=scale,
        anchor="hips",
    )


def _breathing_action(
    n: int = 21, breath: float = 0.008, period: int = 4
) -> object:
    """Planted-stance action with per-frame scale breathing.

    Canonical positions are the base skeleton rescaled by base/scale per
    frame — exactly what a per-frame torso-span scale estimate does to a
    stationary subject. The hips role stays at the origin (the solve anchors
    it there), so the artifact lives entirely in the scale track.
    """
    frames = []
    for i in range(n):
        s = BASE_SCALE * (1.0 + breath * math.sin(2.0 * math.pi * i / period))
        k = BASE_SCALE / s
        positions = {
            role: (p[0] * k, p[1] * k, p[2] * k)
            for role, p in BASE_POSITIONS.items()
        }
        frames.append(
            (
                i,
                CanonicalPose(
                    positions=positions, flips={}, confidence=0.9,
                    reliable=True, scale=s, anchor="hips",
                ),
            )
        )
    return action_from_poses(frames)


def _swaying_action(n: int = 21, amp: float = 0.03) -> object:
    """Planted stance whose whole body rides an alternating anchor wobble."""
    frames = []
    for i in range(n):
        t = (amp if i % 2 == 0 else -amp, 0.0, 0.0)
        frames.append((i, _pose(shift=t)))
    return action_from_poses(frames)


# -- stabilize_hips: the scale track ---------------------------------------------

def test_stabilize_hips_damps_scale_breathing() -> None:
    action = _breathing_action()
    stabilized, report = stabilize_hips(action, strength=1.0)

    def _max_dev(a: object) -> float:
        worst = 0.0
        for af in a.frames:  # type: ignore[union-attr]
            for role, p in af.pose.positions.items():
                b = BASE_POSITIONS[role]
                worst = max(worst, math.dist(p, b))
        return worst

    before, after = _max_dev(action), _max_dev(stabilized)
    assert before > 0.0
    assert after < 0.5 * before
    assert report.scale_sway_before is not None
    assert report.scale_sway_after is not None
    assert report.scale_sway_after < report.scale_sway_before
    assert report.anchor_role == "hips"  # hips pinned at origin: no translation
    assert report.translation_sway_before is not None
    assert report.translation_sway_before == pytest.approx(0.0, abs=1e-9)
    assert report.max_move > 0.0
    # frames whose residual was already sub-snap stay bit-identical (by design)
    assert report.frames_stabilized + report.frames_untouched == len(action.frames)  # type: ignore[union-attr]
    assert report.frames_stabilized > 0
    assert any("D-008" in n for n in stabilized.notes)  # type: ignore[union-attr]


def test_stabilize_hips_updates_pose_scale_with_positions() -> None:
    action = _breathing_action()
    stabilized, _report = stabilize_hips(action, strength=1.0)
    for af in stabilized.frames:  # type: ignore[union-attr]
        # scale provenance must stay consistent with the rescaled positions
        assert af.pose.scale == pytest.approx(BASE_SCALE, abs=0.05 * BASE_SCALE)


def test_stabilize_hips_is_fk_preserving_per_frame() -> None:
    """Uniform per-frame corrections must not change within-frame geometry
    beyond the scale factor: directions (and therefore baked FK rotations)
    are invariant."""
    action = _breathing_action()
    stabilized, _report = stabilize_hips(action, strength=0.7)
    for before, after in zip(  # type: ignore[union-attr]
        action.frames, stabilized.frames, strict=True
    ):
        factor = before.pose.scale / after.pose.scale
        for role, p in before.pose.positions.items():
            if p == (0.0, 0.0, 0.0):
                continue
            q = after.pose.positions[role]
            d_before = math.dist(p, before.pose.positions["hips"])
            d_after = math.dist(q, after.pose.positions["hips"])
            # every bone vector scales by the same per-frame factor
            assert d_after == pytest.approx(d_before * factor, rel=1e-6)


# -- stabilize_hips: the translation track ---------------------------------------

def test_stabilize_hips_damps_anchor_translation_rigidly() -> None:
    action = _swaying_action()
    stabilized, report = stabilize_hips(action, strength=1.0)

    hip_track = [af.pose.positions["hips"][0] for af in stabilized.frames]  # type: ignore[union-attr]
    assert max(hip_track) - min(hip_track) < 0.5 * 0.06  # alternating ±0.03 damped
    assert report.translation_sway_after is not None
    assert report.translation_sway_before is not None
    assert report.translation_sway_after < report.translation_sway_before

    # rigid shift: within-frame distances are untouched by the correction
    for before, after in zip(  # type: ignore[union-attr]
        action.frames, stabilized.frames, strict=True
    ):
        for role in BASE_POSITIONS:
            d_b = math.dist(before.pose.positions[role], before.pose.positions["spine"])
            d_a = math.dist(after.pose.positions[role], after.pose.positions["spine"])
            assert d_a == pytest.approx(d_b, rel=1e-9)


def test_stabilize_hips_falls_back_to_neck_anchor() -> None:
    frames = []
    for i in range(21):
        t = (0.02 if i % 2 == 0 else -0.02, 0.0, 0.0)
        frames.append((i, _pose(shift=t, drop=("hips",))))
    action = action_from_poses(frames)
    stabilized, report = stabilize_hips(action, strength=1.0)
    assert report.anchor_role == "neck"
    track = [af.pose.positions["neck"][0] for af in stabilized.frames]  # type: ignore[union-attr]
    assert max(track) - min(track) < 0.5 * 0.04


# -- honesty + discipline ----------------------------------------------------------

def test_stabilize_hips_zero_strength_is_bit_for_bit_noop() -> None:
    action = _breathing_action()
    original = copy.deepcopy(action)
    stabilized, report = stabilize_hips(action, strength=0.0)
    assert [af.pose.positions for af in stabilized.frames] == \
        [af.pose.positions for af in original.frames]
    assert [af.pose.scale for af in stabilized.frames] == \
        [af.pose.scale for af in original.frames]
    assert report.frames_stabilized == 0
    assert any("untouched" in n for n in stabilized.notes)


def test_stabilize_hips_never_mutates_input() -> None:
    action = _breathing_action()
    original = copy.deepcopy(action)
    stabilize_hips(action, strength=0.7)
    assert action == original


def test_stabilize_hips_is_deterministic() -> None:
    action = _breathing_action()
    a = stabilize_hips(action, strength=0.7)
    b = stabilize_hips(action, strength=0.7)
    assert a == b


def test_stabilize_hips_reports_missing_data_honestly() -> None:
    frames = []
    for i in range(21):
        if i == 5:
            frames.append((i, _pose(drop=("hips", "neck"))))  # no anchor role
        elif i == 9:
            frames.append((i, _pose(scale=0.0)))  # unusable scale
        else:
            frames.append((i, _pose()))
    action = action_from_poses(frames)
    stabilized, report = stabilize_hips(action, strength=0.7)
    # no anchor role on EVERY frame -> translation track honestly skipped
    assert report.anchor_role is None
    assert any("no anchor role" in n for n in report.notes)
    assert any("no usable scale" in n for n in stabilized.notes)
    assert report.frames_untouched >= 2  # frame 5 got no correction at all


def test_stabilize_hips_validates_parameters() -> None:
    action = _breathing_action()
    with pytest.raises(ValueError, match="strength"):
        stabilize_hips(action, strength=1.5)
    with pytest.raises(ValueError, match="window"):
        stabilize_hips(action, window=0)


def test_stabilize_hips_empty_action_is_reported() -> None:
    action = action_from_poses([])
    stabilized, report = stabilize_hips(action)
    assert stabilized.frames == []
    assert "empty action" in report.notes[0]


# -- the denoise composition (documented cleanup order) ---------------------------

def test_condition_action_composes_stabilize_smooth_reduce() -> None:
    action = _breathing_action()
    conditioned = condition_action(
        action, hip_stabilize=0.7, min_cutoff=1.0, tolerance=0.02
    )
    notes = "\n".join(conditioned.notes)
    assert "hip stabilization" in notes
    assert "smoothing" in notes
    assert "keyframe reduction" in notes
    assert len(conditioned.frames) <= len(action.frames)  # reduction ran last
    assert conditioned.failed == action.failed
    again = condition_action(
        action, hip_stabilize=0.7, min_cutoff=1.0, tolerance=0.02
    )
    assert conditioned == again  # deterministic


def test_condition_action_default_has_no_stabilization() -> None:
    action = _breathing_action()
    same = condition_action(action, min_cutoff=None, tolerance=None)
    assert [af.pose.positions for af in same.frames] == \
        [af.pose.positions for af in action.frames]
    assert not any("hip stabilization" in n for n in same.notes)


def test_pipeline_condition_detect_lock_still_gates() -> None:
    """The composition gate: condition -> detect -> lock keeps the foot-lock
    guarantee, and stabilization alone already cuts the breathing slide."""
    action = _breathing_action()

    # raw path: contacts detect through the breathing, lock zeroes the slide
    raw_report = detect_contacts(action.frames)
    assert raw_report.in_contact  # breathing must not hide planted feet
    raw_slide = foot_slide(action.frames, raw_report)
    locked_raw, lock_raw = lock_feet(action, raw_report)
    assert raw_slide.total > 0.0
    assert lock_raw.slide_after.total <= raw_slide.total / 5.0

    # conditioned path: stabilization first, then detect + lock
    conditioned = condition_action(
        action, hip_stabilize=0.7, min_cutoff=None, tolerance=None
    )
    cond_slide_alone = foot_slide(conditioned.frames, raw_report)
    assert cond_slide_alone.total < 0.5 * raw_slide.total

    cond_report = detect_contacts(conditioned.frames)
    assert cond_report.in_contact
    attached = attach_contacts(conditioned, cond_report)
    locked_cond, lock_cond = lock_feet(attached, cond_report)
    assert lock_cond.slide_after.total == 0.0
    assert sum(lock_cond.clamped.values()) == 0  # corrections stayed reachable
    assert locked_cond.frame_indices == attached.frame_indices
