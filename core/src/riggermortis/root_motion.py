"""Root motion (P8-7): the measured hips drift track + the root-motion-aware
contact pass.

Design of record: ``docs/ROOT_MOTION.md`` (written BEFORE this module —
the SPINE.md sibling pattern). The S24 treadmill finding is the
motivation: a clip or video whose subject translates turns hips-anchored
canonical actions into treadmills — planted feet glide at the subject's
speed, the (untuned) contact detector honestly finds no plants, and the
certified foot lock degrades to a verified no-op. The remedy is NOT a
threshold change (D-008: never tune to force plants) — it is rescuing
the subject translation that anchoring destroys, MEASURED at the source,
and running contact classification in the frame where "stationary" is
the true statement.

Three pieces, all additive:

- :class:`DriftTrack` — per-frame canonical-space hips translation
  (referenced to the first observed frame), from the clip sampler's
  world hips heads (``track_from_clip_field``, 3D, measured) or the video
  payload stream's bbox drift (``track_from_payload_stream``,
  in-plane only, LABELED approximate — depth is unobservable and stays
  exactly zero, never guessed). The track rides
  :class:`~riggermortis.action.CanonicalAction` as the additive
  ``root_track`` field — NO payload format change; consumers that ignore
  it are byte-identical.
- :func:`compensate_frames` / :func:`decompensate_frames` — the rigid
  per-frame bracket (FK-identical within the frame, the P2-6 stabilize
  precedent). A zero delta reuses the ORIGINAL position tuples, so a
  zero track compensates to the byte-identical input.
- :func:`detect_contacts_root_aware` / :func:`lock_feet_root_aware` —
  the certified contact stages run UNTOUCHED on the compensated frames;
  the lock's pins land in the compensated (world) frame, so a locked
  action plus its track reconstruct to stationary planted ankles. With
  a zero track both functions reduce to the in-place path byte-
  identically (pinned by test, not asserted).

Pure stdlib; same input = same output (deterministic; no randomness, no
data-dependent iteration).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from .action import ActionFrame, CanonicalAction
from .canonical_pose import TORSO_SPAN
from .contacts import (
    LOCK_NOTE_SUFFIX,
    ContactReport,
    LockReport,
    detect_contacts,
    lock_feet,
)
from .errors import RootMotionError

#: Source labels (frozen vocabulary — provenance travels with the track).
SOURCE_CLIP = "clip-measured-3d"
SOURCE_VIDEO = "video-approximate-in-plane"

_ZERO = (0.0, 0.0, 0.0)


def _vec3(raw: object, where: str) -> tuple[float, float, float]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise RootMotionError(
            f"{where}: expected [x, y, z], got {raw!r}",
            hint="track entries are 3-number arrays in canonical units",
        )
    out = []
    for comp in raw:
        try:
            v = float(comp)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise RootMotionError(
                f"{where}: non-numeric component {comp!r}",
                hint="track entries carry numbers only",
            ) from None
        if not math.isfinite(v):
            raise RootMotionError(
                f"{where}: non-finite component {v!r}",
                hint="track producers must refuse NaN/inf at the source",
            )
        out.append(v)
    return (out[0], out[1], out[2])


@dataclass(frozen=True)
class DriftTrack:
    """Per-frame canonical-space hips translation (canonical units, Z up).

    ``translations`` maps EXACT source frame indices to the subject's hips
    displacement from the reference frame — ``at()`` answers observed
    frames only and ``None`` elsewhere: gaps stay gaps, never interpolated
    (the honesty law; unknown state is never smoothed over). The
    reference frame's entry is exactly ``(0.0, 0.0, 0.0)``. Build through
    :meth:`from_samples` — the constructor validates loudly."""

    source: str
    ref_frame: int
    translations: dict[int, tuple[float, float, float]] = field(
        default_factory=dict
    )
    notes: tuple[str, ...] = ()

    @staticmethod
    def from_samples(
        samples: dict[int, tuple[float, float, float]],
        *,
        source: str,
        notes: tuple[str, ...] = (),
    ) -> DriftTrack:
        """Validate + reference: the minimum frame becomes the zero vector.

        Refuses empty input, non-integer frame keys, and non-finite
        values. ``source`` must be one of the declared labels (provenance
        is contract, not decoration)."""
        if source not in (SOURCE_CLIP, SOURCE_VIDEO):
            raise RootMotionError(
                f"unknown drift-track source {source!r}",
                hint=f"declared sources: {SOURCE_CLIP}, {SOURCE_VIDEO}",
            )
        if not samples:
            raise RootMotionError(
                "a drift track needs at least one observed frame",
                hint="an empty stream has no drift to measure — do not "
                     "attach a track",
            )
        clean: dict[int, tuple[float, float, float]] = {}
        for f, v in samples.items():
            if not isinstance(f, int) or isinstance(f, bool):
                raise RootMotionError(
                    f"drift-track frame key {f!r} is not an integer",
                    hint="keys are source frame indices, exact",
                )
            clean[f] = _vec3(v, f"track[{f}]")
        ref = min(clean)
        clean[ref] = _ZERO
        return DriftTrack(
            source=source, ref_frame=ref, translations=clean, notes=notes
        )

    def at(self, frame: int) -> tuple[float, float, float] | None:
        """The track entry for EXACTLY ``frame`` (None when unobserved)."""
        return self.translations.get(frame)

    def frames(self) -> list[int]:
        """Observed frames, sorted."""
        return sorted(self.translations)

    def path_length(self) -> float:
        """Total traveled hips distance (canonical units) across the
        observed frames in order — zero for a no-drift stream."""
        ordered = self.frames()
        total = 0.0
        # pairwise sliding window — the second sequence is one shorter BY
        # DESIGN, so strict=False is the correct explicit choice here
        for prev, cur in zip(ordered, ordered[1:], strict=False):
            total += math.dist(
                self.translations[prev], self.translations[cur]
            )
        return total

    def span(self) -> float:
        """Reference→last-frame displacement (canonical units)."""
        ordered = self.frames()
        return math.dist(
            self.translations[ordered[0]], self.translations[ordered[-1]]
        )

    def covers(self, frames: list[int]) -> list[int]:
        """Which of ``frames`` lack a track entry (the refuse class)."""
        return [f for f in frames if f not in self.translations]

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "ref_frame": self.ref_frame,
            "translations": {
                str(f): list(self.translations[f]) for f in self.frames()
            },
            "notes": list(self.notes),
        }


def track_from_clip_field(
    hips_track: dict[str, object], scale_ref: float
) -> DriftTrack:
    """The clip-sample format-2 ``hips_track`` object → a canonical track.

    ``hips_track`` is ``{"ref_frame": int, "samples": [[frame, x, y, z],
    ...]}`` in SOURCE meters (armature space, the sampler's own
    ``ROUND_DIGITS``); the conversion uses the converter's own constant
    ``TORSO_SPAN / scale_ref`` so track and positions are
    convention-consistent by construction. Validated loudly: the shape,
    strictly increasing frames, and ``ref_frame`` equal to the minimum
    sample (the sampler's declared reference)."""
    if not isinstance(scale_ref, (int, float)) or not math.isfinite(
        float(scale_ref)
    ) or float(scale_ref) <= 0.0:
        raise RootMotionError(
            f"scale_ref must be finite and > 0, got {scale_ref!r}",
            hint="the clip's own scale_ref normalizes the track",
        )
    if not isinstance(hips_track, dict):
        raise RootMotionError(
            f"hips_track must be an object, got {type(hips_track).__name__}",
            hint='format 2 carries {"ref_frame": int, "samples": [[f,x,y,z], ...]}',
        )
    extra = sorted(set(hips_track) - {"ref_frame", "samples"})
    if extra:
        raise RootMotionError(
            f"unknown hips_track field(s): {extra}",
            hint="hips_track carries exactly ref_frame and samples",
        )
    ref = hips_track.get("ref_frame")
    if not isinstance(ref, int) or isinstance(ref, bool):
        raise RootMotionError(
            f"hips_track.ref_frame must be an integer, got {ref!r}",
            hint="the reference frame's entry is the zero vector",
        )
    raw = hips_track.get("samples")
    if not isinstance(raw, list) or not raw:
        raise RootMotionError(
            "hips_track.samples must be a non-empty list",
            hint="a track with no observations measures nothing — omit it",
        )
    samples: dict[int, tuple[float, float, float]] = {}
    last: int | None = None
    for i, entry in enumerate(raw):
        if not isinstance(entry, (list, tuple)) or len(entry) != 4:
            raise RootMotionError(
                f"hips_track.samples[{i}]: expected [frame, x, y, z]",
                hint="each sample carries the frame index and the hips "
                     "position in source meters",
            )
        f = entry[0]
        if not isinstance(f, int) or isinstance(f, bool):
            raise RootMotionError(
                f"hips_track.samples[{i}].frame must be an integer, got {f!r}",
                hint="frame indices are exact — the track never interpolates",
            )
        if last is not None and f <= last:
            raise RootMotionError(
                f"hips_track.samples not strictly increasing at [{i}] "
                f"({f} <= {last})",
                hint="the sampler writes sorted; the reader refuses to reorder",
            )
        last = f
        samples[f] = _vec3(entry[1:], f"hips_track.samples[{i}]")
    if ref != min(samples):
        raise RootMotionError(
            f"hips_track.ref_frame {ref} is not the minimum sample "
            f"{min(samples)}",
            hint="the track is referenced to its FIRST observed frame",
        )
    scale = TORSO_SPAN / float(scale_ref)
    ref_pos = samples[ref]
    canon = {
        f: (
            (v[0] - ref_pos[0]) * scale,
            (v[1] - ref_pos[1]) * scale,
            (v[2] - ref_pos[2]) * scale,
        )
        for f, v in samples.items()
    }
    canon[ref] = _ZERO
    return DriftTrack.from_samples(
        canon,
        source=SOURCE_CLIP,
        notes=(
            "measured from the sampler's world hips heads (source meters, "
            f"scale_ref={float(scale_ref):g})"
        ),
    )


def track_from_payload_stream(
    entries: list[tuple[int, float, float, float]],
) -> DriftTrack:
    """The video path's APPROXIMATE in-plane track from the payload stream.

    ``entries`` are ``(frame, bbox_center_x_px, bbox_center_y_px,
    scale_px_per_unit)`` per frame — the detector bbox center and the
    solve's own pixels-per-canonical-unit scale, both already in the
    payload. Declared model (docs/ROOT_MOTION.md): lateral and vertical
    drift recovered against the REFERENCE frame's scale;
    ``dy = 0.0`` — depth is unobservable from bbox drift and is never
    guessed. Refuses non-positive/late scales and out-of-order frames."""
    if len(entries) < 1:
        raise RootMotionError(
            "the payload stream is empty — no drift is measurable",
            hint="the track is attached only when the stream exists",
        )
    samples: dict[int, tuple[float, float, float]] = {}
    last: int | None = None
    for i, (f, cx, cy, s) in enumerate(entries):
        if not isinstance(f, int) or isinstance(f, bool):
            raise RootMotionError(
                f"entries[{i}].frame must be an integer, got {f!r}",
                hint="frame indices are exact",
            )
        if last is not None and f <= last:
            raise RootMotionError(
                f"entries not strictly increasing at [{i}] ({f} <= {last})",
                hint="sort the stream by frame; the track never reorders",
            )
        last = f
        vals = (float(cx), float(cy), float(s))
        if not all(math.isfinite(v) for v in vals):
            raise RootMotionError(
                f"entries[{i}]: non-finite bbox/scale",
                hint="payload stream producers refuse NaN/inf",
            )
        if vals[2] <= 0.0:
            raise RootMotionError(
                f"entries[{i}]: scale must be > 0, got {vals[2]!r}",
                hint="pixels-per-canonical-unit from the payload's solve",
            )
        samples[f] = vals
    ref = min(samples)
    r_cx, r_cy, r_s = samples[ref]
    canon = {
        f: ((cx - r_cx) / r_s, 0.0, -(cy - r_cy) / r_s)
        for f, (cx, cy, _s) in samples.items()
    }
    canon[ref] = _ZERO
    return DriftTrack.from_samples(
        canon,
        source=SOURCE_VIDEO,
        notes=(
            "APPROXIMATE: recovered from detector bbox drift against the "
            "reference frame's scale; depth (y) is unobservable from a "
            "single view and stays exactly zero — never guessed (D-008)",
        ),
    )


# -- the compensation bracket ----------------------------------------------------

def _require_coverage(
    frames: list[ActionFrame], track: DriftTrack, what: str
) -> None:
    """Every action frame needs a track entry — a partial track would
    poison the speed chain at the boundary frames. Refuses loud."""
    missing = track.covers([af.frame for af in frames])
    if missing:
        raise RootMotionError(
            f"{what}: {len(missing)} action frame(s) lack a drift-track "
            f"entry (first: {missing[:5]})",
            hint="re-sample with --root-track (clips) or rebuild the stream "
                 "(video) so every frame is covered; a partial track would "
                 "fabricate speed discontinuities — refused, never guessed",
        )


def compensate_frames(
    frames: list[ActionFrame], track: DriftTrack
) -> list[ActionFrame]:
    """World-compensated copies: ``positions + track.at(frame)`` per frame.

    Rigid per-frame translation — FK-identical within the frame. A frame
    whose track entry is exactly zero keeps the ORIGINAL positions dict
    (so a zero track compensates to the byte-identical input). Coverage
    must be total (loud refuse otherwise)."""
    _require_coverage(frames, track, "compensate")
    out: list[ActionFrame] = []
    for af in frames:
        t = track.at(af.frame)
        if t is None:  # defensive — _require_coverage already refused
            raise RootMotionError(
                f"frame {af.frame} lost its track entry",
                hint="coverage was validated — this is a bug",
            )
        if t == _ZERO:
            out.append(af)
            continue
        shifted = {
            role: (p[0] + t[0], p[1] + t[1], p[2] + t[2])
            for role, p in sorted(af.pose.positions.items())
        }
        out.append(replace(af, pose=replace(af.pose, positions=shifted)))
    return out


def decompensate_frames(
    frames: list[ActionFrame], track: DriftTrack
) -> list[ActionFrame]:
    """The exact inverse bracket: ``positions - track.at(frame)``."""
    _require_coverage(frames, track, "decompensate")
    out: list[ActionFrame] = []
    for af in frames:
        t = track.at(af.frame)
        if t is None:  # defensive
            raise RootMotionError(
                f"frame {af.frame} lost its track entry",
                hint="coverage was validated — this is a bug",
            )
        if t == _ZERO:
            out.append(af)
            continue
        shifted = {
            role: (p[0] - t[0], p[1] - t[1], p[2] - t[2])
            for role, p in sorted(af.pose.positions.items())
        }
        out.append(replace(af, pose=replace(af.pose, positions=shifted)))
    return out


# -- the root-motion-aware contact stages ----------------------------------------

def _provenance_note(track: DriftTrack) -> str:
    return (
        f"root-aware contacts: classified in the drift-compensated world "
        f"space (track source={track.source}, path {track.path_length():.4f}u, "
        f"span {track.span():.4f}u)"
    )


def detect_contacts_root_aware(
    frames: list[ActionFrame],
    track: DriftTrack,
    **kwargs: float,
) -> ContactReport:
    """Contact detection on the COMPENSATED (world) frames.

    The untouched :func:`~riggermortis.contacts.detect_contacts` state
    machine (same thresholds, same hysteresis, same gap semantics — the
    optional ``kwargs`` pass straight through) runs on
    ``positions + track.at(frame)``; the report's interval structure is
    the world-honest answer and its notes carry the provenance. A
    no-drift track measures the same intervals as the in-place path
    (byte-identical structure) and says so, loudly."""
    _require_coverage(frames, track, "root-aware contact detection")
    compensated = compensate_frames(frames, track)
    report = detect_contacts(compensated, **kwargs)  # type: ignore[arg-type]
    notes = [*report.notes, _provenance_note(track)]
    if track.path_length() == 0.0:
        notes.append(
            "root-aware contacts: no drift measured — walk-in-place path "
            "(the intervals are byte-identical to the uncompensated run)"
        )
    return replace(report, notes=notes)


def lock_feet_root_aware(
    action: CanonicalAction,
    track: DriftTrack,
    *,
    to_ground: bool = False,
    **detect_kwargs: float,
) -> tuple[CanonicalAction, LockReport, ContactReport]:
    """The certified foot lock, root-motion-aware (docs/ROOT_MOTION.md).

    The DETECTION runs on the drift-compensated (world) frames — plants
    are found where feet are actually stationary, the S24 fix — and the
    UNTOUCHED :func:`~riggermortis.contacts.lock_feet` then pins those
    plants in the action's own stored (hips-relative) space, exactly as
    it does in place: the ankle is pinned at its first-observed STORED
    position within the interval and the knees re-solve. The locked
    action is the walk-in-place conversion of the tracked motion — the
    certified product — and its slide numbers (measured on the stored
    positions over the root-aware intervals) are the >= 5x gate metric:
    before = the treadmill glide, after = pinned.

    The world truth stays recoverable from the DATA: the unlocked stored
    positions plus the track reconstruct the stationary world ankles
    (that is the detection space). The stored pin and the track are two
    honest views of one measurement, not competing claims.

    A zero track reduces to :func:`~riggermortis.contacts.lock_feet`
    byte-identically (the detection finds the same intervals and the
    lock is the same call). The action is never mutated."""
    frames = list(action.frames)
    if not frames:
        raise RootMotionError(
            "root-aware foot lock: the action has no frames",
            hint="an empty action has nothing to lock — check the "
                 "conversion upstream",
        )
    report = detect_contacts_root_aware(frames, track, **detect_kwargs)
    locked, lock_report = lock_feet(action, report, to_ground=to_ground)

    # the inner lock's summary line describes the plain walk-in-place
    # reading; on the tracked path the plants came from the compensated
    # space — swap the summary for the honest one (the per-foot lines are
    # the same pins and stay verbatim)
    inner_notes = [
        n for n in locked.notes if not n.endswith(LOCK_NOTE_SUFFIX)
    ]
    total_frames = sum(lock_report.per_foot_frames.values())
    new_notes = [*inner_notes]
    new_notes.append(
        f"root-motion-aware foot lock: {total_frames} in-contact frame(s) "
        f"across {len(report.intervals)} interval(s), detected in the "
        f"drift-compensated world space (track source={track.source}, "
        f"path {track.path_length():.4f}u) and pinned walk-in-place in "
        f"stored space; slide "
        f"{lock_report.slide_before.total:.4f}u -> "
        f"{lock_report.slide_after.total:.4f}u "
        "(the world truth stays in the data: stored positions + track; "
        "D-008: the drift is MEASURED, never authored)"
    )
    if track.path_length() == 0.0:
        new_notes.append(
            "root-motion-aware foot lock: no drift measured — walk-in-place "
            "path (byte-identical to the uncompensated lock)"
        )
    final = replace(locked, notes=new_notes)
    return final, lock_report, report
