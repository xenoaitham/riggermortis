"""P8-7 tests: the measured drift track + the root-motion-aware contact pass.

Contract pins (docs/ROOT_MOTION.md):
- the track is loud-validated data; gaps stay gaps (at() answers observed
  frames only);
- a ZERO track compensates to the byte-identical input (tuple reuse, not a
  rebuild) and both root-aware stages reduce to the in-place path
  byte-identically (interval structure AND locked positions);
- on a drifting subject the root-aware detection finds the plants the
  in-place detector must miss (the S24 treadmill shape), and the lock's
  world pins cancel the glide (>= 5x family by construction here);
- no payload format change: the track rides the ACTION and survives
  conditioning; MotionClip reads formats 1+2 with the additive carrier and
  writes format 1 bytes when no track is present.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis.action import (  # noqa: E402
    ActionFrame,
    action_from_poses,
    condition_action,
    stabilize_hips,
)
from riggermortis.canonical_pose import TORSO_SPAN, CanonicalPose  # noqa: E402
from riggermortis.contacts import (  # noqa: E402
    LOCK_NOTE_SUFFIX,
    detect_contacts,
    lock_feet,
)
from riggermortis.motion import MotionClip, action_from_clip  # noqa: E402
from riggermortis.root_motion import (  # noqa: E402
    SOURCE_CLIP,
    SOURCE_VIDEO,
    DriftTrack,
    RootMotionError,
    compensate_frames,
    decompensate_frames,
    detect_contacts_root_aware,
    lock_feet_root_aware,
    track_from_clip_field,
    track_from_payload_stream,
)

GROUND = -1.0
DRIFT_STEP = (0.03, 0.0, 0.0)  # canonical units per frame (the treadmill);
# pure horizontal so the world-pinned ankle stays INSIDE the fixed-hips
# stored chain's reach — a fixture with vertical drift exercises the
# lock's honest reach-clamp instead of the pin (measured on the first run)


def _pose(feet: dict[str, tuple[float, float, float]]) -> CanonicalPose:
    positions = {
        "hips": (0.0, 0.0, 0.0),
        "upper_leg.L": (0.09, 0.0, -0.08),
        "lower_leg.L": (0.09, 0.0, -0.55),
        "upper_leg.R": (-0.09, 0.0, -0.08),
        "lower_leg.R": (-0.09, 0.0, -0.55),
    }
    positions.update(feet)
    return CanonicalPose(
        positions=positions,
        flips={},
        confidence=0.9,
        reliable=True,
        scale=30.0,
        anchor="hips",
        joint_confidence={r: 0.9 for r in positions},
    )


def _frames(world_feet: list[tuple[tuple[float, float, float],
                                   tuple[float, float, float]]]) -> list[ActionFrame]:
    """Frames whose ankles are STATIONARY IN THE WORLD at ``world_feet``;
    stored hips-relative positions get the (fabricated-here, measured-in-
    production) drift subtracted — the exact treadmill shape, rigid."""
    out = []
    for i, (wl, wr) in enumerate(world_feet):
        t = (DRIFT_STEP[0] * i, DRIFT_STEP[1] * i, DRIFT_STEP[2] * i)
        stored = {
            "foot.L": (wl[0] - t[0], wl[1] - t[1], wl[2] - t[2]),
            "foot.R": (wr[0] - t[0], wr[1] - t[1], wr[2] - t[2]),
        }
        out.append(ActionFrame(frame=i, pose=_pose(stored)))
    return out


def _track(n: int) -> DriftTrack:
    return DriftTrack.from_samples(
        {i: (DRIFT_STEP[0] * i, DRIFT_STEP[1] * i, DRIFT_STEP[2] * i)
         for i in range(n)},
        source=SOURCE_CLIP,
    )


# -- the track --------------------------------------------------------------------

def test_track_reference_frame_is_zero_and_at_is_exact():
    t = DriftTrack.from_samples(
        {3: (0.1, 0.2, 0.3), 5: (0.4, 0.5, 0.6), 4: (0.0, 0.0, 0.0)},
        source=SOURCE_CLIP,
    )
    assert t.ref_frame == 3
    assert t.at(3) == (0.0, 0.0, 0.0)
    assert t.at(4) == (0.0, 0.0, 0.0)  # the authored zero stays a zero
    assert t.at(5) == (0.4, 0.5, 0.6)
    assert t.at(6) is None  # gaps stay gaps — never interpolated
    assert t.frames() == [3, 4, 5]


def test_track_refuses_bad_inputs():
    with pytest.raises(RootMotionError, match="at least one"):
        DriftTrack.from_samples({}, source=SOURCE_CLIP)
    with pytest.raises(RootMotionError, match="unknown drift-track source"):
        DriftTrack.from_samples({0: (0.0, 0.0, 0.0)}, source="made-up")
    with pytest.raises(RootMotionError, match="not an integer"):
        DriftTrack.from_samples({True: (0.0, 0.0, 0.0)}, source=SOURCE_CLIP)
    with pytest.raises(RootMotionError, match="non-finite"):
        DriftTrack.from_samples(
            {0: (0.0, 0.0, 0.0), 1: (float("nan"), 0.0, 0.0)},
            source=SOURCE_CLIP,
        )


def test_track_path_and_span():
    t = DriftTrack.from_samples(
        {i: (0.1 * i, 0.0, 0.0) for i in range(5)}, source=SOURCE_CLIP
    )
    assert t.path_length() == pytest.approx(0.4)
    assert t.span() == pytest.approx(0.4)
    zero = DriftTrack.from_samples({0: (0, 0, 0), 1: (0, 0, 0)}, source=SOURCE_CLIP)
    assert zero.path_length() == 0.0
    assert zero.span() == 0.0


def test_clip_field_conversion_uses_the_converter_constant():
    scale_ref = 0.9  # source meters
    world = {0: (0.0, 0.0, 0.0), 1: (0.3, 0.0, 0.0), 2: (0.6, 0.0, 0.12)}
    field = {
        "ref_frame": 0,
        "samples": [[f, *p] for f, p in world.items()],
    }
    t = track_from_clip_field(field, scale_ref)
    k = TORSO_SPAN / scale_ref
    assert t.source == SOURCE_CLIP
    assert t.at(2) == pytest.approx((0.6 * k, 0.0, 0.12 * k))
    assert t.at(0) == (0.0, 0.0, 0.0)


def test_clip_field_refuses_shape_violations():
    with pytest.raises(RootMotionError, match="scale_ref"):
        track_from_clip_field({"ref_frame": 0, "samples": [[0, 0, 0, 0]]}, 0.0)
    with pytest.raises(RootMotionError, match="not the minimum"):
        track_from_clip_field(
            {"ref_frame": 1, "samples": [[0, 0, 0, 0], [1, 1, 0, 0]]}, 0.9
        )
    with pytest.raises(RootMotionError, match="strictly increasing"):
        track_from_clip_field(
            {"ref_frame": 0, "samples": [[1, 0, 0, 0], [0, 0, 0, 0]]}, 0.9
        )
    with pytest.raises(RootMotionError, match="unknown hips_track"):
        track_from_clip_field(
            {"ref_frame": 0, "samples": [[0, 0, 0, 0]], "extra": 1}, 0.9
        )


def test_video_stream_is_in_plane_and_approximate():
    t = track_from_payload_stream(
        [(0, 100.0, 200.0, 50.0), (2, 110.0, 190.0, 50.0)]
    )
    assert t.source == SOURCE_VIDEO
    assert t.at(2) == pytest.approx((0.2, 0.0, 0.2))  # dz = -dy_px / scale
    assert any("APPROXIMATE" in n for n in t.notes)
    assert all(v[1] == 0.0 for v in t.translations.values())  # depth stays zero
    with pytest.raises(RootMotionError, match="scale"):
        track_from_payload_stream([(0, 100.0, 200.0, 0.0)])
    with pytest.raises(RootMotionError, match="strictly increasing"):
        track_from_payload_stream([(1, 1.0, 1.0, 50.0), (1, 2.0, 2.0, 50.0)])
    with pytest.raises(RootMotionError, match="empty"):
        track_from_payload_stream([])


# -- the compensation bracket -------------------------------------------------------

def test_zero_track_compensates_to_the_identical_input():
    frames = _frames([((0.09, 0.0, GROUND), (-0.09, 0.0, GROUND))] * 3)
    zero = DriftTrack.from_samples(
        {i: (0.0, 0.0, 0.0) for i in range(3)}, source=SOURCE_CLIP
    )
    out = compensate_frames(frames, zero)
    for a, b in zip(frames, out, strict=True):
        assert b.pose.positions is a.pose.positions  # tuple reuse, not a rebuild
    assert out == frames


def test_compensate_decompensate_round_trip():
    n = 4
    frames = _frames([((0.09, 0.0, GROUND), (-0.09, 0.0, GROUND))] * n)
    t = _track(n)
    back = decompensate_frames(compensate_frames(frames, t), t)
    for a, b in zip(frames, back, strict=True):
        for role, p in a.pose.positions.items():
            assert b.pose.positions[role] == pytest.approx(p, abs=1e-12)


def test_partial_coverage_refuses_loud():
    frames = _frames([((0.09, 0.0, GROUND), (-0.09, 0.0, GROUND))] * 4)
    t = DriftTrack.from_samples(
        {0: (0.0, 0.0, 0.0), 1: (0.1, 0.0, 0.0)}, source=SOURCE_CLIP
    )
    with pytest.raises(RootMotionError, match="lack a drift-track entry"):
        compensate_frames(frames, t)
    with pytest.raises(RootMotionError, match="root-aware contact detection"):
        lock_feet_root_aware(action_from_poses([(i, f.pose) for i, f in
                                                 enumerate(frames)]), t)


# -- the root-aware contact stages ---------------------------------------------------

def _treadmill(n: int = 8) -> list[ActionFrame]:
    """Left foot planted (world-stationary) across all frames, right foot
    clearly airborne (heights far above exit_height) — the S24 treadmill:
    in-place detection sees a gliding ankle above the enter bar and finds
    nothing; the root-aware pass sees the plant."""
    wl = (0.09, 0.0, GROUND)
    frames = []
    for i in range(n):
        wr = (-0.09 + 0.02 * i, 0.0, GROUND + 0.5 + 0.2 * math.sin(i))
        t = (DRIFT_STEP[0] * i, 0.0, DRIFT_STEP[2] * i)
        stored = {
            "foot.L": (wl[0] - t[0], wl[1] - t[1], wl[2] - t[2]),
            "foot.R": (wr[0] - t[0], wr[1] - t[1], wr[2] - t[2]),
        }
        frames.append(ActionFrame(frame=i, pose=_pose(stored)))
    return frames


def test_treadmill_in_place_finds_nothing_root_aware_finds_the_plant():
    frames = _treadmill()
    inplace = detect_contacts(frames)
    assert inplace.intervals == []  # the S24 finding, reproduced
    t = _track(len(frames))
    aware = detect_contacts_root_aware(frames, t)
    assert len(aware.intervals) == 1
    assert aware.intervals[0].foot == "foot.L"
    assert aware.intervals[0].start == 1  # frame 0 has no measurable speed
    assert aware.intervals[0].end == len(frames) - 1
    assert any("compensated world space" in n for n in aware.notes)


def test_root_aware_lock_pins_walk_in_place_and_keeps_the_world_in_data():
    frames = _treadmill()
    action = action_from_poses([(f.frame, f.pose) for f in frames])
    t = _track(len(frames))
    locked, lock_report, report = lock_feet_root_aware(action, t)
    # the >= 5x family, measured on the STORED positions over the
    # root-aware intervals: before = the treadmill glide, after = pinned
    assert lock_report.slide_before is not None
    assert lock_report.slide_before.total > 0.1
    assert lock_report.slide_after is not None
    assert lock_report.slide_after.total < lock_report.slide_before.total / 5.0
    # stored pin: the planted ankle is FIXED in the locked action
    interval = report.intervals[0]
    anchor_stored = next(
        af.pose.positions["foot.L"] for af in locked.frames
        if af.frame == interval.start
    )
    for af in locked.frames:
        if interval.start <= af.frame <= interval.end:
            assert af.pose.positions["foot.L"] == pytest.approx(
                anchor_stored, abs=1e-9
            )
    # the world truth stays in the DATA: unlocked stored + track is
    # stationary (the detection space)
    world = [af.pose.positions["foot.L"] for af in
             compensate_frames(list(action.frames), t)]
    for p in world[1:]:
        assert p == pytest.approx(world[0], abs=1e-9)
    # honest notes: the stale walk-in-place suffix line is replaced
    assert not any(n.endswith(LOCK_NOTE_SUFFIX) for n in locked.notes)
    assert any("root-motion-aware foot lock" in n for n in locked.notes)
    assert any("drift-compensated world space" in n for n in locked.notes)


def test_zero_track_lock_is_byte_identical_to_the_in_place_lock():
    n = 8
    frames = []
    for i in range(n):
        wl = (0.09 - 0.005 * i, 0.0, GROUND)  # a slow in-place stance arc
        wr = (-0.09 + 0.02 * i, 0.0, GROUND + 0.4)
        frames.append(ActionFrame(frame=i, pose=_pose({"foot.L": wl, "foot.R": wr})))
    action = action_from_poses([(f.frame, f.pose) for f in frames])
    zero = DriftTrack.from_samples(
        {i: (0.0, 0.0, 0.0) for i in range(n)}, source=SOURCE_CLIP
    )
    plain_detect = detect_contacts(frames)
    aware_detect = detect_contacts_root_aware(frames, zero)
    assert [(iv.foot, iv.start, iv.end) for iv in plain_detect.intervals] == [
        (iv.foot, iv.start, iv.end) for iv in aware_detect.intervals
    ]
    assert plain_detect.in_contact == aware_detect.in_contact
    assert plain_detect.ground == aware_detect.ground
    plain_locked, plain_lock = lock_feet(action, plain_detect)
    aware_locked, aware_lock, _r = lock_feet_root_aware(action, zero)
    for a, b in zip(plain_locked.frames, aware_locked.frames, strict=True):
        for role in a.pose.positions:
            assert a.pose.positions[role] == b.pose.positions[role]
    assert plain_lock.slide_after.total == aware_lock.slide_after.total
    assert any("no drift measured" in n for n in aware_locked.notes)


def test_root_aware_lock_never_mutates_the_input():
    frames = _treadmill()
    action = action_from_poses([(f.frame, f.pose) for f in frames])
    before = [(f.frame, dict(f.pose.positions)) for f in action.frames]
    lock_feet_root_aware(action, _track(len(frames)))
    after = [(f.frame, dict(f.pose.positions)) for f in action.frames]
    assert before == after


# -- the track rides the action -------------------------------------------------------

def test_action_carries_and_conditioning_preserves_the_track():
    frames = _treadmill()
    t = _track(len(frames))
    action = action_from_poses(
        [(f.frame, f.pose) for f in frames], root_track=t
    )
    assert action.root_track is t
    plain = action_from_poses([(f.frame, f.pose) for f in frames])
    assert plain.root_track is None
    conditioned = condition_action(plain)  # no-op conditioning keeps None
    assert conditioned.root_track is None
    stabilized, _rep = stabilize_hips(action)
    assert stabilized.root_track is t  # dataclasses.replace carries it
    condensed = condition_action(action)
    assert condensed.root_track is t


# -- the clip-sample format 2 carrier ---------------------------------------------------

def _clip_dict(track: list[list[float]] | None) -> dict:
    d = {
        "format": 1,
        "fps": 24.0,
        "scale_ref": 0.84,
        "frames": [
            {"frame": 0, "positions": {
                "hips": [0.0, 0.0, 1.0], "foot.L": [0.09, 0.0, 0.08],
                "foot.R": [-0.09, 0.0, 0.08]}},
            {"frame": 1, "positions": {
                "hips": [0.03, 0.0, 1.0], "foot.L": [0.09, 0.0, 0.08],
                "foot.R": [-0.09, 0.0, 0.08]}},
        ],
        "source": "blender-import",
        "source_fingerprint": None,
        "notes": [],
    }
    if track is not None:
        d["format"] = 2
        d["hips_track"] = {"ref_frame": 0, "samples": track}
    return d


def test_motion_clip_format1_bytes_unchanged_and_format2_reads():
    d1 = _clip_dict(None)
    clip1 = MotionClip.from_dict(d1)
    assert clip1.hips_track == ()
    assert MotionClip.from_dict(clip1.to_dict()) == clip1
    assert set(clip1.to_dict()) == {
        "format", "fps", "scale_ref", "frames", "source",
        "source_fingerprint", "notes",
    }  # the format-1 field set, byte-stable
    track = [[0, 0.0, 0.0, 1.0], [1, 0.03, 0.0, 1.0]]
    d2 = _clip_dict(track)
    clip2 = MotionClip.from_dict(d2)
    assert clip2.hips_track == ((0, 0.0, 0.0, 1.0), (1, 0.03, 0.0, 1.0))
    assert MotionClip.from_dict(clip2.to_dict()) == clip2  # round-trip
    with pytest.raises(Exception, match="cannot carry hips_track"):
        MotionClip.from_dict({**d1, "hips_track": {"ref_frame": 0, "samples": track}})
    with pytest.raises(Exception, match="requires the hips_track"):
        MotionClip.from_dict({**d2, "hips_track": None})


def test_action_from_clip_attaches_the_measured_track():
    track = [[0, 0.0, 0.0, 1.0], [1, 0.03, 0.0, 1.0]]
    action = action_from_clip(MotionClip.from_dict(_clip_dict(track)))
    assert action.root_track is not None
    assert action.root_track.source == SOURCE_CLIP
    k = TORSO_SPAN / 0.84
    assert action.root_track.at(1) == pytest.approx((0.03 * k, 0.0, 0.0))
    assert any("root track attached" in n for n in action.notes)
    plain = action_from_clip(MotionClip.from_dict(_clip_dict(None)))
    assert plain.root_track is None
    assert not any("root track attached" in n for n in plain.notes)


def test_determ_twin_tracks_and_twin_locks():
    frames = _treadmill()
    action = action_from_poses([(f.frame, f.pose) for f in frames])
    t1 = _track(len(frames))
    t2 = _track(len(frames))
    l1, r1, d1 = lock_feet_root_aware(action, t1)
    l2, r2, d2 = lock_feet_root_aware(action, t2)
    assert l1 == l2
    assert r1 == r2
    assert d1 == d2
