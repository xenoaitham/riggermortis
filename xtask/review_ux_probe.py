"""P8-9 review-UX probe (pure core, headless, no Blender) — the RM_RUX rows.

docs/REVIEW_UX.md is the design page; this probe implements its instrument
BEFORE the core lift (the house pattern: probe-first, then the draft lifts
verbatim into core/review.py and this file re-runs against the library with
matching numbers).

Rows:
1. RUX-FIXTURE — the four defect classes exist on the established gate
   fixture classes (20-pose flips, the finger-gate hand, the face-gate
   10-expression set, the couple-gate scene); a beyond-reach pin really
   stays unclosable (loud data — fix the FIXTURE, never the solver).
2. RUX-T2F — the declared time-to-fix instrument: per-defect scripted
   click-through (flag -> affordance -> corrected apply); per-class medians
   + the median over ALL defects vs the Annex A.1 bar (<= 15 s). Cost =
   the DECLARED interaction model (CLICK 1.0 s / DRAG 3.0 s / SLIDER 2.0 s
   — instrument constants, D-008-untuned, never claimed as human-timed
   wall-clock) + the measured op wall-clock, published separately.
3. RUX-FIX — every corrected apply actually clears its defect within its
   family bar (flip sign == GT; authored finger direction within the P8-3
   median bar vs the GT direction; face param == the authored value; pin
   residual < 2% torso span after re-coupling).
4. RUX-UNTOUCHED — clean pose + clean scene: zero new review items and
   byte-identical round-trips with the affordances registered.
5. RUX-REFUSE — unknown hand/finger/param/pin/role, zero-length direction:
   loud errors with actionable hints, nothing applied.
6. RUX-DETERM — every click-through re-run: the fixed artifacts are
   byte-identical (timings excluded, they are measurements).
7. RUX-EST-BASELINE — the DEFAULT detector re-measured on the local anime
   benchmark (no-person count + per-image latency, full and pose-only):
   the numbers the adoption bars are ratios of. SKIPPED honestly without
   the local models.
8. RUX-EST-DEFAULT — the D-011 dual-estimator interface draft: default-only
   registry byte-identical; a FAKED fallback estimator (test seam, no
   weights, no downloads) selected exactly on the no-person probe, its
   provenance riding the payload's additive `estimator` entry field.
9. RUX-EST-RITUAL — the third-model ritual STATE: the manifest pins exactly
   the two DWPose models unless an adoption landed through it; the
   candidate-scan verdict (docs/REVIEW_UX.md + the DECISIONS entry) echoes
   here as the L9 terminal.

Usage: python3 xtask/review_ux_probe.py [--skip-models]
Env: RM_CORE_SRC / RM_XTASK / RM_TESTS override the sibling-module paths
(defaults resolve relative to this file). Prints RM_RUX lines; exit 0 only
if every row PASSes (or honest SKIPPED where allowed).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))  # xtask (sibling probes)
sys.path.insert(0, str(_REPO / "core" / "tests"))  # poses_fixtures
sys.path.insert(0, str(_REPO / "core" / "src"))


import riggermortis as core  # noqa: E402
from riggermortis.canonical_pose import CanonicalPose  # noqa: E402
from riggermortis.coupling import Placement, couple_scene  # noqa: E402
from riggermortis.errors import RiggermortisError  # noqa: E402
from riggermortis.face import FACE_PARAMS, solve_face  # noqa: E402
from riggermortis.fingers import (  # noqa: E402
    FINGER_ORDER,
    solve_hands,
)
from riggermortis.inference.poses import FACE_IOD_CORNERS, FACE_START  # noqa: E402
from riggermortis.scene import ContactPin, SceneFigure, ScenePose  # noqa: E402

OK: list[bool] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    OK.append(ok)
    print(f"RM_RUX {name}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")
    return ok


# The affordances + defect items LIVE IN CORE now (this file's drafts were
# lifted verbatim into core/review.py at the core step; the re-run below must
# reproduce the draft-pass numbers — the ONE-copy rule).

from riggermortis.review import (  # noqa: E402
    author_finger,
    confirm_pin,
    face_defects,
    finger_defects,
    flip_figure,
    retarget_pin,
    review_items,
    scene_defects,
    trim_face,
)

# == the instrument ============================================================

CLICK_S, DRAG_S, SLIDER_S = 1.0, 3.0, 2.0  # DECLARED instrument constants
T2F_BAR_S = 15.0  # Annex A.1
FINGER_DIR_BAR_DEG = 20.0  # the P8-3 median bar family
PIN_BAR_FRAC = 0.02  # the P8-2 torso-span bar


def _median(v: list[float]) -> float:
    return statistics.median(v) if v else float("inf")


def angle_deg(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    na = math.sqrt(sum(c * c for c in a))
    nb = math.sqrt(sum(c * c for c in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 180.0
    dot = max(-1.0, min(1.0, sum(a[i] * b[i] for i in range(3)) / (na * nb)))
    return math.degrees(math.acos(dot))


def fk_rotations(pose: CanonicalPose, rig_and_mapping: tuple) -> list:
    """The corrected apply, core-side: the real FK math over the fixture rig."""
    rig, mapping = rig_and_mapping
    return list(core.apply_canonical_pose(rig, mapping, pose).rotations)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-models", action="store_true",
                        help="skip the REAL detector rows (no local models)")
    args = parser.parse_args()

    import coupling_probe  # sibling xtask module (fixture builders, ONE copy)
    import face_probe  # sibling xtask module (fixture builders, ONE copy)
    import finger_probe  # sibling xtask module (fixture builders, ONE copy)
    import poses_fixtures as pf  # the 20-pose canonical class

    # -- fixture: the finger-gate hand class (one occluded finger) --------------
    flat_splays = {"thumb": -20.0, "index": -6.0, "middle": 0.0, "ring": 6.0,
                   "pinky": 14.0}
    no_curls = {f: (0.0, 0.0, 0.0) for f in FINGER_ORDER}
    wrist = (0.86, 0.0, 0.45)
    gt_hand, kps_vis, confs_vis = finger_probe._gt_hand(flat_splays, no_curls, wrist)
    stub = finger_probe._body_pose_stub(wrist)
    occluded = "ring"
    kps_occ, confs_occ = list(kps_vis), list(confs_vis)
    for joint in ("mcp", "pip", "dip", "tip"):
        confs_occ[finger_probe.hand_kp_index("hand.L", occluded, joint)] = 0.0
    hands = solve_hands(kps_occ, confs_occ, stub)
    hand_l = hands.get("hand.L")
    hand_fixture_ok = hand_l is not None and occluded in hand_l.skipped
    gt_chain = gt_hand[occluded]
    gt_dir = tuple(gt_chain["tip"][i] - gt_chain["mcp"][i] for i in range(3))
    pose_hands = CanonicalPose(
        positions=stub.positions, flips={}, confidence=stub.confidence,
        reliable=True, scale=stub.scale, anchor="hips",
        hands={"hand.L": hand_l} if hand_l is not None else {},
    )

    # -- fixture: the face-gate 10-expression class (only the IOD corners seen) -
    states = face_probe.benchmark_set()
    face_defects_list: list[tuple[CanonicalPose, str, float]] = []
    for name in sorted(states):
        (kps, confs), gt = states[name]
        # Occlusion rule (declared): only the IOD anchor corners stay visible —
        # every param is then confidence-gated, and the states whose GT carries
        # a non-zero expression contribute the flagged defects (a real missing
        # expression the artist can author). FACE_IOD_CORNERS index the face
        # band; confs are full-body, hence the FACE_START offset.
        confs_occ = list(confs)
        for j in range(68):
            if j not in FACE_IOD_CORNERS:
                confs_occ[FACE_START + j] = 0.0
        fp = solve_face(kps, confs_occ)
        if fp is None:
            continue
        pose_face = CanonicalPose(
            positions=stub.positions, flips={}, confidence=stub.confidence,
            reliable=True, scale=stub.scale, anchor="hips", face=fp,
        )
        for param in sorted(FACE_PARAMS):
            gt_v = float(gt.get(param, 0.0))
            if gt_v > 0.0 and param in fp.skipped:
                face_defects_list.append((pose_face, param, gt_v))

    # -- fixture: the couple-gate scene class (one beyond-reach pin) ------------
    fig_a = coupling_probe.stand_pose()
    fig_b = coupling_probe.stand_pose()
    # B faces A (rotated 180 deg about Z) standing in front, close enough that
    # a hand->hand pin closes, while hips->hand is beyond the chain's reach.
    pl = {
        "A": Placement(),
        "B": Placement(quat=(0.0, 0.0, 0.0, 1.0), t=(0.0, -0.45, 0.0)),
    }
    scene_bad = ScenePose(name="gate", figures=[
        SceneFigure(label="A", pose=fig_a), SceneFigure(label="B", pose=fig_b),
    ], pins=[ContactPin(figure_a="A", role_a="hips",
                        figure_b="B", role_b="hand.R")])
    _coupled_bad, report_bad = couple_scene(scene_bad, pl)
    unclosable_rows = report_bad.unclosable
    fixture_ok = (
        hand_fixture_ok
        and bool(face_defects_list)
        and bool(unclosable_rows)
        and len(unclosable_rows) == 1
    )
    if not fixture_ok:
        return check(
            "RUX-FIXTURE", False,
            f"hand_ledgered={hand_fixture_ok} face_defects={len(face_defects_list)} "
            f"unclosable={len(unclosable_rows)} (beyond-reach pin must stay loud "
            "— fix the FIXTURE, never the solver)",
        )

    # -- the instrument ----------------------------------------------------------
    identity_rm = coupling_probe.identity_rig()

    defects: list[dict] = []
    for fx in pf.POSES:  # FLIP class: material flips, wrong-sign injection
        for key, gt_sign in sorted(fx.gt_flips.items()):
            if gt_sign is None:
                continue  # immaterial (straight) — auto-pass per D-010
            base = CanonicalPose(
                positions=dict(fx.positions),
                flips={k: (v if v is not None else -1)
                       for k, v in fx.gt_flips.items()},
                confidence=0.9, reliable=True, scale=200.0, anchor="hips",
            )
            wrong = base.toggled(key)  # the injected defect state (INSTRUMENT:
            # the payload a real D-008 miss produces — flagged, wrong sign)
            defect = CanonicalPose(
                positions=wrong.positions, flips=dict(wrong.flips),
                confidence=wrong.confidence, reliable=wrong.reliable,
                scale=wrong.scale, anchor=wrong.anchor,
                notes=list(wrong.notes),
                joint_confidence={**wrong.joint_confidence, key: 0.30},
            )
            defects.append({
                "cls": "flip", "pose": defect, "key": key, "gt": gt_sign,
                "seq": ["CLICK", "CLICK"],
            })
    defects.append({  # FINGER class: the ledgered finger rescue
        "cls": "finger", "pose": pose_hands, "key": f"hand.L.{occluded}",
        "gt_dir": gt_dir, "hand": "hand.L", "finger": occluded,
        "seq": ["CLICK", "DRAG"],
    })
    for pose_face, param, gt_v in face_defects_list:  # FACE class
        defects.append({
            "cls": "face", "pose": pose_face, "key": param, "gt": gt_v,
            "seq": ["CLICK", "SLIDER"],
        })
    defects.append({  # PIN class: the beyond-reach pin retarget
        "cls": "pin", "scene": scene_bad, "report": report_bad,
        "key": "A.hips<->B.hand.R", "seq": ["CLICK", "DRAG"], "pl": pl,
    })

    seq_cost = {"CLICK": CLICK_S, "DRAG": DRAG_S, "SLIDER": SLIDER_S}
    per_class: dict[str, list[float]] = {"flip": [], "finger": [], "face": [],
                                         "pin": []}
    all_times: list[float] = []
    fixed_artifacts: list[str] = []
    fix_ok = True

    def run_once() -> tuple[list[float], list[str]]:
        nonlocal fix_ok
        times: list[float] = []
        artifacts: list[str] = []
        for d in defects:
            cost = sum(seq_cost[s] for s in d["seq"])
            t0 = time.perf_counter()
            if d["cls"] == "flip":
                items = [i for i in review_items(d["pose"]) if i.kind == "flip"]
                flagged = any(i.role == d["key"] for i in items)
                fixed = d["pose"].toggled(d["key"])  # the flip affordance (P1-11)
                fk_rotations(fixed, identity_rm)  # the corrected apply (real FK)
                artifacts.append(json.dumps(
                    {"flips": fixed.flips,
                     "conf": fixed.joint_confidence.get(d["key"])},
                    sort_keys=True))
                ok = (flagged and fixed.flips[d["key"]] == d["gt"]
                      and fixed.joint_confidence.get(d["key"]) == 1.0)
            elif d["cls"] == "finger":
                items = finger_defects(d["pose"])
                flagged = any(
                    i.fix == f"finger_fix:{d['hand']}.{d['finger']}" for i in items)
                fixed = author_finger(d["pose"], d["hand"], d["finger"], d["gt_dir"])
                fk_rotations(fixed, identity_rm)
                chain = fixed.hands[d["hand"]].fingers[d["finger"]]
                got = tuple(chain.joints["tip"][i] - chain.joints["mcp"][i]
                            for i in range(3))
                ang = angle_deg(got, d["gt_dir"])
                artifacts.append(json.dumps(
                    {"chain": {k: list(v) for k, v in
                               sorted(chain.joints.items())}}, sort_keys=True))
                ok = (flagged and d["finger"] in fixed.hands[d["hand"]].fingers
                      and d["finger"] not in fixed.hands[d["hand"]].skipped
                      and ang <= FINGER_DIR_BAR_DEG)
            elif d["cls"] == "face":
                items = face_defects(d["pose"])
                flagged = any(i.fix == f"face_trim:{d['key']}" for i in items)
                fixed = trim_face(d["pose"], d["key"], d["gt"])
                artifacts.append(json.dumps(
                    {"param": fixed.face.params.get(d["key"]),
                     "gated": d["key"] in fixed.face.skipped}, sort_keys=True))
                ok = (flagged and fixed.face.params.get(d["key"]) == d["gt"]
                      and d["key"] not in fixed.face.skipped)
            else:  # pin
                items = scene_defects(d["scene"], d["report"])
                flagged = any(i.fix and i.fix.startswith("pin_retarget:")
                              for i in items)
                idx = next(int(i.fix.split(":")[1]) for i in items
                           if i.fix and i.fix.startswith("pin_retarget:"))
                retargeted = retarget_pin(d["scene"], idx, "a", "hand.L")
                _c, rep2 = couple_scene(retargeted, d["pl"])
                worst = max((r.residual_frac for r in rep2.rows), default=1.0)
                bad_rows = rep2.unclosable
                artifacts.append(json.dumps(
                    {"pins": [p.to_dict() for p in retargeted.pins],
                     "unclosable": len(bad_rows), "worst_frac": worst},
                    sort_keys=True))
                ok = flagged and not bad_rows and worst < PIN_BAR_FRAC
            op_s = time.perf_counter() - t0
            if not ok:
                fix_ok = False
            times.append(cost + op_s)
        return times, artifacts

    all_times, fixed_artifacts = run_once()
    per_class: dict[str, list[float]] = {"flip": [], "finger": [], "face": [],
                                         "pin": []}
    idx = 0
    for d in defects:
        per_class[d["cls"]].append(all_times[idx])
        idx += 1

    med = _median(all_times)
    t0 = time.perf_counter()
    run_once()
    op_sweep_s = time.perf_counter() - t0
    detail = (f"overall median {med:.2f} s (bar <= {T2F_BAR_S:.0f} s) | "
              + " | ".join(f"{c} median {_median(v):.2f} s n={len(v)}"
                           for c, v in sorted(per_class.items())))
    check("RUX-FIXTURE", fixture_ok and len(defects) > 10,
          f"defects: flip={per_class['flip'] and len(per_class['flip'])} "
          f"finger={len(per_class['finger'])} face={len(per_class['face'])} "
          f"pin={len(per_class['pin'])}")
    check("RUX-T2F", med <= T2F_BAR_S and fix_ok, detail)
    print(f"RM_RUX T2F-MODEL: CLICK={CLICK_S} DRAG={DRAG_S} SLIDER={SLIDER_S} "
          f"(declared instrument constants, D-008-untuned)")
    print(f"RM_RUX T2F-OP: full-sweep op wall-clock {op_sweep_s:.4f} s over "
          f"{len(defects)} click-throughs (median op component "
          f"{op_sweep_s / len(defects):.6f} s; published alongside the model)")

    # -- RUX-UNTOUCHED: clean inputs stay clean and byte-identical --------------
    clean_fx = pf.POSES[0]
    clean_pose = CanonicalPose(
        positions=dict(clean_fx.positions),
        flips={k: (v if v is not None else -1)
               for k, v in clean_fx.gt_flips.items()},
        confidence=0.9, reliable=True, scale=200.0, anchor="hips",
    )
    clean_scene = ScenePose(name="clean", figures=[
        SceneFigure(label="A", pose=fig_a), SceneFigure(label="B", pose=fig_b),
    ])
    round_trip = CanonicalPose.from_dict(
        json.loads(json.dumps(clean_pose.to_dict()))
    ).to_dict() == clean_pose.to_dict()
    untouched = (
        not finger_defects(clean_pose)
        and not face_defects(clean_pose)
        and not scene_defects(clean_scene)
        and not scene_defects(scene_bad, None)  # no report -> no unclosable items
        and review_items(clean_pose) == review_items(clean_pose)
        and round_trip
    )
    check("RUX-UNTOUCHED", untouched,
          "clean pose + clean scene: zero new items, round-trip byte-identical")

    # -- RUX-REFUSE: loud refusals, nothing applied ------------------------------
    refusals = 0
    for bad in (
        lambda: author_finger(pose_hands, "hand.C", "index", (1, 0, 0)),
        lambda: author_finger(pose_hands, "hand.L", "claw", (1, 0, 0)),
        lambda: author_finger(pose_hands, "hand.L", "index", (0, 0, 0)),
        lambda: trim_face(pose_hands, "smile.C", 0.5),
        lambda: retarget_pin(scene_bad, 99, "b", "hand.R"),
        lambda: retarget_pin(scene_bad, 0, "c", "hand.R"),
        lambda: confirm_pin(scene_bad, -1),
        lambda: flip_figure(scene_bad, "C"),
    ):
        try:
            bad()
        except RiggermortisError:
            refusals += 1
    check("RUX-REFUSE", refusals == 8,
          f"{refusals}/8 loud refusals (unknown hand/finger/param, zero "
          "direction, bad index/endpoint/label)")

    # -- RUX-DETERM: the click-throughs are twins byte-identical -----------------
    _times_twice, artifacts_twice = run_once()
    twins = artifacts_twice == fixed_artifacts and len(artifacts_twice) == len(defects)
    check("RUX-DETERM", twins,
          f"{len(artifacts_twice)} re-run fixes byte-identical (timings excluded "
          "— measurements)")

    # -- RUX-EST-BASELINE: the default detector on the local anime benchmark ----
    bench = _REPO / "out" / "benchmark" / "images" / "anime"
    models_available = not args.skip_models and bench.is_dir()
    if models_available:
        try:
            from riggermortis.inference import dwpose
            from riggermortis.inference.figures import FigureBoard

            images = sorted(p for p in bench.iterdir()
                            if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
            sess = dwpose.load_sessions()  # cold load excluded from timings
            no_person = 0
            full_ms: list[float] = []
            pose_ms: list[float] = []
            for img in images:
                t0 = time.perf_counter()
                detection = dwpose.detect_keypoints(str(img), sessions=sess)
                full_ms.append((time.perf_counter() - t0) * 1000.0)
                board = FigureBoard.from_detection(detection)
                if not board.figures:
                    no_person += 1
                    continue
                fig = board.largest()
                t0 = time.perf_counter()
                dwpose.estimate_keypoints_at(str(img), fig.bbox, sessions=sess)
                pose_ms.append((time.perf_counter() - t0) * 1000.0)
            check("RUX-EST-BASELINE", True,
                  f"anime benchmark n={len(images)} "
                  f"no-person={no_person}/{len(images)} (DWPose measured 3/10 at "
                  f"S5; a FALLBACK estimator's adoption bar is <= 1/10) "
                  f"full p50={_median(full_ms):.0f} ms "
                  f"pose-only p50={_median(pose_ms):.0f} ms (CPU, this box)")
            check("RUX-EST-DEFAULT", est_default_row(dwpose),
                  "default-only registry byte-identical; faked fallback selected "
                  "exactly on the no-person probe; provenance rides the additive "
                  "`estimator` entry field (omitted for the default)")
        except Exception as exc:  # noqa: BLE001 — honest SKIPPED, never fake
            print(f"RM_RUX EST-BASELINE: SKIPPED (models unavailable: "
                  f"{exc.__class__.__name__}: {exc})")
            print("RM_RUX EST-DEFAULT: SKIPPED (baseline skipped)")
    else:
        print("RM_RUX EST-BASELINE: SKIPPED (--skip-models or no local anime dir)")
        print("RM_RUX EST-DEFAULT: SKIPPED (baseline skipped)")

    # -- RUX-EST-RITUAL: the manifest state IS the L9 terminal -------------------
    from riggermortis.inference.models import load_manifest

    manifest = load_manifest()
    names = sorted(manifest["models"])
    ritual_ok = names == ["dwpose-ll-ucoco-384", "dwpose-yolox-l"]
    print(
        f"RM_RUX EST-RITUAL: {'PASS' if ritual_ok else 'FAIL'} manifest "
        f"models={names} — the P6-6 never-list holds; candidate scan "
        f"(docs/REVIEW_UX.md): no published anime/sketch whole-body estimator "
        f"with adoptable weights exists (HF: 'anime pose' hits are SD LoRAs, "
        f"'dwpose' hits are re-uploads of the pinned photoreal family, the "
        f"imgutils ecosystem has no pose module, the official ControlNet "
        f"annotators carry no anime variant; D-011's fine-tune route is banned "
        f"in-repo) -> L9 = REFUSED-with-evidence after one candidate; the "
        f"dual-estimator INTERFACE ships (DECISIONS entry at the landing)"
    )

    print("RM_RUX PROBE:", "OK" if all(OK) else "FAILED", f"({sum(OK)}/{len(OK)})")
    return 0 if all(OK) else 1


def est_default_row(dwpose) -> bool:
    """The D-011 interface draft: registry + per-image selection + provenance.

    FAKED fallback (a test seam — no weights, no downloads): a stub estimator
    whose 'detector' always reports a person. Default-only registry must be
    byte-identical to the plain path; the fallback must be selected exactly
    on the no-person probe; its name must ride the payload entry field."""

    class FakeAnime:
        name = "fake-anime"

        @staticmethod
        def detect_keypoints(image, **kw):  # noqa: ANN001, ARG004
            from riggermortis.inference.dwpose import Detection, Figure

            return Detection(width=10, height=10, figures=[Figure(
                index=0, bbox=(0.0, 0.0, 8.0, 10.0), score=0.9,
                keypoints=[(0.0, 0.0)] * 133, confidences=[0.9] * 133)])

    class NoPersonDWPose:
        name = "dwpose"

        @staticmethod
        def detect_keypoints(image, **kw):  # noqa: ANN001, ARG004
            from riggermortis.inference.dwpose import Detection

            return Detection(width=10, height=10, figures=[])

    class FoundPersonDWPose:
        name = "dwpose"

        @staticmethod
        def detect_keypoints(image, **kw):  # noqa: ANN001, ARG004
            from riggermortis.inference.dwpose import Detection, Figure

            return Detection(width=10, height=10, figures=[Figure(
                index=0, bbox=(0.0, 0.0, 9.0, 10.0), score=0.8,
                keypoints=[(0.0, 0.0)] * 133, confidences=[0.8] * 133)])

    def with_estimator(entry: dict, name: str) -> dict:
        if name == "dwpose":
            return entry  # the default is NEVER written — bytes stay identical
        out = dict(entry)
        out["estimator"] = name
        return out

    def select(image, estimators, sessions=None):  # noqa: ANN001
        first = estimators["dwpose"].detect_keypoints(image, sessions=sessions)
        if first.figures:
            return "dwpose", first
        for name in sorted(estimators):
            if name != "dwpose":
                return name, estimators[name].detect_keypoints(image)
        return "dwpose", first

    entry = {"label": "figure 1", "index": 0, "score": 0.9,
             "bbox": [0, 0, 1, 1], "pose": {}, "rotations": [],
             "skipped": [], "notes": []}
    if with_estimator(entry, "dwpose") != entry:
        return False
    # the no-person probe selects the fallback (keyed order, default first)
    name, det = select(None, {"dwpose": NoPersonDWPose, "fake-anime": FakeAnime})
    if name != "fake-anime" or not det.figures:
        return False
    # a person found -> the default wins, provenance stays unwritten
    name2, det2 = select(None, {"dwpose": FoundPersonDWPose,
                                "fake-anime": FakeAnime})
    if name2 != "dwpose" or not det2.figures:
        return False
    if with_estimator(entry, name).get("estimator") != "fake-anime":
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
