"""P9-2 volume pipeline shared constants + pure helpers (probe/measure/rows).

The volume instrument is TWO-WORLD (Blender renders + apply; onnxruntime
masks + solve), so the pipeline is single-mode scripts orchestrated by the
bash block in xtask/verify_pose_apply.sh (the D-009 shape — no subprocess
in any of these scripts):

1. RM_VOL_STAGE=A blender xtask/volume_probe.py  -> base/reference renders
2. $PY xtask/volume_measure.py                   -> u2net masks + the solve
3. RM_VOL_STAGE=B blender xtask/volume_probe.py  -> the candidate applies
4. $PY xtask/volume_rows.py                      -> the IoU rows + verdict

All scripts meet on ONE fixed scratch directory under the repo's own
``out/`` (gitignored — the fixture law: nothing committed but the numbers).
Every scratch path is a MODULE-LEVEL CONSTANT built from fully literal
joins below — no dynamic path building, no formatted names, no
parameterized path helpers, no path-parameterized open() (the Mimosa gate
shapes). The declared constants here are docs/VOLUME.md's law: the band
table, the fixture boxes, the reference classes, the bars.
"""
from __future__ import annotations

import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Declared fixture constants (untuned D-008). The volume fixture class
# deviates from the S36 base in ONE declared way: the arms hang BESIDE the
# torso (x +-0.28) with a gap, so the person silhouette is honest — the S36
# slab was joint-position furniture; volume benchmarks need silhouettes.
# ---------------------------------------------------------------------------
HIPS_Z = 0.98
TORSO_SPAN = 0.44  # |hips - neck|, meters (the P9-1 declared base)

# Band regions as [z0, z1] in T-fractions relative to the hips head, with
# the canonical roles whose skin carries the region (the fixture's
# deterministic nearest-bone weights ARE the region map).
BANDS: tuple[tuple[str, float, float, tuple[str, ...]], ...] = (
    ("vol.thigh_w", -0.98, -0.41, ("upper_leg.L", "upper_leg.R")),
    ("vol.hip_w", -0.41, 0.09, ("hips",)),
    ("vol.waist_w", 0.09, 0.45, ("spine",)),
    ("vol.chest_w", 0.45, 0.91, ("chest",)),
)
BAND_TENT_T = 0.05  # T-fractions; the linear transition half-width
# The measurement constants + pure helpers live in CORE since P9-3 (the
# one-copy law — docs/WIRING.md A1; the product solve and this pipeline
# share them). Values byte-identical to the S37-certified set; the volume
# gate re-run proves the lift. Re-exported for the pipeline scripts
# (probe/measure/rows read them through this namespace).
from riggermortis.sculpt import (  # noqa: E402
    ANCHOR_FRACS as ANCHOR_FRACS,
)
from riggermortis.sculpt import (
    MEDIAN_HALF_BAND as MEDIAN_HALF_BAND,
)
from riggermortis.sculpt import (
    THIGH_ANCHOR_FRAC as THIGH_ANCHOR_FRAC,  # mid-band (fixture repair A2)
)
from riggermortis.sculpt import (
    region_widths as region_widths,
)
from riggermortis.sculpt import (
    runs as runs,
)
from riggermortis.sculpt import (
    solve_factors as solve_factors,
)

CLAMP_LO, CLAMP_HI = 0.5, 2.0  # declared solve clamp (loud when it fires)

# Person-mesh boxes (declared, meters): (name, x0, x1, y0, y1, z0, z1, band).
# `band` is the multiplier key the reference classes scale (None = fixed).
# Fixture repair A1 (measured 2026-09-30, the A8 law): the first draft had
# arms at +-0.24..0.32 and legs +-0.08..0.21 — u2net BRIDGED the 7 px
# arm-torso gap on widened pelvis classes (random per render, poisoning the
# hip rows) and FILLED the 26 px crotch gap (poisoning the thigh sum). The
# landed class: arms +-0.34..0.42 (slight A-pose, no bridging), legs closed
# to touching +-0.02..0.17 (the crotch-fill class cannot exist), leg bones
# under the leg mesh (the inflate centers = the mesh centers).
BOXES: tuple[tuple[str, float, float, float, float, float, float, str | None], ...] = (
    ("pelvis", -0.17, 0.17, -0.10, 0.10, 0.80, 1.02, "hip"),
    ("waist", -0.13, 0.13, -0.085, 0.085, 1.02, 1.178, "waist"),
    ("chest", -0.19, 0.19, -0.105, 0.105, 1.178, 1.38, "chest"),
    ("neck", -0.05, 0.05, -0.05, 0.05, 1.38, 1.46, None),
    ("head", -0.09, 0.09, -0.10, 0.10, 1.46, 1.68, None),
    ("arm.L", 0.34, 0.42, -0.05, 0.05, 0.90, 1.36, None),
    ("arm.R", -0.42, -0.34, -0.05, 0.05, 0.90, 1.36, None),
    ("leg.L", 0.02, 0.17, -0.09, 0.09, 0.02, 0.80, "thigh"),
    ("leg.R", -0.17, -0.02, -0.09, 0.09, 0.02, 0.80, "thigh"),
)
LEG_CENTERS = {"leg.L": 0.095, "leg.R": -0.095}

REF_CLASSES: dict[str, dict[str, float]] = {
    "wide_hip": {"hip": 1.20, "waist": 1.0, "chest": 1.0, "thigh": 1.0},
    "thick_thigh": {"hip": 1.0, "waist": 1.0, "chest": 1.0, "thigh": 1.20},
    "heavy": {"hip": 1.15, "waist": 1.15, "chest": 1.15, "thigh": 1.15},
    "slender": {"hip": 0.88, "waist": 0.88, "chest": 0.88, "thigh": 0.88},
}

# Render recipe (the Scene Test class): deterministic WORKBENCH, fixed
# level frontal camera, film-transparent (the alpha IS the exact
# silhouette), 640x960. CAM_DIST 2.5 (fixture repair A1: at 4.0 the
# box-person's limbs are ~19 px at the model's 320 input and boundary
# noise sinks the blind-guard below its derivation's premise — the
# person class must fill the frame like the scan-mannequin class did).
RES_X, RES_Y = 640, 960
CAM_DIST = 2.5
CAM_LENS = 35.0

COVERAGE_LO, COVERAGE_HI = 0.01, 0.40  # declared sane-band (VOL-FIXTURE)
GUARD_IOU = 0.75  # the blind-guard (VOL-MODEL), NOT the product bar
BAR_IOU = 0.85  # THE Annex A.1 volume bar (visible-view scoped)

# ---------------------------------------------------------------------------
# The scratch paths — every one a literal join at module level. Scripts
# open() these constants INLINE (no path-parameterized file helpers).
# ---------------------------------------------------------------------------
SCRATCH = Path(__file__).resolve().parents[1] / "out" / "volume_probe"

P_META = str(SCRATCH / "fixture_meta.json")
P_SOLVE = str(SCRATCH / "solve.json")
P_APPLY = str(SCRATCH / "apply_report.json")
P_BASE_METARIG = str(SCRATCH / "base_metarig.png")
P_BASE_MIXAMO = str(SCRATCH / "base_mixamo.png")
P_REF_WIDE_HIP = str(SCRATCH / "ref_wide_hip.png")
P_REF_THICK_THIGH = str(SCRATCH / "ref_thick_thigh.png")
P_REF_HEAVY = str(SCRATCH / "ref_heavy.png")
P_REF_SLENDER = str(SCRATCH / "ref_slender.png")
P_SCULPTED_A_METARIG_WIDE_HIP = str(SCRATCH / "sculpted_a_metarig_wide_hip.png")
P_SCULPTED_A_METARIG_THICK_THIGH = str(SCRATCH / "sculpted_a_metarig_thick_thigh.png")
P_SCULPTED_A_METARIG_HEAVY = str(SCRATCH / "sculpted_a_metarig_heavy.png")
P_SCULPTED_A_METARIG_SLENDER = str(SCRATCH / "sculpted_a_metarig_slender.png")
P_SCULPTED_A_MIXAMO_WIDE_HIP = str(SCRATCH / "sculpted_a_mixamo_wide_hip.png")
P_SCULPTED_A_MIXAMO_THICK_THIGH = str(SCRATCH / "sculpted_a_mixamo_thick_thigh.png")
P_SCULPTED_A_MIXAMO_HEAVY = str(SCRATCH / "sculpted_a_mixamo_heavy.png")
P_SCULPTED_A_MIXAMO_SLENDER = str(SCRATCH / "sculpted_a_mixamo_slender.png")
P_SCULPTED_B_METARIG_WIDE_HIP = str(SCRATCH / "sculpted_b_metarig_wide_hip.png")
P_SCULPTED_B_METARIG_THICK_THIGH = str(SCRATCH / "sculpted_b_metarig_thick_thigh.png")
P_SCULPTED_B_METARIG_HEAVY = str(SCRATCH / "sculpted_b_metarig_heavy.png")
P_SCULPTED_B_METARIG_SLENDER = str(SCRATCH / "sculpted_b_metarig_slender.png")
P_SCULPTED_B_MIXAMO_WIDE_HIP = str(SCRATCH / "sculpted_b_mixamo_wide_hip.png")
P_SCULPTED_B_MIXAMO_THICK_THIGH = str(SCRATCH / "sculpted_b_mixamo_thick_thigh.png")
P_SCULPTED_B_MIXAMO_HEAVY = str(SCRATCH / "sculpted_b_mixamo_heavy.png")
P_SCULPTED_B_MIXAMO_SLENDER = str(SCRATCH / "sculpted_b_mixamo_slender.png")
P_SCULPTED_C_METARIG_WIDE_HIP = str(SCRATCH / "sculpted_c_metarig_wide_hip.png")

# Case id ("cand/tag/class" in the reports) -> the render path constant.
P_SCULPTED = {
    "a/metarig/wide_hip": P_SCULPTED_A_METARIG_WIDE_HIP,
    "a/metarig/thick_thigh": P_SCULPTED_A_METARIG_THICK_THIGH,
    "a/metarig/heavy": P_SCULPTED_A_METARIG_HEAVY,
    "a/metarig/slender": P_SCULPTED_A_METARIG_SLENDER,
    "a/mixamo/wide_hip": P_SCULPTED_A_MIXAMO_WIDE_HIP,
    "a/mixamo/thick_thigh": P_SCULPTED_A_MIXAMO_THICK_THIGH,
    "a/mixamo/heavy": P_SCULPTED_A_MIXAMO_HEAVY,
    "a/mixamo/slender": P_SCULPTED_A_MIXAMO_SLENDER,
    "b/metarig/wide_hip": P_SCULPTED_B_METARIG_WIDE_HIP,
    "b/metarig/thick_thigh": P_SCULPTED_B_METARIG_THICK_THIGH,
    "b/metarig/heavy": P_SCULPTED_B_METARIG_HEAVY,
    "b/metarig/slender": P_SCULPTED_B_METARIG_SLENDER,
    "b/mixamo/wide_hip": P_SCULPTED_B_MIXAMO_WIDE_HIP,
    "b/mixamo/thick_thigh": P_SCULPTED_B_MIXAMO_THICK_THIGH,
    "b/mixamo/heavy": P_SCULPTED_B_MIXAMO_HEAVY,
    "b/mixamo/slender": P_SCULPTED_B_MIXAMO_SLENDER,
    "c/metarig/wide_hip": P_SCULPTED_C_METARIG_WIDE_HIP,
}
P_REF = {
    "wide_hip": P_REF_WIDE_HIP,
    "thick_thigh": P_REF_THICK_THIGH,
    "heavy": P_REF_HEAVY,
    "slender": P_REF_SLENDER,
}
P_BASE = {"metarig": P_BASE_METARIG, "mixamo": P_BASE_MIXAMO}


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"RM_VOL {label}: {'PASS' if ok else 'FAIL'}{(' ' + detail) if detail else ''}")


def tent(zt: float, b0: float, b1: float) -> float:
    """The band weight function (the probe's apply drafts; the addon apply
    carries its own copy — BAND_TENT_T shared)."""
    t = BAND_TENT_T
    if zt < b0 - t or zt > b1 + t:
        return 0.0
    if zt < b0 + t:
        return (zt - (b0 - t)) / (2 * t)
    if zt > b1 - t:
        return ((b1 + t) - zt) / (2 * t)
    return 1.0


def torso_px_of(anchors: dict) -> float:
    return math.dist(anchors["hips"], anchors["neck"])


def anchors_px_of(anchors: dict) -> dict:
    out = {p: anchors[p] for p in ANCHOR_FRACS}
    out["vol.thigh_w"] = anchors["vol.thigh_w"]
    out["vol.thigh.L"] = anchors["vol.thigh.L"]
    out["vol.thigh.R"] = anchors["vol.thigh.R"]
    return out


def core_model_entry() -> dict:
    """The D-025 manifest entry (the pin the measure stage verifies)."""
    from riggermortis.inference import models  # noqa: PLC0415

    return models.model_entry("u2net")


def core_model_path() -> str:
    """The MANAGED artifact path (the P1-1 flow's location)."""
    from riggermortis.inference import models  # noqa: PLC0415

    return str(models.model_path("u2net"))


def u2net_session():
    """The ADOPTED model's session (the core wrapper is the ONE copy —
    docs/WIRING.md); the pipeline's SKIPPED-honest shape keeps its
    FileNotFoundError contract, so the InferenceError translates here."""
    from riggermortis.errors import InferenceError  # noqa: PLC0415
    from riggermortis.inference import segment  # noqa: PLC0415

    try:
        return segment.u2net_session()
    except InferenceError as exc:
        raise FileNotFoundError(str(exc)) from exc


def u2net_mask(sess, inp, rgb):
    """The declared preprocess/postprocess — the core wrapper, ONE copy
    (docs/WIRING.md); the render size IS this pipeline's rgb shape."""
    from riggermortis.inference import segment  # noqa: PLC0415

    return segment.u2net_mask(sess, inp, rgb)


def iou(a, b) -> float:
    import numpy as np  # noqa: PLC0415

    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter) / float(union) if union else 0.0
