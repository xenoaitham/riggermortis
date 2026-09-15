"""P2-2 tests: 1€ filter + keyframe reduction on synthetic jitter sequences."""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis.smoothing import (  # noqa: E402
    OneEuroFilter,
    reduce_keyframes,
    smooth_channel,
    smooth_pose_frames,
)


def _jittery_sine(n: int = 120, amp: float = 1.0, jitter: float = 0.2) -> list[float]:
    """A smooth sine plus deterministic sawtooth jitter (no random: CI-stable)."""
    return [
        amp * math.sin(2.0 * math.pi * i / n) + (jitter if i % 2 else -jitter)
        for i in range(n)
    ]


def _variance(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def test_one_euro_reduces_jitter_on_stationary_signal() -> None:
    truth = 0.5
    noisy = [truth + (0.1 if i % 2 else -0.1) for i in range(100)]
    out = smooth_channel(noisy, freq=30.0, min_cutoff=1.0, beta=0.0)
    assert _variance(out[10:]) < _variance(noisy[10:]) / 4.0
    assert abs(out[-1] - truth) < 0.05  # converges to the true value


def test_one_euro_tracks_fast_motion_with_beta() -> None:
    flt = OneEuroFilter(freq=30.0, min_cutoff=0.5, beta=0.05)
    # a step: with beta the filter catches up quickly after the jump
    out = [flt(0.0) for _ in range(10)] + [flt(1.0) for _ in range(30)]
    assert out[9] < 0.1  # stayed put before the step
    assert out[15] > 0.5  # caught most of the step within 5 frames
    assert out[-1] > 0.95


def test_one_euro_is_deterministic_and_timestamp_aware() -> None:
    values = _jittery_sine(60)
    a = smooth_channel(values)
    b = smooth_channel(values)
    assert a == b
    # explicit timestamps drive freq internally (20 Hz here)
    flt = OneEuroFilter(freq=30.0, min_cutoff=1.0)
    stamped = [flt(v, timestamp=i / 20.0) for i, v in enumerate(values)]
    assert len(stamped) == len(values)
    with pytest.raises(ValueError):
        OneEuroFilter(freq=0.0)


def test_smooth_pose_frames_keeps_roles_and_partial_observation() -> None:
    frames = [
        {"hips": (0.0, 0.0, 0.0), "hand.L": (0.1 * i, 0.0, 0.5)}
        for i in range(20)
    ]
    frames[5] = {"hips": (0.01, 0.0, 0.0)}  # hand missing: partial observation
    out = smooth_pose_frames(frames, freq=30.0, min_cutoff=1.0, beta=0.05)
    assert len(out) == 20
    assert set(out[0]) == {"hand.L", "hips"}
    assert set(out[5]) == {"hips"}  # missing role stays missing, honestly
    assert out == smooth_pose_frames(frames, freq=30.0, min_cutoff=1.0, beta=0.05)


def test_reduce_keyframes_keeps_endpoints_and_straight_lines_collapse() -> None:
    line = [{"hips": (i / 99.0, 0.0, 0.0)} for i in range(100)]
    assert reduce_keyframes(line, tolerance=0.01) == [0, 99]


def test_reduce_keyframes_keeps_a_spike_within_tolerance() -> None:
    frames = []
    for i in range(60):
        y = 1.0 if i == 30 else 0.0
        frames.append({"hips": (i / 59.0, y, 0.0)})
    kept = reduce_keyframes(frames, tolerance=0.05)
    assert kept[0] == 0 and kept[-1] == 59
    assert 30 in kept  # the spike is load-bearing
    assert len(kept) < 60  # and the flat parts still collapse


def test_reduce_keyframes_tolerance_and_determinism() -> None:
    sine = [
        {"hips": (i / 119.0, math.sin(2.0 * math.pi * i / 119.0), 0.0)}
        for i in range(120)
    ]
    loose = reduce_keyframes(sine, tolerance=0.2)
    tight = reduce_keyframes(sine, tolerance=0.005)
    assert len(loose) < len(tight)  # looser bar -> fewer keyframes
    assert tight == reduce_keyframes(sine, tolerance=0.005)
    assert reduce_keyframes(sine[:1]) == [0]
    assert reduce_keyframes(sine[:2]) == [0, 1]
    with pytest.raises(ValueError):
        reduce_keyframes(sine, tolerance=-1.0)
