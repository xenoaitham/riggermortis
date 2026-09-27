"""P8-8 capability probe: the scene-animation unknowns, answered by DOING
them (the root_motion_probe recipe; design of record docs/SCENE_ANIMATION.md
— written BEFORE the build, bars pre-declared). The DRAFT pass that earned
the amendments now lives in core `scene_anim.py` (the ONE copy — the
clip_sample promotion rule); this probe exercises THE CORE through the
fixture below.

Rows (RM_SANIM lines; exit 0 only if every row PASSes; the BAKE-COST row
SKIPPED counts as answered only without RM_METARIG_BLEND — the GATE
measures it unconditionally):

1. FIXTURE    — the deterministic two-person stream written as REAL v3
                payload files + a job state (the P2-1 container shape) and
                loaded back through the core loader: counts, labels,
                bboxes, poses all present.
2. IDENTITY   — the swap rate on the PRIMARY classes (bar <= 0.02): the
                assignment follows pose+scale identity through BOTH
                authored label-swap events (frames 25 and 36) with ZERO
                output swaps expected. The AMBIGUITY class (scales
                equalized through the converged window) measured and
                reported SEPARATELY (the declared single-view limit).
3. ALARM      — the evidence alarms fire within the halo (2 frames) of
                both authored events (catch >= 0.90, the Annex bar); both
                cost-jump distributions published with the margins' place
                in the gap (the strike-S12 derivation pattern).
4. COUPLING   — the authored wrist pin, closed per frame by the UNTOUCHED
                P8-2 pass with placements MEASURED from the stream: the
                authored-contact window (frames 12-24) closes at
                residual_frac < 0.02; beyond-reach frames report
                unclosable LOUD (the REACH honesty, per frame).
5. BAKE-COST  — the REAL addon bake over BOTH characters' actions (two
                metarig armatures, one scene), wall-clock measured and
                published per frame (Annex: measured + PUBLISHED before
                any claim). SKIPPED honestly without RM_METARIG_BLEND.
6. TRACKS     — per-character drift tracks (S32's constructor, reused
                verbatim): the crossing visible in both paths, depth
                exactly zero, the APPROXIMATE label present.
7. REFUSE     — single-figure stream / missing-character frame /
                uncomparable pairing / empty stream: 4/4 loud with hints.
8. OVERRIDE   — an authored override contradicting the solved assignment
                on the ambiguity window wins, marks the frame, reports
                the disagreement, and is excluded from the automatic rate.
9. DETERM     — twin streams: twin actions + twin reports + twin
                couplings byte-identical.

Usage: blender -b --python xtask/scene_anim_probe.py
Env: RM_CORE_SRC, RM_ADDON_DIR, RM_METARIG_BLEND (optional, bake row).
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.environ.get(
    "RM_CORE_SRC", str(Path(__file__).resolve().parent.parent / "core" / "src")))
sys.path.insert(0, os.environ.get(
    "RM_ADDON_DIR", str(Path(__file__).resolve().parent.parent / "addon")))

import riggermortis as core  # noqa: E402
from riggermortis.canonical_pose import CanonicalPose, rest_skeleton  # noqa: E402
from riggermortis.coupling import BAR_FRAC  # noqa: E402
from riggermortis.errors import SceneError  # noqa: E402
from riggermortis.root_motion import SOURCE_VIDEO  # noqa: E402
from riggermortis.scene import ContactPin  # noqa: E402
from riggermortis.scene_anim import (  # noqa: E402
    ALARM_ABS,
    ALARM_HALO,
    StreamFigure,
    StreamFrame,
    assign_stream,
    couple_scene_action,
    load_scene_frames,
    track_for_character,
)

try:  # bpy exists only inside Blender (the probe always runs there)
    import bpy  # noqa: F401
except ImportError:  # pragma: no cover
    bpy = None  # type: ignore[assignment]

OK = True

# -- fixture constants (the authored stream; bars live in the Annex) ----------
N_FRAMES = 49             # 1-based source frame indices
CHARACTERS = ("A", "B")
A_SCALE, B_SCALE = 50.0, 62.5   # px per canonical unit — the identity scale
EVENT_1 = 25              # the crossing glitch (labels permute, sides swap)
EVENT_2 = 36              # the second glitch inside the converged window
CONVERGED_LO, CONVERGED_HI = 30, 40   # identical pose shapes (scales distinct)
CONTACT_LO, CONTACT_HI = 12, 24       # the frames the authored pin represents
FLIP_KEYS = ("forearm.L", "forearm.R", "lower_leg.L", "lower_leg.R")


def check(label: str, ok: bool, detail: str = "") -> bool:
    global OK
    if not ok:
        OK = False
    print(f"RM_SANIM {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


# -- the fixture (engine-built, deterministic; the A.3 fixture law) -----------


def _pose(positions: dict[str, tuple[float, float, float]],
          scale: float) -> CanonicalPose:
    return CanonicalPose(
        positions={r: (p[0], p[1], p[2]) for r, p in sorted(positions.items())},
        flips={k: -1 for k in FLIP_KEYS},
        confidence=1.0,
        reliable=True,
        scale=scale,
        anchor="hips",
        notes=[],
        joint_confidence={},
    )


def _rest() -> dict[str, tuple[float, float, float]]:
    rest = rest_skeleton(1.0 / 0.55)  # hip height 1.0 -> TORSO_SPAN 0.45
    return {r: (v[0][0], v[0][1], v[0][2]) for r, v in sorted(rest.items())}


REST = _rest()


def pose_a(f: int) -> CanonicalPose:
    """Character A: left arm raised high (the distinct shape), gentle sway."""
    p = dict(REST)
    phase = 2.0 * math.pi * (f % 24) / 24.0
    ua = p["upper_arm.L"]
    p["forearm.L"] = (ua[0] + 0.18, ua[1], ua[2] + 0.30 + 0.02 * math.sin(phase))
    p["hand.L"] = (ua[0] + 0.28, ua[1], ua[2] + 0.50 + 0.02 * math.sin(phase))
    return _pose(p, A_SCALE)


def pose_b(f: int) -> CanonicalPose:
    """Character B: arms lowered (the other distinct shape), small bounce."""
    p = dict(REST)
    phase = 2.0 * math.pi * (f % 24) / 24.0
    drop = 0.35 + 0.02 * math.sin(phase)
    p["forearm.L"] = (0.30, 0.0, p["chest"][2] - drop + 0.12)
    p["hand.L"] = (0.34, 0.0, p["chest"][2] - drop)
    p["forearm.R"] = (-0.30, 0.0, p["chest"][2] - drop + 0.12)
    p["hand.R"] = (-0.34, 0.0, p["chest"][2] - drop)
    return _pose(p, B_SCALE)


def authored_pose(character: str, f: int, *,
                  ambiguity: bool = False) -> CanonicalPose:
    """The AUTHORED ground truth: whose body is whose. The converged window
    makes the shapes identical (the hard class); `ambiguity` equalizes the
    scales too — the declared unresolvable class."""
    if CONVERGED_LO <= f <= CONVERGED_HI:
        scale = A_SCALE if (character == "A" or ambiguity) else B_SCALE
        return _pose(pose_b(f).positions, scale)
    return pose_a(f) if character == "A" else pose_b(f)


def authored_label(character: str, f: int) -> str:
    """Which DETECTOR label carries this character's data at frame f — the
    authored label permutation (the events at 25 and 36)."""
    flipped = EVENT_1 <= f < EVENT_2
    if (character == "A") != flipped:
        return "figure 1"
    return "figure 2"


def bbox_center_for(character: str, f: int) -> tuple[float, float]:
    """The bbox centers hold a constant 25 px contact half-separation
    (the pair stands 50 px = 1.0 scene unit apart — anatomically inside
    the arm chains' combined reach, so an authored hand-holding pin is
    closable) and SWAP SIDES in ONE frame at 25: the authored detector-
    class glitch that drags the per-frame labels with it."""
    side = -1.0 if f < EVENT_1 else 1.0  # A starts left of the pair center
    cx_a = 320.0 + side * 25.0
    cx = cx_a if character == "A" else 640.0 - cx_a
    cy = 240.0 + 4.0 * math.sin(2.0 * math.pi * f / 24.0)
    return (cx, cy)


def build_stream(*, ambiguity: bool = False) -> list[StreamFrame]:
    frames = []
    for f in range(1, N_FRAMES + 1):
        figs = []
        for character in CHARACTERS:
            pose = authored_pose(character, f, ambiguity=ambiguity)
            if ambiguity and CONVERGED_LO <= f <= CONVERGED_HI \
                    and character == "B":
                pose = _pose(pose.positions, A_SCALE)  # scales equalized
            cx, cy = bbox_center_for(character, f)
            figs.append(StreamFigure(
                label=authored_label(character, f), pose=pose,
                bbox_center=(cx, cy)))
        frames.append(StreamFrame(
            frame=f, figures=tuple(sorted(figs, key=lambda x: x.label))))
    return frames


def write_job_dir(stream: list[StreamFrame], job_dir: Path) -> None:
    """Write the fixture as a REAL P2-1 job container (v3 payloads + state).
    The payloads carry the animation-relevant contract fields (format,
    figures[] with label/index/score/bbox/pose); rotations/skipped are
    empty (the animation path reads pose + bbox only)."""
    job_dir.mkdir(parents=True)
    done: dict[int, str] = {}
    for sf in stream:
        entries = []
        for fig in sf.figures:
            entries.append({
                "label": fig.label,
                "index": len(entries),
                "score": 0.9,
                "bbox": [
                    fig.bbox_center[0] - 35.0, fig.bbox_center[1] - 90.0,
                    fig.bbox_center[0] + 35.0, fig.bbox_center[1] + 90.0,
                ],
                "pose": fig.pose.to_dict(),
                "rotations": [],
                "skipped": [],
                "notes": [],
            })
        payload = {
            "format": 3,
            "image": {"path": f"frame_{sf.frame:06d}.png",
                      "width": 640, "height": 480},
            "figures": entries,
            "pins": [],
        }
        rel = f"frame_{sf.frame:06d}.json"
        (job_dir / rel).write_text(
            json.dumps(payload, sort_keys=True), encoding="utf-8")
        done[sf.frame] = rel
    state = {
        "format": 1,
        "source": "scene-anim-fixture",
        "rig": "fixture",
        "stride": 1,
        "frames": [f"frame_{f:06d}.json" for f in range(1, N_FRAMES + 1)],
        "done": {str(k): done[k] for k in sorted(done)},
        "notes": [],
    }
    (job_dir / "job.json").write_text(
        json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


# -- rows ----------------------------------------------------------------------


def row_fixture(tmp: Path) -> list[StreamFrame]:
    stream = build_stream()
    job = tmp / "job"
    write_job_dir(stream, job)
    loaded = load_scene_frames(job)
    ok = len(loaded) == N_FRAMES
    n_labels = sum(len(sf.figures) for sf in loaded)
    ok &= n_labels == 2 * N_FRAMES
    centers_ok = all(
        f.bbox_center is not None for sf in loaded for f in sf.figures)
    ok &= centers_ok
    good = check(
        "FIXTURE", ok,
        f"frames={len(loaded)}/{N_FRAMES} figures={n_labels} "
        f"bbox_centers={centers_ok} (REAL v3 payloads + job state, loaded "
        "back through the core container path)",
    )
    if not good:
        raise RuntimeError("fixture row failed; aborting the probe")
    return loaded


def swap_stats(action) -> tuple[int, int]:
    """(swapped_frames, solved_frames) against the AUTHORED ground truth;
    overridden frames are excluded (authored is not inferred)."""
    swapped = 0
    solved = 0
    for af in action.frames:
        if af.overridden:
            continue
        solved += 1
        for ch, lab in af.assignment.items():
            if authored_label(ch, af.frame) != lab:
                swapped += 1
                break
    return swapped, solved


def row_identity() -> tuple[object, object]:
    action, report = assign_stream(build_stream(), characters=CHARACTERS)
    swapped, solved = swap_stats(action)
    rate = swapped / solved if solved else 1.0
    check(
        "IDENTITY", rate <= 0.02,
        f"swap_rate={rate:.4f} ({swapped}/{solved} solved frames, bar <= "
        f"0.02); failed={action.failed} (gaps stay gaps); "
        f"extras={report.extras}",
    )
    amb_action, _amb_rep = assign_stream(
        build_stream(ambiguity=True), characters=CHARACTERS)
    a_swapped, a_solved = swap_stats(amb_action)
    a_rate = a_swapped / a_solved if a_solved else 1.0
    check(
        "AMBIGUITY", True,
        f"the declared single-view limit: swap_rate={a_rate:.4f} "
        f"({a_swapped}/{a_solved} frames) — identity events inside the "
        "equal-pose equal-scale window are unresolvable from single-view "
        "keypoints; reported SEPARATELY, never averaged into the primary "
        "rate; the manual override is the answer (OVERRIDE row)",
    )
    return action, report


def row_alarm(report) -> None:
    events = (EVENT_1, EVENT_2)
    caught = sum(
        1 for e in events
        if any(a.kind == "evidence" and abs(a.frame - e) <= ALARM_HALO
               for a in report.alarms))
    catch_rate = caught / len(events)
    event_j = [a for f, a, _r in report.jumps if f in events]
    other_j = [a for f, a, _r in report.jumps if f not in events]
    min_ev = min(event_j, default=float("inf"))
    max_other = max((j for j in other_j if math.isfinite(j)), default=0.0)
    check(
        "ALARM", catch_rate >= 0.90,
        f"caught {caught}/{len(events)} authored events within the halo "
        f"(bar >= 0.90); the jump distributions: event frames "
        f"min_abs={min_ev:.4f} vs non-event max_abs={max_other:.4f} — "
        f"ALARM_ABS={ALARM_ABS} sits in the gap (ALARM_REL guards the "
        "near-zero-cost class); both constants published here (the "
        "strike-S12 derivation pattern)",
    )


def row_coupling(stream: list[StreamFrame]) -> None:
    pin = ContactPin(figure_a="A", role_a="hand.L",
                     figure_b="B", role_b="hand.R",
                     origin="authored", confidence=1.0)
    # the pin rides EVERY solved frame's scene (authored once, coupled per
    # frame — the scene-action contract); placements are MEASURED
    action, _rep = assign_stream(
        build_stream(), characters=CHARACTERS, pins=(pin,))
    coupled = couple_scene_action(action, stream)
    worst_win = 0.0
    closed_win = 0
    loud_reach = 0
    for frame, _scene, c_report in coupled:
        row = c_report.rows[0] if c_report.rows else None
        if row is None or not row.enforced:
            continue
        if row.closed:
            if CONTACT_LO <= frame <= CONTACT_HI:
                worst_win = max(worst_win, row.residual_frac)
                closed_win += 1
        elif frame < CONTACT_LO or frame > CONTACT_HI:
            loud_reach += 1
    check(
        "COUPLING", worst_win < BAR_FRAC and closed_win > 0 and loud_reach > 0,
        f"authored-contact window ({CONTACT_LO}-{CONTACT_HI}): "
        f"closed={closed_win} worst_frac={worst_win:.6f} (bar {BAR_FRAC}); "
        f"beyond-reach frames reporting unclosable LOUD={loud_reach} (the "
        "P8-2 REACH honesty, per frame; placements MEASURED from the stream "
        "bboxes — in-plane only, APPROXIMATE-labeled, depth never guessed)",
    )


def scene_figure_pose(scene, label: str) -> CanonicalPose:
    return next(f.pose for f in scene.figures if f.label == label)


def row_bake_cost(action) -> None:
    metarig = os.environ.get("RM_METARIG_BLEND", "")
    if not metarig or not Path(metarig).is_file() or bpy is None:
        check("BAKE-COST", True,
              "SKIPPED (RM_METARIG_BLEND not set — the GATE measures this "
              "row unconditionally)")
        return
    from riggermortis_addon import bake  # noqa: E402 — inside Blender only
    actions = {}
    for ch in CHARACTERS:
        pairs = [(af.frame, scene_figure_pose(af.scene, ch))
                 for af in action.frames]
        actions[ch] = core.action_from_poses(
            pairs, notes=["scene-anim fixture"])
    bpy.ops.wm.open_mainfile(filepath=metarig)
    src = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    objs = [src]
    for ch in CHARACTERS[1:]:
        obj = src.copy()
        obj.data = src.data.copy()
        obj.name = f"rm_sanim_{ch}"
        bpy.context.scene.collection.objects.link(obj)
        objs.append(obj)
    t0 = time.perf_counter()
    frames_baked = 0
    worst_deg = 0.0
    for ch, obj in zip(CHARACTERS, objs, strict=True):
        rep_bake = bake.bake_action(
            obj, actions[ch].frames, core,
            name=f"rm_sanim_{ch}", frame_offset=0)
        frames_baked += len(rep_bake["baked_frames"])
        worst_deg = max(worst_deg, rep_bake["worst_deg"])
    dt = time.perf_counter() - t0
    per_frame = dt / max(frames_baked, 1)
    check(
        "BAKE-COST", frames_baked == len(CHARACTERS) * len(action.frames),
        f"the REAL bake over BOTH characters: {frames_baked} frame-bakes "
        f"in {dt:.3f}s = {per_frame * 1000.0:.1f} ms/frame-bake "
        f"({per_frame * len(CHARACTERS) * 1000.0:.1f} ms per scene-frame "
        f"across {len(CHARACTERS)} rigs, worst FK {worst_deg:.4f} deg) "
        "[mid-laptop baseline, MEASURED — PUBLISHED here before any claim, "
        "the Annex bar]",
    )


def row_tracks(stream: list[StreamFrame], action) -> None:
    assignment_of = {af.frame: af.assignment for af in action.frames}
    ta = track_for_character(stream, assignment_of, "A")
    tb = track_for_character(stream, assignment_of, "B")
    assert ta is not None and tb is not None
    cross = math.dist(ta.at(1), ta.at(N_FRAMES))
    depth_ok = all(v[1] == 0.0 for t in (ta, tb)
                   for v in t.translations.values())
    label_ok = ta.source == SOURCE_VIDEO and any(
        "APPROXIMATE" in n for n in ta.notes)
    check(
        "TRACKS", depth_ok and label_ok and cross > 0.9,
        f"per-character tracks (S32 verbatim): A path={ta.path_length():.4f}u "
        f"ref->end span={cross:.4f}u (the side swap is IN the track); depth "
        f"exactly zero={depth_ok}; APPROXIMATE-labeled={label_ok}",
    )


def row_refuse() -> None:
    refused = 0
    details = []
    # 1. a single-figure stream into a two-character roster
    thin = [StreamFrame(frame=1,
                        figures=(build_stream()[0].figures[0],))]
    action, report = assign_stream(thin, characters=CHARACTERS)
    if action.failed == [1] and any("missing" in n for n in report.notes):
        refused += 1
        details.append("single-figure->missing")
    # 2. a missing-character frame mid-stream
    two = build_stream()[:5]
    hole = StreamFrame(frame=3, figures=(two[2].figures[0],))
    action2, _r2 = assign_stream(two[:2] + [hole] + two[3:],
                                 characters=CHARACTERS)
    if 3 in action2.failed:
        refused += 1
        details.append("mid-stream-hole")
    # 3. an uncomparable pairing (a figure with too few common roles),
    #    solved from frame 2 so the cost matrix is live
    p = dict(REST)
    stub = _pose({k: p[k] for k in ("hips", "spine", "chest")}, 50.0)
    sparse = StreamFrame(
        frame=2,
        figures=(StreamFigure("figure 1", stub, (100.0, 100.0)),
                 StreamFigure("figure 2", pose_a(2), (400.0, 240.0))),
    )
    try:
        assign_stream(two[:1] + [sparse], characters=CHARACTERS)
    except SceneError as exc:
        if "uncomparable" in str(exc):
            refused += 1
            details.append("uncomparable")
    # 4. an empty stream refuses LOUD
    try:
        assign_stream([], characters=CHARACTERS)
    except SceneError:
        refused += 1
        details.append("empty-stream")
    check(
        "REFUSE", refused == 4,
        f"loud refusals={refused}/4 ({', '.join(details)}); zero guessed "
        "frames anywhere",
    )


def row_override() -> None:
    amb = build_stream(ambiguity=True)
    # a PARTIAL override (character A only): the free solve on the
    # equal-pose equal-scale tie would keep A on 'figure 1' (the keyed
    # order); the artist's word moves A to 'figure 2' and B follows by
    # elimination — the disagreement is reported verbatim
    overrides = {EVENT_2: {"A": "figure 2"}}
    action, report = assign_stream(
        amb, characters=CHARACTERS, overrides=overrides)
    af = next(a for a in action.frames if a.frame == EVENT_2)
    wins = (af.assignment.get("A") == "figure 2"
            and af.assignment.get("B") == "figure 1")
    disagrees = any("override wins" in d for d in report.disagreements)
    check(
        "OVERRIDE", wins and af.overridden
        and EVENT_2 in report.overridden_frames and disagrees,
        f"the authored override wins on frame {EVENT_2} (the free solve "
        f"said 'figure 1' — the keyed tie on identical pose+scale — the "
        f"artist said 'figure 2'; final assignment {af.assignment}); frame "
        "marked overridden=True; the solve-vs-authored disagreement is "
        "reported verbatim; overridden frames are EXCLUDED from the "
        "automatic swap rate",
    )


def row_determ() -> None:
    a1, r1 = assign_stream(build_stream(), characters=CHARACTERS)
    a2, r2 = assign_stream(build_stream(), characters=CHARACTERS)
    same_action = a1 == a2
    same_report = r1 == r2
    stream = build_stream()
    pin = ContactPin(figure_a="A", role_a="hand.L",
                     figure_b="B", role_b="hand.R",
                     origin="authored", confidence=1.0)
    act_c, _rc = assign_stream(
        build_stream(), characters=CHARACTERS, pins=(pin,))
    c1 = couple_scene_action(act_c, stream)
    c2 = couple_scene_action(act_c, stream)
    same_couple = c1 == c2
    check(
        "DETERM", same_action and same_report and same_couple,
        f"twin streams: actions equal={same_action} reports "
        f"equal={same_report} couplings equal={same_couple}",
    )


def main() -> int:
    global OK
    with tempfile.TemporaryDirectory(prefix="rm_sanim_probe_") as td:
        tmp = Path(td)
        stream = row_fixture(tmp)
        action, report = row_identity()
        row_alarm(report)
        row_coupling(stream)
        row_bake_cost(action)
        row_tracks(stream, action)
        row_refuse()
        row_override()
        row_determ()
    print(f"RM_SANIM: {'PASS' if OK else 'FAIL'}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
