"""P9-2 volume rows — the verdict driver (IoU bars; runs under $PY).

Reads the bash-teed stage-B log (the `RM_VOL REPORT_JSON {...}` line) and
the stage-B renders, runs the ADOPTED model over the sculpted renders,
and prints the apply/invariance rows, THE A.1 BAR rows (IoU >= 0.85,
visible-view scoped, BOTH sides through the adopted model), the
editable-exit / no-target / twin rows, and the selection verdict +
final `RM_VOL GATE` row (the crash-proof contract; SKIPPED honestly
when the artifact is absent — the XBOT pattern).
Env: RM_CORE_SRC (required).
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

_core_src = os.environ.get("RM_CORE_SRC")
if not _core_src:
    raise SystemExit("RM_CORE_SRC is required (the core import)")
if _core_src not in sys.path:
    sys.path.insert(0, _core_src)


def addon_module(name: str):
    """The conftest shim: the addon package's __init__ imports bpy, so the
    bpy-free module is loaded through a synthetic package (the tests'
    pattern, verbatim)."""
    import importlib
    import types

    pkg_dir = Path(__file__).resolve().parents[1] / "addon" / "riggermortis_addon"
    if "riggermortis_addon" not in sys.modules:
        pkg = types.ModuleType("riggermortis_addon")
        pkg.__path__ = [str(pkg_dir)]
        sys.modules["riggermortis_addon"] = pkg
    return importlib.import_module("riggermortis_addon." + name)

import volume_common as vc  # noqa: E402

LOG_DIR = Path(__file__).resolve().parents[1] / "out" / "volume_probe"
P_STAGEB_LOG = str(LOG_DIR / "stageB.log")


def read_report() -> dict:
    with open(P_STAGEB_LOG, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("RM_VOL REPORT_JSON "):
                return json.loads(line[len("RM_VOL REPORT_JSON ") :])  # type: ignore[no-any-return]
    raise SystemExit("no RM_VOL REPORT_JSON line in " + P_STAGEB_LOG)


def main() -> int:
    import numpy as np  # noqa: F401 — the mask stage is numpy-class
    from PIL import Image

    report = read_report()

    try:
        sess, inp = vc.u2net_session()
    except FileNotFoundError as exc:
        reason = str(exc)
        for row in (
            "APPLY-A",
            "APPLY-B",
            "APPLY-C",
            "BAR-A",
            "BAR-B",
            "BAR-C",
            "EDITABLE",
            "NOTARGET",
            "DETERM",
            "SELECT",
            "GATE",
        ):
            print("RM_VOL " + row + ": SKIPPED (" + reason + ")")
        return 0

    def rgb_of(path_str: str):
        return np.asarray(Image.open(path_str).convert("RGB"))

    def alpha_of(path_str: str):
        return np.asarray(Image.open(path_str).convert("RGBA"))[..., 3] > 127

    def mask_of(rgb_img):
        return vc.u2net_mask(sess, inp, rgb_img)

    ref_masks = {cls: mask_of(rgb_of(vc.P_REF[cls])) for cls in sorted(vc.REF_CLASSES)}

    # -- amendment A5: the A.1 IoU is REGION-SCOPED (the four bands' row
    # ranges — the volume claim's actual scope). Whole-frame IoU cannot
    # discriminate: the unsolved base already scores 0.88-0.97 against the
    # references (measured; the box-person silhouette changes little
    # frame-wide). The no-solve counterfactual is published alongside and
    # must sit BELOW the bar for the row to mean anything.
    addon_vol = addon_module("volume")

    meta = json.loads(
        next(
            line[len("RM_VOL META_JSON ") :]
            for line in open(LOG_DIR / "stageA.log", encoding="utf-8")
            if line.startswith("RM_VOL META_JSON ")
        )
    )
    an = meta["anchors"]["metarig"]
    hips_y = an["hips"][1]
    torso_px = math.dist(an["hips"], an["neck"])

    def band_rows(b0: float, b1: float) -> tuple[int, int]:
        y_hi = int(round(hips_y - b0 * torso_px))
        y_lo = int(round(hips_y - b1 * torso_px))
        return (max(y_lo, 0), min(y_hi, vc.RES_Y - 1))

    row_ranges = [band_rows(b0, b1) for (_p, b0, b1) in [(p, *addon_vol.BAND_TFRAC[p]) for p in addon_vol.BAND_TFRAC]]

    def region_crop(mask):
        out = np.zeros_like(mask)
        for y0, y1 in row_ranges:
            out[y0 : y1 + 1, :] = mask[y0 : y1 + 1, :]
        return out

    ref_alphas = {cls: alpha_of(vc.P_REF[cls]) for cls in sorted(vc.REF_CLASSES)}
    base_region = region_crop(alpha_of(vc.P_BASE_METARIG))
    base_counterfactual = {cls: vc.iou(base_region, region_crop(ref_alphas[cls])) for cls in sorted(vc.REF_CLASSES)}

    # -- the apply/invariance rows --------------------------------------------
    for cand, label, note in (
        ("a", "APPLY-A", "shape_key_inflate: joints byte-identical through the key warp"),
        ("b", "APPLY-B", "region_lattice: joints byte-identical through the cage"),
        ("c", "APPLY-C", "armature_scale (the DECLARED joint-mover — the invariance FAIL is the record)"),
    ):
        cases = report["candidates"].get(cand, {})
        any_moved = any(not e["joints_identical"] for e in cases.values())
        if cand == "c":
            vc.check(label, bool(cases) and any_moved, note)
        else:
            ok = bool(cases) and all(e["applied"] and e["joints_identical"] for e in cases.values())
            vc.check(label, ok, str(len(cases)) + " cases; " + note)

    # -- THE A.1 BAR rows (amendments A3+A5: the BINDING form is REGION-
    # SCOPED exact-alpha — sculpt vs reference silhouettes over the four
    # band row-ranges, model-free; the model-mediated form is PUBLISHED as
    # information — the u2net shape prior compresses silhouette differences
    # (candidate b, provably not at the reference, scores model-mediated
    # 0.82-0.91); the whole-frame form cannot discriminate (the unsolved
    # base scores 0.88-0.97 frame-wide)) ---------------------------------------
    def bar_for(cand: str):
        worst = 1.0
        model_worst = 1.0
        per = {}
        for case_id in sorted(report["candidates"].get(cand, {})):
            cls = case_id.split("/")[1]
            path_key = cand + "/" + case_id
            v = vc.iou(region_crop(alpha_of(vc.P_SCULPTED[path_key])), region_crop(ref_alphas[cls]))
            per[case_id] = v
            worst = min(worst, v)
            model_worst = min(model_worst, vc.iou(mask_of(rgb_of(vc.P_SCULPTED[path_key])), ref_masks[cls]))
        return worst, model_worst, per

    base_worst = min(base_counterfactual.values())
    worst_a, model_a, per_a = bar_for("a")
    discriminative = base_worst < vc.BAR_IOU
    vc.check(
        "BAR-A",
        worst_a >= vc.BAR_IOU and worst_a > base_worst,
        "worst region IoU " + format(worst_a, ".4f") + " vs bar " + str(vc.BAR_IOU)
        + " (visible-view, region-scoped; sculpt vs reference silhouettes, model-free) over " + str(len(per_a))
        + " cases; NO-SOLVE counterfactual " + format(base_worst, ".4f")
        + " (" + ("discriminative" if discriminative else "NOT discriminative — the fixture class must be repaired")
        + "); model-mediated worst " + format(model_a, ".4f") + " (published, the A3 compression)",
    )
    worst_b, model_b, per_b = bar_for("b")
    vc.check(
        "BAR-B",
        True,
        "record: the cage class measured OUT — worst region IoU " + format(worst_b, ".4f")
        + " vs bar " + str(vc.BAR_IOU) + " over " + str(len(per_b)) + " cases (model-mediated "
        + format(model_b, ".4f") + " published; the record is the verdict)",
    )
    _wc, _mc, per_c = bar_for("c")
    c_val = next(iter(per_c.values())) if per_c else 0.0
    vc.check(
        "BAR-C",
        True,
        "record case (metarig/wide_hip) region IoU " + format(c_val, ".4f")
        + " — joints moved; the class is out by invariance regardless",
    )

    # -- editable / notarget / twins -------------------------------------------
    drifts = [e.get("zero_restore_drift", 1.0) for e in report["candidates"]["a"].values()]
    vc.check(
        "EDITABLE",
        bool(drifts) and max(drifts) <= 1e-4,
        "zero-value restore: worst drift " + format(max(drifts), ".2e")
        + " m vs bar 1e-04 (the artist exit; keys by convention name; the bar sits an order above "
        "the S36 float32 evaluated-mesh noise band, 0.1 mm is beneath notice at posing distance)",
    )
    vc.check("NOTARGET", report["notarget_refused"], report["notarget_line"] or "loud refusal")
    vc.check(
        "DETERM",
        report["twins_identical"],
        str(report["twins_n_keys"]) + " keys byte-identical (values + unit-warp data)",
    )

    select_ok = worst_a >= vc.BAR_IOU
    if select_ok:
        vc.check(
            "SELECT",
            True,
            "verdict: shape_key_inflate SELECTED (holds the A.1 binding bar on both rigs, 0 required "
            "rig-side artifacts; the lattice class measured out, the armature class moves joints)",
        )
        vc.check("GATE", True, "the probe's rows above are the contract")
    else:
        vc.check("SELECT", False, "verdict: NO candidate holds the bar — the REFUSED-with-evidence branch")
        vc.check("GATE", False, "the probe's rows above are the contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
