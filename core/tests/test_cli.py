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


# -- P6-1a: chain-binding presets through the CLI authoring surface ----------

def _bindings_file(tmp_path, name="bindings.json"):
    path = tmp_path / name
    path.write_text(
        json.dumps({
            "format": 1,
            "secondary": [{
                "chain": {
                    "format": 1, "name": "tail", "anchor_role": "hips",
                    "links": 4, "rest_direction": [0.0, -0.35, -1.0],
                },
                "bones": ["rm_tail_1", "rm_tail_2", "rm_tail_3", "rm_tail_4"],
            }],
        }),
        encoding="utf-8",
    )
    return path


def test_preset_save_with_secondary_then_load_prints_chains(
    rig_json, tmp_path, capsys
):
    from riggermortis.presets import load_preset

    preset = tmp_path / "p.rigpreset.json"
    bindings = _bindings_file(tmp_path)
    assert (
        main(["preset", "save", str(rig_json), str(preset),
              "--secondary", str(bindings)])
        == EXIT_OK
    )
    assert "secondary chain tail" in capsys.readouterr().out
    loaded = load_preset(preset)
    assert loaded.format == 2
    assert [b.chain.name for b in loaded.secondary] == ["tail"]
    assert loaded.secondary[0].bones == ("rm_tail_1", "rm_tail_2", "rm_tail_3", "rm_tail_4")
    # the same preset re-applies to its rig, chains visible — never hidden
    assert main(["preset", "load", str(rig_json), str(preset)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "preset override" in out
    assert "secondary chain tail: 4 link(s) off hips" in out


def test_preset_set_secondary_replaces_bindings_in_place(
    rig_json, tmp_path, capsys
):
    from riggermortis.presets import load_preset

    preset = tmp_path / "p.rigpreset.json"
    assert main(["preset", "save", str(rig_json), str(preset)]) == EXIT_OK
    assert "secondary chains: none" in capsys.readouterr().out
    assert (
        main(["preset", "set-secondary", str(preset),
              str(_bindings_file(tmp_path))])
        == EXIT_OK
    )
    assert "preset updated" in capsys.readouterr().out
    loaded = load_preset(preset)
    assert loaded.format == 2
    assert [b.chain.name for b in loaded.secondary] == ["tail"]


def test_preset_save_with_bad_bindings_is_actionable(
    rig_json, tmp_path, capsys
):
    bad = tmp_path / "bad.json"
    bad.write_text('{"format": 1, "secondary": [{"chain": {}}]}', encoding="utf-8")
    code = main(["preset", "save", str(rig_json), str(tmp_path / "p.json"),
                 "--secondary", str(bad)])
    captured = capsys.readouterr()
    assert code == EXIT_HANDLED_ERROR
    assert "error:" in captured.err
    assert "hint:" in captured.err
    assert "Traceback" not in captured.err


def test_map_set_applies_manual_reassignment(rig_json, capsys):
    assert main(["map", str(rig_json), "--json", "--set", "hips=spine"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["assignments"]["hips"]["bone"] == "spine"
    assert payload["assignments"]["hips"]["confidence"] == 1.0
    assert payload["assignments"]["hips"]["evidence"] == ["manual reassignment"]
    # the spine bone's previous role (spine) was freed and is reported
    assert "spine" in payload["core_missing"]
    assert any("manual reassignment: hips -> spine" in n for n in payload["notes"])


def test_map_set_multiple_pairs_in_order(rig_json, capsys):
    assert main([
        "map", str(rig_json), "--json", "--set", "hips=spine,root=pelvis",
    ]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["assignments"]["hips"]["bone"] == "spine"
    assert payload["assignments"]["root"]["bone"] == "pelvis"


def test_map_set_bad_format_is_actionable(rig_json, capsys):
    code = main(["map", str(rig_json), "--set", "nonsense"])
    assert code == EXIT_HANDLED_ERROR
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "hint:" in err
    assert "Traceback" not in err


def test_map_set_unknown_bone_is_actionable(rig_json, capsys):
    code = main(["map", str(rig_json), "--set", "hips=not_a_bone"])
    assert code == EXIT_HANDLED_ERROR
    err = capsys.readouterr().err
    assert "not_a_bone" in err and "hint:" in err


def test_map_set_unknown_role_is_actionable(rig_json, capsys):
    code = main(["map", str(rig_json), "--set", "not_a_role=spine"])
    assert code == EXIT_HANDLED_ERROR
    err = capsys.readouterr().err
    assert "not_a_role" in err and "hint:" in err


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
