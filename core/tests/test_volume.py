"""P9-2 volume core contract: the pure mechanism bits (the probe's
selected ``shape_key_inflate`` core half — the clamp law, the absolute-
target value law, the loud capability line, the structured REPORT) plus
the addon apply module's bpy-free import (the REAL bpy flows run in the
RM_VOL gate, xtask/volume_gate.py).

The numbers these tests pin are the probe-first numbers (docs/VOLUME.md
§ As-built, amendments A1–A3); the probe re-run against this core
reproduced them exactly (the S33 re-run rule).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from conftest import addon_module  # noqa: E402
from riggermortis import volume as vol  # noqa: E402
from riggermortis.volume import AutoSculptError  # noqa: E402


# -- the clamp law (declared [0.5, 2.0], loud at the fire sites) ------------
def test_clamp_law_bounds():
    assert vol.clamp_factor(1.15) == pytest.approx(1.15)
    assert vol.clamp_factor(0.2) == 0.5
    assert vol.clamp_factor(5.0) == 2.0
    assert vol.clamp_factor(0.5) == 0.5
    assert vol.clamp_factor(2.0) == 2.0


def test_value_law_is_absolute_target():
    # the S36 law: value = clamp(f) - 1 — a re-solve OVERWRITES, never composes
    assert vol.value_of_factor(1.15) == pytest.approx(0.15)
    assert vol.value_of_factor(0.88) == pytest.approx(-0.12)
    assert vol.value_of_factor(3.0) == 1.0
    assert vol.value_of_factor(0.1) == -0.5


def test_validate_factors_refuses_unknown_params():
    with pytest.raises(AutoSculptError) as e:
        vol.validate_factors({"vol.hip_w": 1.1, "vol.shoulder_w": 1.2})
    assert "vol.shoulder_w" in str(e.value)
    assert "band params are" in str(e.value)


def test_validate_factors_clamps_known_params():
    out = vol.validate_factors({"vol.hip_w": 9.9, "vol.thigh_w": 0.1})
    assert out["vol.hip_w"] == 2.0
    assert out["vol.thigh_w"] == 0.5


# -- the capability line (the P8-4 verbatim pattern) -------------------------
def test_capability_line_no_mesh_is_loud():
    assert vol.capability_lines(False) == [vol.CAPABILITY_NO_MESH]
    assert "no armature-deformed mesh" in vol.CAPABILITY_NO_MESH
    assert vol.capability_lines(True) == []


# -- the REPORT ships as data (round-trip) ------------------------------------
def test_volume_report_round_trip():
    rep = vol.VolumeReport(
        factors={"vol.hip_w": 1.2, "vol.waist_w": 1.0},
        values={"vol.hip_w": 0.2, "vol.waist_w": 0.0},
        capability_lines=[],
        notes=["clamped loudly: vol.thigh_w"],
    )
    d = rep.to_dict()
    rep2 = vol.VolumeReport.from_dict(d)
    assert rep2.factors == rep.factors
    assert rep2.values == rep.values
    assert rep2.notes == rep.notes
    assert rep2.capability_lines == []


# -- the band param set is the declared four, symmetrized ---------------------
def test_band_params_are_the_declared_four():
    assert vol.BAND_PARAMS == ("vol.thigh_w", "vol.hip_w", "vol.waist_w", "vol.chest_w")


# -- the addon apply module imports bpy-free (the shim pattern) ---------------
def test_addon_volume_module_bpy_free_import():
    mod = addon_module("volume")
    assert hasattr(mod, "apply_volume_sculpt")
    assert hasattr(mod, "measure_zero_restore")
    # the band table is shared with the core param set
    assert set(mod.BAND_TFRAC) == set(vol.BAND_PARAMS)
    assert set(mod.BAND_ROLES) == set(vol.BAND_PARAMS)


def test_addon_volume_refuses_without_mesh():
    mod = addon_module("volume")
    rep = mod.apply_volume_sculpt(object(), None, {"vol.hip_w": 1.2}, {})
    assert rep["applied"] is False
    assert rep["capability_lines"] == [vol.CAPABILITY_NO_MESH]
