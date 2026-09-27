"""P8-8 scene-animation gate (run INSIDE Blender, headless) — the RM_SANIM
rows.

The sibling of scene_gate/couple_gate/finger_gate/face_gate/camera_gate/
spine_gate/root_motion_gate (the Mimosa new-file rule). Design of record:
docs/SCENE_ANIMATION.md — the pre-declared Annex A.1 bars (identity swap
rate <= 2% of frames on the synthetic fixture; the swap alarm catching
>= 90% of the authored events; per-frame scene bake cost MEASURED and
PUBLISHED before any claim). The fixture builders are imported from the
probe (ONE fixture copy — the motion_fixture rule).

Rows (every row grepped by xtask/verify_pose_apply.sh — Blender can mask a
crashed script with exit 0, so the FINAL row line is the contract):

1. SANIM-FIXTURE    — the two-person stream through a REAL v3 job
                      container + the core loader.
2. SANIM-IDENTITY   — swap rate 0.0000 on the primary classes (bar 0.02);
                      the ambiguity class published separately.
3. SANIM-ALARM      — both authored events caught within the halo
                      (catch 1.00 >= 0.90); the jump distributions with
                      the margins' place in the gap.
4. SANIM-COUPLING   — the authored pin closes on every contact-window
                      frame (worst_frac < 0.02) through the UNTOUCHED P8-2
                      pass with placements MEASURED from the stream;
                      beyond-reach frames loud.
5. SANIM-BAKE-COST  — the REAL bake over BOTH characters (two metarig
                      armatures, one scene), wall-clock per frame,
                      PUBLISHED (the Annex publication bar).
6. SANIM-TRACKS     — per-character drift tracks (S32 verbatim), depth
                      exactly zero, APPROXIMATE-labeled.
7. SANIM-REFUSE     — 4/4 loud refusal classes.
8. SANIM-OVERRIDE   — the authored override wins, marks, reports.
9. SANIM-DETERM     — twin actions + reports + couplings byte-identical.

Usage: blender -b --python xtask/scene_anim_gate.py
Env: RM_CORE_SRC, RM_ADDON_DIR, RM_METARIG_BLEND.
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.environ["RM_CORE_SRC"])
sys.path.insert(0, os.environ["RM_ADDON_DIR"])

import bpy  # noqa: E402
import riggermortis as core  # noqa: E402
from riggermortis.coupling import BAR_FRAC  # noqa: E402
from riggermortis.root_motion import SOURCE_VIDEO  # noqa: E402
from riggermortis.scene import ContactPin  # noqa: E402
from riggermortis.scene_anim import (  # noqa: E402
    ALARM_ABS,
    ALARM_HALO,
    assign_stream,
    couple_scene_action,
    load_scene_frames,
    track_for_character,
)

OK = True

EVENT_1 = 25
EVENT_2 = 36
CONTACT_LO, CONTACT_HI = 12, 24
CHARACTERS = ("A", "B")
N_FRAMES = 49


def check(label: str, ok: bool, detail: str = "") -> bool:
    global OK
    if not ok:
        OK = False
    print(f"RM_SANIM {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


def load_probe_fixture():
    """The fixture builders live in the probe (ONE copy)."""
    path = Path(__file__).resolve().parent / "scene_anim_probe.py"
    spec = importlib.util.spec_from_file_location("rm_sanim_fixture", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def swap_stats(action, authored_label):
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


def main() -> int:
    global OK
    fx = load_probe_fixture()
    with tempfile.TemporaryDirectory(prefix="rm_sanim_gate_") as td:
        tmp = Path(td)

        # 1. the container round trip (REAL v3 payloads + job state)
        stream = fx.build_stream()
        job = tmp / "job"
        fx.write_job_dir(stream, job)
        loaded = load_scene_frames(job)
        ok = (
            len(loaded) == N_FRAMES
            and sum(len(sf.figures) for sf in loaded) == 2 * N_FRAMES
            and all(f.bbox_center is not None
                    for sf in loaded for f in sf.figures)
        )
        check("SANIM-FIXTURE", ok,
              f"frames={len(loaded)}/{N_FRAMES} figures="
              f"{sum(len(sf.figures) for sf in loaded)} (REAL v3 job "
              "container, loaded through the core loader)")

        # 2. the identity bars (Annex A.1: swap <= 0.02 on the fixture)
        action, report = assign_stream(
            fx.build_stream(), characters=CHARACTERS)
        swapped, solved = swap_stats(action, fx.authored_label)
        rate = swapped / solved if solved else 1.0
        ok = rate <= 0.02
        amb_action, _r = assign_stream(
            fx.build_stream(ambiguity=True), characters=CHARACTERS)
        a_swapped, a_solved = swap_stats(amb_action, fx.authored_label)
        a_rate = a_swapped / a_solved if a_solved else 1.0
        check("SANIM-IDENTITY", ok,
              f"swap_rate={rate:.4f} ({swapped}/{solved} solved frames, "
              f"bar <= 0.02); failed={action.failed}; the AMBIGUITY class "
              f"(equal pose AND equal scale through the window) measures "
              f"{a_rate:.4f} separately — the declared single-view limit, "
              "never averaged into the primary rate [SYNTHETIC, "
              "prior-consistent GT; the optimism caveat: measured on "
              "synthetic prior-consistent ground truth; real-detector "
              "noise is not in these numbers; the Annex A.1 re-validation "
              "trigger applies when real labeled fixtures enter the "
              "workflow]")

        # 3. the alarm bar (Annex A.1: catch >= 0.90 within the halo)
        events = (EVENT_1, EVENT_2)
        caught = sum(
            1 for e in events
            if any(a.kind == "evidence" and abs(a.frame - e) <= ALARM_HALO
                   for a in report.alarms))
        catch_rate = caught / len(events)
        event_j = [a for f, a, _r in report.jumps if f in events]
        other_j = [a for f, a, _r in report.jumps if f not in events]
        min_ev = min(event_j, default=float("inf"))
        max_other = max((j for j in other_j if math.isfinite(j)),
                        default=0.0)
        check("SANIM-ALARM", catch_rate >= 0.90,
              f"caught {caught}/{len(events)} authored events within the "
              f"halo (catch {catch_rate:.2f} >= 0.90); the jump "
              f"distributions: event min_abs={min_ev:.4f} vs non-event "
              f"max_abs={max_other:.4f} — ALARM_ABS={ALARM_ABS} sits in "
              "the gap (the strike-S12 derivation pattern; ALARM_REL "
              "guards the near-zero-cost class)")

        # 4. the per-frame coupling bar (the P8-2 2% torso-span family)
        pin = ContactPin(figure_a="A", role_a="hand.L",
                         figure_b="B", role_b="hand.R",
                         origin="authored", confidence=1.0)
        action_c, _rc = assign_stream(
            fx.build_stream(), characters=CHARACTERS, pins=(pin,))
        coupled = couple_scene_action(action_c, loaded)
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
        check("SANIM-COUPLING",
              worst_win < BAR_FRAC and closed_win > 0 and loud_reach > 0,
              f"contact window ({CONTACT_LO}-{CONTACT_HI}): closed="
              f"{closed_win} worst_frac={worst_win:.6f} (bar {BAR_FRAC}); "
              f"beyond-reach frames loud={loud_reach} (the P8-2 REACH "
              "honesty, per frame; placements MEASURED from the stream "
              "bboxes — in-plane only, depth never guessed)")

        # 5. the bake cost, MEASURED + PUBLISHED (the Annex publication bar)
        actions = {}
        for ch in CHARACTERS:
            pairs = [(af.frame, next(f.pose for f in af.scene.figures
                                     if f.label == ch))
                     for af in action.frames]
            actions[ch] = core.action_from_poses(
                pairs, notes=["scene-anim gate fixture"])
        bpy.ops.wm.open_mainfile(filepath=os.environ["RM_METARIG_BLEND"])
        src = next(o for o in bpy.context.scene.objects
                   if o.type == "ARMATURE")
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
            rep = core_bake(obj, actions[ch])
            frames_baked += len(rep["baked_frames"])
            worst_deg = max(worst_deg, rep["worst_deg"])
        dt = time.perf_counter() - t0
        per_frame = dt / max(frames_baked, 1)
        check("SANIM-BAKE-COST",
              frames_baked == len(CHARACTERS) * len(action.frames),
              f"the REAL bake over BOTH characters: {frames_baked} "
              f"frame-bakes in {dt:.3f}s = {per_frame * 1000.0:.1f} "
              f"ms/frame-bake ({per_frame * len(CHARACTERS) * 1000.0:.1f} "
              f"ms per scene-frame across {len(CHARACTERS)} rigs, worst FK "
              f"{worst_deg:.4f} deg) [mid-laptop baseline, MEASURED — "
              "PUBLISHED here before any claim, the Annex bar]")

        # 6. the per-character drift tracks (S32 verbatim)
        assignment_of = {af.frame: af.assignment for af in action.frames}
        ta = track_for_character(loaded, assignment_of, "A")
        tb = track_for_character(loaded, assignment_of, "B")
        cross = math.dist(ta.at(1), ta.at(N_FRAMES))
        depth_ok = all(v[1] == 0.0 for t in (ta, tb)
                       for v in t.translations.values())
        label_ok = ta.source == SOURCE_VIDEO and any(
            "APPROXIMATE" in n for n in ta.notes)
        check("SANIM-TRACKS",
              ta is not None and tb is not None and depth_ok
              and label_ok and cross > 0.9,
              f"A path={ta.path_length():.4f}u ref->end span={cross:.4f}u "
              f"(the side swap is IN the track); depth exactly "
              f"zero={depth_ok}; APPROXIMATE-labeled={label_ok}")

        # 7. the loud refusal classes
        refused = 0
        thin = [fx.StreamFrame(frame=1,
                               figures=(fx.build_stream()[0].figures[0],))]
        a_thin, r_thin = assign_stream(thin, characters=CHARACTERS)
        if a_thin.failed == [1] and any(
                "missing" in n for n in r_thin.notes):
            refused += 1
        two = fx.build_stream()[:5]
        hole = fx.StreamFrame(frame=3, figures=(two[2].figures[0],))
        a_hole, _rh = assign_stream(two[:2] + [hole] + two[3:],
                                    characters=CHARACTERS)
        if 3 in a_hole.failed:
            refused += 1
        stub = fx._pose({k: fx.REST[k]
                         for k in ("hips", "spine", "chest")}, 50.0)
        sparse = fx.StreamFrame(
            frame=2,
            figures=(fx.StreamFigure("figure 1", stub, (100.0, 100.0)),
                     fx.StreamFigure("figure 2", fx.pose_a(2),
                                     (400.0, 240.0))))
        try:
            assign_stream(two[:1] + [sparse], characters=CHARACTERS)
        except core.SceneError as exc:
            if "uncomparable" in str(exc):
                refused += 1
        try:
            assign_stream([], characters=CHARACTERS)
        except core.SceneError:
            refused += 1
        check("SANIM-REFUSE", refused == 4,
              f"loud refusals={refused}/4 (single-figure, missing-"
              "character frame, uncomparable pairing, empty stream); "
              "zero guessed frames anywhere")

        # 8. the override wins (authored > inferred)
        amb = fx.build_stream(ambiguity=True)
        a_ov, r_ov = assign_stream(
            amb, characters=CHARACTERS,
            overrides={EVENT_2: {"A": "figure 2"}})
        af_ov = next(a for a in a_ov.frames if a.frame == EVENT_2)
        wins = (af_ov.assignment.get("A") == "figure 2"
                and af_ov.assignment.get("B") == "figure 1")
        disagrees = any(
            "override wins" in d for d in r_ov.disagreements)
        check("SANIM-OVERRIDE",
              wins and af_ov.overridden
              and EVENT_2 in r_ov.overridden_frames and disagrees,
              f"the authored override wins on frame {EVENT_2} (the free "
              "solve held the keyed tie on identical pose+scale; the "
              f"artist's word moved A); final assignment "
              f"{af_ov.assignment}; the disagreement is reported verbatim; "
              "overridden frames are EXCLUDED from the automatic rate")

        # 9. DETERM twins
        a1, r1 = assign_stream(fx.build_stream(), characters=CHARACTERS)
        a2, r2 = assign_stream(fx.build_stream(), characters=CHARACTERS)
        act_c2, _r2 = assign_stream(
            fx.build_stream(), characters=CHARACTERS, pins=(pin,))
        c1 = couple_scene_action(act_c2, fx.build_stream())
        c2 = couple_scene_action(act_c2, fx.build_stream())
        check("SANIM-DETERM",
              a1 == a2 and r1 == r2 and c1 == c2,
              f"twin streams: actions equal={a1 == a2} reports "
              f"equal={r1 == r2} couplings equal={c1 == c2}")

    print(f"RM_SANIM GATE: {'PASS' if OK else 'FAIL'}")
    return 0 if OK else 1


def core_bake(obj, action):
    """The REAL addon bake (imported here — bpy-dependent)."""
    from riggermortis_addon import bake
    return bake.bake_action(obj, action.frames, core,
                            name="rm_sanim_bake", frame_offset=0)


if __name__ == "__main__":
    sys.exit(main())
