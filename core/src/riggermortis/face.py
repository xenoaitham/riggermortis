"""Facial expression params (P8-4): the D-022 namespace + the face solve.

Design of record: docs/FACE.md (including the amendment record A1-A4 the
probe earned before this build). The DECISIONS entry for the namespace is
D-022, written when this module landed. The frozen 22-role canonical core
is untouched: face params ride ``CanonicalPose.face`` (default None) and
consumers that ignore faces work byte-identically.

The one structural fact (docs/FACE.md § the insight): every P8-4 param is
a DIMENSIONLESS landmark ratio (IOD- or aspect-normalized) — the solve is
pure 2D arithmetic on the detection the body solve already consumed, no
canonical conversion, no depth prior. The payload carries SOLVED PARAMS
(the D-009 pattern), not landmark geometry.

The honesty rules (the finger rules one level up): the face solves only
when the IOD anchor's four corner kps clear ``FACE_CONF_FLOOR`` (an
absent face reads as clean); a param whose consumed kps fall below the
floor is SKIPPED + LEDGERED, never guessed; a solved value below
``FACE_ACT_FLOOR`` is LEDGERED as below-threshold and never interpolated
into ``params``. GAZE IS NOT A PARAM: the pinned DWPose has no iris kps;
gaze enters only if a detector variant supplies them (conditional-OUT).

Pure stdlib (math only), deterministic everywhere (sorted keys, fixed
tie-breaks). ``mirrored()`` swaps ``.L``/``.R`` params — a geometry-free
param swap.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .errors import RiggermortisError
from .inference.poses import (
    FACE_CORNER,
    FACE_EYE_CORNERS,
    FACE_IOD_CORNERS,
    FACE_MOUTH_LOW,
    FACE_MOUTH_UP,
    FACE_NOSE_BOTTOM,
    FACE_START,
    KEYPOINT_COUNT,
    face_kp_index,
)

# -- the D-022 namespace (10 params) ----------------------------------------------
#: The fixed facial parameter set (docs/FACE.md § the published table).
#: Names are stable public API — never rename casually (the D-021 rule).
FACE_PARAMS: tuple[str, ...] = (
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

#: Depth for the per-param solve.
FACE_CONF_FLOOR = 0.55  # the CONVENTIONS ambiguity bar, reused; untuned
#: Activation floor: below this a solved value is LEDGERED, not applied.
FACE_ACT_FLOOR = 0.08
#: Neutral-geometry priors (docs/FACE.md constants table; the three marked
#: redeclared values were measured on real faces by the S29 probe — pooled
#: over both face bands — before this build; amendment A4).
PRIOR_BROW_RAISE = 0.30  # measured pooled median 0.296 — stands
SPAN_BROW = 0.15
EAR_OPEN = 0.28  # measured pooled median 0.283 — stands
PRIOR_LIP_GAP = 0.02  # anatomical lips-touching prior (see docs/FACE.md)
SPAN_JAW = 0.55
PRIOR_CORNER_DROP = 0.40  # measured pooled median 0.403 (declared 0.45)
SPAN_SMILE = 0.12
PRIOR_MOUTH_W = 0.83  # measured pooled median 0.832 (declared 1.00)
SPAN_POUT = 0.25
PRIOR_CHEEK = 0.72  # measured pooled median 0.731 (declared 0.45)
SPAN_CHEEK = 0.10

Vec3 = tuple[float, float, float]

#: The declared bone-rotation plan (docs/FACE.md § apply): per param, the
#: canonical rotation axis (character space: X = character left, Y = depth,
#: Z = up) and the angle at param 1.0, in degrees, DECLARED untuned. The
#: rig's preset decides WHICH bone; this table decides HOW MUCH. Side-sensed
#: axes where mirroring matters (a +Y rotation lowers a +X-side brow and
#: raises a −X-side one — the right-hand rule around the depth axis).
FACE_BONE_PLAN: dict[str, tuple[Vec3, float]] = {
    "jaw.open": ((1.0, 0.0, 0.0), 25.0),
    "blink.L": ((1.0, 0.0, 0.0), 12.0),
    "blink.R": ((1.0, 0.0, 0.0), 12.0),
    "brow.raise.L": ((0.0, -1.0, 0.0), 20.0),
    "brow.raise.R": ((0.0, 1.0, 0.0), 20.0),
    "smile.L": ((0.0, -1.0, 0.0), 10.0),
    "smile.R": ((0.0, 1.0, 0.0), 10.0),
    "pout": ((1.0, 0.0, 0.0), 10.0),
    "cheek.L": ((0.0, -1.0, 0.0), 10.0),
    "cheek.R": ((0.0, 1.0, 0.0), 10.0),
}


def is_face_param(name: str) -> bool:
    """True for D-022 namespace params (never true for role names)."""
    return name in FACE_PARAMS


# -- result model -----------------------------------------------------------------

@dataclass
class FacePose:
    """One solved face: the applied params, the LOUD ledger, anchor strength."""

    params: dict[str, float] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    iod_conf: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "params": {k: round(self.params[k], 4) for k in sorted(self.params)},
            "skipped": {k: self.skipped[k] for k in sorted(self.skipped)},
            "iod_conf": round(self.iod_conf, 4),
        }

    @staticmethod
    def from_dict(d: dict[str, object]) -> FacePose:
        if not isinstance(d, dict):
            raise RiggermortisError(
                "face pose must be a JSON object",
                hint="expected {'params': {...}, 'skipped': {...}, 'iod_conf': c} "
                     "(docs/FACE.md, the D-022 namespace)",
            )
        raw_params = d.get("params", {})
        if not isinstance(raw_params, dict):
            raise RiggermortisError(
                "face 'params' must be an object keyed by param name",
                hint=f"known params: {', '.join(FACE_PARAMS)}",
            )
        unknown = sorted(set(raw_params) - set(FACE_PARAMS))
        if unknown:
            raise RiggermortisError(
                f"unknown face param(s): {', '.join(unknown)}",
                hint=f"known params: {', '.join(FACE_PARAMS)}",
            )
        params: dict[str, float] = {}
        for k in sorted(raw_params):
            v = float(raw_params[k])  # type: ignore[arg-type]
            if not 0.0 <= v <= 1.0:
                raise RiggermortisError(
                    f"face param {k!r} must be in [0, 1], got {v}",
                    hint="params are normalized; clamp at the source",
                )
            params[k] = v
        raw_skipped = d.get("skipped", {})
        if not isinstance(raw_skipped, dict):
            raise RiggermortisError(
                "face 'skipped' must be an object keyed by param name",
                hint="each value is the verbatim below-floor / below-threshold reason",
            )
        return FacePose(
            params=params,
            skipped={str(k): str(v) for k, v in raw_skipped.items()},
            iod_conf=float(d.get("iod_conf", 0.0)),  # type: ignore[arg-type]
        )

    def mirrored(self) -> FacePose:
        """The mirrored face: ``.L``/``.R`` param values swap sides; center
        params carry; the ledger transfers with sides swapped (its reasons
        are confidence text, side-free). A geometry-free param swap."""
        def swap(key: str) -> str:
            if key.endswith(".L"):
                return key[:-2] + ".R"
            if key.endswith(".R"):
                return key[:-2] + ".L"
            return key

        return FacePose(
            params={swap(k): v for k, v in self.params.items()},
            skipped={swap(k): v for k, v in self.skipped.items()},
            iod_conf=self.iod_conf,
        )


# -- the solve ---------------------------------------------------------------------

def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def solve_face(
    kps: list[tuple[float, float]], confs: list[float]
) -> FacePose | None:
    """Solve one detected figure's expression params (docs/FACE.md table).

    Returns None when the IOD anchor is unusable — the whole face is
    skipped, an absent face reads as clean (the absent-hand rule).
    Deterministic: same inputs, same output, byte-for-byte.
    """
    if len(kps) != KEYPOINT_COUNT or len(confs) != KEYPOINT_COUNT:
        raise RiggermortisError(
            f"face solve expects {KEYPOINT_COUNT} keypoints/confidences, "
            f"got {len(kps)}/{len(confs)}",
            hint="solve_face consumes the same detection the body solve did",
        )
    start = FACE_START

    def pt(rel: int) -> tuple[float, float]:
        return kps[start + rel]

    anchor_cs = [confs[start + i] for i in FACE_IOD_CORNERS]
    if any(c < FACE_CONF_FLOOR for c in anchor_cs):
        return None

    def mid(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

    def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    corner_l = pt(FACE_EYE_CORNERS["L"][0])
    corner_li = pt(FACE_EYE_CORNERS["L"][1])
    corner_r = pt(FACE_EYE_CORNERS["R"][0])
    corner_ri = pt(FACE_EYE_CORNERS["R"][1])
    line_l = mid(corner_l, corner_li)
    line_r = mid(corner_r, corner_ri)
    iod = dist(line_l, line_r)
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
            skipped[name] = (
                f"below activation floor {FACE_ACT_FLOOR} (value {value:.4f})"
            )
        else:
            params[name] = value

    nose_bottom = pt(FACE_NOSE_BOTTOM)
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
        eye_idxs = [face_kp_index(side, "eye", i) for i in range(6)]
        rs = gate(eye_idxs)
        if rs:
            skipped[f"blink.{side}"] = rs
        else:
            p = [kps[i] for i in eye_idxs]
            ear = (
                (dist(p[1], p[5]) + dist(p[2], p[4])) / 2.0
            ) / max(dist(p[0], p[3]), 1e-9)
            put(
                f"blink.{side}",
                (EAR_OPEN - ear) / EAR_OPEN,
                min(confs[i] for i in eye_idxs),
            )
        # cheek: under-eye to same-side nose wing compression
        lid_lo = face_kp_index(side, "lower_lid", 0)
        lid_hi = face_kp_index(side, "lower_lid", 1)
        cheek_idxs = [lid_lo, lid_hi, face_kp_index(side, "wing")]
        rs = gate(cheek_idxs)
        if rs:
            skipped[f"cheek.{side}"] = rs
        else:
            lid = mid(kps[lid_lo], kps[lid_hi])
            wing = kps[face_kp_index(side, "wing")]
            put(
                f"cheek.{side}",
                (PRIOR_CHEEK - dist(lid, wing) / iod) / SPAN_CHEEK,
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
        c_l = pt(FACE_CORNER["L"])
        c_r = pt(FACE_CORNER["R"])
        # smile: corner rise toward the nose bottom (amendment A1 — a
        # stable midface reference; the corners' own line is degenerate
        # under symmetric smiles, it rises with them)
        mouth_conf = min(confs[i] for i in mouth_idxs)
        put(
            "smile.L",
            (PRIOR_CORNER_DROP - (c_l[1] - nose_bottom[1]) / iod) / SPAN_SMILE,
            mouth_conf,
        )
        put(
            "smile.R",
            (PRIOR_CORNER_DROP - (c_r[1] - nose_bottom[1]) / iod) / SPAN_SMILE,
            mouth_conf,
        )
        width = abs(c_l[0] - c_r[0]) / iod
        put("pout", (PRIOR_MOUTH_W - width) / SPAN_POUT, mouth_conf)

    jaw_idxs = [FACE_START + FACE_MOUTH_UP, FACE_START + FACE_MOUTH_LOW]
    rs = gate(jaw_idxs)
    if rs:
        skipped["jaw.open"] = rs
    else:
        gap = (pt(FACE_MOUTH_LOW)[1] - pt(FACE_MOUTH_UP)[1]) / iod
        put("jaw.open", (gap - PRIOR_LIP_GAP) / SPAN_JAW, min(confs[i] for i in jaw_idxs))

    return FacePose(
        params={k: params[k] for k in sorted(params)},
        skipped=skipped,
        iod_conf=iod_conf,
    )


# -- apply math (pure; the bpy side lives in the add-on) ---------------------------

@dataclass
class FaceBoneRotation:
    """One face-bound bone's declared rotation: param, bone, canonical axis,
    angle at the solved param value."""

    param: str
    bone: str
    axis: Vec3
    angle_rad: float

    def to_dict(self) -> dict[str, object]:
        return {
            "param": self.param,
            "bone": self.bone,
            "axis": [round(v, 6) for v in self.axis],
            "angle_rad": round(self.angle_rad, 6),
            "angle_deg": round(math.degrees(self.angle_rad), 3),
        }


def face_bone_rotations(
    face: FacePose, face_bones: dict[str, str]
) -> list[FaceBoneRotation]:
    """Declared axis-angle rotations for the solved, bound params (sorted by
    param — deterministic; the caller joins them into the FK order)."""
    out: list[FaceBoneRotation] = []
    for param in sorted(face_bones):
        value = face.params.get(param)
        if value is None:
            continue  # ledgered at the solve — never guessed
        axis_plan, max_deg = FACE_BONE_PLAN[param]
        out.append(
            FaceBoneRotation(
                param=param,
                bone=face_bones[param],
                axis=axis_plan,
                angle_rad=math.radians(max_deg) * value,
            )
        )
    return out
