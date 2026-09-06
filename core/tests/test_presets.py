"""Per-rig preset round-trips and fingerprint safety."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from riggermortis.errors import PresetError  # noqa: E402
from riggermortis.mapper import map_rig  # noqa: E402
from riggermortis.presets import (  # noqa: E402
    apply_preset,
    load_preset,
    preset_from_mapping,
    save_preset,
)
from rigs import rigify_rig  # noqa: E402


def test_preset_round_trip(tmp_path):
    rig = rigify_rig()
    mapping = map_rig(rig)
    path = save_preset(preset_from_mapping(rig, mapping), tmp_path / "p.rigpreset.json")
    loaded = load_preset(path)
    assert loaded.fingerprint == rig.fingerprint()
    assert loaded.mapping == {role: a.bone for role, a in mapping.assignments.items()}


def test_apply_preset_pins_roles(tmp_path):
    rig = rigify_rig()
    auto = map_rig(rig)
    save_preset(preset_from_mapping(rig, auto), tmp_path / "p.json")
    preset = load_preset(tmp_path / "p.json")
    applied = apply_preset(rig, preset)
    for role, bone in preset.mapping.items():
        assert applied.assignments[role].bone == bone
        assert applied.assignments[role].confidence == 1.0
        assert not applied.assignments[role].ambiguous


def test_fingerprint_mismatch_refuses(tmp_path):
    rig = rigify_rig()
    save_preset(preset_from_mapping(rig, map_rig(rig)), tmp_path / "p.json")
    preset = load_preset(tmp_path / "p.json")
    moved = rigify_rig()
    moved.bones["head"].tail = (0.0, 0.0, 1.75)  # rig changed since the preset
    with pytest.raises(PresetError):
        apply_preset(moved, preset)
    forced = apply_preset(moved, preset, force=True)
    assert forced.assignments["head"].bone == preset.mapping["head"]


def test_malformed_preset_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"format": 99, "mapping": {}}', encoding="utf-8")
    with pytest.raises(PresetError):
        load_preset(bad)
    junk = tmp_path / "junk.json"
    junk.write_text("not json", encoding="utf-8")
    with pytest.raises(PresetError):
        load_preset(junk)
