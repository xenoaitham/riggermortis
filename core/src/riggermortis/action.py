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
tuning per D-008):
- 1€ smoothing per canonical channel (P2-2's ``smooth_pose_frames``);
- keyframe reduction (P2-2's ``reduce_keyframes``) with ``tolerance`` defined
  as joint-position error in canonical units — positions are the input of
  every baked rotation, so this is the honest proxy for rotation error.

Pure stdlib; same input = same output (deterministic, keyed sorts).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from .canonical_pose import CanonicalPose
from .errors import RiggermortisError
from .payload import entry_for_label, pose_for_figure
from .smoothing import reduce_keyframes, smooth_pose_frames
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


def condition_action(
    action: CanonicalAction,
    *,
    min_cutoff: float | None = 1.0,
    beta: float = 0.0,
    tolerance: float | None = None,
    freq: float = 30.0,
) -> CanonicalAction:
    """Return a conditioned copy: optional 1€ smoothing + keyframe reduction.

    ``min_cutoff`` (None disables smoothing): 1€ low-pass per canonical
    channel (Casiez 2012 defaults here: min_cutoff=1.0, beta=0.0 — gentle
    jitter death, fast motion untouched). ``tolerance`` (None disables
    reduction): canonical-unit joint-position error; endpoints always kept.
    Smoothing treats surviving frames as consecutive observations — a gap
    from a failed frame is NOT interpolated, it just shortens the series.

    The input action is never mutated; conditioning notes are appended to the
    copy so provenance travels with it.
    """
    if not action.frames:
        return replace(action, notes=list(action.notes))
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
