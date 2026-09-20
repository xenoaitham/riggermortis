"""P4-7 animatic-preset contract tests — validation + timing math, no bpy.

``animatics.py`` is import-safe WITHOUT Blender (engine calls lazy-import
bpy like ``pages.py``), so the preset contract ships CI-tested: the
validator fails loudly on unknown fields (preset/shot/resolution level),
loads are deterministic, and ``animatic_frames`` lands the exact timing
plan the builder renders (shots contiguous, action frames consumed evenly
in order). The render half is gated by the Blender style probe
(``RM_STYLE ANIMATIC`` in ``xtask/style_probe.py``); movie assembly is
shell glue (ffmpeg), never Python.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ADDON_DIR = Path(__file__).resolve().parents[2] / "addon" / "riggermortis_addon"
_spec = importlib.util.spec_from_file_location(
    "rm_animatics", _ADDON_DIR / "animatics.py"
)
assert _spec is not None and _spec.loader is not None
animatics = importlib.util.module_from_spec(_spec)
sys.modules["rm_animatics"] = animatics
_spec.loader.exec_module(animatics)


def _animatic() -> dict:
    return animatics.load_animatic("demo_shots")


def test_known_animatics_is_the_shipped_preset() -> None:
    assert animatics.known_animatics() == ["demo_shots"]


def test_shipped_animatic_carries_the_schema() -> None:
    a = _animatic()
    assert a["format"] == 1
    assert a["resolution"] == {"width_px": 480, "height_px": 360}
    assert a["fps"] == 12
    assert a["style"] == "manga"
    assert a["shots"] == [
        {"camera": "rm_cam_1", "frames": 12},
        {"camera": "rm_cam_2", "frames": 8, "style": "anime"},
    ]


def test_unknown_preset_field_fails_loudly() -> None:
    a = _animatic()
    a["container"] = {"format": "mkv"}
    with pytest.raises(ValueError, match="unknown animatic fields"):
        animatics._validate_animatic(a, "bad.json")


def test_unknown_shot_and_resolution_fields_fail_loudly() -> None:
    a = _animatic()
    a["shots"][0]["tail"] = "se"
    with pytest.raises(ValueError, match="unknown shot 0 fields"):
        animatics._validate_animatic(a, "bad.json")
    a = _animatic()
    a["resolution"]["dpi"] = 72
    with pytest.raises(ValueError, match="unknown resolution fields"):
        animatics._validate_animatic(a, "bad.json")


def test_bad_types_fail_loudly() -> None:
    for mutate, pattern in (
        (lambda a: a.update(format=2), "format must be 1"),
        (lambda a: a.update(fps=0), "fps must be a positive int"),
        (lambda a: a.update(fps=12.0), "fps must be a positive int"),
        (lambda a: a["resolution"].update(width_px=-1), "must be a positive int"),
        (lambda a: a.update(shots=[]), "shots must be a non-empty list"),
        (lambda a: a["shots"][0].update(frames=0), "frames must be a positive int"),
        (lambda a: a["shots"][0].update(camera=""), "camera must be a scene object name"),
        (lambda a: a["shots"][0].update(style="nope"), "not a shipped style"),
        (lambda a: a.update(style="nope"), "not a shipped style"),
    ):
        a = _animatic()
        mutate(a)
        with pytest.raises(ValueError, match=pattern):
            animatics._validate_animatic(a, "bad.json")


def test_unknown_animatic_name_is_actionable() -> None:
    with pytest.raises(ValueError, match="known animatics: demo_shots"):
        animatics.load_animatic("nope")


def test_timing_plan_shots_are_contiguous_and_in_order() -> None:
    plan = animatics.animatic_frames(_animatic(), action_len=8)
    assert len(plan) == 20
    assert [e["frame"] for e in plan] == list(range(20))
    assert [e["shot"] for e in plan] == [0] * 12 + [1] * 8
    assert all(e["camera"] == "rm_cam_1" for e in plan[:12])
    assert all(e["camera"] == "rm_cam_2" for e in plan[12:])
    # the per-shot style rides every entry of its shot
    assert all(e["style"] is None for e in plan[:12])
    assert all(e["style"] == "anime" for e in plan[12:])


def test_action_frames_consumed_evenly_and_in_order() -> None:
    plan = animatics.animatic_frames(_animatic(), action_len=8)
    got = [e["action_frame"] for e in plan]
    assert got == [(k * 8) // 20 for k in range(20)]
    assert got == sorted(got)
    assert set(got) == set(range(8))


def test_long_timeline_loops_a_short_action() -> None:
    a = _animatic()
    a["shots"] = [{"camera": "c", "frames": 10}]
    plan = animatics.animatic_frames(a, action_len=3)
    assert [e["action_frame"] for e in plan] == [(k * 3) // 10 for k in range(10)]
    assert set(e["action_frame"] for e in plan) == {0, 1, 2}


def test_one_frame_action_is_a_held_panel() -> None:
    a = _animatic()
    a["shots"] = [{"camera": "c", "frames": 6}]
    plan = animatics.animatic_frames(a, action_len=1)
    assert [e["action_frame"] for e in plan] == [0] * 6


def test_timing_is_deterministic() -> None:
    assert animatics.animatic_frames(_animatic(), 8) == animatics.animatic_frames(
        _animatic(), 8
    )


def test_bad_action_len_is_actionable() -> None:
    with pytest.raises(ValueError, match="action_len must be a positive int"):
        animatics.animatic_frames(_animatic(), 0)
