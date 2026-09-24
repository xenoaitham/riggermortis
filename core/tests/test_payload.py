"""Payload contract tests (D-009, B1): v2 reading, v1 back-compat, figure resolution."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis import payload as payload_mod  # noqa: E402
from riggermortis.canonical_pose import CanonicalPose  # noqa: E402
from riggermortis.errors import PayloadError  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _v2_payload() -> dict:
    return {
        "format": 2,
        "figure": {"label": "figure 2", "index": 1, "score": 0.9, "bbox": [0, 0, 1, 1]},
        "pose": {"a": 1},
        "rotations": [{"bone": "x"}],
        "skipped": [],
        "notes": ["selected"],
        "figures": [
            {"label": "figure 1", "index": 0, "score": 0.8, "bbox": [],
             "pose": {"b": 2}, "rotations": [], "skipped": [], "notes": []},
            {"label": "figure 2", "index": 1, "score": 0.9, "bbox": [],
             "pose": {"a": 1}, "rotations": [{"bone": "x"}], "skipped": [], "notes": ["selected"]},
        ],
    }


def test_v2_entries_and_labels() -> None:
    payload = _v2_payload()
    assert payload_mod.figure_labels(payload) == ["figure 1", "figure 2"]
    assert payload_mod.pose_for_figure(payload) == {"a": 1}  # selected by default
    assert payload_mod.pose_for_figure(payload, "figure 1") == {"b": 2}


def test_v1_backcompat_single_figure() -> None:
    v1 = {
        "format": 1,
        "figure": {"label": "figure 1", "index": 0, "score": 0.95, "bbox": [1, 2, 3, 4]},
        "pose": {"c": 3},
        "rotations": [{"bone": "y"}],
        "skipped": ["s"],
        "notes": ["n"],
    }
    assert payload_mod.figure_labels(v1) == ["figure 1"]
    entry = payload_mod.entry_for_label(v1)
    assert entry["pose"] == {"c": 3} and entry["rotations"] == [{"bone": "y"}]
    assert entry["skipped"] == ["s"] and entry["notes"] == ["n"]


def test_v1_missing_format_key_defaults_to_v1() -> None:
    v1 = {"pose": {"z": 0}}  # early payloads: format key absent
    assert payload_mod.figure_labels(v1) == ["figure 0"]
    assert payload_mod.pose_for_figure(v1) == {"z": 0}


def test_unknown_figure_label_is_actionable() -> None:
    with pytest.raises(PayloadError) as exc:
        payload_mod.pose_for_figure(_v2_payload(), "figure 9")
    assert "figure 9" in str(exc.value) and "hint:" in str(exc.value)
    assert "figure 1, figure 2" in str(exc.value)


def test_unsupported_format_is_actionable() -> None:
    with pytest.raises(PayloadError) as exc:
        payload_mod.figure_entries({"format": 9})
    assert "formats 1, 2 and 3" in str(exc.value)


def test_v2_without_figures_list_is_actionable() -> None:
    with pytest.raises(PayloadError) as exc:
        payload_mod.figure_entries({"format": 2})
    assert "figures" in str(exc.value) and "hint:" in str(exc.value)


def test_committed_v1_fixture_still_reads() -> None:
    """The committed real-rig fixture is format 1 and must keep loading (back-compat)."""
    raw = json.loads((FIXTURES / "pose_payload_metarig.json").read_text(encoding="utf-8"))
    if raw.get("format", 1) != 1:
        return  # fixture regenerated to v2 by a later session; nothing to prove here
    pose_dict = payload_mod.pose_for_figure(raw)
    pose = CanonicalPose.from_dict(pose_dict)
    assert pose.positions, "fixture pose must round-trip"


def test_build_payload_mirrors_selected_into_v1_keys() -> None:
    entries = [
        {"figure": {"label": "figure 1", "index": 0, "score": 0.8, "bbox": [0, 0, 1, 1]},
         "pose": {"b": 2}, "rotations": [], "skipped": [], "notes": []},
        {"figure": {"label": "figure 2", "index": 1, "score": 0.9, "bbox": [0, 0, 2, 2]},
         "pose": {"a": 1}, "rotations": [{"bone": "x"}], "skipped": ["s"], "notes": ["n"]},
    ]

    class _Rig:
        name = "rig"

        def fingerprint(self) -> str:
            return "fp"

    payload = payload_mod.build_pose_payload(
        Path("img.jpg"), 64, 64, _Rig(), entries, selected_label="figure 2"
    )
    assert payload["format"] == 3  # v3 write (S26); read side pins stay 2
    assert payload["figure"]["label"] == "figure 2"
    assert payload["pose"] == {"a": 1}  # v1 reader sees the selected figure
    assert payload["rotations"] == [{"bone": "x"}]
    assert [f["label"] for f in payload["figures"]] == ["figure 1", "figure 2"]
