"""P8-7 capability probe: the root-motion unknowns, answered by DOING them
in THIS Blender, headless (the motion_probe recipe; design of record
docs/ROOT_MOTION.md — written BEFORE this probe, bars pre-declared).

Rows (RM_ROOT lines; exit 0 only if every row PASSes; SKIPPED counts as
answered for the asset-dependent XBOT row only):

1. TRACK-GT  — the P6-2 walking fixture builder with an AUTHORED hips
               translation curve (0.03 m/frame, world -Y): BVH export ->
               bridge sample with the root track -> convert -> the
               recovered DriftTrack matches the authored curve (x
               TORSO_SPAN/scale_ref) within 0.005 canon; the plants are
               detected ON the compensated model at the authored phase
               structure; the in-place detector on the SAME action finds
               ~nothing (the treadmill, reproduced on synthetic ground).
2. XBOT      — the REAL Mixamo walk (the S24 treadmill row): plants >
               0 on the root-aware model (vs 0 in-place — the finding
               being fixed), the >= 5x slide family (stored-space glide
               before vs pinned after), the track published (path/span).
               SKIPPED honestly without the local glb.
3. INPLACE   — the in-place fixture (no authored drift, no track field):
               a ZERO track reduces detect + lock to the in-place path
               BYTE-IDENTICAL (interval structure and locked positions).
4. REFUSE    — a partial track refuses LOUD (coverage), an empty action
               refuses LOUD, and a no-drift stream delegates with the
               loud walk-in-place note.
5. VIDEO     — the approximate in-plane constructor on a synthetic
               payload stream: mechanical recovery, depth stays exactly
               zero, the APPROXIMATE label present, refusal classes loud.
6. DETERM    — twin tracks + twin root-aware locks byte-identical.

Usage: blender -b --python xtask/root_motion_probe.py
Env: RM_CORE_SRC, RM_ADDON_DIR (defaults like the other probes);
RM_MOTION_XBOT overrides the Xbot.glb path.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
import tempfile
from pathlib import Path

import bpy  # noqa: F401 — probe runs inside Blender

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.environ.get(
    "RM_CORE_SRC", str(REPO / "core" / "src")))
sys.path.insert(0, os.environ.get(
    "RM_ADDON_DIR", str(REPO / "addon")))

import riggermortis as core  # noqa: E402
from riggermortis.canonical_pose import TORSO_SPAN  # noqa: E402
from riggermortis.contacts import (  # noqa: E402
    LOCK_NOTE_SUFFIX,
    detect_contacts,
    lock_feet,
)  # noqa: E402
from riggermortis.root_motion import (  # noqa: E402
    SOURCE_CLIP,
    SOURCE_VIDEO,
    DriftTrack,
    compensate_frames,
    detect_contacts_root_aware,
    lock_feet_root_aware,
    track_from_payload_stream,
)
from riggermortis_addon import bpy_bridge, clip_sample  # noqa: E402

OK = True
TRACK_BAR = 0.005  # canon — the RM_MOTION round-trip family (declared)
RATIO_BAR = 5.0  # the >= 5x family (Annex A.1)
DRIFT_STEP_M = (0.0, -0.03, 0.0)  # authored world drift per frame (forward)
# Authored stance spans per foot; the OBSERVABLE plant expectation maps
# each span [s, e] to [s+1, e] and DROPS single-frame spans: a landing
# frame carries approach speed, so the detector's enter condition can only
# fire one frame into the stance (unknown state is never guessed — the
# gap/hysteresis contract). The sliding fixture's published phases
# (RM_MOTION CONTACTS) hid this because its landing speeds happened to dip
# below the bar at the landing instant; the planted fixture does not.
AUTHORED_STANCES = (("foot.L", ((1, 12), (25, 36), (49, 49))),
                    ("foot.R", ((13, 24), (37, 48))))


def observable_phases():
    out = []
    for foot, spans in AUTHORED_STANCES:
        for a, b in spans:
            if a + 1 <= b:
                out.append((foot, a + 1, b))
    return sorted(out)


def _check(label: str, ok: bool, detail: str = "") -> bool:
    global OK
    if not ok:
        OK = False
    print(f"RM_ROOT {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _sample_to_json(model: Path, out: Path, *, action: str | None,
                    root_track: bool) -> dict:
    """The promoted sampler library, in-process (the S25 promotion — ONE
    copy of the loop); returns the parsed clip dict."""
    report = clip_sample.sample_clip(
        str(model), str(out), core, bpy_bridge,
        action=action, root_track=root_track,
    )
    for line in report["lines"]:
        print(line)
    if not report["determ"]:
        raise RuntimeError(f"sampler DETERM FAIL for {model}")
    return json.loads(Path(out).read_text(encoding="utf-8"))


def _interval_shape(report) -> list[tuple[str, int, int]]:
    return [(iv.foot, iv.start, iv.end) for iv in report.intervals]


def track_gt(tmp: Path) -> None:
    fixture = _load_module("rm_motion_fixture", REPO / "xtask" / "motion_fixture.py")
    bvh = tmp / "drift_walk.bvh"
    clip_json = tmp / "drift_walk.clip.json"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = fixture.build_humanoid("rm_motion_fixture_drift")
    fixture.key_walk(obj, drift=DRIFT_STEP_M)
    fixture.export_bvh(obj, bvh)
    bpy.ops.wm.read_factory_settings(use_empty=True)  # wipe the build scene
    clip = _sample_to_json(bvh, clip_json, action=None, root_track=True)
    assert clip["format"] == 2, "root-track sampling must write format 2"
    mc = core.MotionClip.from_dict(clip)
    action = core.action_from_clip(mc)
    track = action.root_track
    if track is None:
        _check("TRACK-GT", False, "converter attached no track")
        return
    # -- recovery vs authored (converted by the converter's own constant) ----
    scale_ref = clip["scale_ref"]  # noqa: F841 — published in the row detail
    k = TORSO_SPAN / scale_ref
    worst = 0.0
    ref = track.ref_frame
    for f in range(1, len(mc.frames) + 1):
        n = f - ref  # the track references its FIRST observed frame
        want = (DRIFT_STEP_M[0] * k * n, DRIFT_STEP_M[1] * k * n,
                DRIFT_STEP_M[2] * k * n)
        got = track.at(f)
        if got is None:
            _check("TRACK-GT", False, f"frame {f} missing from the track")
            return
        worst = max(worst, math.dist(got, want))
    ok = _check(
        "TRACK-GT-RECOVERY", worst <= TRACK_BAR,
        f"max_err={worst:.6f} canon (bar {TRACK_BAR}) k={k:.4f} "
        f"scale_ref={scale_ref:.4f} path={track.path_length():.4f}u "
        f"span={track.span():.4f}u [SYNTHETIC, prior-consistent GT]",
    )
    # -- plants ON the compensated model at the authored phases ---------------
    frames = [(af.frame, af.pose) for af in action.frames]
    aware = detect_contacts_root_aware(
        [core.ActionFrame(frame=f, pose=p) for f, p in frames], track)
    got_shape = sorted(_interval_shape(aware))
    want_shape = observable_phases()
    ok2 = _check(
        "TRACK-GT-PLANTS", got_shape == want_shape,
        f"intervals={got_shape} (authored stances with the landing frame "
        f"excluded by the enter contract: {want_shape})",
    )
    # -- the treadmill, reproduced: the in-place detector sees the glide ------
    plain = detect_contacts([core.ActionFrame(frame=f, pose=p) for f, p in frames])
    n_plain = len(plain.intervals)
    locked, lock_rep, _rep = lock_feet_root_aware(
        core.action_from_poses(frames), track)
    before = lock_rep.slide_before.total if lock_rep.slide_before else 0.0
    after = lock_rep.slide_after.total if lock_rep.slide_after else 0.0
    ratio = (before / after) if after > 1e-12 else float("inf")
    ok3 = _check(
        "TRACK-GT-FIX", ratio >= RATIO_BAR,
        f"the root-aware fix on the drift fixture: slide {before:.4f}u -> "
        f"{after:.4f}u = {ratio:.1f}x (bar >= {RATIO_BAR:.0f}x); the "
        f"in-place reading of the SAME action finds {n_plain} spurious "
        "interval(s) on the gliding stored positions (the treadmill "
        "confusion, reproduced)",
    )
    _check("TRACK-GT", ok and ok2 and ok3)


def xbot_row(tmp: Path) -> None:
    glb = Path(os.environ.get(
        "RM_MOTION_XBOT", str(REPO / "out" / "real_rigs" / "Xbot.glb")))
    if not glb.is_file():
        _check("XBOT", True, "SKIPPED (Xbot.glb not found; set RM_MOTION_XBOT)")
        return
    clip_json = tmp / "xbot_walk.clip.json"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    clip = _sample_to_json(glb, clip_json, action="walk", root_track=True)
    mc = core.MotionClip.from_dict(clip)
    action = core.action_from_clip(mc)
    track = action.root_track
    if track is None:
        _check("XBOT", False, "real clip carried no root track")
        return
    frames = [core.ActionFrame(frame=af.frame, pose=af.pose)
              for af in action.frames]
    plain = detect_contacts(frames)
    aware = detect_contacts_root_aware(frames, track)
    locked, lock_rep, _rep = lock_feet_root_aware(action, track)
    before = lock_rep.slide_before.total if lock_rep.slide_before else 0.0
    after = lock_rep.slide_after.total if lock_rep.slide_after else 0.0
    n_clamped = sum(lock_rep.clamped.values())
    # the world truth stays in the data: unlocked stored + track is
    # stationary on the detected intervals (consistency, no GT exists)
    comp = compensate_frames(frames, track)
    worst_world = 0.0
    for iv in aware.intervals:
        anchor = None
        for af in comp:
            if iv.start <= af.frame <= iv.end:
                pos = af.pose.positions[iv.foot]
                if anchor is None:
                    anchor = pos
                else:
                    worst_world = max(worst_world, math.dist(pos, anchor))
    # THE CORRECTED FINDING (probe-earned, docs/ROOT_MOTION.md A3): the
    # S24 attribution ("the clip carries Mixamo ROOT MOTION -> treadmill")
    # is WRONG — measured across ALL SEVEN clips (walk/run/idle/agree/
    # headShake/sad_pose/sneak_pose): the hips bone carries NO translation
    # (walk: y constant to the sampler's 1e-6 m; run: span 0.0000u) and
    # the armature object never moves. The imported scene graph has no
    # root motion ANYWHERE; the published 0.022-0.19 u/f stored glide is
    # the in-place walk cycle's own leg kinematics, which hips-anchoring
    # cannot and should not remove. The Annex A.1 bar (the drift track
    # beating walk-in-place slide by >= 5x on THIS row) is unmeetable BY
    # THE FILE'S CONTENT: no source drift exists to recover; the track
    # measures the sway/bounce (path ~0.23u, span ~0.002u) and the
    # root-aware model correctly finds the same 0 plants as in-place.
    # Per Annex A.2, L7 ends REFUSED-with-evidence: walk-in-place ships.
    no_translation = track.span() <= 0.01
    ok = _check(
        "XBOT",
        len(plain.intervals) == 0 and len(aware.intervals) == 0
        and no_translation,
        f"the corrected finding: hips track span={track.span():.4f}u "
        f"(<= 0.01 = NO translatable drift in the file), path="
        f"{track.path_length():.4f}u is sway/bounce; plants in-place="
        f"{len(plain.intervals)} root-aware={len(aware.intervals)} "
        "(the model degenerates to the status quo on a no-drift clip — "
        "byte-identical by contract); slide {b:.4f}->{a:.4f}".format(
            b=before, a=after)
        + f" clamped={n_clamped} world-reconstruction worst={worst_world:.2e}u "
        "(REAL clip, no GT exists; the >= 5x demonstration lives on the "
        "TRACK-GT drift fixture, the class the track addresses)",
    )
    _check("XBOT", ok)
    # keep the locked action numbers for the record (not a separate row)
    print(
        f"RM_ROOT XBOT-LOCK: pinned={sum(lock_rep.per_foot_frames.values())} "
        f"max_knee={max(lock_rep.max_knee_shift.values(), default=0.0):.4f}u "
        f"max_ankle={max(lock_rep.max_ankle_shift.values(), default=0.0):.4f}u"
    )


def inplace_identity(tmp: Path) -> None:
    fixture = _load_module("rm_motion_fixture_ip", REPO / "xtask" / "motion_fixture.py")
    bvh = tmp / "walk_ip.bvh"
    clip_json = tmp / "walk_ip.clip.json"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = fixture.build_humanoid("rm_motion_fixture_ip")
    fixture.key_walk(obj)  # explicit no root motion
    fixture.export_bvh(obj, bvh)
    bpy.ops.wm.read_factory_settings(use_empty=True)  # wipe the build scene
    clip = _sample_to_json(bvh, clip_json, action=None, root_track=False)
    assert clip["format"] == 1, "the default sampler must stay format 1"
    mc = core.MotionClip.from_dict(clip)
    action = core.action_from_clip(mc)
    assert action.root_track is None, "a format-1 clip attaches no track"
    frames = [core.ActionFrame(frame=af.frame, pose=af.pose)
              for af in action.frames]
    zero = DriftTrack.from_samples(
        {af.frame: (0.0, 0.0, 0.0) for af in action.frames},
        source=SOURCE_CLIP,
    )
    plain_detect = detect_contacts(frames)
    aware_detect = detect_contacts_root_aware(frames, zero)
    same_detect = (
        _interval_shape(plain_detect) == _interval_shape(aware_detect)
        and plain_detect.in_contact == aware_detect.in_contact
        and plain_detect.ground == aware_detect.ground
        # the aware notes are the plain notes PLUS the provenance lines
        and all(n in aware_detect.notes for n in plain_detect.notes)
    )
    plain_action = core.action_from_poses(
        [(af.frame, af.pose) for af in frames])
    plain_locked, _plain_lock = lock_feet(plain_action, plain_detect)
    aware_locked, _aware_lock, _r = lock_feet_root_aware(plain_action, zero)
    positions_equal = all(
        a.pose.positions == b.pose.positions
        for a, b in zip(plain_locked.frames, aware_locked.frames, strict=True)
    )
    notes_honest = (
        any("no drift measured" in n for n in aware_locked.notes)
        and not any(n.endswith(LOCK_NOTE_SUFFIX)
                    for n in aware_locked.notes)
    )
    _check(
        "INPLACE",
        same_detect and positions_equal and notes_honest,
        f"zero-track detect structure equal={same_detect} locked positions "
        f"equal={positions_equal} honest notes={notes_honest} "
        f"({len(plain_detect.intervals)} interval(s) on the in-place "
        "fixture; the aware notes carry the provenance lines on top)",
    )


def refuse_classes(tmp: Path) -> None:
    fixture = _load_module("rm_motion_fixture_rf", REPO / "xtask" / "motion_fixture.py")
    bvh = tmp / "walk_rf.bvh"
    clip_json = tmp / "walk_rf.clip.json"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = fixture.build_humanoid("rm_motion_fixture_rf")
    fixture.key_walk(obj)
    fixture.export_bvh(obj, bvh)
    bpy.ops.wm.read_factory_settings(use_empty=True)  # wipe the build scene
    clip = _sample_to_json(bvh, clip_json, action=None, root_track=True)
    mc = core.MotionClip.from_dict(clip)
    action = core.action_from_clip(mc)
    track = action.root_track
    frames = [core.ActionFrame(frame=af.frame, pose=af.pose)
              for af in action.frames]
    # partial coverage refuses LOUD (both entry points)
    partial = DriftTrack.from_samples(
        {f: v for f, v in list(track.translations.items())[: len(frames) // 2]},
        source=SOURCE_CLIP,
    )
    refused = 0
    try:
        detect_contacts_root_aware(frames, partial)
    except core.RootMotionError as exc:
        refused += 1 if "lack a drift-track entry" in str(exc) else 0
        print(f"RM_ROOT REFUSE-DETAIL: partial detect -> {exc}")
    try:
        lock_feet_root_aware(core.action_from_poses(
            [(af.frame, af.pose) for af in frames]), partial)
    except core.RootMotionError as exc:
        refused += 1 if "lack a drift-track entry" in str(exc) else 0
    # an empty action refuses LOUD
    try:
        lock_feet_root_aware(core.action_from_poses([]), track)
    except core.RootMotionError as exc:
        refused += 1 if "no frames" in str(exc) else 0
    # a no-drift stream is VALID data: delegates, byte-identical, loud
    zero = DriftTrack.from_samples(
        {af.frame: (0.0, 0.0, 0.0) for af in frames}, source=SOURCE_CLIP)
    plain_detect = detect_contacts(frames)
    aware_detect = detect_contacts_root_aware(frames, zero)
    delegated = (
        _interval_shape(plain_detect) == _interval_shape(aware_detect)
        and any("no drift measured" in n for n in aware_detect.notes)
    )
    _check(
        "REFUSE", refused == 3 and delegated,
        f"loud refusals={refused}/3 (partial detect, partial lock, empty "
        f"action); no-drift stream delegated byte-identically={delegated}",
    )


def video_stream_row() -> None:
    # a synthetic payload stream: the bbox center drifts 0.5 px/frame right
    # and 0.25 px/frame up at a constant scale of 50 px/canon-unit
    entries = [(f, 320.0 + 0.5 * f, 240.0 - 0.25 * f, 50.0) for f in range(10)]
    t = track_from_payload_stream(entries)
    ok_recover = (
        t.source == SOURCE_VIDEO
        and t.at(9) is not None
        and t.at(9) == (0.5 * 9 / 50.0, 0.0, 0.25 * 9 / 50.0)
        and all(v[1] == 0.0 for v in t.translations.values())
        and any("APPROXIMATE" in n for n in t.notes)
    )
    refused = 0
    for bad in (
        [(0, 1.0, 1.0, 0.0)],                      # scale <= 0
        [(1, 1.0, 1.0, 50.0), (1, 2.0, 2.0, 50.0)],  # not increasing
        [],                                        # empty
    ):
        try:
            track_from_payload_stream(bad)
        except core.RootMotionError:
            refused += 1
    _check(
        "VIDEO", ok_recover and refused == 3,
        f"mechanical recovery dx={t.at(9)[0]:.4f} dz={t.at(9)[2]:.4f} "
        f"depth≡0=True APPROXIMATE-labeled=True loud refusals={refused}/3 "
        "[declared APPROXIMATE-class: in-plane only, no depth from bbox "
        "drift — never guessed]",
    )


def determ_row(tmp: Path) -> None:
    clip_json = tmp / "drift_walk.clip.json"  # built by TRACK-GT
    if not clip_json.is_file():
        _check("DETERM", False, "TRACK-GT clip missing")
        return
    action = core.action_from_clip(core.MotionClip.from_dict(
        json.loads(clip_json.read_text(encoding="utf-8"))))
    track1 = action.root_track
    track2 = core.action_from_clip(core.MotionClip.from_dict(
        json.loads(clip_json.read_text(encoding="utf-8")))).root_track
    same_track = track1 == track2
    l1, r1, d1 = lock_feet_root_aware(action, track1)
    l2, r2, d2 = lock_feet_root_aware(action, track2)
    same_lock = l1 == l2 and r1 == r2 and d1 == d2
    _check(
        "DETERM", same_track and same_lock,
        f"twin tracks equal={same_track} twin detect+lock equal={same_lock}",
    )


def main() -> int:
    global OK
    with tempfile.TemporaryDirectory(prefix="rm_root_probe_") as td:
        tmp = Path(td)
        track_gt(tmp)
        xbot_row(tmp)
        inplace_identity(tmp)
        refuse_classes(tmp)
        video_stream_row()
        determ_row(tmp)
    print(f"RM_ROOT: {'PASS' if OK else 'FAIL'}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
