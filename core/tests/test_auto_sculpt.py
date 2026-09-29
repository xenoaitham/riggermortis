"""P9-1 auto-sculpt core contract: the pure target math (the probe's
selected mechanism's core half), the Annex A.1 5% bar instrument, the loud
capability lines, and the proportion REPORT — plus the addon apply module's
bpy-free import (the REAL bpy flows run in the RM_ASCULPT gate).

The numbers these tests pin are the probe-first numbers (docs/AUTO_SCULPT.md
§ Probe answers); the probe re-run against this core reproduced them exactly.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from conftest import addon_module  # noqa: E402
from riggermortis import auto_sculpt as asc  # noqa: E402
from riggermortis.auto_sculpt import AutoSculptError  # noqa: E402

# A declared base skeleton (meters; the probe's fixture family — inline so
# the tests never depend on xtask).
BASE = {
    "hips": (0.0, 0.0, 0.98),
    "spine": (0.0, 0.0, 1.068),
    "chest": (0.0, 0.0, 1.234),
    "neck": (0.0, 0.0, 1.42),
    "head": (0.0, 0.0, 1.53),
    "upper_arm.L": (0.18, 0.0, 1.38),
    "upper_arm.R": (-0.18, 0.0, 1.38),
    "forearm.L": (0.18, 0.0, 1.12),
    "forearm.R": (-0.18, 0.0, 1.12),
    "hand.L": (0.18, 0.0, 0.88),
    "hand.R": (-0.18, 0.0, 0.88),
    "upper_leg.L": (0.14, 0.0, 0.94),
    "upper_leg.R": (-0.14, 0.0, 0.94),
    "lower_leg.L": (0.14, 0.0, 0.52),
    "lower_leg.R": (-0.14, 0.0, 0.52),
    "foot.L": (0.14, 0.0, 0.12),
    "foot.R": (-0.14, 0.0, 0.12),
}

HEAVY = {"shoulder_w": 0.25, "hip_w": 0.20, "upper_arm": 0.0, "forearm": 0.0, "thigh": 0.0, "shin": 0.0}
TALL = {"shoulder_w": 0.05, "hip_w": 0.05, "upper_arm": 0.15, "forearm": 0.15, "thigh": 0.15, "shin": 0.15}


def _ratios(deltas: dict[str, float]) -> dict[str, float]:
    base_ratios = asc.measure_proportion_ratios(BASE)
    return {k: (1.0 if k == "torso" else base_ratios[k] * (1.0 + deltas[k])) for k in base_ratios}


def test_module_imports_without_bpy():
    """The add-on apply half imports bpy-free (the shim proves it); the REAL
    bpy flow is the RM_ASCULPT gate's job."""
    mod = addon_module("auto_sculpt")
    assert mod.FOLLOW_EPS == 1e-6
    assert callable(mod.apply_proportion_sculpt)
    assert callable(mod.measure_mesh_follow)


def test_measure_ratios_unit_free_and_torso_anchored():
    ratios = asc.measure_proportion_ratios(BASE)
    assert ratios["torso"] == 1.0
    assert ratios["shoulder_w"] == pytest.approx(0.36 / 0.44)
    assert ratios["hip_w"] == pytest.approx(0.28 / 0.44)
    assert ratios["upper_arm"] == pytest.approx(0.26 / 0.44)
    # unit-free: the same skeleton in cm reads the SAME ratios
    cm = {k: (v[0] * 100.0, v[1] * 100.0, v[2] * 100.0) for k, v in BASE.items()}
    assert asc.measure_proportion_ratios(cm) == pytest.approx(ratios)


def test_measure_refuses_degenerate_torso_loud():
    bad = dict(BASE)
    bad["neck"] = bad["hips"]
    with pytest.raises(AutoSculptError, match="torso span degenerate"):
        asc.measure_proportion_ratios(bad)


def test_target_heavy_moves_girdles_symmetrically_and_keeps_torso():
    base_ratios = asc.measure_proportion_ratios(BASE)
    tgt, factors, adjusted = asc.build_proportion_target(BASE, _ratios(HEAVY), base_ratios)
    # hips/neck fixed (the torso anchor)
    assert tgt["hips"] == BASE["hips"]
    assert tgt["neck"] == BASE["neck"]
    # shoulder girdle: width x1.25 about the kept center
    w0 = 0.36
    assert abs(tgt["upper_arm.L"][0] - tgt["upper_arm.R"][0]) == pytest.approx(w0 * 1.25)
    assert tgt["upper_arm.L"][0] == pytest.approx(+(w0 * 1.25) / 2)
    assert tgt["upper_arm.R"][0] == pytest.approx(-(w0 * 1.25) / 2)
    # limbs unscaled in this class: chains ride the moved girdle joints
    assert tgt["forearm.L"] == pytest.approx((0.18 * 1.25, 0.0, 1.12))
    assert tgt["hand.L"] == pytest.approx((0.18 * 1.25, 0.0, 0.88))
    assert adjusted == ["upper_arm.L", "upper_arm.R", "upper_leg.L", "upper_leg.R"]
    assert factors["shoulder_w"] == pytest.approx(1.25)


def test_target_tall_scales_limb_chains_along_base_directions():
    base_ratios = asc.measure_proportion_ratios(BASE)
    tgt, _f, adjusted = asc.build_proportion_target(BASE, _ratios(TALL), base_ratios)
    assert "upper_arm.L" in adjusted and "foot.R" in adjusted
    # upper arm: 0.26 x1.15 hanging straight down from the (girdle-moved) shoulder
    shoulder = tgt["upper_arm.L"]
    assert tgt["forearm.L"][2] == pytest.approx(shoulder[2] - 0.26 * 1.15)
    assert tgt["forearm.L"][0] == pytest.approx(shoulder[0])
    # forearm: 0.24 x1.15 from the NEW elbow
    assert tgt["hand.L"][2] == pytest.approx(tgt["forearm.L"][2] - 0.24 * 1.15)
    # hip girdle moved x1.05; the thigh rides the moved hip joint
    hip = tgt["upper_leg.L"]
    assert hip[0] == pytest.approx(0.14 * 1.05)
    assert tgt["lower_leg.L"][2] == pytest.approx(hip[2] - 0.42 * 1.15)


def test_target_ratio_round_trip_matches_declared_deltas():
    base_ratios = asc.measure_proportion_ratios(BASE)
    for deltas in (HEAVY, TALL):
        ref = _ratios(deltas)
        tgt, _f, _a = asc.build_proportion_target(BASE, ref, base_ratios)
        back = asc.measure_proportion_ratios(tgt)
        for k, v in ref.items():
            assert back[k] == pytest.approx(v, abs=1e-9)


def test_validate_fp_exact_apply_passes_the_bar():
    base_ratios = asc.measure_proportion_ratios(BASE)
    tgt, _f, _a = asc.build_proportion_target(BASE, _ratios(TALL), base_ratios)
    worst, fracs, worst_role, ok = asc.validate_sculpt(tgt, tgt, BASE)
    assert ok and worst == 0.0
    assert all(v == 0.0 for v in fracs.values())


def test_validate_names_the_worst_role_and_misses_past_the_bar():
    intended = dict(BASE)
    intended["hand.L"] = (0.18 + 0.05, 0.0, 0.88 - 0.03)  # a big wrong offset
    worst, _fracs, worst_role, ok = asc.validate_sculpt(BASE, intended, BASE)
    assert worst_role == "hand.L"
    assert not ok
    assert worst > asc.BAR_FRAC


def test_capability_lines_loud_on_missing_roles_and_silent_when_complete():
    lines = asc.sculpt_capability_lines(set(BASE) - {"lower_leg.L", "upper_leg.L"})
    assert len(lines) == 1
    assert "lower_leg.L" in lines[0]
    assert lines[0].endswith("— proportions not applied")
    assert asc.sculpt_capability_lines(set(BASE)) == []
    assert asc.sculpt_capability_lines({"hips"}) == asc.sculpt_capability_lines({"hips"})


def test_proportion_report_ships_as_data_and_round_trips():
    base_ratios = asc.measure_proportion_ratios(BASE)
    rep = asc.proportion_report(BASE, asc.build_proportion_target(BASE, _ratios(HEAVY), base_ratios)[0])
    d = rep.to_dict()
    assert d["adjusted_roles"] == ["hip_w", "shoulder_w"]  # the report lists RULERS
    assert d["factors"]["shoulder_w"] == pytest.approx(1.25)
    assert rep.capability_lines == []
    rep2 = asc.ProportionReport.from_dict(d)
    assert rep2.to_dict() == d
    # a base missing movable roles carries the loud lines IN the report
    starved = {k: v for k, v in BASE.items() if not k.startswith("lower_leg")}
    rep3 = asc.proportion_report(starved, BASE)
    assert rep3.capability_lines and "lower_leg.L" in rep3.capability_lines[0]


def test_determinism_twin_calls_byte_equal():
    base_ratios = asc.measure_proportion_ratios(BASE)
    ref = _ratios(TALL)
    t1, f1, a1 = asc.build_proportion_target(BASE, ref, base_ratios)
    t2, f2, a2 = asc.build_proportion_target(BASE, ref, base_ratios)
    assert t1 == t2 and f1 == f2 and a1 == a2
    assert asc.measure_proportion_ratios(BASE) == base_ratios
