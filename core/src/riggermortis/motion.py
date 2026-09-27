"""Motion library conversion (P6-2): imported clips -> canonical actions.

An imported clip (Mixamo glTF/FBX, BVH, DCC FBX) is measured, not solved:
the Blender-side sampler (shell glue, D-009 — the probe's recipe,
``docs/MOTION_LIBRARY.md``) reads each frame's evaluated canonical-role
joint positions off the imported armature and writes a clip-sample JSON.
This module turns that file into the same :class:`CanonicalAction` the
video pipeline produces, so the certified downstream (condition → contact
detect → foot lock → bake) runs UNCHANGED — mocap foot-slide cleaning for
free, the composition never learns the action came from a clip.

Conversion rules (each pinned by a test, see the design page):

- positions are HIPS-ANCHORED and scaled by the source REST torso span
  (``scale_ref``, one constant — a rig is rigid, unlike the per-frame
  pixels-per-unit the detector path must cope with);
- flips are MEASURED flexion signs, not enumerated guesses — a 3D pose has
  no flip ambiguity (they are review metadata only: the FK apply derives
  rotations from positions);
- confidence is 1.0 with a provenance note: measured 3D, no detection
  uncertainty — distinguishable from solved poses, which never claim 1.0;
- root translation is dropped (walk-in-place, D-008 — same boundary as the
  video path), and the frame indices are the clip's own. P8-7 amendment:
  when the sampler carried the per-frame world hips track (format 2's
  additive ``hips_track`` field), the converter attaches the MEASURED
  :class:`~riggermortis.root_motion.DriftTrack` to the action — the root
  information is rescued at the source instead of reconstructed; the
  positions themselves stay hips-anchored exactly as before.

Pure stdlib; same input = same output (deterministic, keyed sorts).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .action import CanonicalAction, action_from_poses
from .canonical import ALL_ROLES
from .canonical_pose import TORSO_SPAN, CanonicalPose
from .errors import MotionError
from .root_motion import DriftTrack, track_from_clip_field

#: distal role -> its child role: the measured-flip pairs (a distal segment
#: whose child sits forward of the joint is flexed forward, -1; else +1).
_FLIP_PAIRS: tuple[tuple[str, str], ...] = (
    ("forearm.L", "hand.L"),
    ("forearm.R", "hand.R"),
    ("lower_leg.L", "foot.L"),
    ("lower_leg.R", "foot.R"),
)

_PROVENANCE = "measured from 3D clip (P6-2), not solved from 2D"


def _vec3(raw: object, where: str) -> tuple[float, float, float]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise MotionError(
            f"{where}: expected [x, y, z], got {raw!r}",
            hint="clip-sample positions are 3-number arrays in source meters",
        )
    out = []
    for comp in raw:
        v = float(comp)  # type: ignore[arg-type]
        if not math.isfinite(v):
            raise MotionError(
                f"{where}: non-finite coordinate {v!r}",
                hint="clip samplers must refuse NaN/inf at the source",
            )
        out.append(v)
    return (out[0], out[1], out[2])


@dataclass(frozen=True)
class ClipFrame:
    """One sampled frame: source frame index + role-keyed joint positions
    (source meters, armature space)."""

    frame: int
    positions: dict[str, tuple[float, float, float]]


@dataclass(frozen=True)
class MotionClip:
    """A sampled imported clip: the converter's input contract.

    Formats 1+2 read (the preset-schema pattern): format 1 is the P6-2
    shape, byte-stable; format 2 adds the REQUIRED ``hips_track`` object
    (the P8-7 root-motion carrier — ``{"ref_frame": int, "samples":
    [[frame, x, y, z], ...]}`` in source meters). ``hips_track`` is empty
    when absent (format 1)."""

    fps: float
    scale_ref: float  # source-meter hips->mid-shoulders span of the REST pose
    frames: tuple[ClipFrame, ...]
    source: str = "blender-import"
    source_fingerprint: str | None = None
    notes: tuple[str, ...] = ()
    hips_track: tuple[tuple[int, float, float, float], ...] = ()

    @staticmethod
    def from_dict(d: dict[str, Any]) -> MotionClip:
        """Validate loudly: unknown fields refuse, every refusal carries a
        usable hint. Roles must be canonical (frozen API) — a typo'd role is
        a sampler bug and refuses, while a role the clip's skeleton LACKS
        simply never appears (ledgered later, never an error)."""
        if not isinstance(d, dict):
            raise MotionError(
                f"clip sample must be a JSON object, got {type(d).__name__}",
                hint='the sampler writes {"format": 1, ...}; see docs/MOTION_LIBRARY.md',
            )
        known = {
            "format", "fps", "scale_ref", "frames", "source",
            "source_fingerprint", "notes", "hips_track",
        }
        unknown = sorted(set(d) - known)
        if unknown:
            raise MotionError(
                f"unknown clip-sample field(s): {unknown}",
                hint=f"formats 1+2 fields are exactly {sorted(known)}; "
                     "hips_track requires format 2",
            )
        if d.get("format") not in (1, 2):
            raise MotionError(
                f"unsupported clip-sample format {d.get('format')!r}",
                hint="this build reads formats 1 and 2 "
                     "(2 = format 1 + the hips_track root-motion carrier)",
            )
        fmt = d["format"]
        hips_track_field = d.get("hips_track")
        if fmt == 2 and hips_track_field is None:
            raise MotionError(
                "format 2 requires the hips_track field",
                hint="format 2 = format 1 + {\"ref_frame\": int, "
                     "\"samples\": [[f, x, y, z], ...]} (source meters)",
            )
        if fmt == 1 and hips_track_field is not None:
            raise MotionError(
                "a format-1 clip sample cannot carry hips_track",
                hint='write "format": 2 when the sampler runs with '
                     "--root-track (the P8-7 root-motion carrier)",
            )
        try:
            fps = float(d["fps"])  # type: ignore[arg-type]
            scale_ref = float(d["scale_ref"])  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError) as exc:
            raise MotionError(
                f"fps and scale_ref are required positive numbers ({exc})",
                hint="scale_ref = the source rest torso span in meters (the probe prints it)",
            ) from None
        if not (math.isfinite(fps) and fps > 0.0):
            raise MotionError(
                f"fps must be finite and > 0, got {fps!r}", hint="the clip's own frame rate"
            )
        if not (math.isfinite(scale_ref) and scale_ref > 0.0):
            raise MotionError(
                f"scale_ref must be finite and > 0, got {scale_ref!r}",
                hint="a non-positive torso span cannot normalize positions",
            )
        raw_frames = d.get("frames")
        if not isinstance(raw_frames, list) or not raw_frames:
            raise MotionError(
                "frames must be a non-empty list",
                hint="an empty clip converts to nothing — refuse at the source",
            )
        frames: list[ClipFrame] = []
        last: int | None = None
        for i, raw in enumerate(raw_frames):
            if not isinstance(raw, dict) or set(raw) != {"frame", "positions"}:
                raise MotionError(
                    f"frames[{i}]: expected exactly {{frame, positions}}, got {sorted(raw) if isinstance(raw, dict) else type(raw).__name__}",
                    hint="frame entries carry the index and its role-keyed positions",
                )
            f = raw["frame"]
            if not isinstance(f, int) or isinstance(f, bool):
                raise MotionError(
                    f"frames[{i}].frame must be an integer, got {f!r}",
                    hint="frame indices are the clip's own, 1:1 (no interpolation)",
                )
            if last is not None and f <= last:
                raise MotionError(
                    f"frames not strictly increasing at index {i} ({f} <= {last})",
                    hint="sort the sampler's output; the converter refuses to reorder",
                )
            last = f
            raw_pos = raw["positions"]
            if not isinstance(raw_pos, dict) or not raw_pos:
                raise MotionError(
                    f"frames[{i}].positions must be a non-empty object",
                    hint="a frame with no observed roles cannot produce a pose",
                )
            positions: dict[str, tuple[float, float, float]] = {}
            for role in sorted(raw_pos):
                if role not in ALL_ROLES:
                    raise MotionError(
                        f"frames[{i}]: unknown role {role!r}",
                        hint="roles are the frozen canonical API; the sampler maps "
                             "bone names -> roles via the rig's mapping, so an "
                             "unknown role is a sampler bug",
                    )
                positions[role] = _vec3(raw_pos[role], f"frames[{i}].positions.{role}")
            frames.append(ClipFrame(frame=f, positions=positions))
        source = d.get("source", "blender-import")
        fingerprint = d.get("source_fingerprint")
        notes = d.get("notes", [])
        if not isinstance(source, str):
            raise MotionError(
                "source must be a string label", hint="provenance only, e.g. 'blender-import'"
            )
        if fingerprint is not None and not isinstance(fingerprint, str):
            raise MotionError(
                "source_fingerprint must be a string or null",
                hint="the sampled source rig's fingerprint, when the sampler extracted one",
            )
        if not isinstance(notes, list) or not all(isinstance(n, str) for n in notes):
            raise MotionError(
                "notes must be a list of strings", hint="free-form provenance lines"
            )
        track: tuple[tuple[int, float, float, float], ...] = ()
        if fmt == 2:
            track = _parse_hips_track(hips_track_field)
        return MotionClip(
            fps=fps,
            scale_ref=scale_ref,
            frames=tuple(frames),
            source=source,
            source_fingerprint=fingerprint,
            notes=tuple(notes),
            hips_track=track,
        )

    @staticmethod
    def load(path: Path) -> MotionClip:
        """Read a clip-sample JSON file (the sampler's output)."""
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise MotionError(
                f"cannot read clip sample {path}: {exc}",
                hint="the sampler (shell glue) writes the file first",
            ) from None
        try:
            d = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MotionError(
                f"clip sample {path} is not valid JSON: {exc}",
                hint="re-run the sampler; the file may be torn",
            ) from None
        return MotionClip.from_dict(d)

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            "format": 2 if self.hips_track else 1,
            "fps": self.fps,
            "scale_ref": self.scale_ref,
            "frames": [
                {
                    "frame": cf.frame,
                    "positions": {r: list(p) for r, p in sorted(cf.positions.items())},
                }
                for cf in self.frames
            ],
            "source": self.source,
            "source_fingerprint": self.source_fingerprint,
            "notes": list(self.notes),
        }
        if self.hips_track:
            frames_ = self.hips_track
            d["hips_track"] = {
                "ref_frame": frames_[0][0],
                "samples": [list(s) for s in frames_],
            }
        return d


def _parse_hips_track(raw: object) -> tuple[tuple[int, float, float, float], ...]:
    """Format-2 ``hips_track`` shape validation (the semantic checks —
    strictly increasing frames, the reference rule — live in
    ``root_motion.track_from_clip_field``, which consumes the parsed
    value at conversion time and refuses there, loudly)."""
    if not isinstance(raw, dict) or set(raw) != {"ref_frame", "samples"}:
        raise MotionError(
            "hips_track must carry exactly {ref_frame, samples}",
            hint='format 2: {"ref_frame": int, "samples": [[f, x, y, z], ...]}',
        )
    if not isinstance(raw["ref_frame"], int) or isinstance(raw["ref_frame"], bool):
        raise MotionError(
            "hips_track.ref_frame must be an integer",
            hint="the reference frame's entry is the zero vector",
        )
    samples = raw["samples"]
    if not isinstance(samples, list) or not samples:
        raise MotionError(
            "hips_track.samples must be a non-empty list",
            hint="a track with no observations measures nothing — omit it",
        )
    out: list[tuple[int, float, float, float]] = []
    for i, entry in enumerate(samples):
        if not isinstance(entry, (list, tuple)) or len(entry) != 4:
            raise MotionError(
                f"hips_track.samples[{i}]: expected [frame, x, y, z]",
                hint="each sample carries the frame index and the hips "
                     "position in source meters",
            )
        f, x, y, z = entry
        if not isinstance(f, int) or isinstance(f, bool):
            raise MotionError(
                f"hips_track.samples[{i}].frame must be an integer, got {f!r}",
                hint="frame indices are exact — the track never interpolates",
            )
        pos = _vec3([x, y, z], f"hips_track.samples[{i}]")
        out.append((f, pos[0], pos[1], pos[2]))
    return tuple(out)


def pose_from_sample(
    positions: dict[str, tuple[float, float, float]], scale_ref: float
) -> CanonicalPose:
    """One sampled frame -> a canonical pose (hips-anchored, span-scaled).

    Flips are measured flexion signs for the distal pairs whose BOTH
    endpoints are present; roles the clip lacks are simply absent (the
    ledger lives on the action). Confidence is 1.0 with the provenance
    note — measured 3D, no detection uncertainty.
    """
    if "hips" not in positions:
        raise MotionError(
            "frame has no hips position",
            hint="hips is the anchor every canonical pose needs; a clip whose "
                 "skeleton cannot map hips must refuse at the sampler",
        )
    scale = TORSO_SPAN / scale_ref  # canonical units per source meter
    canon = {
        role: (
            (p[0] - positions["hips"][0]) * scale,
            (p[1] - positions["hips"][1]) * scale,
            (p[2] - positions["hips"][2]) * scale,
        )
        for role, p in positions.items()
    }
    flips: dict[str, int] = {}
    for distal, child in _FLIP_PAIRS:
        if distal in positions and child in positions:
            dy = positions[child][1] - positions[distal][1]
            flips[distal] = -1 if dy < 0.0 else 1
    return CanonicalPose(
        positions=canon,
        flips=flips,
        confidence=1.0,
        reliable=True,
        scale=scale_ref / TORSO_SPAN,
        anchor="hips",
        notes=[_PROVENANCE],
        joint_confidence={role: 1.0 for role in sorted(positions)},
    )


def action_from_clip(clip: MotionClip) -> CanonicalAction:
    """Sampled clip -> canonical action through the P2-3 constructor.

    Carries a missing-role ledger (roles the clip's skeleton never
    observed, listed once against the canonical set) and the clip's own
    provenance in notes. Never mutates the clip. When the clip carries
    the P8-7 ``hips_track`` (format 2), the MEASURED drift track rides
    the action (``root_track``) — the positions stay hips-anchored
    exactly as before; the track is data, not a behavior change.
    """
    seen: set[str] = set()
    for cf in clip.frames:
        seen.update(cf.positions)
    missing = sorted(set(ALL_ROLES) - seen)
    pairs = [(cf.frame, pose_from_sample(cf.positions, clip.scale_ref)) for cf in clip.frames]
    notes = [
        f"motion clip: source={clip.source} fps={clip.fps:g} "
        f"scale_ref={clip.scale_ref:g} frames={len(clip.frames)}",
        _PROVENANCE,
        *clip.notes,
    ]
    if missing:
        notes.append(
            f"{len(missing)} canonical role(s) absent from the clip's skeleton: "
            f"{missing} (skipped honestly, never guessed)"
        )
    root_track: DriftTrack | None = None
    if clip.hips_track:
        root_track = track_from_clip_field(
            {
                "ref_frame": clip.hips_track[0][0],
                "samples": [list(s) for s in clip.hips_track],
            },
            clip.scale_ref,
        )
        notes.append(
            "root track attached (P8-7): MEASURED per-frame hips drift from "
            f"the sampler's world heads — path "
            f"{root_track.path_length():.4f}u, span {root_track.span():.4f}u; "
            "the positions stay hips-anchored (walk-in-place data; the "
            "root-motion-aware contact pass consumes the track explicitly)"
        )
    return action_from_poses(
        pairs,
        notes=notes,
        rig_fingerprint=clip.source_fingerprint,
        root_track=root_track,
    )
