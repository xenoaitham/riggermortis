"""P8-3 capability probe: the finger-solve unknowns, answered by DOING.

The finger solve is PURE CORE (133-kp arrays + the solved body pose in,
canonical finger chains out; nothing here touches bpy — the real-rig apply
is the GATE's job). Design of record: docs/FINGERS.md § As-built design
(S28). Every constant below is pre-declared there (D-008 style:
order-of-magnitude choices, never fixture-fitted).

DEPTH-SIGN FINDING (the probe's reason to exist, earned on the first
draft): a flatten prior with 2^3 sign enumeration CANNOT solve curled
fingers — the all-flat sign combo minimizes the flatten energy, so the
"solve" un-curls every grip. The declared v1 discriminator is the
FORWARD-CURL SIGN (segments take delta-y = -|delta|, the D-008
elbow-forward prior one level down; declared, never enumerated): curled
hands that curl AWAY from canonical forward are the documented single-view
miss class (the elbow prior's exact analog — review-fixable, never
guessed). Clenched hands are occlusion fixtures (gated-skip per Annex A.1)
and never reach the direction bars.

Rows (synthetic fixtures engine-built per Annex A.3; real rows run the
pinned DWPose models on the local P1-9 photo set, Apache-2.0, git-ignored):

1.  LAYOUT      — the draft hand-kp table lands inside the COCO-WholeBody
                  partition (wrist + 5 fingers x 4 joints per hand; both
                  hands' index ranges covered exactly).
2.  GATE-OCCL   — hand-behind-back class: finger kps conf 0 -> 100%
                  gated-skip, every finger ledgered with its verbatim
                  reason, zero guessed fingers.
3.  GATE-FIST   — clenched class: kps present but below the floor
                  -> 100% gated-skip, ledgered.
4.  GATE-SOLVE  — visible-hand class: all kps >= floor -> all five fingers
                  solve, ledger empty, joints finite.
5.  DIRECTION   — parametric GT hands (flat/spread/curl, prior-consistent)
                  projected to 2D + conf, solved: per-SEGMENT direction
                  error vs GT — median/p90 vs the Annex A.1 bars
                  (median <= 20, p90 <= 35 deg on visible fingers).
                  SYNTHETIC-labeled preview.
6.  DETERM      — twin solves byte-identical (pure function).
7.  REAL-FRAME  — real detections: the canonical wrist->forearm span per
                  hand (the hand frame's stability surface; degeneracy =
                  span < 10% of the canonical forearm 0.28). Needs models.
8.  REAL-CHAINS — real detections: fingers solved/skipped at the floor per
                  photo (the audit's 0.65/0.86 hand-conf bands), including
                  the occlusion-class photo (hand behind head) on purpose.

Prints RM_FINGER lines; exit 0 only if every row PASSes (real rows run for
real on this box — the models are pinned as downloaded; a SKIP there is a
FAIL so the box cannot silently lose the real evidence).
Usage: /home/potato/miniconda3/bin/python3 xtask/finger_probe.py [--photos DIR]
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

CORE_SRC = Path(
    os.environ.get(
        "RM_CORE_SRC",
        Path(__file__).resolve().parent.parent / "core" / "src",
    )
)
sys.path.insert(0, str(CORE_SRC))

from riggermortis.canonical_pose import (  # noqa: E402
    CanonicalPose,
    observations_from_keypoints,
    solve_pose,
)
from riggermortis.inference.poses import (  # noqa: E402
    HAND_L_END,
    HAND_L_START,
    HAND_R_END,
    HAND_R_START,
    HIP_L,
    HIP_R,
    KEYPOINT_COUNT,
    SHOULDER_L,
    SHOULDER_R,
    WRIST_L,
    WRIST_R,
)

# -- draft hand layout (lifted into poses.py at the core landing) --------------
FINGER_ORDER = ("thumb", "index", "middle", "ring", "pinky")
FINGER_JOINTS = ("mcp", "pip", "dip", "tip")
HAND_KP_COUNT = 21


def hand_kp_index(hand: str, finger: str, joint: str) -> int:
    if hand not in ("hand.L", "hand.R"):
        raise ValueError(f"unknown hand {hand!r} (known: hand.L, hand.R)")
    if finger not in FINGER_ORDER:
        raise ValueError(f"unknown finger {finger!r} (known: {', '.join(FINGER_ORDER)})")
    if joint not in FINGER_JOINTS:
        raise ValueError(f"unknown joint {joint!r} (known: {', '.join(FINGER_JOINTS)})")
    base = HAND_L_START if hand == "hand.L" else HAND_R_START
    return base + 1 + 4 * FINGER_ORDER.index(finger) + FINGER_JOINTS.index(joint)


# -- pre-declared solve constants (docs/FINGERS.md § As-built design) ----------
FINGER_CONF_FLOOR = 0.55  # the CONVENTIONS ambiguity bar, reused; untuned
_SEGMENT_LENGTHS = (0.030, 0.022, 0.016)  # index..pinky: mcp->pip, pip->dip, dip->tip
_SEGMENTS: dict[str, tuple[float, float, float]] = {
    "thumb": (0.032, 0.026, 0.020),
    "index": _SEGMENT_LENGTHS,
    "middle": _SEGMENT_LENGTHS,
    "ring": _SEGMENT_LENGTHS,
    "pinky": _SEGMENT_LENGTHS,
}
FOREARM_CANONICAL = 0.28  # canonical forearm length (length_ratio 0.28)
FRAME_DEGENERACY_FRAC = 0.10  # span < 10% of canonical = degenerate hand frame


# -- the draft solve (the recipe core fingers.py lifts) -------------------------

def _plane_anchor(
    pose: CanonicalPose, kps: list[tuple[float, float]]
) -> tuple[float, float, float] | None:
    """The body solve's anchor pixels + scale (hips midpoint, neck fallback),
    rebuilt exactly as observations_from_keypoints builds them."""
    if len(kps) != KEYPOINT_COUNT:
        return None
    hips = ((kps[HIP_L][0] + kps[HIP_R][0]) / 2.0, (kps[HIP_L][1] + kps[HIP_R][1]) / 2.0)
    neck = (
        (kps[SHOULDER_L][0] + kps[SHOULDER_R][0]) / 2.0,
        (kps[SHOULDER_L][1] + kps[SHOULDER_R][1]) / 2.0,
    )
    if pose.anchor == "hips":
        return hips[0], hips[1], pose.scale
    if pose.anchor == "neck":
        return neck[0], neck[1], pose.scale
    return None


def _to_plane(u: float, v: float, ax: float, ay: float, scale: float) -> tuple[float, float]:
    return ((u - ax) / scale, (ay - v) / scale)


def solve_hand(
    hand: str,
    kps: list[tuple[float, float]],
    confs: list[float],
    pose: CanonicalPose,
    ax: float,
    ay: float,
    scale: float,
) -> dict[str, object] | None:
    """Draft per-hand solve. Returns None when the wrist anchor is unusable
    (the whole hand is skipped; an absent hand reads as clean)."""
    w_idx = WRIST_L if hand == "hand.L" else WRIST_R
    if confs[w_idx] < FINGER_CONF_FLOOR:
        return None
    if hand not in pose.positions:
        return None
    y_wrist = pose.positions[hand][1]
    fingers: dict[str, object] = {}
    skipped: dict[str, str] = {}
    for finger in FINGER_ORDER:
        idxs = [hand_kp_index(hand, finger, j) for j in FINGER_JOINTS]
        cs = [confs[i] for i in idxs]
        if any(c < FINGER_CONF_FLOOR for c in cs):
            skipped[finger] = (
                "confidence " + "/".join(f"{c:.2f}" for c in cs)
                + f" below floor {FINGER_CONF_FLOOR}"
            )
            continue
        plane = [_to_plane(kps[i][0], kps[i][1], ax, ay, scale) for i in idxs]
        lengths = _SEGMENTS[finger]
        joints: dict[str, tuple[float, float, float]] = {
            "mcp": (plane[0][0], y_wrist, plane[0][1])
        }
        y = y_wrist
        for k, jname in enumerate(("pip", "dip", "tip")):
            inplane = math.hypot(
                plane[k + 1][0] - plane[k][0], plane[k + 1][1] - plane[k][1]
            )
            length = lengths[k]
            depth = math.sqrt(max(length * length - inplane * inplane, 0.0))
            y -= depth  # the declared FORWARD-CURL sign (see module docstring)
            joints[jname] = (plane[k + 1][0], y, plane[k + 1][1])
        fingers[finger] = {"joints": joints, "confidence": min(cs)}
    return {"fingers": fingers, "skipped": skipped, "wrist_conf": confs[w_idx]}


def draft_solve_hands(
    kps: list[tuple[float, float]], confs: list[float], pose: CanonicalPose
) -> dict[str, dict[str, object]]:
    anchor = _plane_anchor(pose, kps)
    if anchor is None:
        return {}
    ax, ay, scale = anchor
    out: dict[str, dict[str, object]] = {}
    for hand in ("hand.L", "hand.R"):
        solved = solve_hand(hand, kps, confs, pose, ax, ay, scale)
        if solved is not None:
            out[hand] = solved
    return out


# -- parametric GT hands (SYNTHETIC fixtures; the gate's benchmark generator
#    grows this to the 20-pose class) ---------------------------------------------

def gt_finger_joints(
    base_dir: tuple[float, float, float],
    splay_deg: float,
    curls_deg: tuple[float, float, float],
    lengths: tuple[float, float, float],
    mcp: tuple[float, float, float],
) -> dict[str, tuple[float, float, float]]:
    """Chain 4 GT joints: splay rotates the base direction in the hand plane
    (about Y), each curl kinks one segment INTO DEPTH (negative = canonical
    forward, the prior-consistent direction)."""
    def rot_y(v: tuple[float, float, float], deg: float) -> tuple[float, float, float]:
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        return (v[0] * c - v[2] * s, v[1], v[0] * s + v[2] * c)

    def curl(v: tuple[float, float, float], deg: float) -> tuple[float, float, float]:
        # rotate about the hand-plane lateral axis Z: x toward -y for deg > 0
        a = math.radians(deg)
        c, s = math.cos(a), math.sin(a)
        return (v[0] * c, -(v[0] * s) + v[1] * c, v[2])

    d = rot_y(base_dir, splay_deg)
    joints: dict[str, tuple[float, float, float]] = {"mcp": mcp}
    prev = mcp
    for k, name in enumerate(("pip", "dip", "tip")):
        d = curl(d, curls_deg[k])
        prev = (
            prev[0] + d[0] * lengths[k],
            prev[1] + d[1] * lengths[k],
            prev[2] + d[2] * lengths[k],
        )
        joints[name] = prev
    return joints


def _project(p3: tuple[float, float, float], ax: float, ay: float, scale: float) -> tuple[float, float]:
    """Orthographic GT projection: u = ax + x*scale, v = ay - z*scale."""
    return (ax + p3[0] * scale, ay - p3[2] * scale)


# -- probe harness ---------------------------------------------------------------

_OK: list[bool] = []


def check(name: str, ok: bool, detail: str) -> None:
    _OK.append(ok)
    print(f"RM_FINGER {name}: {'PASS' if ok else 'FAIL'} {detail}")


def _gt_hand(
    splays: dict[str, float],
    curls: dict[str, tuple[float, float, float]],
    wrist: tuple[float, float, float],
) -> tuple[dict[str, dict[str, tuple[float, float, float]]], list[tuple[float, float]], list[float]]:
    """One GT hand (hand.L, 5 fingers) in canonical space, projected to the
    133-kp array at the probe's fixed anchor (320, 240) / scale 400."""
    ax, ay, scale = 320.0, 240.0, 400.0
    gt: dict[str, dict[str, tuple[float, float, float]]] = {}
    kps: list[tuple[float, float]] = [(0.0, 0.0)] * KEYPOINT_COUNT
    confs: list[float] = [0.0] * KEYPOINT_COUNT
    kps[WRIST_L] = _project(wrist, ax, ay, scale)
    confs[WRIST_L] = 0.95
    for finger in FINGER_ORDER:
        mcp3 = (wrist[0] + 0.02, wrist[1], wrist[2] + 0.01 * FINGER_ORDER.index(finger))
        gj = gt_finger_joints(
            (1.0, 0.0, 0.0), splays[finger], curls[finger], _SEGMENTS[finger], mcp3
        )
        gt[finger] = gj
        for jname in FINGER_JOINTS:
            idx = hand_kp_index("hand.L", finger, jname)
            kps[idx] = _project(gj[jname], ax, ay, scale)
            confs[idx] = 0.9
    return gt, kps, confs


def _body_pose_stub(wrist: tuple[float, float, float]) -> CanonicalPose:
    """Minimal CanonicalPose stub: the anchor + hand/forearm positions the
    solve reads (scale matches the GT projection)."""
    return CanonicalPose(
        positions={
            "hips": (0.0, 0.0, 0.0),
            "hand.L": wrist,
            "forearm.L": (wrist[0] - FOREARM_CANONICAL, wrist[1], wrist[2]),
        },
        flips={},
        confidence=0.8,
        reliable=True,
        scale=400.0,
        anchor="hips",
        notes=[],
        joint_confidence={},
    )


def _direction_errors(
    solved: dict[str, dict[str, object]],
    gt: dict[str, dict[str, tuple[float, float, float]]],
) -> list[float]:
    hs = solved.get("hand.L")
    if hs is None:
        return []
    out: list[float] = []
    for finger, chain in sorted(hs["fingers"].items()):  # type: ignore[union-attr]
        sj: dict[str, tuple[float, float, float]] = chain["joints"]  # type: ignore[index]
        gj = gt[finger]
        for a, b in (("mcp", "pip"), ("pip", "dip"), ("dip", "tip")):
            d1 = tuple(sj[b][i] - sj[a][i] for i in range(3))
            d2 = tuple(gj[b][i] - gj[a][i] for i in range(3))
            n1 = math.sqrt(sum(c * c for c in d1))
            n2 = math.sqrt(sum(c * c for c in d2))
            if n1 <= 1e-12 or n2 <= 1e-12:
                continue
            dot = max(-1.0, min(1.0, sum(d1[i] * d2[i] for i in range(3)) / (n1 * n2)))
            out.append(math.degrees(math.acos(dot)))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--photos", default="out/benchmark/images/photo", help="P1-9 photo dir"
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    photos_dir = (repo / args.photos) if not Path(args.photos).is_absolute() else Path(args.photos)

    # 1. LAYOUT — the draft table lands inside the COCO-WholeBody partition.
    covered: list[int] = []
    ok_layout = True
    for hand, lo, hi in (
        ("hand.L", HAND_L_START, HAND_L_END),
        ("hand.R", HAND_R_START, HAND_R_END),
    ):
        idx = [hand_kp_index(hand, f, j) for f in FINGER_ORDER for j in FINGER_JOINTS]
        ok_layout = ok_layout and all(lo <= i < hi for i in idx) and len(set(idx)) == 20
        covered.extend(idx)
    ok_layout = ok_layout and len(covered) == 40 and HAND_L_END == HAND_R_START
    check("LAYOUT", ok_layout, f"40 joint indices inside [{HAND_L_START}, {HAND_R_END})")

    # 2-4. GATE rows on synthetic fixtures (the honesty line, made numeric).
    wrist = (0.5, 0.0, 0.9)
    pose_stub = _body_pose_stub(wrist)
    flat_splays = {"thumb": -20.0, "index": -6.0, "middle": 0.0, "ring": 6.0, "pinky": 14.0}
    no_curls = {f: (0.0, 0.0, 0.0) for f in FINGER_ORDER}
    _gt_flat, kps_vis, confs_vis = _gt_hand(flat_splays, no_curls, wrist)

    confs_occl = list(confs_vis)
    for i in range(HAND_L_START, HAND_L_END):
        confs_occl[i] = 0.0  # hand-behind-back: no hand response at all
    hs_occl = draft_solve_hands(kps_vis, confs_occl, pose_stub).get("hand.L")
    occl_ok = (
        hs_occl is not None
        and len(hs_occl["fingers"]) == 0  # type: ignore[union-attr]
        and len(hs_occl["skipped"]) == 5  # type: ignore[union-attr]
    )
    check(
        "GATE-OCCL",
        occl_ok,
        f"solved=0 skipped={len(hs_occl['skipped']) if hs_occl else '-'}/5 ledgered",  # type: ignore[index]
    )

    confs_low = list(confs_vis)
    for i in range(HAND_L_START + 1, HAND_L_END):
        confs_low[i] = 0.3  # clenched class: kps present, all below floor
    hs_low = draft_solve_hands(kps_vis, confs_low, pose_stub).get("hand.L")
    low_ok = (
        hs_low is not None
        and len(hs_low["fingers"]) == 0  # type: ignore[union-attr]
        and len(hs_low["skipped"]) == 5  # type: ignore[union-attr]
    )
    ledger_ok = low_ok and all(
        "below floor 0.55" in r for r in hs_low["skipped"].values()  # type: ignore[union-attr]
    )
    check("GATE-FIST", low_ok and ledger_ok, "solved=0 skipped=5/5 reasons verbatim")

    hs_vis = draft_solve_hands(kps_vis, confs_vis, pose_stub).get("hand.L")
    vis_ok = (
        hs_vis is not None
        and len(hs_vis["fingers"]) == 5  # type: ignore[union-attr]
        and len(hs_vis["skipped"]) == 0  # type: ignore[union-attr]
    )
    finite_ok = vis_ok and all(
        all(math.isfinite(c) for c in ch["joints"][j])  # type: ignore[index]
        for ch in hs_vis["fingers"].values()  # type: ignore[union-attr]
        for j in FINGER_JOINTS
    )
    check("GATE-SOLVE", vis_ok and finite_ok, "solved=5/5 skipped=0 joints finite")

    # 5. DIRECTION — prior-consistent GT poses, projected + solved, vs bars.
    pose_set: dict[str, tuple[dict, list, list]] = {"flat": (_gt_flat, kps_vis, confs_vis)}
    gt_sp, kps_sp, confs_sp = _gt_hand(
        {"thumb": -40.0, "index": -15.0, "middle": 0.0, "ring": 15.0, "pinky": 32.0},
        no_curls,
        wrist,
    )
    pose_set["spread"] = (gt_sp, kps_sp, confs_sp)
    gt_cu, kps_cu, confs_cu = _gt_hand(
        {"thumb": -10.0, "index": -4.0, "middle": 0.0, "ring": 4.0, "pinky": 10.0},
        {f: (35.0, 40.0, 30.0) for f in FINGER_ORDER},
        wrist,
    )
    pose_set["curl"] = (gt_cu, kps_cu, confs_cu)

    all_errs: list[float] = []
    for name in sorted(pose_set):
        gt, kps, confs = pose_set[name]
        errs = _direction_errors(draft_solve_hands(kps, confs, pose_stub), gt)
        all_errs.extend(errs)
        med = sorted(errs)[len(errs) // 2] if errs else float("nan")
        print(f"RM_FINGER DIRECTION {name}: n={len(errs)} median={med:.2f} deg")
    all_errs.sort()
    med_all = all_errs[len(all_errs) // 2]
    p90_all = all_errs[min(int(0.9 * len(all_errs)), len(all_errs) - 1)]
    check(
        "DIRECTION",
        med_all <= 20.0 and p90_all <= 35.0,
        f"median={med_all:.2f} (bar 20) p90={p90_all:.2f} (bar 35) "
        f"over {len(all_errs)} segments [SYNTHETIC, prior-consistent GT]",
    )

    # 6. DETERM — twin solves byte-identical.
    twin_a = draft_solve_hands(kps_cu, confs_cu, pose_stub)
    twin_b = draft_solve_hands(kps_cu, confs_cu, pose_stub)
    check("DETERM", twin_a == twin_b, "twin solves identical")

    # 7-8. REAL rows — the pinned DWPose models on the local photo set.
    try:
        from riggermortis.inference.dwpose import detect_keypoints
        from riggermortis.inference.figures import FigureBoard
    except Exception as exc:  # noqa: BLE001 — honest degradation path
        print(f"RM_FINGER REAL: FAIL models unavailable ({exc})")
        print("RM_FINGER PROBE: FAILED (real evidence required on this box)")
        return 1

    frame_spans: list[float] = []
    degenerate = 0
    hands_checked = 0
    total_solved = 0
    total_skipped = 0
    behind_head_skipped = -1
    photos = sorted(list(photos_dir.glob("*.png")) + list(photos_dir.glob("*.jpg")))[:6]
    for photo in photos:
        det = detect_keypoints(str(photo))
        board = FigureBoard.from_detection(det)
        if not board.figures:
            continue
        fig = board.largest()
        if fig is None:
            continue
        body = solve_pose(observations_from_keypoints(fig.keypoints, fig.confidences))
        if body.anchor == "none":
            continue
        solved = draft_solve_hands(fig.keypoints, fig.confidences, body)
        for hand in ("hand.L", "hand.R"):
            if hand in body.positions and hand in solved:
                forearm_pos = body.positions.get(f"forearm.{hand[-1]}")
                if forearm_pos is not None:
                    span = math.dist(body.positions[hand], forearm_pos)
                    frame_spans.append(span)
                    hands_checked += 1
                    if span < FRAME_DEGENERACY_FRAC * FOREARM_CANONICAL:
                        degenerate += 1
        for _hand, hs in sorted(solved.items()):
            total_solved += len(hs["fingers"])  # type: ignore[arg-type]
            total_skipped += len(hs["skipped"])  # type: ignore[arg-type]
        if "human_hand_behind_head" in photo.name:
            behind = solved.get("hand.L") or solved.get("hand.R")
            behind_head_skipped = (
                len(behind["skipped"]) if behind is not None else -1
            )

    span_txt = (
        f"span_median={sorted(frame_spans)[len(frame_spans) // 2]:.3f}u "
        if frame_spans
        else ""
    )
    check(
        "REAL-FRAME",
        hands_checked > 0,
        f"hands={hands_checked} {span_txt}degenerate={degenerate} "
        f"over {len(photos)} photos",
    )
    check(
        "REAL-CHAINS",
        (total_solved + total_skipped) > 0,
        f"solved={total_solved} skipped={total_skipped} (floor {FINGER_CONF_FLOOR}); "
        f"behind-head photo gated_skips={behind_head_skipped}",
    )

    passed = all(_OK)
    print(f"RM_FINGER PROBE: {'OK' if passed else 'FAILED'} ({sum(_OK)}/{len(_OK)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
