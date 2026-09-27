"""P8-7 root-motion gate (run INSIDE Blender, headless) — the RM_ROOT rows.

The sibling of scene_gate/couple_gate/finger_gate/face_gate/camera_gate/
spine_gate (the Mimosa new-file rule). Design of record:
docs/ROOT_MOTION.md — the pre-declared Annex A.1 bar (the >= 5x family on
the REAL fixture) was measured UNMEETABLE on the Xbot walk (the clip
carries NO root motion — the corrected finding, A3), so per Annex A.2 the
L7 ledger row ends REFUSED-with-evidence: walk-in-place ships. THIS gate
certifies the machinery that the evidence rides on — every bar here is
mechanical and reproducible:

1. ROOT-TRACK-GT   — the drift fixture (authored world-planted walk with a
                     KNOWN 0.03 m/frame hips translation), built at gate
                     time, bridge-sampled with the root track, converted:
                     the recovered track matches the authored curve within
                     0.005 canon, the plants land on the observable stance
                     structure, and the root-aware lock zeroes the stored
                     glide at the >= 5x family (SYNTHETIC-labeled).
2. ROOT-INPLACE    — a ZERO track reduces detect + lock to the in-place
                     path byte-identically (interval structure AND locked
                     positions), with the loud no-drift note.
3. ROOT-BAKE       — the REAL bake: the root-motion-locked action bakes
                     onto the metarig through the add-on's bake_action and
                     re-evaluates from the fcurves within the 0.5 deg
                     family (the certified apply path is untouched).
4. ROOT-REFUSE     — partial track coverage / empty action refuse LOUD; a
                     no-drift stream delegates byte-identically, loudly.
5. ROOT-XBOT       — the corrected finding (SKIPPED honestly without the
                     glb): the walk clip's hips track span is ~0 (no
                     translatable drift in the file), both models find the
                     same 0 plants — the model degenerates to the status
                     quo on a no-drift clip, byte-identical by contract.
6. ROOT-DETERM     — twin tracks + twin locks byte-identical.

Usage: blender -b --python xtask/root_motion_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR, RM_METARIG_BLEND;
RM_MOTION_XBOT overrides the Xbot.glb path.
Prints RM_ROOT lines; exit 0 only if every row PASSes.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.environ["RM_CORE_SRC"])
sys.path.insert(0, os.environ["RM_ADDON_DIR"])

import bpy  # noqa: E402
import riggermortis as core  # noqa: E402
from mathutils import Vector  # noqa: E402
from riggermortis.canonical_pose import TORSO_SPAN  # noqa: E402
from riggermortis.contacts import (  # noqa: E402
    LOCK_NOTE_SUFFIX,
    detect_contacts,
    lock_feet,
)
from riggermortis.root_motion import (  # noqa: E402
    SOURCE_CLIP,
    DriftTrack,
    detect_contacts_root_aware,
    lock_feet_root_aware,
)
from riggermortis_addon import bake, bpy_bridge, clip_sample, pose_apply  # noqa: E402

OK = True
TRACK_BAR = 0.005  # canon — the RM_MOTION round-trip family (declared)
RATIO_BAR = 5.0  # the >= 5x family (Annex A.1)
REEVAL_BAR_DEG = 0.5  # the FK family
DRIFT_STEP_M = (0.0, -0.03, 0.0)  # the authored world drift per frame
NO_TRANSLATION_SPAN = 0.01  # canon — "no translatable drift in the file"
AUTHORED_STANCES = (("foot.L", ((1, 12), (25, 36), (49, 49))),
                    ("foot.R", ((13, 24), (37, 48))))


def check(label: str, ok: bool, detail: str = "") -> bool:
    global OK
    if not ok:
        OK = False
    print(f"RM_ROOT {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


def observable_phases():
    out = []
    for foot, spans in AUTHORED_STANCES:
        for a, b in spans:
            if a + 1 <= b:  # the landing frame carries approach speed
                out.append((foot, a + 1, b))
    return sorted(out)


def load_fixture_builder():
    path = Path(__file__).resolve().parent / "motion_fixture.py"
    spec = importlib.util.spec_from_file_location("rm_motion_fixture_gate", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def sample_in_process(model: Path, out: Path, *, action: str | None = None,
                      root_track: bool) -> dict:
    report = clip_sample.sample_clip(
        str(model), str(out), core, bpy_bridge, action=action,
        root_track=root_track
    )
    for line in report["lines"]:
        print(line)
    if not report["determ"]:
        raise RuntimeError(f"sampler DETERM FAIL for {model}")
    return json.loads(Path(out).read_text(encoding="utf-8"))


def intervals_of(report):
    return sorted((iv.foot, iv.start, iv.end) for iv in report.intervals)


def first_armature():
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE":
            return obj
    raise RuntimeError("no armature found in scene")


def metarig():
    bpy.ops.wm.open_mainfile(filepath=os.environ["RM_METARIG_BLEND"])
    obj = first_armature()
    mapping = pose_apply.mapping_from_props(obj, core) or core.map_rig(
        core.RigData.from_dict(bpy_bridge.rig_data_from_armature(obj))
    )
    return obj, mapping


def build_drift_action(tmp: Path, *, drift: bool):
    """Build + sample + convert the walking fixture; returns
    (action, clip dict)."""
    fixture = load_fixture_builder()
    bvh = tmp / ("drift_walk.bvh" if drift else "walk_ip.bvh")
    clip_json = tmp / ("drift_walk.clip.json" if drift else "walk_ip.clip.json")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    obj = fixture.build_humanoid("rm_motion_fixture_gate")
    fixture.key_walk(obj, drift=DRIFT_STEP_M if drift else (0.0, 0.0, 0.0))
    fixture.export_bvh(obj, bvh)
    bpy.ops.wm.read_factory_settings(use_empty=True)  # wipe the build scene
    clip = sample_in_process(bvh, clip_json, root_track=drift)
    return core.action_from_clip(core.MotionClip.from_dict(clip)), clip


def reeval(obj, mapping, frames):
    """Independent fcurve re-evaluation (the RM_MOTION REEVAL recipe):
    mapped-role bone world directions vs the canonical targets."""
    worst, checked = 0.0, 0
    step = max(1, len(frames) // 6)
    for af in frames[::step]:
        bpy.context.scene.frame_set(af.frame)
        bpy.context.view_layer.update()
        for role, assignment in sorted(mapping.assignments.items()):
            target = core.bone_target_direction(af.pose, role)
            if target is None:
                continue
            pb = obj.pose.bones.get(assignment.bone)
            if pb is None:
                continue
            d = (pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
            checked += 1
            worst = max(worst, math.degrees(d.angle(Vector(target).normalized())))
    return checked, worst


def rows_track_gt(tmp: Path) -> None:
    action, clip = build_drift_action(tmp, drift=True)
    track = action.root_track
    if track is None or clip["format"] != 2:
        check("ROOT-TRACK-GT", False, "no track attached / not format 2")
        return
    k = TORSO_SPAN / clip["scale_ref"]
    ref = track.ref_frame
    worst = max(
        math.dist(
            track.at(f),
            (DRIFT_STEP_M[0] * k * (f - ref), DRIFT_STEP_M[1] * k * (f - ref),
             DRIFT_STEP_M[2] * k * (f - ref)),
        )
        for f in track.frames()
    )
    ok = check(
        "ROOT-TRACK-RECOVERY", worst <= TRACK_BAR,
        f"max_err={worst:.6f} canon (bar {TRACK_BAR}) k={k:.4f} "
        f"path={track.path_length():.4f}u span={track.span():.4f}u "
        "[SYNTHETIC, prior-consistent GT; the optimism caveat: measured on "
        "synthetic prior-consistent ground truth; real-detector noise is "
        "not in these numbers]",
    )
    frames = [core.ActionFrame(frame=af.frame, pose=af.pose) for af in action.frames]
    aware = detect_contacts_root_aware(frames, track)
    ok &= check(
        "ROOT-TRACK-PLANTS",
        intervals_of(aware) == observable_phases(),
        f"intervals={intervals_of(aware)} (authored stances, landing frames "
        "excluded by the enter contract)",
    )
    locked, lock_rep, _rep = lock_feet_root_aware(
        core.action_from_poses([(af.frame, af.pose) for af in frames]), track)
    before = lock_rep.slide_before.total if lock_rep.slide_before else 0.0
    after = lock_rep.slide_after.total if lock_rep.slide_after else 0.0
    ratio = (before / after) if after > 1e-12 else float("inf")
    ok &= check(
        "ROOT-TRACK-FIX", ratio >= RATIO_BAR,
        f"slide {before:.4f}u -> {after:.4f}u = {ratio:.1f}x "
        f"(bar >= {RATIO_BAR:.0f}x, the Annex family; the in-place reading "
        "of the same action misreads the glide — see docs/ROOT_MOTION.md)",
    )
    check("ROOT-TRACK-GT", ok)
    return


def rows_inplace(tmp: Path) -> None:
    action, clip = build_drift_action(tmp, drift=False)
    if action.root_track is not None or clip["format"] != 1:
        check("ROOT-INPLACE", False, "format-1 clip attached a track / wrong format")
        return
    frames = [core.ActionFrame(frame=af.frame, pose=af.pose) for af in action.frames]
    zero = DriftTrack.from_samples(
        {af.frame: (0.0, 0.0, 0.0) for af in action.frames}, source=SOURCE_CLIP
    )
    plain_detect = detect_contacts(frames)
    aware_detect = detect_contacts_root_aware(frames, zero)
    struct_equal = (
        intervals_of(plain_detect) == intervals_of(aware_detect)
        and plain_detect.in_contact == aware_detect.in_contact
        and plain_detect.ground == aware_detect.ground
        and all(n in aware_detect.notes for n in plain_detect.notes)
    )
    plain_action = core.action_from_poses(
        [(af.frame, af.pose) for af in frames])
    plain_locked, _pl = lock_feet(plain_action, plain_detect)
    aware_locked, _al, _r = lock_feet_root_aware(plain_action, zero)
    positions_equal = all(
        a.pose.positions == b.pose.positions
        for a, b in zip(plain_locked.frames, aware_locked.frames, strict=True)
    )
    notes_honest = (
        any("no drift measured" in n for n in aware_locked.notes)
        and not any(n.endswith(LOCK_NOTE_SUFFIX) for n in aware_locked.notes)
    )
    check(
        "ROOT-INPLACE",
        struct_equal and positions_equal and notes_honest,
        f"zero-track detect structure equal={struct_equal} locked positions "
        f"equal={positions_equal} honest notes={notes_honest} "
        f"({len(plain_detect.intervals)} interval(s) on the in-place fixture)",
    )


def rows_bake(tmp: Path) -> None:
    action, _clip = build_drift_action(tmp, drift=True)
    track = action.root_track
    frames = [core.ActionFrame(frame=af.frame, pose=af.pose) for af in action.frames]
    locked, lock_rep, report = lock_feet_root_aware(
        core.action_from_poses([(af.frame, af.pose) for af in frames]), track)
    obj, mapping = metarig()
    rep = bake.bake_action(
        obj, locked.frames, core, name="rm_root_locked", frame_offset=0,
        contacts=report,
    )
    baked_ok = (
        len(rep["baked_frames"]) == len(locked.frames)
        and rep["worst_deg"] <= REEVAL_BAR_DEG
    )
    check(
        "ROOT-BAKE", baked_ok,
        f"frames={len(rep['baked_frames'])} keys={rep['keys']} "
        f"worst={rep['worst_deg']:.4f}deg (bar {REEVAL_BAR_DEG}) "
        f"locked={rep['locked_frames']} mapping={rep['mapping_source']} "
        "(the certified bake path is untouched by the root-aware pass)",
    )
    checked, worst = reeval(obj, mapping, locked.frames)
    check(
        "ROOT-REEVAL", worst <= REEVAL_BAR_DEG,
        f"checked={checked} worst={worst:.4f}deg bar<={REEVAL_BAR_DEG}deg",
    )


def rows_refuse(tmp: Path) -> None:
    action, _clip = build_drift_action(tmp, drift=True)
    track = action.root_track
    frames = [core.ActionFrame(frame=af.frame, pose=af.pose) for af in action.frames]
    partial = DriftTrack.from_samples(
        {f: v for f, v in list(track.translations.items())[: len(frames) // 2]},
        source=SOURCE_CLIP,
    )
    refused = 0
    try:
        detect_contacts_root_aware(frames, partial)
    except core.RootMotionError as exc:
        refused += 1 if "lack a drift-track entry" in str(exc) else 0
    try:
        lock_feet_root_aware(
            core.action_from_poses([(af.frame, af.pose) for af in frames]),
            partial)
    except core.RootMotionError as exc:
        refused += 1 if "lack a drift-track entry" in str(exc) else 0
    try:
        lock_feet_root_aware(core.action_from_poses([]), track)
    except core.RootMotionError as exc:
        refused += 1 if "no frames" in str(exc) else 0
    zero = DriftTrack.from_samples(
        {af.frame: (0.0, 0.0, 0.0) for af in frames}, source=SOURCE_CLIP)
    plain_detect = detect_contacts(frames)
    aware_detect = detect_contacts_root_aware(frames, zero)
    delegated = (
        intervals_of(plain_detect) == intervals_of(aware_detect)
        and any("no drift measured" in n for n in aware_detect.notes)
    )
    check(
        "ROOT-REFUSE", refused == 3 and delegated,
        f"loud refusals={refused}/3 (partial detect, partial lock, empty "
        f"action); no-drift stream delegated byte-identically={delegated}",
    )


def rows_xbot(tmp: Path) -> None:
    glb = Path(os.environ.get(
        "RM_MOTION_XBOT",
        str(Path(__file__).resolve().parent.parent / "out" / "real_rigs" / "Xbot.glb")))
    if not glb.is_file():
        check("ROOT-XBOT", True,
              "SKIPPED (Xbot.glb not found; set RM_MOTION_XBOT)")
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    clip = sample_in_process(glb, tmp / "xbot_walk.clip.json",
                             action="walk", root_track=True)
    action = core.action_from_clip(core.MotionClip.from_dict(clip))
    track = action.root_track
    if track is None:
        check("ROOT-XBOT", False, "real clip carried no root track")
        return
    frames = [core.ActionFrame(frame=af.frame, pose=af.pose) for af in action.frames]
    plain = detect_contacts(frames)
    aware = detect_contacts_root_aware(frames, track)
    no_translation = track.span() <= NO_TRANSLATION_SPAN
    check(
        "ROOT-XBOT",
        len(plain.intervals) == 0 and len(aware.intervals) == 0
        and no_translation,
        f"the corrected finding (docs/ROOT_MOTION.md A3): hips track "
        f"span={track.span():.4f}u <= {NO_TRANSLATION_SPAN} = NO translatable "
        f"drift in the file (path={track.path_length():.4f}u is sway/bounce); "
        f"plants in-place={len(plain.intervals)} "
        f"root-aware={len(aware.intervals)} — the model degenerates to the "
        "status quo on a no-drift clip; the >= 5x demonstration lives on "
        "ROOT-TRACK-GT (SYNTHETIC). L7 ends REFUSED-with-evidence per "
        "Annex A.2: walk-in-place ships.",
    )


def rows_determ(tmp: Path) -> None:
    action, _clip = build_drift_action(tmp, drift=True)
    a2 = core.action_from_clip(core.MotionClip.from_dict(json.loads(
        (tmp / "drift_walk.clip.json").read_text(encoding="utf-8"))))
    t1, t2 = action.root_track, a2.root_track
    same_track = t1 == t2
    l1, r1, d1 = lock_feet_root_aware(action, t1)
    l2, r2, d2 = lock_feet_root_aware(a2, t2)
    same_lock = l1 == l2 and r1 == r2 and d1 == d2
    check(
        "ROOT-DETERM", same_track and same_lock,
        f"twin tracks equal={same_track} twin detect+lock equal={same_lock}",
    )


def main() -> int:
    global OK
    with tempfile.TemporaryDirectory(prefix="rm_root_gate_") as td:
        tmp = Path(td)
        rows_track_gt(tmp)
        rows_inplace(tmp)
        rows_bake(tmp)
        rows_refuse(tmp)
        rows_xbot(tmp)
        rows_determ(tmp)
    print(f"RM_ROOT GATE: {'PASS' if OK else 'FAIL'}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
