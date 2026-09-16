"""Temporal smoothing (P2-2): a 1€ filter class plus keyframe reduction.

Pure stdlib, frame-rate aware, and deterministic — the same numbers Casiez's
1€ filter publishes (Casiez, Roussel & Vogel, CHI 2012): an adaptive low-pass
whose cutoff rises with signal speed (``beta``), wrapped around its own
low-passed derivative estimate. Applied per canonical channel so pose
jitter dies while fast limb motion survives.

``reduce_keyframes`` is the P2-2 *sketch* of the retarget-time keyframe pass
(P2-3 wires it into actions): greedy error-driven decimation — a frame is
kept when any tracked channel bends more than ``tolerance`` away from the
linear path between its kept neighbours. Deterministic; endpoints always kept.

``moving_average`` (P2-6) is the offline companion: a centered moving average
for separation of low-frequency drift from high-frequency sway on tracks that
are fully observed (an action is conditioned after the fact, so a phase-neutral
centered window beats a causal filter). Windows shrink at the edges instead of
shifting the signal.
"""
from __future__ import annotations

import math

Point3 = tuple[float, float, float]
PoseFrame = dict[str, Point3]


def _alpha(cutoff: float, freq: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    te = 1.0 / freq
    return 1.0 / (1.0 + tau / te)


def moving_average(values: list[float], window: int) -> list[float]:
    """Centered moving average; same length out as in.

    ``window`` counts observed samples (an even window is bumped to the next
    odd, deterministically). Edge windows shrink to the available neighbours
    rather than padding, so the ends stay phase-true. Pure stdlib; same input
    = same output.
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")
    if not values:
        return []
    half = max(window // 2, 0)
    if window % 2 == 0:
        half = window // 2  # even window: asymmetric bump, still deterministic
    out: list[float] = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


class OneEuroFilter:
    """Adaptive low-pass for one scalar channel (Casiez et al. 2012)."""

    def __init__(
        self, freq: float = 30.0, min_cutoff: float = 1.0,
        beta: float = 0.0, d_cutoff: float = 1.0,
    ) -> None:
        if freq <= 0.0:
            raise ValueError(f"freq must be > 0, got {freq}")
        self.freq = float(freq)
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._x_prev: float | None = None
        self._dx_prev = 0.0

    def __call__(self, x: float, timestamp: float | None = None) -> float:
        if timestamp is not None and self._x_prev is not None:
            dt = timestamp - getattr(self, "_t_prev", timestamp - 1.0 / self.freq)
            if dt > 0.0:
                self.freq = 1.0 / dt
        if self._x_prev is None:
            self._x_prev = x
            self._t_prev = timestamp if timestamp is not None else 0.0
            self._dx_prev = 0.0
            return x
        dx = (x - self._x_prev) * self.freq
        a_d = _alpha(self.d_cutoff, self.freq)
        dx_hat = a_d * dx + (1.0 - a_d) * self._dx_prev

        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = _alpha(cutoff, self.freq)
        x_hat = a * x + (1.0 - a) * self._x_prev

        self._x_prev = x_hat
        self._dx_prev = dx_hat
        if timestamp is not None:
            self._t_prev = timestamp
        return x_hat


def smooth_channel(
    values: list[float], freq: float = 30.0, min_cutoff: float = 1.0,
    beta: float = 0.0,
) -> list[float]:
    """Filter one scalar track; same length out as in."""
    flt = OneEuroFilter(freq=freq, min_cutoff=min_cutoff, beta=beta)
    return [flt(v) for v in values]


def smooth_pose_frames(
    frames: list[PoseFrame], freq: float = 30.0, min_cutoff: float = 1.0,
    beta: float = 0.0,
) -> list[PoseFrame]:
    """Per-role, per-channel 1€ smoothing across a pose sequence.

    Frames are ``{role: (x, y, z)}``; roles missing from a frame are simply
    absent from that output frame (partial observation stays partial).
    """
    if not frames:
        return []
    roles = sorted({role for frame in frames for role in frame})
    out: list[PoseFrame] = []
    filters: dict[str, tuple[OneEuroFilter, OneEuroFilter, OneEuroFilter]] = {}
    for role in roles:
        filters[role] = tuple(
            OneEuroFilter(freq=freq, min_cutoff=min_cutoff, beta=beta)
            for _ in range(3)
        )
    for frame in frames:
        smoothed: PoseFrame = {}
        for role in sorted(frame):
            x, y, z = frame[role]
            fx, fy, fz = filters[role]
            smoothed[role] = (fx(x), fy(y), fz(z))
        out.append(smoothed)
    return out


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _frame_max_error(
    frame: PoseFrame, a: PoseFrame, b: PoseFrame, t: float
) -> float:
    """Max per-role distance from ``frame`` to the a->b linear path."""
    worst = 0.0
    for role, (x, y, z) in frame.items():
        if role not in a or role not in b:
            continue
        ax, ay, az = a[role]
        bx, by, bz = b[role]
        dx = x - _lerp(ax, bx, t)
        dy = y - _lerp(ay, by, t)
        dz = z - _lerp(az, bz, t)
        err = math.sqrt(dx * dx + dy * dy + dz * dz)
        if err > worst:
            worst = err
    return worst


def reduce_keyframes(
    frames: list[PoseFrame], tolerance: float = 0.01
) -> list[int]:
    """Greedy error-driven keyframe decimation; returns the KEPT indices.

    Endpoints always kept. A frame is kept when any channel sits further than
    ``tolerance`` (canonical units) from the straight path between its two
    nearest kept neighbours. First pass keeps everything between two anchors,
    then anchors grow — a single deterministic sweep pair (P2-2 sketch; the
    P2-3 retarget pass may refine to a full RDP on more anchors).
    """
    if len(frames) <= 2:
        return list(range(len(frames)))
    if tolerance < 0.0:
        raise ValueError(f"tolerance must be >= 0, got {tolerance}")

    kept = {0, len(frames) - 1}
    # forward sweep against the previous kept anchor pair
    anchor = 0
    for i in range(1, len(frames) - 1):
        t = i / (len(frames) - 1)
        if _frame_max_error(frames[i], frames[anchor], frames[-1], t) > tolerance:
            kept.add(i)
            anchor = i
    # backward refinement: split error against both sides of each kept pair
    ordered = sorted(kept)
    for lo, hi in zip(ordered, ordered[1:], strict=False):
        for i in range(lo + 1, hi):
            t = (i - lo) / (hi - lo)
            if _frame_max_error(frames[i], frames[lo], frames[hi], t) > tolerance:
                kept.add(i)
    return sorted(kept)
