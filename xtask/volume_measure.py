"""P9-2 volume measure — the driver half (masks + solve; runs under $PY).

Reads the bash-teed stage-A log (the `RM_VOL META_JSON {...}` line) and
the stage-A renders, verifies the ADOPTED artifact against its D-025 pin
at the MANAGED path, produces the u2net masks, prints the FIXTURE /
MODEL / MODEL-GUARD / SOLVE rows and ONE `RM_VOL SOLVE_JSON {...}` line
(bash greps it into the scratch solve file for stage B — python opens
nothing for write).

When the artifact is absent (the P1-1 flow is user-initiated: `rigpose
models download u2net`), every model-dependent row prints SKIPPED
honestly — the XBOT pattern — and the bash block skips stage B + rows.
Env: RM_CORE_SRC (required — the core import for the manifest pin).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

_core_src = os.environ.get("RM_CORE_SRC")
if not _core_src:
    raise SystemExit("RM_CORE_SRC is required (the core import)")
if _core_src not in sys.path:
    sys.path.insert(0, _core_src)

import volume_common as vc  # noqa: E402

LOG_DIR = Path(__file__).resolve().parents[1] / "out" / "volume_probe"
P_STAGEA_LOG = str(LOG_DIR / "stageA.log")


def read_meta() -> dict:
    with open(P_STAGEA_LOG, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("RM_VOL META_JSON "):
                return json.loads(line[len("RM_VOL META_JSON ") :])  # type: ignore[no-any-return]
    raise SystemExit("no RM_VOL META_JSON line in " + P_STAGEA_LOG)


def main() -> int:
    import numpy as np  # noqa: F401 — the mask stage is numpy-class
    from PIL import Image

    meta = read_meta()

    # -- VOL-FIXTURE: alpha coverage sane-band (reads the Blender renders) ---
    coverages = {}
    for tag in ("metarig", "mixamo"):
        a = np.asarray(Image.open(vc.P_BASE[tag]).convert("RGBA"))[..., 3] > 127
        coverages[tag] = float(a.mean())
    for cls in sorted(vc.REF_CLASSES):
        a = np.asarray(Image.open(vc.P_REF[cls]).convert("RGBA"))[..., 3] > 127
        coverages[cls] = float(a.mean())
    cov_ok = len(meta["renders"]) == 6 and all(vc.COVERAGE_LO <= v <= vc.COVERAGE_HI for v in coverages.values())
    vc.check(
        "FIXTURE",
        cov_ok,
        "6 renders, alpha coverage in the declared sane band: "
        + " ".join(k + "=" + format(v, ".4f") for k, v in sorted(coverages.items())),
    )

    # -- the adopted artifact (managed path; honest SKIPPED when absent) -----
    try:
        sess, inp = vc.u2net_session()
    except FileNotFoundError as exc:
        reason = str(exc)
        for row in (
            "MODEL",
            "MODEL-GUARD",
            "SOLVE",
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

    entry = vc.core_model_entry()
    path = vc.core_model_path()
    with open(path, "rb") as fh:
        blob = fh.read()
    sha = hashlib.sha256(blob).hexdigest()
    pin_ok = sha == entry["sha256"] and len(blob) == entry["bytes"]
    out0 = sess.get_outputs()[0]
    contract_ok = (
        inp.name == "input.1"
        and list(inp.shape) == [1, 3, 320, 320]
        and list(out0.shape) == [1, 1, 320, 320]
    )
    vc.check(
        "MODEL",
        pin_ok and contract_ok,
        "pin " + ("ok" if pin_ok else "MISMATCH") + " (sha256 " + sha[:16] + ".., " + str(len(blob)) + " bytes); "
        "contract " + ("ok" if contract_ok else "BAD"),
    )

    def alpha_of(path_str: str):
        return np.asarray(Image.open(path_str).convert("RGBA"))[..., 3] > 127

    def mask_of(rgb_img):
        return vc.u2net_mask(sess, inp, rgb_img)

    def rgb_of(path_str: str):
        return np.asarray(Image.open(path_str).convert("RGB"))

    # -- VOL-MODEL: the blind-guard on the reference renders ------------------
    guard_vals = {}
    for cls in sorted(vc.REF_CLASSES):
        guard_vals[cls] = vc.iou(mask_of(rgb_of(vc.P_REF[cls])), alpha_of(vc.P_REF[cls]))
    worst_guard = min(guard_vals.values())
    vc.check(
        "MODEL-GUARD",
        worst_guard >= vc.GUARD_IOU,
        "u2net vs alpha on the reference renders (the blind-guard, NOT the product bar): "
        + " ".join(k + "=" + format(v, ".4f") for k, v in sorted(guard_vals.items())),
    )

    # -- widths + the solve ----------------------------------------------------
    def widths_of(mask, anchors_px):
        return vc.region_widths(mask, vc.anchors_px_of(anchors_px), vc.torso_px_of(anchors_px))

    base_ratios = {}
    for tag in ("metarig", "mixamo"):
        an = meta["anchors"][tag]
        base_ratios[tag] = widths_of(mask_of(rgb_of(vc.P_BASE[tag])), an)

    fake_base = {"vol.hip_w": 0.50, "vol.waist_w": 0.40, "vol.chest_w": 0.55, "vol.thigh_w": 0.30}
    fake_ref = {"vol.hip_w": 0.60, "vol.waist_w": 0.40, "vol.chest_w": 0.44, "vol.thigh_w": 0.18}
    expect = {"vol.hip_w": 1.2, "vol.waist_w": 1.0, "vol.chest_w": 0.8, "vol.thigh_w": 0.6}
    f1 = vc.solve_factors(fake_ref, fake_base)
    f2 = vc.solve_factors(fake_ref, fake_base)
    solve_ok = all(
        abs(f1[p] - f2[p]) < 1e-9 and abs(f1[p] - expect[p]) < 1e-9 for p in expect
    )

    an = meta["anchors"]["metarig"]
    solve = {}
    for cls in sorted(vc.REF_CLASSES):
        ref_r = widths_of(mask_of(rgb_of(vc.P_REF[cls])), an)
        solve[cls] = vc.solve_factors(ref_r, base_ratios["metarig"])
    clamp_notes = []
    for cls, fs in solve.items():
        for p, v in fs.items():
            if v in (vc.CLAMP_LO, vc.CLAMP_HI):
                clamp_notes.append(cls + "/" + p)
    vc.check(
        "SOLVE",
        solve_ok,
        "authored recovery + determinism exact; solved "
        + " ".join(
            c + ":hip=" + format(fs["vol.hip_w"], ".3f") + ",thigh=" + format(fs["vol.thigh_w"], ".3f")
            for c, fs in sorted(solve.items())
        )
        + ("; CLAMPED loudly at " + ",".join(sorted(clamp_notes)) if clamp_notes else ""),
    )
    print("RM_VOL SOLVE_JSON " + json.dumps(solve, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
