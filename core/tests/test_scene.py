"""Scene contract tests (P8-1): schema validation, determinism, payload v3,
the v2 back-compat pin, and the casting validator (docs/SCENES.md)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

import riggermortis as rm  # noqa: E402
from riggermortis import payload as payload_mod  # noqa: E402
from riggermortis.canonical_pose import CanonicalPose  # noqa: E402
from riggermortis.errors import PayloadError, SceneError  # noqa: E402
from riggermortis.scene import ContactPin, SceneFigure, ScenePose  # noqa: E402


def _pose() -> CanonicalPose:
    return CanonicalPose(
        positions={"hips": (0.0, 0.0, 1.0), "chest": (0.0, 0.0, 1.3)},
        flips={}, confidence=0.9, reliable=True, scale=1.0, anchor="hips",
    )


def _scene(**pins_kwargs) -> ScenePose:
    pins = list(pins_kwargs.get("pins", []))
    return ScenePose(
        name="duet",
        figures=[SceneFigure("B", _pose()), SceneFigure("A", _pose())],
        pins=pins,
    )


def _pin(**over) -> ContactPin:
    fields = dict(figure_a="A", role_a="hand.R", figure_b="B", role_b="chest")
    fields.update(over)
    return ContactPin(**fields)


def _rig() -> rm.RigData:
    return rm.RigData(name="t", bones={
        "pelvis": rm.BoneData(name="pelvis", head=(0.0, 0.0, 1.0), tail=(0.0, 0.0, 1.1)),
    })


def _entries() -> list[dict]:
    return [
        {"figure": {"label": label, "index": i, "score": 0.9, "bbox": [0.0, 0.0, 10.0, 10.0]},
         "pose": _pose().to_dict(), "rotations": [], "skipped": [], "notes": []}
        for i, label in enumerate(("A", "B"))
    ]


# -- ContactPin validation --------------------------------------------------------


def test_pin_defaults_authored_confidence_one() -> None:
    pin = _pin()
    assert pin.origin == "authored" and pin.confidence == 1.0


def test_pin_unknown_field_refuses_with_hint() -> None:
    with pytest.raises(SceneError, match="unknown field"):
        ContactPin.from_dict({**_pin().to_dict(), "enforce": True})
    with pytest.raises(SceneError, match="known fields"):
        ContactPin.from_dict({**_pin().to_dict(), "bone": "x"})


def test_pin_empty_or_missing_field_refuses() -> None:
    for drop in ("figure_a", "role_a", "figure_b", "role_b"):
        d = _pin().to_dict()
        del d[drop]
        with pytest.raises(SceneError, match=drop):
            ContactPin.from_dict(d)
    with pytest.raises(SceneError, match="figure_a"):
        ContactPin.from_dict({**_pin().to_dict(), "figure_a": ""})


def test_pin_unknown_origin_refuses() -> None:
    with pytest.raises(SceneError, match="unknown origin"):
        ContactPin.from_dict({**_pin().to_dict(), "origin": "inferred"})


def test_pin_confidence_bands_and_bool() -> None:
    assert ContactPin.from_dict({**_pin().to_dict(), "origin": "suggested",
                                 "confidence": 0.7}).confidence == 0.7
    for bad in (1.5, -0.1):
        with pytest.raises(SceneError, match=r"confidence must be in \[0, 1\]"):
            ContactPin.from_dict({**_pin().to_dict(), "confidence": bad})
    with pytest.raises(SceneError, match="confidence"):
        ContactPin.from_dict({**_pin().to_dict(), "confidence": True})


def test_pin_round_trip_and_note_omission() -> None:
    plain = _pin().to_dict()
    assert "note" not in plain  # empty note never written
    noted = _pin(note="grip").to_dict()
    assert noted["note"] == "grip"
    assert ContactPin.from_dict(noted).to_dict() == noted


# -- SceneFigure / ScenePose validation -------------------------------------------


def test_figure_unknown_field_and_label_refuse() -> None:
    with pytest.raises(SceneError, match="unknown field"):
        SceneFigure.from_dict({"label": "A", "pose": _pose().to_dict(), "rig": "x"})
    with pytest.raises(SceneError, match="label"):
        SceneFigure.from_dict({"label": "", "pose": _pose().to_dict()})


def test_figure_bad_pose_refuses_with_hint() -> None:
    with pytest.raises(SceneError, match="not a valid CanonicalPose"):
        SceneFigure.from_dict({"label": "A", "pose": {"positions": "nope"}})


def test_scene_unknown_field_and_format_refuse() -> None:
    d = _scene().to_dict()
    with pytest.raises(SceneError, match="unknown field"):
        ScenePose.from_dict({**d, "camera": {}})
    bad = {**d, "format": 99}
    with pytest.raises(SceneError, match="unsupported format"):
        ScenePose.from_dict(bad)


def test_scene_requires_name() -> None:
    d = _scene().to_dict()
    del d["name"]
    with pytest.raises(SceneError, match="name"):
        ScenePose.from_dict(d)


def test_scene_duplicate_labels_refuse() -> None:
    with pytest.raises(SceneError, match="duplicate figure label"):
        ScenePose(name="s", figures=[SceneFigure("A", _pose()), SceneFigure("A", _pose())])


def test_scene_figures_sorted_labels_pins_authored_order() -> None:
    scene = _scene(pins=[_pin(figure_a="B", figure_b="A"), _pin()])
    assert [f.label for f in scene.figures] == ["A", "B"]  # keyed sort
    assert [p.figure_a for p in scene.pins] == ["B", "A"]  # authored order KEPT


def test_scene_pin_endpoint_validation() -> None:
    with pytest.raises(SceneError, match="unknown figure 'C'"):
        ScenePose(name="s", figures=[SceneFigure("A", _pose())], pins=[_pin(figure_b="C")])
    with pytest.raises(SceneError, match="unknown canonical role 'tail'"):
        ScenePose(name="s", figures=[SceneFigure("A", _pose()), SceneFigure("B", _pose())],
                  pins=[_pin(role_a="tail")])
    with pytest.raises(SceneError, match="self-contact"):
        ScenePose(name="s", figures=[SceneFigure("A", _pose())], pins=[_pin(figure_b="A")])


def test_scene_round_trip_byte_stable() -> None:
    scene = _scene(pins=[_pin(origin="suggested", confidence=0.7, note="grip")])
    one = json.dumps(scene.to_dict(), sort_keys=True)
    two = json.dumps(ScenePose.from_dict(json.loads(one)).to_dict(), sort_keys=True)
    assert one == two
    again = json.dumps(ScenePose.from_dict(json.loads(two)).to_dict(), sort_keys=True)
    assert two == again


# -- payload v3 + the back-compat pin ----------------------------------------------


def test_payload_v3_writes_pins_and_omits_when_empty() -> None:
    entries = _entries()
    plain = payload_mod.build_pose_payload(
        Path("i.png"), 100, 100, _rig(), entries, "A")
    assert plain["format"] == 3 and "pins" not in plain
    with_pin = payload_mod.build_pose_payload(
        Path("i.png"), 100, 100, _rig(), entries, "A",
        pins=[_pin().to_dict()])
    assert with_pin["pins"] == [_pin().to_dict()]
    assert payload_mod.figure_entries(with_pin) == payload_mod.figure_entries(plain)


def test_payload_v3_entry_shape_identical_to_v2() -> None:
    """The back-compat pin (read side): a v2 file and a v3 file with the same
    figures list expose the IDENTICAL entry surface through the v3 code."""
    entries = _entries()
    base = payload_mod.build_pose_payload(Path("i.png"), 100, 100, _rig(), entries, "A")
    as_v2 = {**base, "format": 2}
    assert payload_mod.figure_entries(base) == payload_mod.figure_entries(as_v2)
    assert payload_mod.pose_for_figure(base) == payload_mod.pose_for_figure(as_v2)
    assert payload_mod.figure_labels(base) == payload_mod.figure_labels(as_v2)


def test_pins_of_absent_empty_and_malformed() -> None:
    assert rm.pins_of({"format": 3}) == []
    with pytest.raises(PayloadError, match="'pins' is not a list"):
        rm.pins_of({"pins": "nope"})


def test_scene_from_payload_v3_carries_pins() -> None:
    payload = payload_mod.build_pose_payload(
        Path("i.png"), 100, 100, _rig(), _entries(), "A",
        pins=[_pin(origin="suggested", confidence=0.6).to_dict()])
    scene = rm.scene_from_payload(payload)
    assert [f.label for f in scene.figures] == ["A", "B"]
    assert scene.pins[0].origin == "suggested" and scene.pins[0].confidence == 0.6


def test_v2_payload_is_a_valid_scene_zero_pins() -> None:
    payload = payload_mod.build_pose_payload(Path("i.png"), 100, 100, _rig(), _entries(), "A")
    v2_file = {**payload, "format": 2}
    scene = rm.scene_from_payload(v2_file)
    assert [f.label for f in scene.figures] == ["A", "B"] and scene.pins == []


def test_v1_payload_synthesizes_one_figure_scene() -> None:
    v1 = {"format": 1, "figure": {"label": "solo"}, "pose": _pose().to_dict()}
    scene = rm.scene_from_payload(v1)
    assert [f.label for f in scene.figures] == ["solo"] and scene.pins == []


def test_scene_from_payload_missing_pose_refuses() -> None:
    payload = payload_mod.build_pose_payload(Path("i.png"), 100, 100, _rig(), _entries(), "A")
    payload["figures"][0]["pose"] = None  # type: ignore[assignment]
    with pytest.raises(SceneError, match="carry no pose dict"):
        rm.scene_from_payload(payload)


def test_malformed_payload_pin_refuses_with_index() -> None:
    payload = payload_mod.build_pose_payload(
        Path("i.png"), 100, 100, _rig(), _entries(), "A",
        pins=[{"figure_a": "A", "role_a": "hand.R", "figure_b": "B"}])
    with pytest.raises(SceneError, match=r"payload pin\[0\]"):
        rm.scene_from_payload(payload)


# -- casting validator --------------------------------------------------------------


def test_validate_casting_normalizes_sorted() -> None:
    scene = _scene()
    out = rm.validate_casting(scene, {"B": "RigB", "A": "RigA"}, ["RigA", "RigB"])
    assert out == {"A": "RigA", "B": "RigB"}


def test_validate_casting_subset_is_valid_and_reported() -> None:
    """Subset-casting (S26 as-built): only the PAIRED figures are posed; the
    uncast labels are reported by the apply, never silently skipped."""
    out = rm.validate_casting(_scene(), {"A": "RigA"}, ["RigA", "RigB"])
    assert out == {"A": "RigA"}
    uncast = sorted(f.label for f in _scene().figures if f.label not in out)
    assert uncast == ["B"]


def test_validate_casting_unknown_figure_label_refuses() -> None:
    with pytest.raises(SceneError, match="unknown figure"):
        rm.validate_casting(_scene(), {"A": "RigA", "B": "RigB", "C": "RigA"},
                            ["RigA", "RigB"])


def test_validate_casting_unknown_armature_refuses() -> None:
    with pytest.raises(SceneError, match="not in the scene"):
        rm.validate_casting(_scene(), {"A": "RigX", "B": "RigB"}, ["RigA", "RigB"])


def test_validate_casting_double_cast_refuses() -> None:
    with pytest.raises(SceneError, match="multiple figures"):
        rm.validate_casting(_scene(), {"A": "RigA", "B": "RigA"}, ["RigA"])


# -- scene schema DATA validation ----------------------------------------------------


def test_scene_dict_validates_against_its_own_schema() -> None:
    d = _scene(pins=[_pin()]).to_dict()
    assert d["format"] == rm.SCENE_FORMAT
    assert rm.PIN_ORIGINS == ("authored", "suggested")
