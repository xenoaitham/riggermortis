"""Foot contact detection (P2-4): velocity + height heuristic with hysteresis.

Input: a canonical action's per-frame poses (canonical units, hip-anchored —
the solve already normalizes person scale, and per-frame hip anchoring cancels
whole-body translation, so a planted ankle is near-stationary in this space
even when the subject walks across the frame).

Per foot, a frame is IN CONTACT when the ankle is simultaneously:
- SLOW: ankle speed below a threshold (canonical units per source frame), and
- LOW: ankle height near the sequence's ground estimate (a nearest-rank
  percentile of that ankle's z values, so the anchor choice — hips or neck —
  self-normalizes).

A Schmitt trigger keeps it from flickering: ENTERING needs the tighter
``enter_*`` thresholds; LEAVING needs the looser ``exit_*`` thresholds
(``enter_speed <= exit_speed``, ``enter_height <= exit_height``). Thresholds
are order-of-magnitude choices on the canonical scale (hip height = 1.0),
documented here and NOT fitted to any fixture (D-008 discipline).

Honesty rules: a failed frame (no pose) splits contact intervals — unknown
state is never interpolated; the very first observation has no measurable
speed and starts OUT of contact until an enter condition is seen. Output is
a deterministic interval list per foot, attachable to the action
(:func:`attach_contacts`) as the input metadata for P2-5's IK foot lock.

Pure stdlib; same input = same output.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from .action import ActionFrame, CanonicalAction

#: Foot roles detected (canonical roles are frozen API).
FOOT_ROLES = ("foot.L", "foot.R")

#: Defaults in canonical units/frame and canonical units above ground.
ENTER_SPEED = 0.02
EXIT_SPEED = 0.06
ENTER_HEIGHT = 0.08
EXIT_HEIGHT = 0.20
GROUND_PERCENTILE = 10.0


@dataclass
class ContactInterval:
    """One planted stretch for one foot; source frame indices, INCLUSIVE."""

    foot: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


@dataclass
class ContactReport:
    """All contact intervals plus honest bookkeeping."""

    intervals: list[ContactInterval] = field(default_factory=list)
    in_contact: dict[str, int] = field(default_factory=dict)  # foot -> frame count
    ground: dict[str, float] = field(default_factory=dict)  # foot -> z estimate
    notes: list[str] = field(default_factory=list)


def _nearest_rank_percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile of a non-empty list (deterministic)."""
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def _detect_foot(
    foot: str, obs: list[tuple[int, float, tuple[float, float, float]]],
    *, enter_speed: float, exit_speed: float,
    enter_height: float, exit_height: float, ground_pct: float,
    notes: list[str],
) -> tuple[list[ContactInterval], int, float]:
    """State machine over one foot's ``(frame, z, position)`` observations."""
    ground = _nearest_rank_percentile([z for _f, z, _p in obs], ground_pct)
    intervals: list[ContactInterval] = []
    start: int | None = None
    prev: tuple[int, tuple[float, float, float]] | None = None

    for frame, z, pos in obs:
        height = z - ground
        if prev is None:
            speed = None  # first observation: speed unknown -> stays out
        else:
            pf, ppos = prev
            dt = frame - pf
            if dt <= 0:  # defensive: action frames are strictly increasing
                speed = None
            else:
                speed = math.dist(pos, ppos) / dt
        if prev is not None and frame - prev[0] > 1:
            # gap: unknown state — close the open interval, require re-enter
            if start is not None:
                intervals.append(ContactInterval(foot, start, prev[0]))
                start = None
            notes.append(
                f"{foot}: contact state unknown across the gap before frame "
                f"{frame} — interval split, not interpolated"
            )

        if start is None:
            if speed is not None and speed <= enter_speed and height <= enter_height:
                start = frame
        else:
            if speed is not None and (speed > exit_speed or height > exit_height):
                intervals.append(ContactInterval(foot, start, prev[0]))
                start = None
        prev = (frame, pos)

    if start is not None and prev is not None:
        intervals.append(ContactInterval(foot, start, prev[0]))
    return intervals, sum(iv.length for iv in intervals), ground


def detect_contacts(
    frames: list[ActionFrame],
    *,
    enter_speed: float = ENTER_SPEED,
    exit_speed: float = EXIT_SPEED,
    enter_height: float = ENTER_HEIGHT,
    exit_height: float = EXIT_HEIGHT,
    ground_percentile: float = GROUND_PERCENTILE,
) -> ContactReport:
    """Detect planted-foot intervals from an action's frames.

    Parameters are in canonical units (hip height = 1.0) and canonical units
    per source frame; see the module docstring for the semantics and the
    no-fitting discipline. Gap frames (failed detections) split intervals.
    """
    if not (0.0 <= enter_speed <= exit_speed):
        raise ValueError(
            f"enter_speed must be <= exit_speed (hysteresis), "
            f"got {enter_speed} > {exit_speed}"
        )
    if not (0.0 <= enter_height <= exit_height):
        raise ValueError(
            f"enter_height must be <= exit_height (hysteresis), "
            f"got {enter_height} > {exit_height}"
        )
    notes: list[str] = []
    all_intervals: list[ContactInterval] = []
    in_contact: dict[str, int] = {}
    ground: dict[str, float] = {}

    for foot in FOOT_ROLES:
        obs = [
            (af.frame, af.pose.positions[foot][2], af.pose.positions[foot])
            for af in sorted(frames, key=lambda f: f.frame)
            if foot in af.pose.positions
        ]
        if len(obs) < 2:
            notes.append(
                f"{foot}: {len(obs)} observed frame(s) — not enough to "
                "measure speed; no contacts reported"
            )
            continue
        intervals, count, est = _detect_foot(
            foot, obs,
            enter_speed=enter_speed, exit_speed=exit_speed,
            enter_height=enter_height, exit_height=exit_height,
            ground_pct=ground_percentile, notes=notes,
        )
        all_intervals.extend(intervals)
        in_contact[foot] = count
        ground[foot] = est

    all_intervals.sort(key=lambda iv: (iv.foot, iv.start, iv.end))
    return ContactReport(
        intervals=all_intervals,
        in_contact=in_contact,
        ground=ground,
        notes=notes,
    )


def attach_contacts(
    action: CanonicalAction, report: ContactReport
) -> CanonicalAction:
    """Return a copy of ``action`` carrying ``report`` as metadata (P2-5 input)."""
    return replace(action, contacts=report)


# -- foot-slide metric (P2-5's number to beat) ----------------------------------

@dataclass
class SlideReport:
    """Ankle path length traveled WHILE in contact (canonical units).

    This is the foot-slide metric the Phase-2 gate publishes: raw retargets
    slide because the solve has no ground constraint; P2-5's IK foot lock
    must reduce this number (gate: >=5x). Path length is used, not endpoint
    distance, so micro-jitter slide inside a planted stretch counts.
    """

    per_foot: dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    contact_frames: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def foot_slide(frames: list[ActionFrame], report: ContactReport) -> SlideReport:
    """Measure ankle slide over ``report``'s contact intervals.

    Only frames inside a contact interval contribute (the foot is supposed
    to be planted there); gaps contribute nothing and no interpolation is
    done. Pure stdlib, deterministic.
    """
    by_frame = {af.frame: af.pose.positions for af in frames}
    per_foot: dict[str, float] = {foot: 0.0 for foot in FOOT_ROLES if foot in report.in_contact}
    notes: list[str] = []
    for interval in report.intervals:
        if interval.foot not in per_foot:
            continue
        prev = None
        for frame in range(interval.start, interval.end + 1):
            pos = by_frame.get(frame, {}).get(interval.foot)
            if pos is None:
                continue  # gap inside the interval: skip, never interpolate
            if prev is not None:
                per_foot[interval.foot] += math.dist(pos, prev)
            prev = pos
    for foot in sorted(per_foot):
        spans = [
            iv for iv in report.intervals
            if iv.foot == foot and (iv.end - iv.start + 1) > 1
        ]
        if spans and per_foot[foot] == 0.0:
            notes.append(f"{foot}: no measurable slide across {len(spans)} interval(s)")
    return SlideReport(
        per_foot=per_foot,
        total=sum(per_foot.values()),
        contact_frames=dict(report.in_contact),
        notes=notes,
    )
