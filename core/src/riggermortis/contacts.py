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

Pure stdlib; same input = same output. The P2-5 lock (:func:`lock_feet`)
consumes a report here too: it pins planted ankles and re-solves the knee.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from .action import ActionFrame, CanonicalAction
from .linalg import Vec3, v_add, v_dist, v_dot, v_len, v_norm, v_scale, v_sub

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


# -- IK foot lock (P2-5) ---------------------------------------------------------

#: Leg-chain roles pinned while a foot is in contact (append ".L"/".R").
LOCK_CHAIN_BASES = ("upper_leg", "lower_leg", "foot", "toe")

_EPS = 1e-9
#: A pin satisfied within this distance keeps the original values, so locking
#: an already-clean action is a bit-for-bit no-op (no float noise keyed).
_SNAP = 1e-12


@dataclass
class LockReport:
    """What the IK foot lock did, measured honestly (canonical units).

    ``slide_before``/``slide_after`` are the gate numbers (>=5x improvement on
    the same action + report). The shift/clamp fields are the COST of the
    lock: how far pinned ankles and re-solved knees moved away from the
    source observation. A lock that reports zero cost did nothing.
    """

    per_foot_frames: dict[str, int] = field(default_factory=dict)
    per_foot_intervals: dict[str, int] = field(default_factory=dict)
    slide_before: SlideReport | None = None
    slide_after: SlideReport | None = None
    max_knee_shift: dict[str, float] = field(default_factory=dict)
    max_ankle_shift: dict[str, float] = field(default_factory=dict)
    clamped: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _solve_knee(
    h: Vec3, a: Vec3, k0: Vec3, l1: float, l2: float
) -> tuple[Vec3, float]:
    """Knee for hip ``h`` and ankle target ``a`` with thigh/shin lengths
    ``l1``/``l2``: the point on the reachable circle closest to the original
    knee ``k0`` (preserves the bend direction). Deterministic; degenerate
    straight-leg input falls back to the canonical knee-forward prior
    (character faces -Y) via a fixed axis ladder."""
    d_vec = v_sub(a, h)
    d = v_len(d_vec)
    axis = v_scale(d_vec, 1.0 / d)
    along = (l1 * l1 - l2 * l2 + d * d) / (2.0 * d)
    r = math.sqrt(max(l1 * l1 - along * along, 0.0))
    plane = v_add(h, v_scale(axis, along))
    radial = v_sub(k0, plane)
    radial = v_sub(radial, v_scale(axis, v_dot(radial, axis)))
    if v_len(radial) <= _EPS:
        for fallback in ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)):
            radial = v_sub(fallback, v_scale(axis, v_dot(fallback, axis)))
            if v_len(radial) > _EPS:
                break
    return v_add(plane, v_scale(v_norm(radial), r)), r


def _clamp_target(h: Vec3, target: Vec3, l1: float, l2: float) -> tuple[Vec3, int]:
    """Pull/push ``target`` along h->target so the 2-bone chain can reach it.

    Returns (target, clamped) with clamped in {0, 1}. FK bones cannot stretch,
    so an unreachable pinned ankle would make the pose lie about lengths —
    clamping keeps the geometry valid and is counted, never hidden."""
    d = v_dist(h, target)
    reach = l1 + l2
    eps = 1e-6 * reach
    if d > reach - eps:
        axis = v_scale(v_sub(target, h), 1.0 / d)
        return v_add(h, v_scale(axis, reach - eps)), 1
    if d < abs(l1 - l2) + eps:
        if d > _EPS:
            axis = v_scale(v_sub(target, h), 1.0 / d)
        else:  # ankle at the hip: any direction; canonical down, deterministic
            axis = (0.0, 0.0, -1.0)
        return v_add(h, v_scale(axis, abs(l1 - l2) + eps)), 1
    return target, 0


def lock_feet(
    action: CanonicalAction, report: ContactReport, *, to_ground: bool = False
) -> tuple[CanonicalAction, LockReport]:
    """Pin planted feet: P2-5's IK foot lock, v1 = position pin + knee re-solve.

    For every contact interval the ankle (and toe, when present) is pinned to
    its FIRST OBSERVED position inside that interval — a real, detected plant
    pose, never a fabricated one — and the knee is re-solved by a deterministic
    2-bone IK so thigh/shin lengths are preserved. In-contact ankle motion in a
    canonical action is an artifact of per-frame hip anchoring (the planted
    foot was stationary in the world); pinning removes the artifact and the
    locked action is walk-in-place — the honest alternative to fabricating
    root motion (D-008). Swing frames and gap frames are untouched; the input
    action is never mutated. Frames missing leg-chain positions are left
    unlocked with a note (ambiguity reported, never swallowed).

    ``to_ground`` additionally projects each pinned ankle onto the report's
    ground estimate (uniform ground height across intervals); the toe follows
    rigidly.

    Returns ``(locked_action, lock_report)``; the report carries the
    before/after ``foot_slide`` numbers the >=5x gate publishes.
    """
    frames = list(action.frames)
    if not frames:
        report_copy = LockReport(notes=["foot lock: empty action — nothing to lock"])
        return replace(action, notes=list(action.notes)), report_copy
    by_frame = {af.frame: af for af in frames}
    lock = LockReport(slide_before=foot_slide(frames, report))
    lock_notes: list[str] = []
    changed: dict[int, dict[str, Vec3]] = {}

    for interval in report.intervals:
        foot = interval.foot
        side = foot[-2:]  # ".L"/".R" — FOOT_ROLES are always side-marked
        toe, upper, lower = (f"{b}{side}" for b in ("toe", "upper_leg", "lower_leg"))
        anchor = next(
            (f for f in range(interval.start, interval.end + 1) if f in by_frame), None
        )
        if anchor is None:
            lock_notes.append(
                f"foot lock {foot}: interval {interval.start}-{interval.end} has "
                "no observed frame — skipped"
            )
            continue
        anchor_pos = by_frame[anchor].pose.positions
        if foot not in anchor_pos:
            lock_notes.append(
                f"foot lock {foot}: anchor frame {anchor} lacks the ankle "
                "position — interval skipped"
            )
            continue
        pinned: Vec3 = tuple(anchor_pos[foot])  # type: ignore[assignment]
        if to_ground and foot in report.ground:
            pinned = (pinned[0], pinned[1], report.ground[foot])
        toe_offset: Vec3 | None = None
        if toe in anchor_pos:
            toe_offset = v_sub(tuple(anchor_pos[toe]), tuple(anchor_pos[foot]))

        frames_locked = 0
        for f in range(interval.start, interval.end + 1):
            af = by_frame.get(f)
            if af is None:
                continue  # gap: unknown state is never interpolated
            pos = af.pose.positions
            if foot not in pos or upper not in pos or lower not in pos:
                lock_notes.append(
                    f"foot lock {foot}: frame {f} lacks leg-chain positions — "
                    "left unlocked"
                )
                continue
            if f == anchor and not to_ground:
                continue  # anchor already holds the pinned values exactly
            h = tuple(pos[upper])
            k0 = tuple(pos[lower])
            a0 = tuple(pos[foot])
            l1 = v_dist(h, k0)
            l2 = v_dist(k0, a0)
            target, clamped = _clamp_target(h, pinned, l1, l2)
            knee, _r = _solve_knee(h, target, k0, l1, l2)
            updates: dict[str, Vec3] = {foot: target, lower: knee}
            if toe_offset is not None:
                updates[toe] = v_add(target, toe_offset)
            if not clamped and all(
                v_dist(val, tuple(pos[role])) <= _SNAP for role, val in updates.items()
            ):
                frames_locked += 1  # pin already satisfied: keep original values
                continue
            merged = dict(changed.get(f, pos))
            merged.update(updates)  # both feet may lock the same frame
            changed[f] = merged
            frames_locked += 1
            lock.clamped[foot] = lock.clamped.get(foot, 0) + clamped
            lock.max_ankle_shift[foot] = max(
                lock.max_ankle_shift.get(foot, 0.0), v_dist(target, a0)
            )
            lock.max_knee_shift[foot] = max(
                lock.max_knee_shift.get(foot, 0.0), v_dist(knee, k0)
            )
        lock.per_foot_frames[foot] = lock.per_foot_frames.get(foot, 0) + frames_locked
        lock.per_foot_intervals[foot] = lock.per_foot_intervals.get(foot, 0) + 1

    locked_frames = [
        replace(af, pose=replace(af.pose, positions=changed[af.frame]))
        if af.frame in changed
        else af
        for af in frames
    ]
    lock.slide_after = foot_slide(locked_frames, report)

    notes = list(action.notes)
    total_frames = sum(lock.per_foot_frames.values())
    notes.append(
        f"foot lock: pinned {total_frames} in-contact frame(s) across "
        f"{len(report.intervals)} interval(s); slide "
        f"{lock.slide_before.total:.4f}u -> {lock.slide_after.total:.4f}u "
        "(walk-in-place by design; root motion stays unimplemented — D-008)"
    )
    for foot in sorted(lock.per_foot_frames):
        notes.append(
            f"foot lock {foot}: {lock.per_foot_frames[foot]} frame(s) in "
            f"{lock.per_foot_intervals[foot]} interval(s); max knee correction "
            f"{lock.max_knee_shift.get(foot, 0.0):.4f}u; max ankle shift "
            f"{lock.max_ankle_shift.get(foot, 0.0):.4f}u; "
            f"{lock.clamped.get(foot, 0)} unreachable clamp(s)"
        )
    if to_ground:
        notes.append("foot lock: ankle z projected onto the ground estimate (to_ground)")
    notes.extend(lock_notes)
    if action.contacts is not None and action.contacts is not report:
        notes.append("foot lock: action carried a different ContactReport — the passed one was used")

    return (
        replace(action, frames=locked_frames, notes=notes),
        lock,
    )
