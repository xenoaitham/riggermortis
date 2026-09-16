"""Canonical actions (P2-3): ordered per-frame poses sampled from a video job.

The video job (P2-1) writes one contract payload per planned frame. This
module turns a job directory into a *canonical action* — an ordered list of
``(source frame index, CanonicalPose)`` pairs, the rig-free animation
representation every consumer (add-on bake, foot contacts, export) reads.
Payloads are parsed exclusively through :mod:`riggermortis.payload` (D-009:
one contract implementation); failed frames are carried in ``failed`` and
never silently interpolated — a gap in the source stays a gap in the action.

Timing: the canonical solve is single-view and hip-anchored, so an action
carries **no world translation** — frame indices are source frames and the
bake maps them onto Blender frame numbers (source index + offset). Playing
the baked action at the source video's frame rate reproduces the timing;
there is deliberately no root-motion bake (D-008: positions are anchored per
frame, any root translation would be fabricated).

Bake-time conditioning (optional, documented parameters, NO solve-prior
tuning per D-008), applied in this order:
- hip stabilization (P2-6, ``stabilize_hips``): re-anchor every frame to a
  damped hip frame;
- 1€ smoothing per canonical channel (P2-2's ``smooth_pose_frames``);
- keyframe reduction (P2-2's ``reduce_keyframes``) with ``tolerance`` defined
  as joint-position error in canonical units — positions are the input of
  every baked rotation, so this is the honest proxy for rotation error.

Hip stabilization scope (P2-6, honest): the solve anchors the hips at the
origin EVERY frame, so no absolute hip translation survives into the action.
What survives is the hip *frame* wobbling around the body: the per-frame
pixels-per-unit scale (bob + detector noise modulate the torso span, which
rescales every coordinate — the "breathing" artifact) and, when anchoring
fell back to the neck, the anchor translation itself. ``stabilize_hips``
low-passes those two tracks (centered moving average) and damps their
high-frequency residual by ``strength``, applying each frame's correction as
a RIGID transform of the whole pose. Rigid per-frame transforms are
FK-identical within the frame, so this re-anchoring changes no pose geometry;
its effect is exactly on the inter-frame tracks the rest of the pipeline
reads — contact detection, the foot-lock cost, and the slide metric. No
translation is fabricated (D-008): the result stays walk-in-place, and the
report publishes what moved.

Pure stdlib; same input = same output (deterministic, keyed sorts).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from .canonical_pose import CanonicalPose
from .errors import RiggermortisError
from .payload import entry_for_label, pose_for_figure
from .smoothing import moving_average, reduce_keyframes, smooth_pose_frames
from .video import STATE_NAME, load_state

if TYPE_CHECKING:  # runtime import lives in contacts.py (one direction only)
    from .contacts import ContactReport  # noqa: F401


@dataclass
class ActionFrame:
    """One kept frame: source frame index plus its solved canonical pose."""

    frame: int  # source frame index from the video job plan (0-based)
    pose: CanonicalPose


@dataclass
class CanonicalAction:
    """Rig-free animation: ordered frames + honest failure ledger."""

    frames: list[ActionFrame] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    rig_fingerprint: str | None = None
    contacts: ContactReport | None = None  # attached by contacts.attach_contacts

    @property
    def frame_indices(self) -> list[int]:
        return [af.frame for af in self.frames]

    def summary(self) -> str:
        return (
            f"canonical action: {len(self.frames)} frame(s), "
            f"{len(self.failed)} failed frame(s) carried"
        )


def action_from_poses(
    pairs: list[tuple[int, CanonicalPose]],
    *,
    notes: list[str] | None = None,
    rig_fingerprint: str | None = None,
) -> CanonicalAction:
    """Build an action from ``(source frame index, pose)`` pairs (sorted)."""
    ordered = sorted(pairs, key=lambda p: p[0])
    return CanonicalAction(
        frames=[ActionFrame(frame=i, pose=p) for i, p in ordered],
        failed=[],
        notes=list(notes or []),
        rig_fingerprint=rig_fingerprint,
    )


def load_action(job_dir: Path, figure: str | None = None) -> CanonicalAction:
    """Sample a video job's payloads into a canonical action.

    ``figure``: label of the figure to sample (payload v2 may carry several
    when written with ``--all-figures``); None = each payload's selected
    figure. Raises an actionable error when the job state is missing — the
    plan (and therefore the failure ledger) lives in ``job.json``.
    """
    job_dir = Path(job_dir)
    state = load_state(job_dir)
    if state is None:
        raise RiggermortisError(
            f"no video job state in {job_dir}",
            hint=f"run the job first: rigpose pose-video <frames_dir> <rig.json> "
                 f"--out {job_dir} (state file: {STATE_NAME})",
        )
    planned = len(state.get("frames", []))
    done: dict[int, str] = {int(k): str(v) for k, v in state.get("done", {}).items()}
    failed = [i for i in range(planned) if i not in done]

    notes: list[str] = [str(n) for n in state.get("notes", [])]
    fingerprint: str | None = None
    frames: list[ActionFrame] = []
    for index in sorted(done):
        rel = done[index]
        path = job_dir / rel
        if not path.exists():
            notes.append(f"frame {index}: state lists {rel} but the file is gone")
            failed.append(index)
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if fingerprint is None:
            rig = payload.get("rig")
            if isinstance(rig, dict):
                fingerprint = rig.get("fingerprint")
        try:
            entry_for_label(payload, figure)  # resolves + validates the label
            pose = CanonicalPose.from_dict(pose_for_figure(payload, figure))
        except RiggermortisError as exc:
            notes.append(f"frame {index}: unreadable payload ({exc})")
            failed.append(index)
            continue
        frames.append(ActionFrame(frame=index, pose=pose))

    if failed:
        notes.append(
            f"{len(failed)} frame(s) failed and are NOT in the action: "
            f"{failed[:10]}{' …' if len(failed) > 10 else ''}"
        )
    frames.sort(key=lambda af: af.frame)
    return CanonicalAction(
        frames=frames,
        failed=sorted(set(failed)),
        notes=notes,
        rig_fingerprint=fingerprint,
    )


# -- hip stabilization (P2-6) ---------------------------------------------------

#: Defaults are order-of-magnitude choices on the canonical scale, documented
#: here and NOT fitted to any fixture (D-008 discipline): window 9 observed
#: frames (~0.3 s at 30 fps) sits above the walk-band frequencies (<2 Hz) and
#: below nothing we track — it separates frame-to-frame anchor/scale noise
#: from real weight shifts; strength 0.7 damps most of the residual sway while
#: keeping some anchor responsiveness.
STABILIZE_WINDOW = 9
STABILIZE_STRENGTH = 0.7

#: A correction smaller than this keeps the original values, so stabilizing
#: an already-clean action is a bit-for-bit no-op (no float noise keyed).
_STAB_SNAP = 1e-12


@dataclass
class HipStabReport:
    """What hip stabilization did, measured honestly.

    ``*_sway_before``/``*_sway_after`` are RMS residuals of the anchor
    translation (canonical units) and relative scale tracks against their own
    low-pass — the high-frequency energy the pass targets. ``max_move`` is the
    largest rigid correction applied to any frame (canonical units): a
    stabilization that reports zero moved nothing.
    """

    window: int = 0
    strength: float = 0.0
    anchor_role: str | None = None
    frames_stabilized: int = 0
    frames_untouched: int = 0
    translation_sway_before: float | None = None
    translation_sway_after: float | None = None
    scale_sway_before: float | None = None
    scale_sway_after: float | None = None
    max_move: float = 0.0
    notes: list[str] = field(default_factory=list)


def _rms(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(v * v for v in values) / len(values))


def stabilize_hips(
    action: CanonicalAction,
    *,
    strength: float = STABILIZE_STRENGTH,
    window: int = STABILIZE_WINDOW,
) -> tuple[CanonicalAction, HipStabReport]:
    """Re-anchor every frame to a damped hip frame (P2-6, see module docstring).

    Two tracks are low-passed with a centered moving average (``window``
    observed frames) and their high-frequency residual damped by ``strength``
    (0 = no-op, 1 = follow the low-pass exactly):

    - the anchor translation track (``hips`` when every frame carries it, else
      ``neck``); each frame's correction is applied rigidly to ALL roles;
    - the per-frame scale track (``pose.scale``): positions are rescaled by
      ``s / s_target`` with ``s_target = s + strength * (lowpass - s)`` and the
      pose's scale updated to match, so provenance stays consistent.

    Frames missing the anchor role or a usable scale are left untouched and
    counted (ambiguity reported, never swallowed); failed frames are not
    interpolated — the tracks run over observed frames only. The input action
    is never mutated. Returns ``(stabilized_action, HipStabReport)``.
    """
    if not 0.0 <= strength <= 1.0:
        raise ValueError(
            f"strength must be within [0, 1], got {strength} "
            "(0 = off, 1 = follow the low-pass exactly)"
        )
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")

    frames = list(action.frames)
    report = HipStabReport(window=window, strength=strength)
    if not frames:
        report.notes.append("hip stabilization: empty action — nothing to stabilize")
        return replace(action, notes=list(action.notes)), report

    # -- track collection over observed frames only -----------------------------
    for role in ("hips", "neck"):
        if all(role in af.pose.positions for af in frames):
            report.anchor_role = role
            break
    if report.anchor_role is None:
        report.notes.append(
            "hip stabilization: no anchor role observed on every frame "
            "(hips/neck) — translation track skipped"
        )

    anchor_obs: list[tuple[int, tuple[float, float, float]]] = []
    if report.anchor_role is not None:
        anchor_obs = [
            (af.frame, tuple(af.pose.positions[report.anchor_role]))
            for af in frames
        ]
    scale_obs: list[tuple[int, float]] = [
        (af.frame, af.pose.scale) for af in frames if af.pose.scale > 0.0
    ]
    if len(scale_obs) < len(frames):
        report.notes.append(
            f"hip stabilization: {len(frames) - len(scale_obs)} frame(s) carry "
            "no usable scale — their scale correction skipped"
        )

    deltas: dict[int, tuple[float, float, float]] = {}
    if len(anchor_obs) >= 2:
        xs = moving_average([p[0] for _f, p in anchor_obs], window)
        ys = moving_average([p[1] for _f, p in anchor_obs], window)
        zs = moving_average([p[2] for _f, p in anchor_obs], window)
        before: list[float] = []
        after: list[float] = []
        for (f, pos), lx, ly, lz in zip(anchor_obs, xs, ys, zs, strict=True):
            sway = (pos[0] - lx, pos[1] - ly, pos[2] - lz)
            sway_len = math.sqrt(sway[0] ** 2 + sway[1] ** 2 + sway[2] ** 2)
            before.append(sway_len)
            after.append(sway_len * (1.0 - strength))
            d = (-strength * sway[0], -strength * sway[1], -strength * sway[2])
            if max(abs(d[0]), abs(d[1]), abs(d[2])) > _STAB_SNAP:
                deltas[f] = d
        report.translation_sway_before = _rms(before)
        report.translation_sway_after = _rms(after)
    elif report.anchor_role is not None:
        report.notes.append(
            "hip stabilization: fewer than 2 anchor observations — "
            "translation track skipped"
        )

    factors: dict[int, float] = {}
    scales_before: list[float] = []
    scales_after: list[float] = []
    if len(scale_obs) >= 2:
        lp = moving_average([s for _f, s in scale_obs], window)
        for (f, s), low in zip(scale_obs, lp, strict=True):
            residual = (s - low) / low if abs(low) > 1e-12 else 0.0
            scales_before.append(abs(residual))
            s_target = s + strength * (low - s)
            if s_target <= 0.0 or abs(s_target - s) <= _STAB_SNAP:
                continue
            factors[f] = s / s_target
            scales_after.append(abs((s_target - low) / low))
        if scales_before:
            report.scale_sway_before = _rms(scales_before)
            report.scale_sway_after = _rms(scales_after)
    elif scale_obs:
        report.notes.append(
            "hip stabilization: fewer than 2 scale observations — "
            "scale track skipped"
        )

    if not deltas and not factors:
        report.frames_untouched = len(frames)
        report.notes.append(
            "hip stabilization: tracks already smooth (or disabled) — "
            "action untouched"
        )
        return replace(action, notes=[*action.notes, *report.notes]), report

    stabilized_frames: list[ActionFrame] = []
    for af in frames:
        f = af.frame
        d = deltas.get(f, (0.0, 0.0, 0.0))
        factor = factors.get(f, 1.0)
        if d == (0.0, 0.0, 0.0) and factor == 1.0:
            stabilized_frames.append(af)
            continue
        positions = {
            role: (p[0] * factor + d[0], p[1] * factor + d[1], p[2] * factor + d[2])
            for role, p in sorted(af.pose.positions.items())
        }
        stabilized_frames.append(
            replace(
                af,
                pose=replace(
                    af.pose,
                    positions=positions,
                    scale=af.pose.scale / factor if factor != 1.0 else af.pose.scale,
                ),
            )
        )
        report.frames_stabilized += 1
        move = max(
            (math.dist(positions[r], af.pose.positions[r]) for r in positions),
            default=0.0,
        )
        report.max_move = max(report.max_move, move)

    report.frames_untouched = len(frames) - report.frames_stabilized
    notes = list(action.notes)
    notes.append(
        f"hip stabilization: re-anchored {report.frames_stabilized}/{len(frames)} "
        f"frame(s) to the damped hip frame (window={window} observed frames, "
        f"strength={strength}, anchor={report.anchor_role or 'none'}) — "
        f"max rigid correction {report.max_move:.4f}u; D-008: no translation "
        "fabricated, the result stays walk-in-place"
    )
    notes.extend(report.notes)
    return (
        replace(action, frames=stabilized_frames, notes=notes),
        report,
    )


def condition_action(
    action: CanonicalAction,
    *,
    hip_stabilize: float | None = None,
    min_cutoff: float | None = 1.0,
    beta: float = 0.0,
    tolerance: float | None = None,
    freq: float = 30.0,
    stabilize_window: int = STABILIZE_WINDOW,
) -> CanonicalAction:
    """Return a conditioned copy in the documented cleanup order (P2-6):

    1. hip stabilization (``hip_stabilize`` = strength, None disables; see
       :func:`stabilize_hips`),
    2. 1€ smoothing (``min_cutoff``, None disables; Casiez 2012 defaults here:
       min_cutoff=1.0, beta=0.0 — gentle jitter death, fast motion untouched),
    3. keyframe reduction (``tolerance``, None disables): canonical-unit
       joint-position error; endpoints always kept.

    Smoothing and reduction treat surviving frames as consecutive
    observations — a gap from a failed frame is NOT interpolated, it just
    shortens the series. The input action is never mutated; conditioning
    notes are appended to the copy so provenance travels with it.
    """
    if not action.frames:
        return replace(action, notes=list(action.notes))

    if hip_stabilize is not None:
        action, _report = stabilize_hips(
            action, strength=hip_stabilize, window=stabilize_window
        )

    frames = list(action.frames)
    notes = list(action.notes)

    if min_cutoff is not None:
        smoothed = smooth_pose_frames(
            [af.pose.positions for af in frames],
            freq=freq, min_cutoff=min_cutoff, beta=beta,
        )
        frames = [
            replace(af, pose=replace(af.pose, positions=positions))
            for af, positions in zip(frames, smoothed, strict=True)
        ]
        notes.append(
            f"conditioned: 1€ smoothing (min_cutoff={min_cutoff}, beta={beta}) — "
            "gap frames were not interpolated"
        )

    if tolerance is not None:
        kept = set(reduce_keyframes([af.pose.positions for af in frames], tolerance))
        before = len(frames)
        frames = [af for i, af in enumerate(frames) if i in kept]
        notes.append(
            f"conditioned: keyframe reduction (tolerance={tolerance} canonical "
            f"units) — kept {len(frames)}/{before} frames"
        )

    return CanonicalAction(
        frames=frames,
        failed=list(action.failed),
        notes=notes,
        rig_fingerprint=action.rig_fingerprint,
        contacts=action.contacts,
    )
