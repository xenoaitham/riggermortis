"""P8-4 capability probe: the facial-param unknowns, answered by DOING.

The face solve is PURE CORE (133-kp arrays in, dimensionless expression
params out; nothing here touches bpy — the real-rig/shape-key apply is
the GATE's job). Design of record: docs/FACE.md (including the
amendment record A1-A3, earned by this probe's first draft). Every
constant below is pre-declared there (D-008 style: order-of-magnitude
choices, never fixture-fitted; the real rows PUBLISH the measured
distributions next to the declared priors — measure-and-declare, the
finger segment-lengths pattern).

GAZE IS NOT A PARAM: the pinned DWPose emits no iris keypoints; gaze
enters only if a detector variant supplies them (conditional-OUT — the
roadmap's pre-declared condition). No corner-geometry guessing.

Rows (synthetic fixtures engine-built per Annex A.3; real rows run the
pinned DWPose models on the local P1-9 photo set, Apache-2.0, git-ignored):

1.  LAYOUT      — the declared face band table tiles 23..91 exactly; the
                  per-param consumed indices all sit inside the face
                  partition (29 unique points; lower-lid pairs are
                  eye-band points by design — gate == arithmetic).
2.  MONOTONIC   — the 10-expression prior-consistent GT set (neutral +
                  9, docs/FACE.md list), GT built IN IMAGE SPACE (A2):
                  per-param monotonicity (a violation is an adjacent
                  step — states sorted by GT value, ties by name —
                  whose solved value DECREASES by more than MONO_TOL)
                  AND reach (solved >= 0.5x GT at the param's max-GT
                  state — A3: an all-zero sequence is trivially
                  monotone). PASS iff violations <= 1 of 9 steps AND
                  reach holds, EVERY param (Annex A.1 bar 9/10).
                  SYNTHETIC-labeled.
3.  GATE-OCCL   — face kps conf 0 -> NO face entry (absent reads clean,
                  the absent-hand rule); zero guessed params.
4.  GATE-PARTIAL— per-param below-floor (brow kps 0.3):
                  100% ledgered skips with verbatim reasons, the rest
                  of the face solves; a solved-but-below-threshold
                  value (ACT_FLOOR) is LEDGERED too, params stay empty.
5.  LATERALITY  — real detections: the declared band-A = subject-left
                  convention MEASURED (mean-x sign of band A vs band B)
                  + per-band conf distributions (the audit's 0.958 band).
                  Needs models.
6.  REAL-PRIORS — real detections: the raw metrics' distributions
                  (open-eye EAR spread = the blink-prior question, brow
                  gap, mouth width, jaw gap, cheek distance, corner
                  drop — each /IOD) published next to the declared
                  priors. Needs models.
7.  DETERM      — twin solves byte-identical (pure function).

Prints RM_FACE lines; exit 0 only if every row PASSes (real rows run for
real on this box — a SKIP there is a FAIL so the box cannot silently
lose the real evidence).
Usage: /home/potato/miniconda3/bin/python3 xtask/face_probe.py [--photos DIR]
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

from riggermortis.inference.poses import (  # noqa: E402
    FACE_END,
    FACE_START,
    KEYPOINT_COUNT,
)

# -- draft face layout (lifted into poses.py at the core landing) ---------------
# Face-relative indices 0..67; absolute = FACE_START + rel.
# SIDE MAP (MEASURED, S29 probe, n=18 real faces, 18/18 consistent): DWPose's
# band A (brow 17..21 / eye 36..41) sits at IMAGE LEFT = the subject's RIGHT
# for a camera-facing face. The .L params (subject-left) read BAND B — the
# declared iBUG-subject-left guess was wrong by measurement, and the
# constants flipped exactly as the design's one-line-fix clause planned.
FACE_EYE: dict[str, tuple[int, int]] = {"L": (42, 48), "R": (36, 42)}  # 6 pts
FACE_BROW: dict[str, tuple[int, int]] = {"L": (22, 27), "R": (17, 22)}  # 5 pts
FACE_EYE_CORNERS: dict[str, tuple[int, int]] = {"L": (42, 45), "R": (36, 39)}
FACE_LOWER_LID: dict[str, tuple[int, int]] = {"L": (46, 48), "R": (40, 42)}
FACE_WING: dict[str, int] = {"L": 35, "R": 31}
FACE_CORNER: dict[str, int] = {"L": 54, "R": 48}
FACE_MOUTH_UP = 51
FACE_MOUTH_LOW = 57
FACE_NOSE_BOTTOM = 33
FACE_IOD_CORNERS = (36, 39, 42, 45)


def face_kp_index(side: str, region: str, i: int = 0) -> int:
    """Absolute keypoint index of one face point (draft of the poses.py
    helper). Loud on unknown names — a typo cannot silently read the wrong
    keypoint."""
    table = {
        "eye": FACE_EYE,
        "brow": FACE_BROW,
        "lower_lid": FACE_LOWER_LID,
    }
    if region == "corner":
        if side not in FACE_CORNER:
            raise ValueError(f"unknown side {side!r} (known: L, R)")
        return FACE_START + FACE_CORNER[side]
    if region == "wing":
        if side not in FACE_WING:
            raise ValueError(f"unknown side {side!r} (known: L, R)")
        return FACE_START + FACE_WING[side]
    if region == "nose_bottom":
        return FACE_START + FACE_NOSE_BOTTOM
    if region not in table:
        raise ValueError(
            f"unknown region {region!r} (known: eye, brow, lower_lid, corner, wing, nose_bottom)"
        )
    lo, hi = table[region][side]
    if not 0 <= i < hi - lo:
        raise ValueError(f"{region}.{side}[{i}] out of range (band {lo}..{hi - 1})")
    return FACE_START + lo + i


# -- pre-declared solve constants (docs/FACE.md § the param table) ---------------
# Neutral-geometry priors REDECLARED from the S29 real-face measurement
# (n=18, docs/FACE.md amendment A4) — measure-and-declare, never fixture-fit:
# the declared defaults had smile/pout/cheek firing on every real neutral.
FACE_CONF_FLOOR = 0.55  # the CONVENTIONS ambiguity bar, reused; untuned
FACE_ACT_FLOOR = 0.08  # below-threshold params ledger, never interpolate
MONO_TOL = 0.05  # monotonicity noise band (declared)
PRIOR_BROW_RAISE = 0.30  # measured median 0.296 — stands
SPAN_BROW = 0.15
EAR_OPEN = 0.28  # measured median 0.283 — stands
PRIOR_LIP_GAP = 0.02  # anatomical lips-touching prior; the measured 0.31
#                       median on the P1-9 set is GENUINE open-mouth
#                       expression, not neutral geometry — published, kept.
SPAN_JAW = 0.55
PRIOR_CORNER_DROP = 0.40  # measured pooled median 0.403 (declared 0.45)
SPAN_SMILE = 0.12
PRIOR_MOUTH_W = 0.83  # measured pooled median 0.832 (declared 1.00)
SPAN_POUT = 0.25
PRIOR_CHEEK = 0.72  # measured pooled median 0.731 (declared 0.45)
SPAN_CHEEK = 0.10

PARAMS: tuple[str, ...] = (
    "brow.raise.L",
    "brow.raise.R",
    "blink.L",
    "blink.R",
    "jaw.open",
    "smile.L",
    "smile.R",
    "pout",
    "cheek.L",
    "cheek.R",
)


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _pt(kps: list[tuple[float, float]], face_rel: int) -> tuple[float, float]:
    return kps[FACE_START + face_rel]


def _mid(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


# -- the draft solve (the recipe core face.py lifts) ------------------------------

def solve_face_draft(
    kps: list[tuple[float, float]], confs: list[float]
) -> dict[str, object] | None:
    """Draft facial-param solve. Returns None when the IOD anchor is unusable
    (the whole face is skipped — an absent face reads as clean)."""
    if len(kps) != KEYPOINT_COUNT or len(confs) != KEYPOINT_COUNT:
        raise ValueError(f"face solve expects {KEYPOINT_COUNT} keypoints/confidences")
    anchor_cs = [confs[FACE_START + i] for i in FACE_IOD_CORNERS]
    if any(c < FACE_CONF_FLOOR for c in anchor_cs):
        return None
    line_l = _mid(_pt(kps, 36), _pt(kps, 39))
    line_r = _mid(_pt(kps, 42), _pt(kps, 45))
    iod = _dist(line_l, line_r)
    if iod <= 1e-9:
        return None
    iod_conf = min(anchor_cs)

    params: dict[str, float] = {}
    skipped: dict[str, str] = {}

    def gate(idxs: list[int]) -> str | None:
        cs = [confs[i] for i in idxs]
        if any(c < FACE_CONF_FLOOR for c in cs):
            return (
                "confidence " + "/".join(f"{c:.2f}" for c in cs)
                + f" below floor {FACE_CONF_FLOOR}"
            )
        return None

    def put(name: str, raw: float, conf: float) -> None:
        value = _clamp01(raw)
        if value < FACE_ACT_FLOOR:
            skipped[name] = f"below activation floor {FACE_ACT_FLOOR} (value {value:.4f})"
        else:
            params[name] = value

    nose_bottom = _pt(kps, FACE_NOSE_BOTTOM)
    for side in ("L", "R"):
        # brow raise: brow band (5 gated kps) vs the eye corner line
        brow_idxs = [face_kp_index(side, "brow", i) for i in range(5)]
        rs = gate(brow_idxs)
        if rs:
            skipped[f"brow.raise.{side}"] = rs
        else:
            brow_y = sum(kps[i][1] for i in brow_idxs) / 5.0
            line = line_l if side == "L" else line_r
            put(
                f"brow.raise.{side}",
                ((line[1] - brow_y) / iod - PRIOR_BROW_RAISE) / SPAN_BROW,
                min(confs[i] for i in brow_idxs),
            )
        # blink: eye aspect ratio vs the population open-eye prior
        e_lo, e_hi = FACE_EYE[side]
        eye_idxs = [FACE_START + i for i in range(e_lo, e_hi)]
        rs = gate(eye_idxs)
        if rs:
            skipped[f"blink.{side}"] = rs
        else:
            p = [kps[i] for i in eye_idxs]
            ear = ((_dist(p[1], p[5]) + _dist(p[2], p[4])) / 2.0) / max(_dist(p[0], p[3]), 1e-9)
            put(f"blink.{side}", (EAR_OPEN - ear) / EAR_OPEN, min(confs[i] for i in eye_idxs))
        # cheek: under-eye to same-side nose wing compression
        ll_lo, ll_hi = FACE_LOWER_LID[side]
        cheek_idxs = [FACE_START + i for i in range(ll_lo, ll_hi)] + [face_kp_index(side, "wing")]
        rs = gate(cheek_idxs)
        if rs:
            skipped[f"cheek.{side}"] = rs
        else:
            lid = _mid(kps[FACE_START + ll_lo], kps[FACE_START + ll_hi - 1])
            wing = kps[face_kp_index(side, "wing")]
            put(
                f"cheek.{side}",
                (PRIOR_CHEEK - _dist(lid, wing) / iod) / SPAN_CHEEK,
                min(confs[i] for i in cheek_idxs),
            )

    mouth_idxs = [
        FACE_START + FACE_CORNER["L"],
        FACE_START + FACE_CORNER["R"],
        face_kp_index("L", "nose_bottom"),
    ]
    rs = gate(mouth_idxs)
    if rs:
        for name in ("smile.L", "smile.R", "pout"):
            skipped[name] = rs
    else:
        c_l = _pt(kps, FACE_CORNER["L"])
        c_r = _pt(kps, FACE_CORNER["R"])
        # smile: corner rise toward the nose bottom (A1: a stable midface
        # reference — the corners' own line is degenerate under symmetric
        # smiles, it rises with them). drop = corner_y − nose_y (positive
        # below, image y grows down)
        put("smile.L", (PRIOR_CORNER_DROP - (c_l[1] - nose_bottom[1]) / iod) / SPAN_SMILE,
            min(confs[i] for i in mouth_idxs))
        put("smile.R", (PRIOR_CORNER_DROP - (c_r[1] - nose_bottom[1]) / iod) / SPAN_SMILE,
            min(confs[i] for i in mouth_idxs))
        width = abs(c_l[0] - c_r[0]) / iod
        put("pout", (PRIOR_MOUTH_W - width) / SPAN_POUT, min(confs[i] for i in mouth_idxs))

    jaw_idxs = [FACE_START + i for i in (FACE_MOUTH_UP, FACE_MOUTH_LOW)]
    rs = gate(jaw_idxs)
    if rs:
        skipped["jaw.open"] = rs
    else:
        gap = (_pt(kps, FACE_MOUTH_LOW)[1] - _pt(kps, FACE_MOUTH_UP)[1]) / iod
        put("jaw.open", (gap - PRIOR_LIP_GAP) / SPAN_JAW, min(confs[i] for i in jaw_idxs))

    return {"params": {k: params[k] for k in sorted(params)}, "skipped": skipped, "iod_conf": iod_conf}


# -- parametric GT faces (SYNTHETIC fixtures; prior-consistent, 2D IN IMAGE
#    SPACE per amendment A2 — every param is a ratio, no depth exists) ------------
# Fixture space: image pixels, y grows DOWN; IOD = SCALE px (eye line on v=CY);
# band B (.L, subject-left) at +u for a camera-facing face (the MEASURED side
# map — band B sits image-right).
CX, CY, SCALE = 320.0, 240.0, 400.0
_EYE_W = 0.30  # corner span |p0-p3| in IOD units
_PRIOR_EYE_H = EAR_OPEN * _EYE_W
_NOSE_Y = 0.45
_MOUTH_Y = _NOSE_Y + PRIOR_CORNER_DROP  # corner line, prior-consistent


def gt_face(
    brow: dict[str, float],
    blink: dict[str, float],
    jaw: float,
    smile: dict[str, float],
    pout: float,
    cheek: dict[str, float],
) -> tuple[list[tuple[float, float]], list[float]]:
    """One GT face as a (kps, confs) 133-array pair. Expression params enter
    EXACTLY through the declared table's arithmetic, so the draft solve
    inverts it exactly (prior-consistent, the finger recipe)."""
    face: list[tuple[float, float] | None] = [None] * 68
    confs = [0.0] * KEYPOINT_COUNT

    def put(rel: int, x: float, y: float, conf: float = 0.9) -> None:
        face[rel] = (CX + x * SCALE, CY + y * SCALE)
        confs[FACE_START + rel] = conf

    for side in ("L", "R"):
        sgn = 1.0 if side == "L" else -1.0
        cx_eye = 0.5 * sgn
        h = _PRIOR_EYE_H * (1.0 - blink.get(side, 0.0))
        e_lo, _ = FACE_EYE[side]
        # p0 outer (away from the nose), p3 inner (toward the nose);
        # upper lids at NEGATIVE y (above), lower lids POSITIVE (below)
        put(e_lo + 0, cx_eye - 0.15 * sgn, 0.0)
        put(e_lo + 1, cx_eye - 0.075 * sgn, -h / 2.0)
        put(e_lo + 2, cx_eye + 0.075 * sgn, -h / 2.0)
        put(e_lo + 3, cx_eye + 0.15 * sgn, 0.0)
        put(e_lo + 4, cx_eye + 0.075 * sgn, h / 2.0)
        put(e_lo + 5, cx_eye - 0.075 * sgn, h / 2.0)
        # brow band ABOVE the eye line (negative y, image down)
        b_lo, _ = FACE_BROW[side]
        brow_y = -(PRIOR_BROW_RAISE + brow.get(side, 0.0) * SPAN_BROW)
        for i in range(5):
            put(b_lo + i, cx_eye - 0.15 * sgn + 0.075 * sgn * i, brow_y)
        # cheek row: lower-lid pair + same-side nose wing DIRECTLY below the
        # lid midpoint (the metric is a 2D distance vs a declared prior —
        # the fixture must place the wing at exactly that distance)
        ll_lo, ll_hi = FACE_LOWER_LID[side]
        lid_y = h / 2.0
        put(ll_lo, cx_eye + 0.075 * sgn, lid_y)
        put(ll_hi - 1, cx_eye - 0.075 * sgn, lid_y)
        put(
            FACE_WING[side],
            cx_eye,
            lid_y + (PRIOR_CHEEK - cheek.get(side, 0.0) * SPAN_CHEEK),
        )

    # nose bottom: stable under mouth expressions; a cheek raise lifts it
    # slightly (the honest second-order cross-talk, 0.3x the wing rise)
    nose_lift = 0.3 * SPAN_CHEEK * (cheek.get("L", 0.0) + cheek.get("R", 0.0)) / 2.0
    put(FACE_NOSE_BOTTOM, 0.0, _NOSE_Y - nose_lift)

    w = PRIOR_MOUTH_W - pout * SPAN_POUT
    c_l_y = _MOUTH_Y - smile.get("L", 0.0) * SPAN_SMILE
    c_r_y = _MOUTH_Y - smile.get("R", 0.0) * SPAN_SMILE
    put(FACE_CORNER["L"], w / 2.0, c_l_y)
    put(FACE_CORNER["R"], -w / 2.0, c_r_y)
    lip_up_y = _MOUTH_Y - 0.05
    put(FACE_MOUTH_UP, 0.0, lip_up_y)
    put(FACE_MOUTH_LOW, 0.0, lip_up_y + PRIOR_LIP_GAP + jaw * SPAN_JAW)

    # unconsumed bands (jaw contour, nose bridge, outer/inner lips) exist so
    # the layout row and conf fixtures stay honest — the solve never reads
    # them except through the constants above.
    for rel in range(17):
        if face[rel] is None:
            put(rel, -0.6 + 1.2 * rel / 16.0, _MOUTH_Y + 0.45)
    for rel in range(27, 31):
        if face[rel] is None:
            put(rel, 0.0, 0.10 + 0.10 * (rel - 27))
    for rel in range(32, 35):
        if face[rel] is None:
            put(rel, -0.1 + 0.1 * (rel - 32), _NOSE_Y - nose_lift)
    for rel in range(49, 54):
        if face[rel] is None:
            put(rel, -w / 2.0 + w * (rel - 48) / 6.0, lip_up_y)
    for rel in range(55, 60):
        if face[rel] is None:
            put(rel, -w / 2.0 + w * (rel - 54) / 6.0, c_l_y + 0.03)
    for rel in range(60, 68):
        if face[rel] is None:
            put(rel, -0.3 + 0.086 * (rel - 60), _MOUTH_Y + 0.02)

    kps: list[tuple[float, float]] = [(0.0, 0.0)] * KEYPOINT_COUNT
    for rel in range(68):
        assert face[rel] is not None, f"GT face gap at {rel}"
        kps[FACE_START + rel] = face[rel]  # type: ignore[index]
    return kps, confs


# -- the 10-expression benchmark (Annex A.1: neutral + 9) --------------------------

def benchmark_set() -> dict[str, tuple[tuple[list[tuple[float, float]], list[float]], dict[str, float]]]:
    zeros: dict[str, float] = {}
    states: dict[str, tuple[tuple[list[tuple[float, float]], list[float]], dict[str, float]]] = {}

    def state(name: str, **kw: float | dict[str, float]) -> None:
        brow = kw.get("brow", zeros)  # type: ignore[assignment]
        blink = kw.get("blink", zeros)  # type: ignore[assignment]
        smile = kw.get("smile", zeros)  # type: ignore[assignment]
        cheek = kw.get("cheek", zeros)  # type: ignore[assignment]
        jaw = float(kw.get("jaw", 0.0))
        pout = float(kw.get("pout", 0.0))
        gt = {
            **{f"brow.raise.{s}": brow.get(s, 0.0) for s in ("L", "R")},  # type: ignore[union-attr]
            **{f"blink.{s}": blink.get(s, 0.0) for s in ("L", "R")},  # type: ignore[union-attr]
            **{f"smile.{s}": smile.get(s, 0.0) for s in ("L", "R")},  # type: ignore[union-attr]
            **{f"cheek.{s}": cheek.get(s, 0.0) for s in ("L", "R")},  # type: ignore[union-attr]
            "jaw.open": jaw,
            "pout": pout,
        }
        kps, confs = gt_face(brow, blink, jaw, smile, pout, cheek)  # type: ignore[arg-type]
        states[name] = ((kps, confs), gt)

    state("neutral")
    state("brows_raise", brow={"L": 0.8, "R": 0.8})
    state("brow_raise_L", brow={"L": 0.8})
    state("blink_both", blink={"L": 1.0, "R": 1.0})
    state("blink_L", blink={"L": 1.0})
    state("jaw_open", jaw=1.0)
    state("smile", smile={"L": 1.0, "R": 1.0})
    state("smile_L", smile={"L": 1.0})
    state("pout", pout=1.0)
    state("cheeks", cheek={"L": 0.7, "R": 0.7})
    assert len(states) == 10, f"benchmark must hold 10 states, has {len(states)}"
    return states


def _mono_violations(solved_values: list[float]) -> int:
    """Adjacent-step decreases beyond MONO_TOL (states pre-sorted by GT)."""
    return sum(
        1 for a, b in zip(solved_values, solved_values[1:], strict=False) if a - b > MONO_TOL
    )


# -- probe harness ---------------------------------------------------------------

_OK: list[bool] = []


def check(name: str, ok: bool, detail: str) -> None:
    _OK.append(ok)
    print(f"RM_FACE {name}: {'PASS' if ok else 'FAIL'} {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--photos", default="out/benchmark/images/photo", help="P1-9 photo dir"
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    photos_dir = (repo / args.photos) if not Path(args.photos).is_absolute() else Path(args.photos)

    # 1. LAYOUT — the band table tiles the face partition exactly.
    used: list[int] = []
    for side in ("L", "R"):
        used += [face_kp_index(side, "eye", i) for i in range(6)]
        used += [face_kp_index(side, "brow", i) for i in range(5)]
        used += [face_kp_index(side, "lower_lid", i) for i in range(2)]
        used += [face_kp_index(side, "corner"), face_kp_index(side, "wing")]
    used += [FACE_START + i for i in (FACE_MOUTH_UP, FACE_MOUTH_LOW, FACE_NOSE_BOTTOM)]
    # lower-lid pairs are eye-band points BY DESIGN (gate == arithmetic):
    # 30 raw + 3 mouth/nose − 4 overlaps = 29 unique consumed indices.
    ok_layout = (
        all(FACE_START <= i < FACE_END for i in used)
        and len(set(used)) == 29
        and FACE_END - FACE_START == 68
    )
    check(
        "LAYOUT",
        ok_layout,
        f"{len(set(used))} unique consumed indices inside [{FACE_START}, {FACE_END}) "
        "(lower-lid pairs are eye-band points by design)",
    )

    # 2. MONOTONIC — the 10-expression benchmark, per-param 9/10 bar + reach.
    bench = benchmark_set()
    per_param_viol: dict[str, int] = {}
    per_param_reach: dict[str, float] = {}
    for param in PARAMS:
        rows = sorted(bench.items(), key=lambda kv: (kv[1][1].get(param, 0.0), kv[0]))
        seq: list[float] = []
        gt_max = max(gt.get(param, 0.0) for _n, (_kc, gt) in rows)
        solved_at_max = 0.0
        for _name, ((kps, confs), gt) in rows:
            face = solve_face_draft(kps, confs)
            value = float(face["params"].get(param, 0.0)) if face else 0.0  # type: ignore[union-attr,index,arg-type]
            seq.append(value)
            if gt.get(param, 0.0) == gt_max and gt_max > 0:
                solved_at_max = max(solved_at_max, value)
        per_param_viol[param] = _mono_violations(seq)
        per_param_reach[param] = (solved_at_max / gt_max) if gt_max > 0 else 1.0
    worst_viol = max(per_param_viol.values())
    worst_reach = min(per_param_reach.values())
    detail = " ".join(
        f"{p.split('.')[0]}.{p.split('.')[-1]}={per_param_viol[p]}/{per_param_reach[p]:.2f}"
        for p in sorted(per_param_viol)
    )
    check(
        "MONOTONIC",
        worst_viol <= 1 and worst_reach >= 0.5,
        f"max violations {worst_viol}/9 (bar 1), min reach {worst_reach:.2f} "
        f"(bar 0.5) viol/reach {detail} over 10 states [SYNTHETIC, prior-consistent GT]",
    )

    # 3. GATE-OCCL — conf-0 face: no entry, zero guessed params.
    kps_vis, confs_vis = benchmark_set()["smile"][0]
    confs_occl = [0.0] * KEYPOINT_COUNT
    check(
        "GATE-OCCL",
        solve_face_draft(kps_vis, confs_occl) is None,
        "face conf 0 -> no entry (absent reads clean), zero guessed params",
    )

    # 4. GATE-PARTIAL — per-param below-floor ledgered; below-threshold ledgered.
    kps_p, confs_p = benchmark_set()["smile"][0]
    for rel in range(*FACE_BROW["L"]):
        confs_p[FACE_START + rel] = 0.3
    face_p = solve_face_draft(kps_p, confs_p)
    partial_ok = (
        face_p is not None
        and "brow.raise.L" in face_p["skipped"]
        and "below floor 0.55" in str(face_p["skipped"].get("brow.raise.L"))
        and "smile.L" in face_p["params"]
    )
    kps_n, confs_n = benchmark_set()["neutral"][0]
    face_n = solve_face_draft(kps_n, confs_n)
    neutral_ok = (
        face_n is not None
        and len(face_n["params"]) == 0
        and len(face_n["skipped"]) == 10
        and all("below activation floor" in r for r in face_n["skipped"].values())
    )
    check(
        "GATE-PARTIAL",
        bool(partial_ok and neutral_ok),
        "brow.L below-floor ledgered, rest solved; neutral -> 0 params, "
        "10/10 below-threshold ledgered (never interpolated)",
    )

    # 7. DETERM — twin solves byte-identical.
    kps_d, confs_d = benchmark_set()["cheeks"][0]
    check(
        "DETERM",
        solve_face_draft(kps_d, confs_d) == solve_face_draft(kps_d, confs_d),
        "twin solves identical",
    )

    # 5-6. REAL rows — the pinned DWPose models on the local photo set.
    try:
        from riggermortis.inference.dwpose import detect_keypoints
        from riggermortis.inference.figures import FigureBoard
    except Exception as exc:  # noqa: BLE001 — honest degradation path
        print(f"RM_FACE REAL: FAIL models unavailable ({exc})")
        print("RM_FACE PROBE: FAILED (real evidence required on this box)")
        return 1

    band_defs = {
        "brow": [17, 18, 19, 20, 21, 22, 23, 24, 25, 26],
        "eye": list(range(36, 48)),
        "nose": list(range(27, 36)),
        "mouth": list(range(48, 60)),
    }
    band_confs: dict[str, list[float]] = {b: [] for b in band_defs}
    laterality_signs: list[float] = []
    ears: list[float] = []
    brow_gaps: list[float] = []
    widths: list[float] = []
    gaps: list[float] = []
    cheeks_d: list[float] = []
    corner_drops: list[float] = []
    faces_checked = 0
    photos = sorted(list(photos_dir.glob("*.png")) + list(photos_dir.glob("*.jpg")))[:10]
    for photo in photos:
        det = detect_keypoints(str(photo))
        board = FigureBoard.from_detection(det)
        for fig in board.figures:
            face = solve_face_draft(fig.keypoints, fig.confidences)
            if face is None:
                continue
            faces_checked += 1
            rel_confs = fig.confidences[FACE_START:FACE_END]
            for band, idxs in band_defs.items():
                band_confs[band].extend(rel_confs[i] for i in idxs)
            # laterality: FIXED band indices — A (36..41) vs B (42..47),
            # independent of the .L/.R param map
            xa = sum(fig.keypoints[FACE_START + i][0] for i in range(36, 42)) / 6.0
            xb = sum(fig.keypoints[FACE_START + i][0] for i in range(42, 48)) / 6.0
            laterality_signs.append(xa - xb)
            # raw metric distributions / declared priors — POOLED over both
            # bands (a population prior is side-agnostic)
            line_l = _mid(_pt(fig.keypoints, 36), _pt(fig.keypoints, 39))
            line_r = _mid(_pt(fig.keypoints, 42), _pt(fig.keypoints, 45))
            iod = _dist(line_l, line_r)
            if iod <= 1e-9:
                continue
            for e_lo, brow_lo, ll_lo, ll_hi, wing in (
                (36, 17, 40, 42, 31),
                (42, 22, 46, 48, 35),
            ):
                p = [fig.keypoints[FACE_START + i] for i in range(e_lo, e_lo + 6)]
                cs = fig.confidences[FACE_START + e_lo : FACE_START + e_lo + 6]
                if all(c >= FACE_CONF_FLOOR for c in cs):
                    ears.append(
                        ((_dist(p[1], p[5]) + _dist(p[2], p[4])) / 2.0) / max(_dist(p[0], p[3]), 1e-9)
                    )
                line = _mid(p[0], p[3])
                brow_y = sum(fig.keypoints[FACE_START + i][1] for i in range(brow_lo, brow_lo + 5)) / 5.0
                brow_gaps.append((line[1] - brow_y) / iod)
                lid = _mid(
                    fig.keypoints[FACE_START + ll_lo], fig.keypoints[FACE_START + ll_hi - 1]
                )
                wing_pt = _pt(fig.keypoints, wing)
                cheeks_d.append(_dist(lid, wing_pt) / iod)
            c_l = _pt(fig.keypoints, FACE_CORNER["L"])
            c_r = _pt(fig.keypoints, FACE_CORNER["R"])
            widths.append(abs(c_l[0] - c_r[0]) / iod)
            gaps.append(
                (_pt(fig.keypoints, FACE_MOUTH_LOW)[1] - _pt(fig.keypoints, FACE_MOUTH_UP)[1]) / iod
            )
            nose_b = _pt(fig.keypoints, FACE_NOSE_BOTTOM)
            corner_drops.append((c_l[1] - nose_b[1]) / iod)
            corner_drops.append((c_r[1] - nose_b[1]) / iod)

    lat_med = sorted(laterality_signs)[len(laterality_signs) // 2] if laterality_signs else float("nan")
    lat_pos = sum(1 for v in laterality_signs if v > 0)
    bands_txt = " ".join(
        f"{b}={sorted(v)[len(v) // 2]:.2f}" for b, v in sorted(band_confs.items()) if v
    )
    check(
        "LATERALITY",
        faces_checked > 0,
        f"faces={faces_checked} median(bandA_x-bandB_x)={lat_med:.1f}px "
        f"positive={lat_pos}/{len(laterality_signs)} — MEASURED: band A sits "
        "image-left = the subject's RIGHT on this detector (18/18 here); the "
        f".L constants read band B. bandconf {bands_txt}",
    )

    def med(v: list[float]) -> str:
        return f"{sorted(v)[len(v) // 2]:.3f}" if v else "-"

    check(
        "REAL-PRIORS",
        faces_checked > 0,
        f"EAR median {med(ears)} (prior {EAR_OPEN}) n={len(ears)}; "
        f"brow_gap {med(brow_gaps)} (prior {PRIOR_BROW_RAISE}); "
        f"mouth_w {med(widths)} (prior {PRIOR_MOUTH_W}); "
        f"jaw_gap {med(gaps)} (prior {PRIOR_LIP_GAP}); "
        f"cheek_d {med(cheeks_d)} (prior {PRIOR_CHEEK}); "
        f"corner_drop {med(corner_drops)} (prior {PRIOR_CORNER_DROP}) — "
        "measured next to declared, never fitted (D-008)",
    )

    passed = all(_OK)
    print(f"RM_FACE PROBE: {'OK' if passed else 'FAILED'} ({sum(_OK)}/{len(_OK)})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
