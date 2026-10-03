"""P9-3 sculpt wiring contract: the reference-side solve artifact
(docs/WIRING.md), the product anchor math (amendment A1), the lifted
S37 measurement (the one-copy law — the volume pipeline aliases these
copies), the solve/clamp laws, and the addon wiring module's bpy-free
import. The REAL bpy flows run in the RM_WIRE gate (xtask/wiring_gate.py).
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
_XTASK = Path(__file__).resolve().parents[2] / "xtask"

import pytest  # noqa: E402

from conftest import addon_module  # noqa: E402
from riggermortis import sculpt as sc  # noqa: E402
from riggermortis.errors import AutoSculptError  # noqa: E402


# -- the certified measurement constants (byte-identical to the S37 set) ----
def test_constants_are_the_certified_set():
    assert sc.ANCHOR_FRACS == {"vol.hip_w": 0.0, "vol.waist_w": 0.25, "vol.chest_w": 0.80}
    assert sc.THIGH_ANCHOR_FRAC == -0.70
    assert sc.MEDIAN_HALF_BAND == 3
    assert sc.SCULPT_FORMAT == 1
    assert sc.READ_FORMATS == (1,)


def test_volume_pipeline_aliases_the_core_copies():
    """The one-copy law: volume_common's measurement re-exports the core
    functions — same objects, not copies (the volume gate re-run proves
    the numbers byte-identical)."""
    sys.path.insert(0, str(_XTASK))
    import os  # noqa: E402

    os.environ.setdefault("RM_CORE_SRC", str(Path(__file__).resolve().parents[1] / "src"))
    vc = importlib.import_module("volume_common")
    assert vc.region_widths is sc.region_widths
    assert vc.solve_factors is sc.solve_factors
    assert vc.runs is sc.runs
    assert vc.ANCHOR_FRACS is sc.ANCHOR_FRACS
    assert vc.THIGH_ANCHOR_FRAC is sc.THIGH_ANCHOR_FRAC
    assert vc.MEDIAN_HALF_BAND is sc.MEDIAN_HALF_BAND


# -- the product anchors (WIRING.md amendment A1) -----------------------------
def test_anchor_points_px_interpolate_the_certified_fracs():
    anchors, span = sc.anchor_points_px({
        "hips": (100.0, 500.0),
        "neck": (100.0, 300.0),
        "upper_leg.L": (120.0, 500.0),
        "upper_leg.R": (80.0, 500.0),
    })
    assert span == pytest.approx(200.0)
    assert anchors["hips"] == (100.0, 500.0)
    assert anchors["neck"] == (100.0, 300.0)
    # waist = hips + 0.25 * (neck - hips); y grows DOWN in image space
    assert anchors["vol.waist_w"] == pytest.approx((100.0, 450.0))
    assert anchors["vol.chest_w"] == pytest.approx((100.0, 340.0))
    # thigh = the line EXTENDED to -0.70, leg centers at the hip keypoints' x
    assert anchors["vol.thigh_w"] == pytest.approx((100.0, 640.0))
    assert anchors["vol.thigh.L"] == pytest.approx((120.0, 640.0))
    assert anchors["vol.thigh.R"] == pytest.approx((80.0, 640.0))


def test_anchor_points_px_refuses_missing_roles_and_degenerate_torso():
    with pytest.raises(AutoSculptError) as e:
        sc.anchor_points_px({"hips": (0, 0), "neck": (0, 10)})
    assert "upper_leg.L" in str(e.value)
    with pytest.raises(AutoSculptError):
        sc.anchor_points_px({
            "hips": (50.0, 500.0), "neck": (50.0, 500.0),
            "upper_leg.L": (60.0, 500.0), "upper_leg.R": (40.0, 500.0),
        })


# -- the mask measurement (a synthetic rectangle GT) ---------------------------
def test_region_widths_measure_synthetic_rectangles():
    pytest.importorskip("numpy")  # the mask math is numpy-class (the extra)
    import numpy as np

    w, h = 200, 400
    mask = np.zeros((h, w), dtype=bool)
    mask[150:250, 60:140] = True  # an 80 px wide torso band
    anchors = {
        "hips": (100.0, 200.0),
        "vol.hip_w": (100.0, 200.0),
        "vol.waist_w": (100.0, 200.0),
        "vol.chest_w": (100.0, 200.0),
        "vol.thigh_w": (100.0, 200.0),
        "vol.thigh.L": (80.0, 200.0),
        "vol.thigh.R": (120.0, 200.0),
    }
    out = sc.region_widths(mask, anchors, 100.0)
    for param in ("vol.hip_w", "vol.waist_w", "vol.chest_w"):
        assert out[param] == pytest.approx(0.80)


def test_region_widths_thigh_sums_separated_legs():
    pytest.importorskip("numpy")  # the mask math is numpy-class (the extra)
    import numpy as np

    w, h = 200, 400
    mask = np.zeros((h, w), dtype=bool)
    mask[300:360, 70:90] = True   # left leg: 20 px
    mask[300:360, 110:130] = True  # right leg: 20 px (closed legs merge; these gap)
    anchors = {
        "hips": (100.0, 330.0),
        "vol.hip_w": (100.0, 330.0),
        "vol.waist_w": (100.0, 330.0),
        "vol.chest_w": (100.0, 330.0),
        "vol.thigh_w": (100.0, 330.0),
        "vol.thigh.L": (80.0, 330.0),
        "vol.thigh.R": (120.0, 330.0),
    }
    out = sc.region_widths(mask, anchors, 100.0)
    assert out["vol.thigh_w"] == pytest.approx(0.40)


# -- the solve law (byte-identical to the certified copy) ----------------------
def test_solve_factors_clamp_and_flag():
    ref = {"vol.hip_w": 1.2, "vol.waist_w": 1.0, "vol.chest_w": 0.8, "vol.thigh_w": 9.9}
    base = {"vol.hip_w": 1.0, "vol.waist_w": 1.0, "vol.chest_w": 1.0, "vol.thigh_w": 1.0}
    f1 = sc.solve_factors(ref, base)
    f2 = sc.solve_factors(ref, base)
    assert f1 == f2  # deterministic
    assert f1["vol.hip_w"] == pytest.approx(1.2)
    assert f1["vol.waist_w"] == pytest.approx(1.0)
    assert f1["vol.chest_w"] == pytest.approx(0.8)
    assert f1["vol.thigh_w"] == 2.0  # the clamp
    assert sc.clamp_note_params(f1) == ["vol.thigh_w"]
    assert sc.clamp_note_params({"vol.hip_w": 1.1}) == []


# -- the sculpt solve artifact contract (loud validation) ----------------------
def _gt_solve() -> dict:
    return {
        "format": 1,
        "figure": "figure 1",
        "reference_image": "ref.jpg",
        "image_size": [640, 960],
        "proportions": {
            "reference_ratios": {
                "torso": 1.0, "shoulder_w": 0.41, "hip_w": 0.36,
                "upper_arm": 0.59, "forearm": 0.55, "thigh": 0.95, "shin": 0.91,
            },
        },
        "volume": {
            "ref_ratios": {
                "vol.thigh_w": 0.30, "vol.hip_w": 0.50,
                "vol.waist_w": 0.40, "vol.chest_w": 0.55,
            },
        },
        "notes": [],
    }


def test_sculpt_solve_round_trip_is_deterministic():
    solve = sc.SculptSolve.from_dict(_gt_solve())
    d = solve.to_dict()
    assert json.loads(json.dumps(d, sort_keys=True)) == json.loads(
        json.dumps(sc.SculptSolve.from_dict(d).to_dict(), sort_keys=True)
    )
    assert solve.figure == "figure 1"
    assert solve.volume_ratios["vol.hip_w"] == pytest.approx(0.50)
    assert solve.reference_ratios["shoulder_w"] == pytest.approx(0.41)


def test_sculpt_solve_refuses_loud():
    bad = _gt_solve()
    bad["format"] = 99
    with pytest.raises(AutoSculptError) as e:
        sc.SculptSolve.from_dict(bad)
    assert "format 99" in str(e.value)

    bad = _gt_solve()
    del bad["proportions"]["reference_ratios"]["torso"]
    with pytest.raises(AutoSculptError) as e:
        sc.SculptSolve.from_dict(bad)
    assert "missing rulers" in str(e.value)

    bad = _gt_solve()
    bad["volume"]["ref_ratios"]["vol.shoulder_w"] = 1.0
    with pytest.raises(AutoSculptError) as e:
        sc.SculptSolve.from_dict(bad)
    assert "unknown volume params" in str(e.value)

    bad = _gt_solve()
    bad["volume"]["ref_ratios"]["vol.hip_w"] = 0.0
    with pytest.raises(AutoSculptError) as e:
        sc.SculptSolve.from_dict(bad)
    assert "finite and positive" in str(e.value)

    bad = _gt_solve()
    del bad["volume"]
    with pytest.raises(AutoSculptError) as e:
        sc.SculptSolve.from_dict(bad)
    assert "no 'volume' section" in str(e.value)


# -- the addon wiring module imports bpy-free (the shim pattern) ---------------
def test_addon_sculpt_wire_module_bpy_free_import():
    mod = addon_module("sculpt_wire")
    assert hasattr(mod, "apply_sculpt")
    assert hasattr(mod, "measure_volume_base_ratios")
    assert hasattr(mod, "report_lines")
    assert "solve-sculpt" in mod.CAPABILITY_NO_SCULPT
    assert "rigpose pose" in mod.CAPABILITY_NO_PAYLOAD
    # the declared frontal camera fit is the S37 fixture class ratio
    assert mod.CAM_FIT_TORSO == pytest.approx(2.5 / 0.44)


def test_addon_sculpt_wire_missing_inputs_are_loud():
    mod = addon_module("sculpt_wire")

    class _FakeArm:
        type = "ARMATURE"

    report = mod.apply_sculpt(_FakeArm(), payload=None, solve=None)
    assert report["proportions"] is None
    assert report["volume"] is None
    assert mod.CAPABILITY_NO_PAYLOAD in report["capability_lines"]
    assert mod.CAPABILITY_NO_SCULPT in report["capability_lines"]
    lines = mod.report_lines(report)
    assert any("rigpose pose" in line for line in lines)
    assert any("solve-sculpt" in line for line in lines)

    report = mod.apply_sculpt(_FakeArm(), payload=None, solve=None, volume=False)
    assert mod.CAPABILITY_NO_PAYLOAD in report["capability_lines"]
    assert mod.CAPABILITY_NO_SCULPT not in report["capability_lines"]
    lines = mod.report_lines(report)
    assert any("rigpose pose" in line for line in lines)
    assert not any("solve-sculpt" in line for line in lines)


def test_addon_sculpt_wire_refuses_non_armature():
    mod = addon_module("sculpt_wire")
    with pytest.raises(ValueError):
        mod.apply_sculpt(None, payload=None, solve=None)


# -- the math import surface (the wiring gate + tests use these) ---------------
def test_core_exports_the_wiring_surface():
    import riggermortis as core

    for name in (
        "SculptSolve", "anchor_points_px", "region_widths", "solve_factors",
        "clamp_note_params", "SCULPT_FORMAT", "ANCHOR_FRACS",
        "THIGH_ANCHOR_FRAC", "MEDIAN_HALF_BAND",
    ):
        assert hasattr(core, name), name
