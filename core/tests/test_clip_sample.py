"""P6-2/S25: the clip-sampler library (addon/riggermortis_addon/clip_sample.py)
imports bpy-free headlessly and its pure parts hold the format-1 contract.

The bpy-owning half (import, per-frame sampling, DETERM twin pass) is the
RM_MOTION gate's job (``make pose-verify`` — real Blender, real importers);
the refactor's contract there is byte-identity with the pre-promotion
script's output.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from conftest import addon_module  # noqa: E402

clip_sample = addon_module("clip_sample")


def test_module_imports_without_bpy():
    """The add-on convention: bpy lives inside functions, so the promoted
    sampler library imports cleanly outside Blender (the shim proves it —
    this module IS imported bpy-free by the line above)."""
    assert clip_sample.ROUND_DIGITS == 6
    assert clip_sample.STATIC_EXTENT_M == 1e-5


def test_build_clip_format1_shape_and_sorted_frames():
    samples = {
        7: {"hips": [0.0, 0.0, 1.0], "head": [0.0, 0.0, 1.7]},
        1: {"hips": [0.0, 0.0, 1.0], "head": [0.0, 0.0, 1.7]},
        4: {"hips": [0.0, 0.0, 1.0], "head": [0.0, 0.0, 1.7]},
    }
    clip = clip_sample.build_clip(
        samples, fps=24.0, scale_ref=0.4200004, fingerprint="abc", notes=["n"],
    )
    assert clip["format"] == 1
    assert clip["fps"] == 24.0
    assert clip["scale_ref"] == 0.42
    assert clip["source"] == "blender-import"
    assert clip["source_fingerprint"] == "abc"
    assert [f["frame"] for f in clip["frames"]] == [1, 4, 7]  # sorted, not insertion
    assert clip["notes"] == ["n"]


def test_build_clip_is_deterministic():
    def run():
        return clip_sample.build_clip(
            {2: {"hips": [1.0, 2.0, 3.0]}, 0: {"hips": [1.0, 2.0, 3.0]}},
            fps=30.0, scale_ref=1.0, fingerprint="f", notes=[],
        )

    assert run() == run()


def test_motion_extent_is_the_largest_axis_range():
    samples = {
        0: {"hips": [0.0, 0.0, 1.0], "hand": [0.5, -1.0, 1.2]},
        1: {"hips": [0.1, 0.0, 1.4], "hand": [0.5, 1.0, 0.2]},
    }
    extent = clip_sample.motion_extent(samples)
    assert extent == pytest.approx(2.0)  # the hand's Y swing dominates


def test_sample_clip_refuses_a_missing_file_without_bpy():
    import riggermortis as core

    with pytest.raises(ValueError) as excinfo:
        clip_sample.sample_clip(
            "/nonexistent/model.bvh", "/tmp/out.json", core, bridge=None,
        )
    assert "no such file" in str(excinfo.value)
