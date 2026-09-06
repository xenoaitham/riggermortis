"""CLI behaviour: exit codes, structured output, no tracebacks on bad input."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from riggermortis.cli import EXIT_HANDLED_ERROR, EXIT_OK, main  # noqa: E402
from rigs import rigify_rig  # noqa: E402


@pytest.fixture()
def rig_json(tmp_path):
    path = tmp_path / "rig.json"
    rigify_rig().to_json(path)
    return path


def test_inspect_human_readable(rig_json, capsys):
    assert main(["inspect", str(rig_json)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "rig: rigify_meta" in out
    assert "bones: 21" in out
    assert "upper_arm.L" in out


def test_inspect_json(rig_json, capsys):
    assert main(["inspect", str(rig_json), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["bone_count"] == 21
    assert payload["fingerprint"] == rigify_rig().fingerprint()


def test_map_prints_table_and_summary(rig_json, capsys):
    assert main(["map", str(rig_json)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "upper_leg.L" in out and "thigh.L" in out
    assert "roles assigned" in out


def test_map_json_round_trip(rig_json, capsys):
    assert main(["map", str(rig_json), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["assignments"]["hips"]["bone"] == "pelvis"
    assert payload["core_missing"] == []


def test_map_save_preset_then_load(rig_json, tmp_path, capsys):
    preset = tmp_path / "p.rigpreset.json"
    assert main(["map", str(rig_json), "--save-preset", str(preset)]) == EXIT_OK
    assert preset.exists()
    assert main(["preset", "load", str(rig_json), str(preset)]) == EXIT_OK
    assert "preset override" in capsys.readouterr().out


def test_policy_status_default_off(capsys):
    assert main(["policy", "status"]) == EXIT_OK
    status = json.loads(capsys.readouterr().out)
    assert status["adult_module_enabled"] is False


def test_errors_are_actionable_not_tracebacks(tmp_path, capsys):
    code = main(["map", str(tmp_path / "missing.json")])
    captured = capsys.readouterr()
    assert code == EXIT_HANDLED_ERROR
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "rigpose" in capsys.readouterr().out
