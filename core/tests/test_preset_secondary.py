"""P6-1a chain-binding presets: the format-2 schema, loud validation, the
format-1 back-compat read, the fingerprint gate, and the bindings-file
loader (the CLI authoring surface rides the same loader; its command
round-trips are pinned in test_cli.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from riggermortis.errors import PresetError, SecondaryError  # noqa: E402
from riggermortis.mapper import map_rig  # noqa: E402
from riggermortis.presets import (  # noqa: E402
    PRESET_FORMAT,
    SecondaryBinding,
    load_preset,
    load_secondary_bindings,
    preset_from_mapping,
    resolve_secondary,
    save_preset,
)
from riggermortis.secondary import ChainSpec  # noqa: E402
from rigs import rigify_rig  # noqa: E402

TAIL = {
    "format": 1,
    "name": "tail",
    "anchor_role": "hips",
    "links": 4,
    "rest_direction": [0.0, -0.35, -1.0],
}
HAIR = {
    "format": 1,
    "name": "ponytail",
    "anchor_role": "head",
    "links": 2,
    "rest_direction": [0.0, -0.5, -1.0],
    "freq_hz": 4.0,
}


def _binding(chain: dict) -> dict:
    return {
        "chain": chain,
        "bones": [f"rm_{chain['name']}_{i + 1}" for i in range(chain["links"])],
    }


def _rig_and_preset(secondary=None):
    rig = rigify_rig()
    preset = preset_from_mapping(rig, map_rig(rig), secondary=secondary)
    return rig, preset


# ---------------------------------------------------------------------------
# round-trips: format 2 written, format 1 read, floats exact
# ---------------------------------------------------------------------------

def test_v2_preset_round_trip_with_binding(tmp_path):
    rig, preset = _rig_and_preset(secondary=[SecondaryBinding.from_dict(_binding(TAIL))])
    path = save_preset(preset, tmp_path / "p.rigpreset.json")
    loaded = load_preset(path)
    assert loaded.format == PRESET_FORMAT == 2
    assert [b.chain.name for b in loaded.secondary] == ["tail"]
    # the chain validates to the SAME object the standalone spec produces —
    # one validator implementation (docs/SECONDARY_MOTION.md discipline)
    assert loaded.secondary[0].chain == ChainSpec.from_dict(TAIL)
    assert loaded.secondary[0].bones == ("rm_tail_1", "rm_tail_2", "rm_tail_3", "rm_tail_4")
    # and the mapping half is untouched by the schema bump
    assert loaded.fingerprint == rig.fingerprint()
    assert loaded.mapping == preset.mapping


def test_directions_round_trip_exactly(tmp_path):
    """Already-unit rest directions pass through normalization unchanged, so
    a save -> load -> save cycle is byte-stable (the determinism rule)."""
    _, preset = _rig_and_preset(secondary=[SecondaryBinding.from_dict(_binding(TAIL))])
    first = save_preset(preset, tmp_path / "a.json")
    loaded = load_preset(first)
    second = save_preset(loaded, tmp_path / "b.json")
    assert first.read_bytes() == second.read_bytes()


def test_v1_preset_still_loads_mapping_only(tmp_path):
    """The P1-11 payload pattern: an old file still loads — it just carries
    no chains (an old build reading a NEW file refuses loudly instead)."""
    rig, preset = _rig_and_preset()
    d = preset.to_dict()
    d["format"] = 1
    d.pop("secondary", None)
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(d), encoding="utf-8")
    loaded = load_preset(path)
    assert loaded.format == 1
    assert loaded.secondary == []
    assert loaded.fingerprint == rig.fingerprint()


def test_v2_preset_without_secondary_key_loads(tmp_path):
    rig, preset = _rig_and_preset()
    d = preset.to_dict()
    del d["secondary"]
    path = tmp_path / "minimal.json"
    path.write_text(json.dumps(d), encoding="utf-8")
    loaded = load_preset(path)
    assert loaded.format == 2
    assert loaded.secondary == []


def test_unsupported_format_refuses_with_hint(tmp_path):
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"format": 3, "mapping": {}}), encoding="utf-8")
    with pytest.raises(PresetError) as excinfo:
        load_preset(path)
    assert "formats 1-2" in str(excinfo.value)


# ---------------------------------------------------------------------------
# loud binding validation (every refusal carries a hint)
# ---------------------------------------------------------------------------

def test_binding_unknown_field_refuses():
    bad = _binding(TAIL)
    bad["length"] = 3
    with pytest.raises(PresetError) as excinfo:
        SecondaryBinding.from_dict(bad)
    assert "length" in str(excinfo.value)
    assert "known fields" in str(excinfo.value)


def test_binding_chain_validates_through_chainspec():
    bad = _binding({**TAIL, "anchor_role": "nope"})
    with pytest.raises(SecondaryError):
        SecondaryBinding.from_dict(bad)


def test_binding_bones_count_must_match_links():
    bad = _binding(TAIL)
    bad["bones"] = bad["bones"][:2]
    with pytest.raises(PresetError) as excinfo:
        SecondaryBinding.from_dict(bad)
    assert "4 link(s)" in str(excinfo.value)


def test_binding_rejects_empty_or_nonstring_bones():
    for bones in ([], ["rm_tail_1", 2, "rm_tail_3", "rm_tail_4"], "rm_tail_1"):
        bad = _binding(TAIL)
        bad["bones"] = bones
        with pytest.raises(PresetError):
            SecondaryBinding.from_dict(bad)


def test_binding_rejects_duplicate_bone_within_chain():
    bad = _binding(TAIL)
    bad["bones"] = ["rm_tail_1", "rm_tail_1", "rm_tail_3", "rm_tail_4"]
    with pytest.raises(PresetError) as excinfo:
        SecondaryBinding.from_dict(bad)
    assert "duplicate bone name" in str(excinfo.value)


# ---------------------------------------------------------------------------
# preset-level guards: sorted storage, unique names, one bone per chain
# ---------------------------------------------------------------------------

def test_bindings_stored_sorted_by_chain_name():
    _, preset = _rig_and_preset(
        secondary=[
            SecondaryBinding.from_dict(_binding(TAIL)),
            SecondaryBinding.from_dict(_binding(HAIR)),
        ]
    )
    assert [b.chain.name for b in preset.secondary] == ["ponytail", "tail"]


def test_preset_rejects_duplicate_chain_names():
    second_tail = {**TAIL, "anchor_role": "spine"}
    with pytest.raises(PresetError) as excinfo:
        _rig_and_preset(
            secondary=[
                SecondaryBinding.from_dict(_binding(TAIL)),
                SecondaryBinding.from_dict(_binding(second_tail)),
            ]
        )
    assert "duplicate secondary chain name" in str(excinfo.value)


def test_preset_rejects_a_bone_bound_to_two_chains():
    hair = _binding(HAIR)
    hair["bones"] = ["rm_tail_1", "rm_head_2"]
    with pytest.raises(PresetError) as excinfo:
        _rig_and_preset(
            secondary=[
                SecondaryBinding.from_dict(_binding(TAIL)),
                SecondaryBinding.from_dict(hair),
            ]
        )
    assert "rm_tail_1" in str(excinfo.value)
    assert "ONE chain" in str(excinfo.value)


# ---------------------------------------------------------------------------
# the fingerprint gate: bindings ride the same contract as the mapping
# ---------------------------------------------------------------------------

def test_resolve_secondary_fingerprint_gate_and_force():
    rig, preset = _rig_and_preset(secondary=[SecondaryBinding.from_dict(_binding(TAIL))])
    bindings = resolve_secondary(preset, rig.fingerprint())
    assert [b.chain.name for b in bindings] == ["tail"]
    moved = rig.fingerprint()[:-1] + ("0" if rig.fingerprint()[-1] != "0" else "1")
    with pytest.raises(PresetError) as excinfo:
        resolve_secondary(preset, moved)
    assert "force=True" in str(excinfo.value)
    forced = resolve_secondary(preset, moved, force=True)
    assert len(forced) == 1


def test_resolve_secondary_on_mapping_only_preset_is_empty():
    rig, preset = _rig_and_preset()
    assert resolve_secondary(preset, rig.fingerprint()) == []


# ---------------------------------------------------------------------------
# the bindings-file loader (CLI authoring surface)
# ---------------------------------------------------------------------------

def test_bindings_file_round_trip(tmp_path):
    path = tmp_path / "bindings.json"
    path.write_text(
        json.dumps({"format": 1, "secondary": [_binding(TAIL), _binding(HAIR)]}),
        encoding="utf-8",
    )
    bindings = load_secondary_bindings(path)
    assert [b.chain.name for b in bindings] == ["ponytail", "tail"]
    assert bindings[0].bones == ("rm_ponytail_1", "rm_ponytail_2")


def test_bindings_file_loud_rejections(tmp_path):
    missing = tmp_path / "gone.json"
    with pytest.raises(PresetError):
        load_secondary_bindings(missing)

    junk = tmp_path / "junk.json"
    junk.write_text("not json", encoding="utf-8")
    with pytest.raises(PresetError):
        load_secondary_bindings(junk)

    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps([_binding(TAIL)]), encoding="utf-8")
    with pytest.raises(PresetError) as excinfo:
        load_secondary_bindings(bare)
    assert "JSON object" in str(excinfo.value)

    extra = tmp_path / "extra.json"
    extra.write_text(
        json.dumps({"format": 1, "secondary": [], "notes": "hi"}), encoding="utf-8",
    )
    with pytest.raises(PresetError) as excinfo:
        load_secondary_bindings(extra)
    assert "unknown field" in str(excinfo.value)

    future = tmp_path / "future.json"
    future.write_text(json.dumps({"format": 2, "secondary": []}), encoding="utf-8")
    with pytest.raises(PresetError) as excinfo:
        load_secondary_bindings(future)
    assert "bindings format 1" in str(excinfo.value)
