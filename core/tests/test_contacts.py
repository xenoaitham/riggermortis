"""P2-4 tests: foot contact detection on sequences with KNOWN ground truth.

The synthetic walk is hand-constructed: stance frames are exactly planted,
swing frames follow a sine arc whose peak speed/height clear the exit
thresholds by wide margins. Ground truth = the frames the ankle is truly
stationary (a touchdown frame and the speed-unmeasurable first frame are
genuinely undetectable and excluded from GT by construction).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis.action import ActionFrame, action_from_poses  # noqa: E402
from riggermortis.canonical_pose import CanonicalPose  # noqa: E402
from riggermortis.contacts import (  # noqa: E402
    ContactInterval,
    ContactReport,
    attach_contacts,
    detect_contacts,
    foot_slide,
    lock_feet,
)

GROUND = -1.0  # planted ankle height in the synthetic world


def _pose(foot_l: tuple[float, float, float], foot_r: tuple[float, float, float],
          scale: float = 30.0) -> CanonicalPose:
    return CanonicalPose(
        positions={"foot.L": foot_l, "foot.R": foot_r, "hips": (0.0, 0.0, 0.0)},
        flips={}, confidence=0.9, reliable=True, scale=scale, anchor="hips",
    )


def _swing(frame: int, start: int, end: int, x: float, h_max: float = 0.35,
           dx: float = 0.02) -> tuple[float, float, float]:
    """Sine arc: tiny lift at the edges, h_max at mid-swing; x advances."""
    span = end - start + 2
    t = (frame - start + 1) / span
    return (x + dx * (frame - start), 0.0, GROUND + h_max * math.sin(math.pi * t))


def _walk(
    phases_l: list[tuple[str, int, int]],
    phases_r: list[tuple[str, int, int]],
    *,
    wobble: float = 0.0,
    scale: float = 30.0,
    drop: set[int] | None = None,
) -> list[ActionFrame]:
    """Build frames from per-foot phase lists [("stance"|"swing", start, end)]."""
    drop = drop or set()

    def _track(phases: list[tuple[str, int, int]], sign: float) -> dict[int, tuple[float, float, float]]:
        out: dict[int, tuple[float, float, float]] = {}
        for kind, start, end in phases:
            for i in range(start, end + 1):
                if kind == "stance":
                    wob = wobble * math.sin(0.9 * i)
                    out[i] = (sign * 0.11 + wob * 0.25, 0.0, GROUND + wob)
                else:
                    out[i] = _swing(i, start, end, x=sign * 0.11)
        return out

    left, right = _track(phases_l, -1.0), _track(phases_r, 1.0)
    frames = []
    for i in sorted(set(left) | set(right)):
        if i in drop:
            continue  # failed frame: honest gap
        frames.append(ActionFrame(
            frame=i,
            pose=_pose(left[i], right[i], scale=scale),  # type: ignore[arg-type]
        ))
    return frames


# A 70-frame walk: L stance 0-9, swing 10-23, stance 24-39, swing 40-53,
# stance 54-69. R is the half-cycle offset mirror.
PHASES_L = [("stance", 0, 9), ("swing", 10, 23), ("stance", 24, 39),
            ("swing", 40, 53), ("stance", 54, 69)]
PHASES_R = [("swing", 0, 13), ("stance", 14, 29), ("swing", 30, 43),
            ("stance", 44, 59), ("swing", 60, 69)]

# Detectable GT: stance minus each touchdown frame (landing speed is real
# motion) minus frame 0 (speed unmeasurable) — see module docstring.
GT_L = [ContactInterval("foot.L", 1, 9), ContactInterval("foot.L", 25, 39),
        ContactInterval("foot.L", 55, 69)]
GT_R = [ContactInterval("foot.R", 15, 29), ContactInterval("foot.R", 45, 59)]


def _pr(detected: list[ContactInterval], gt: list[ContactInterval]) -> tuple[float, float]:
    d = {f for iv in detected for f in range(iv.start, iv.end + 1)}
    g = {f for iv in gt for f in range(iv.start, iv.end + 1)}
    precision = len(d & g) / len(d) if d else 0.0
    recall = len(d & g) / len(g) if g else 0.0
    return precision, recall


def test_clean_walk_matches_ground_truth_exactly() -> None:
    report = detect_contacts(_walk(PHASES_L, PHASES_R))
    assert report.intervals == GT_L + GT_R  # sorted by (foot, start): L before R
    assert report.in_contact == {"foot.L": 39, "foot.R": 30}
    assert report.ground["foot.L"] == pytest.approx(GROUND)
    assert not report.notes


def test_noisy_walk_precision_and_recall() -> None:
    report = detect_contacts(_walk(PHASES_L, PHASES_R, wobble=0.004))
    p_l, r_l = _pr([iv for iv in report.intervals if iv.foot == "foot.L"],
                   [iv for iv in GT_L])
    p_r, r_r = _pr([iv for iv in report.intervals if iv.foot == "foot.R"],
                   [iv for iv in GT_R])
    assert p_l >= 0.9 and r_l >= 0.9
    assert p_r >= 0.9 and r_r >= 0.9


def test_failed_frame_splits_intervals_honestly() -> None:
    frames = _walk([("stance", 0, 19)], [("swing", 0, 19)], drop={10})
    report = detect_contacts(frames)
    l_intervals = [iv for iv in report.intervals if iv.foot == "foot.L"]
    # gap closes the interval AND requires re-enter (touchdown semantics)
    assert [(iv.start, iv.end) for iv in l_intervals] == [(1, 9), (11, 19)]
    assert any("gap" in n and "foot.L" in n for n in report.notes)


def test_gap_note_only_fires_once_per_gap() -> None:
    frames = _walk([("stance", 0, 29)], [("swing", 0, 29)], drop={10, 20})
    report = detect_contacts(frames)
    l_gaps = [n for n in report.notes if "gap" in n and "foot.L" in n]
    assert len(l_gaps) == 2


def test_detection_is_deterministic() -> None:
    a = detect_contacts(_walk(PHASES_L, PHASES_R, wobble=0.004))
    b = detect_contacts(_walk(PHASES_L, PHASES_R, wobble=0.004))
    assert a == b


def test_scale_field_does_not_leak_into_detection() -> None:
    """Positions are canonical-unit by construction; the px/unit scale value
    carried by each pose must not change the verdict."""
    low = detect_contacts(_walk(PHASES_L, PHASES_R, scale=20.0))
    high = detect_contacts(_walk(PHASES_L, PHASES_R, scale=200.0))
    assert low == high


def test_airborne_sequence_has_no_contacts() -> None:
    frames = _walk([("swing", 0, 29)], [("swing", 0, 29)])
    report = detect_contacts(frames)
    assert not report.intervals
    # both feet analyzed, zero contact frames each
    assert report.in_contact == {"foot.L": 0, "foot.R": 0}


def test_standing_still_is_one_long_contact() -> None:
    frames = _walk([("stance", 0, 29)], [("stance", 0, 29)])
    report = detect_contacts(frames)
    assert [(iv.foot, iv.start, iv.end) for iv in report.intervals] == [
        ("foot.L", 1, 29), ("foot.R", 1, 29),
    ]


def test_hysteresis_parameters_are_validated() -> None:
    frames = _walk([("stance", 0, 9)], [("stance", 0, 9)])
    with pytest.raises(ValueError, match="enter_speed"):
        detect_contacts(frames, enter_speed=0.5, exit_speed=0.1)
    with pytest.raises(ValueError, match="enter_height"):
        detect_contacts(frames, enter_height=0.5, exit_height=0.1)


def test_attach_contacts_copies_and_keeps_source() -> None:
    frames = _walk(PHASES_L, PHASES_R)
    action = action_from_poses([(f.frame, f.pose) for f in frames])
    report = detect_contacts(frames)
    attached = attach_contacts(action, report)
    assert attached.contacts is report
    assert action.contacts is None  # source untouched
    assert attached.frames == action.frames


# -- foot-slide metric (P2-5's baseline instrument) ------------------------------

def test_clean_planted_foot_does_not_slide() -> None:
    frames = _walk([("stance", 0, 29)], [("stance", 0, 29)])
    report = detect_contacts(frames)
    slide = foot_slide(frames, report)
    assert slide.per_foot["foot.L"] == pytest.approx(0.0, abs=1e-9)
    assert slide.total == pytest.approx(0.0, abs=1e-9)


def test_slide_counts_drift_inside_intervals_only() -> None:
    """A planted-but-drifting ankle slides; swing frames contribute nothing."""
    frames = _walk([("stance", 0, 29)], [("stance", 0, 29)], wobble=0.01)
    report = detect_contacts(frames)
    slide = foot_slide(frames, report)
    # wobble 0.01*sin(0.9i) on z + 0.0025 on x per stance frame — small but nonzero
    assert 0.0 < slide.per_foot["foot.L"] < 0.5
    # the same wobble outside any contact interval must not be counted:
    swing_only = _walk([("swing", 0, 29)], [("swing", 0, 29)], wobble=0.01)
    empty_report = detect_contacts(swing_only)
    assert foot_slide(swing_only, empty_report).total == 0.0


def test_slide_gap_inside_interval_is_skipped_not_interpolated() -> None:
    frames = _walk([("stance", 0, 9)], [("stance", 0, 9)], drop={5})
    report = detect_contacts(frames)
    slide = foot_slide(frames, report)
    # positions identical across the gap -> skipping frame 5 changes nothing
    assert slide.per_foot["foot.L"] == pytest.approx(0.0, abs=1e-9)


def test_slide_is_deterministic() -> None:
    frames = _walk(PHASES_L, PHASES_R, wobble=0.004)
    report = detect_contacts(frames)
    assert foot_slide(frames, report) == foot_slide(frames, report)


# -- IK foot lock (P2-5) ----------------------------------------------------------

def _chain_pose(foot_l: tuple[float, float, float], foot_r: tuple[float, float, float],
                *, hips: tuple[float, float, float] = (0.0, 0.0, 0.0),
                scale: float = 30.0) -> CanonicalPose:
    """Pose with the full leg chain: hip joints, knees (bent forward), toes."""
    positions = {"hips": hips, "foot.L": tuple(foot_l), "foot.R": tuple(foot_r)}
    for side, foot in ((".L", foot_l), (".R", foot_r)):
        sign = -1.0 if side == ".L" else 1.0
        h = (sign * 0.08 + hips[0], hips[1], hips[2])
        knee = ((h[0] + foot[0]) / 2.0, (h[1] + foot[1]) / 2.0 - 0.08,
                (h[2] + foot[2]) / 2.0)
        positions[f"upper_leg{side}"] = h
        positions[f"lower_leg{side}"] = knee
        positions[f"toe{side}"] = (foot[0], foot[1] - 0.12, foot[2])
    return CanonicalPose(
        positions=positions,  # type: ignore[arg-type]
        flips={}, confidence=0.9, reliable=True, scale=scale, anchor="hips",
    )


def _chain_walk(
    phases_l: list[tuple[str, int, int]],
    phases_r: list[tuple[str, int, int]],
    *,
    wobble: float = 0.0,
    drift: float = 0.0,
    drop: set[int] | None = None,
) -> list[ActionFrame]:
    """Full-leg-chain walk; stance ankles drift `drift`/frame in x — the
    hip-anchoring artifact the lock exists to remove."""
    drop = drop or set()

    def _track(phases: list[tuple[str, int, int]], sign: float) -> dict[int, tuple[float, float, float]]:
        out: dict[int, tuple[float, float, float]] = {}
        for kind, start, end in phases:
            for i in range(start, end + 1):
                x = sign * 0.11
                if kind == "stance":
                    wob = wobble * math.sin(0.9 * i)
                    out[i] = (x + drift * (i - start) + wob * 0.25, 0.0, GROUND + wob)
                else:
                    out[i] = _swing(i, start, end, x=x)
        return out

    left, right = _track(phases_l, -1.0), _track(phases_r, 1.0)
    frames = []
    for i in sorted(set(left) | set(right)):
        if i in drop:
            continue
        frames.append(ActionFrame(frame=i, pose=_chain_pose(left[i], right[i])))
    return frames


def _action(frames: list[ActionFrame]) -> Any:
    return action_from_poses([(f.frame, f.pose) for f in frames])


def test_lock_pins_drift_and_zeroes_slide() -> None:
    frames = _chain_walk(PHASES_L, PHASES_R, drift=0.01)
    action = _action(frames)
    report = detect_contacts(frames)
    locked, lock = lock_feet(action, report)
    # stance drift accumulates ~0.01u per frame inside intervals — the artifact
    assert lock.slide_before.total > 0.3
    assert lock.slide_after.total == pytest.approx(0.0, abs=1e-9)
    # per-interval anchors are kept as-is, all later in-contact frames pinned
    assert lock.per_foot_frames == {"foot.L": 36, "foot.R": 28}
    assert sum(lock.clamped.values()) == 0
    assert lock.max_knee_shift["foot.L"] > 0.0  # the lock did real work


def test_lock_preserves_leg_lengths() -> None:
    frames = _chain_walk(PHASES_L, PHASES_R, drift=0.01, wobble=0.004)
    action = _action(frames)
    report = detect_contacts(frames)
    locked, _lock = lock_feet(action, report)
    src = {af.frame: af.pose.positions for af in action.frames}
    for af in locked.frames:
        new = af.pose.positions
        old = src[af.frame]
        for side in (".L", ".R"):
            for pair in (("upper_leg", "lower_leg"), ("lower_leg", "foot")):
                a, b = (f"{base}{side}" for base in pair)
                assert math.dist(new[a], new[b]) == pytest.approx(
                    math.dist(old[a], old[b]), abs=1e-9
                )


def test_lock_noop_on_already_planted() -> None:
    frames = _chain_walk([("stance", 0, 29)], [("stance", 0, 29)])
    action = _action(frames)
    report = detect_contacts(frames)
    locked, lock = lock_feet(action, report)
    assert locked.frames == action.frames  # equal by value — nothing to do
    assert lock.slide_after.total == pytest.approx(0.0, abs=1e-9)
    assert all(v == pytest.approx(0.0, abs=1e-9) for v in lock.max_knee_shift.values())


def test_lock_clamps_unreachable_ankle() -> None:
    # frame 1's hips+chain jump far up while the pinned ankle stays planted:
    # the target sits beyond the leg's reach, so the lock must clamp (counted).
    p0 = _chain_pose((-0.11, 0.0, -1.0), (0.11, 0.0, -1.0))
    p1 = _chain_pose((-0.11, 0.0, -0.40), (0.11, 0.0, -0.40), hips=(0.0, 0.0, 0.45))
    action = action_from_poses([(0, p0), (1, p1)])
    report = ContactReport(
        intervals=[ContactInterval("foot.L", 0, 1)],
        in_contact={"foot.L": 2},
        ground={"foot.L": -1.0},
    )
    locked, lock = lock_feet(action, report)
    assert lock.clamped["foot.L"] == 1
    h = p1.positions["upper_leg.L"]
    k = p1.positions["lower_leg.L"]
    reach = math.dist(h, k) + math.dist(k, p1.positions["foot.L"])
    a1 = locked.frames[1].pose.positions["foot.L"]
    assert math.dist(h, a1) <= reach + 1e-9  # FK bones cannot stretch
    assert lock.max_ankle_shift["foot.L"] > 0.0


def test_lock_skips_gap_frames_without_interpolation() -> None:
    frames = _chain_walk([("stance", 0, 9)], [("swing", 0, 9)], drift=0.01, drop={5})
    action = _action(frames)
    report = detect_contacts(frames)
    locked, lock = lock_feet(action, report)
    # intervals (1,4) and (6,9): two anchors, each kept, 3 frames pinned each
    assert lock.per_foot_frames["foot.L"] == 6
    assert 5 not in {af.frame for af in locked.frames}  # gap stays a gap
    by_frame = {af.frame: af.pose.positions for af in locked.frames}
    a4 = by_frame[4]["foot.L"]
    a9 = by_frame[9]["foot.L"]
    assert a4 != a9  # each interval pins to ITS anchor — no cross-gap bridging


def test_lock_is_deterministic() -> None:
    frames = _chain_walk(PHASES_L, PHASES_R, drift=0.01, wobble=0.004)
    action = _action(frames)
    report = detect_contacts(frames)
    a, la = lock_feet(action, report)
    b, lb = lock_feet(action, report)
    assert a == b and la == lb


def test_lock_to_ground_projects_ankle() -> None:
    frames = _chain_walk([("stance", 0, 9)], [("swing", 0, 9)], wobble=0.005)
    action = _action(frames)
    report = detect_contacts(frames)
    locked, _lock = lock_feet(action, report, to_ground=True)
    contact_frames = {
        f for iv in report.intervals if iv.foot == "foot.L"
        for f in range(iv.start, iv.end + 1)
    }
    src = {af.frame: af.pose.positions for af in action.frames}
    for af in locked.frames:
        if af.frame in contact_frames:
            new = af.pose.positions
            assert new["foot.L"][2] == pytest.approx(report.ground["foot.L"], abs=1e-12)
            # toe rides rigidly: foot length preserved
            assert math.dist(new["foot.L"], new["toe.L"]) == pytest.approx(
                math.dist(src[af.frame]["foot.L"], src[af.frame]["toe.L"]), abs=1e-9
            )


def test_lock_never_mutates_input() -> None:
    frames = _chain_walk(PHASES_L, PHASES_R, drift=0.01)
    action = _action(frames)
    snapshot = [(af.frame, dict(af.pose.positions)) for af in action.frames]
    lock_feet(action, detect_contacts(frames))
    for af, (frame, positions) in zip(action.frames, snapshot, strict=True):
        assert af.frame == frame and af.pose.positions == positions


def test_lock_leaves_swing_foot_untouched() -> None:
    frames = _chain_walk([("stance", 0, 9)], [("swing", 0, 9)], drift=0.01)
    action = _action(frames)
    report = detect_contacts(frames)  # foot.R never enters contact
    locked, lock = lock_feet(action, report)
    assert "foot.R" not in lock.per_foot_frames
    for before, after in zip(action.frames, locked.frames, strict=True):
        for role in ("foot.R", "toe.R", "upper_leg.R", "lower_leg.R"):
            assert before.pose.positions[role] == after.pose.positions[role]


def test_lock_both_feet_sharing_a_frame() -> None:
    frames = _chain_walk([("stance", 0, 9)], [("stance", 0, 9)], drift=0.01)
    action = _action(frames)
    report = detect_contacts(frames)
    locked, lock = lock_feet(action, report)
    assert lock.per_foot_frames["foot.L"] > 0 and lock.per_foot_frames["foot.R"] > 0
    by_frame = {af.frame: af.pose.positions for af in locked.frames}
    # frame 3 is locked by BOTH feet — neither chain may clobber the other
    assert by_frame[3]["foot.L"] == by_frame[1]["foot.L"]
    assert by_frame[3]["foot.R"] == by_frame[1]["foot.R"]
    assert by_frame[3]["lower_leg.L"] != by_frame[3]["lower_leg.R"]
