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

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis.action import ActionFrame, action_from_poses  # noqa: E402
from riggermortis.canonical_pose import CanonicalPose  # noqa: E402
from riggermortis.contacts import (  # noqa: E402
    ContactInterval,
    attach_contacts,
    detect_contacts,
    foot_slide,
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
