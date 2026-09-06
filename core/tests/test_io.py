"""Rig JSON I/O: round trips, malformed input, dangling parents, .blend routing."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from riggermortis.errors import RigLoadError  # noqa: E402
from riggermortis.io import load_rig, load_rig_json_text  # noqa: E402
from riggermortis.types import RigData  # noqa: E402
from rigs import rigify_rig  # noqa: E402


def test_json_round_trip(tmp_path):
    rig = rigify_rig()
    path = rig.to_json(tmp_path / "rig.json")
    loaded = load_rig(path)
    assert loaded.fingerprint() == rig.fingerprint()
    assert loaded.bones.keys() == rig.bones.keys()
    assert loaded.bones["upper_arm.L"].parent == "shoulder.L"


def test_missing_file_is_actionable(tmp_path):
    with pytest.raises(RigLoadError) as excinfo:
        load_rig(tmp_path / "nope.json")
    assert "not found" in str(excinfo.value)


def test_blend_files_are_routed_to_the_bridge(tmp_path):
    fake = tmp_path / "model.blend"
    fake.write_bytes(b"BLENDER-v404")  # not a real blend; core must not touch it
    with pytest.raises(RigLoadError) as excinfo:
        load_rig(fake)
    assert "extract_blend" in str(excinfo.value)


def test_bridge_payload_wrapper():
    rig = rigify_rig()
    text = '{"format": 1, "source": "blender", "rigs": [' + _to_json(rig) + "]}"
    loaded = load_rig_json_text(text)
    assert loaded.fingerprint() == rig.fingerprint()


def test_bridge_multi_rig_payload_refuses():
    rig = rigify_rig()
    text = '{"rigs": [' + _to_json(rig) + ", " + _to_json(rig) + "]}"
    with pytest.raises(RigLoadError):
        load_rig_json_text(text)


def test_dangling_parent_becomes_root():
    rig = rigify_rig()
    rig.bones["shoulder.L"].parent = "deleted_bone"
    data = RigData.from_dict(rig.to_dict())
    assert data.bones["shoulder.L"].parent is None


def test_malformed_json_is_actionable(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(RigLoadError):
        load_rig(bad)


def _to_json(rig: RigData) -> str:
    import json

    return json.dumps(rig.to_dict())
