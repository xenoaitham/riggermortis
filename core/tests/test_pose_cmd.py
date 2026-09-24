"""P1-6/D-009 tests: ``rigpose pose`` — payload build, figure selection, errors.

The DWPose detection is faked (canned Detection objects, no models, no
network); everything after ``detect`` — figure board, solve, FK, payload — is
pure stdlib and runs in CI unchanged.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from riggermortis import payload as payload_mod  # noqa: E402
from riggermortis.canonical_pose import CanonicalPose  # noqa: E402
from riggermortis.cli import EXIT_HANDLED_ERROR, EXIT_OK, main  # noqa: E402
from riggermortis.errors import InferenceError  # noqa: E402
from riggermortis.fk_apply import apply_canonical_pose, verify_application  # noqa: E402
from riggermortis.inference.poses import KEYPOINT_COUNT, Detection, Figure  # noqa: E402
from riggermortis.io import load_rig  # noqa: E402
from riggermortis.mapper import map_rig  # noqa: E402
from rigs import rigify_rig  # noqa: E402

ANGLE_TOL_RAD = math.radians(0.5)


def _standing_keypoints(cx: float, cy: float, scale_px: float) -> list[tuple[float, float]]:
    """A standing figure in pixel space (image y grows downward)."""
    body = {
        0: (0.0, -2.6),  # nose
        5: (-0.7, -1.8), 6: (0.7, -1.8),  # shoulders
        7: (-0.8, -0.5), 8: (0.8, -0.5),  # elbows
        9: (-0.85, 0.7), 10: (0.85, 0.7),  # wrists
        11: (-0.25, -0.0), 12: (0.25, 0.0),  # hips
        13: (-0.3, 1.6), 14: (0.3, 1.6),  # knees
        15: (-0.32, 2.8), 16: (0.32, 2.8),  # ankles
        17: (-0.38, 3.0), 18: (-0.26, 3.0),  # L toes
        20: (0.26, 3.0), 21: (0.38, 3.0),  # R toes
    }
    return [(cx + dx * scale_px, cy + dy * scale_px) for dx, dy in
            (body.get(i, (0.0, -1.0)) for i in range(KEYPOINT_COUNT))]


def _detection(two_figures: bool = False) -> Detection:
    kps = _standing_keypoints(320.0, 500.0, 100.0)
    fig0 = Figure(
        index=0, bbox=(200.0, 180.0, 440.0, 820.0), score=0.95,
        keypoints=kps, confidences=[0.9] * KEYPOINT_COUNT,
    )
    figures = [fig0]
    if two_figures:
        # Smaller score but LARGER bbox -> 'largest' must pick it over fig0.
        fig1 = Figure(
            index=1, bbox=(520.0, 100.0, 900.0, 900.0), score=0.8,
            keypoints=_standing_keypoints(710.0, 500.0, 110.0),
            confidences=[0.85] * KEYPOINT_COUNT,
        )
        figures.append(fig1)
    return Detection(width=640 if not two_figures else 960, height=820, figures=figures)


@pytest.fixture()
def rig_json(tmp_path: Path) -> Path:
    path = tmp_path / "rig.json"
    rigify_rig().to_json(path)
    return path


@pytest.fixture()
def fake_detect(monkeypatch: pytest.MonkeyPatch):
    """Replace the real DWPose call with a canned standing figure."""
    holder: dict[str, Detection] = {"detection": _detection()}

    def _fake(image_path: str, providers=None):  # noqa: ANN001
        return holder["detection"]

    import riggermortis.inference.dwpose as dwpose

    monkeypatch.setattr(dwpose, "detect_keypoints", _fake)
    return holder


def _image_file(tmp_path: Path) -> Path:
    path = tmp_path / "reference.jpg"
    path.write_bytes(b"\xff\xd8fake")  # content irrelevant; existence is checked
    return path


# -- happy path ------------------------------------------------------------------


def test_pose_writes_payload_and_round_trips(fake_detect, rig_json, tmp_path, capsys) -> None:
    out = tmp_path / "payload.json"
    assert main(["pose", str(_image_file(tmp_path)), str(rig_json), "--out", str(out)]) == EXIT_OK
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format"] == 3  # v3 write (S26)
    assert payload["image"]["width"] == 640 and payload["image"]["height"] == 820
    assert payload["figure"]["label"] == "figure 1"
    assert payload["rig"]["fingerprint"] == rigify_rig().fingerprint()
    # v2: figures list mirrors the selected figure into the v1 top-level keys.
    assert [f["label"] for f in payload["figures"]] == ["figure 1"]
    assert payload["figures"][0]["pose"] == payload["pose"]

    pose = CanonicalPose.from_dict(payload["pose"])
    assert "hips" in pose.positions and pose.reliable

    rig = load_rig(rig_json)
    mapping = map_rig(rig)
    application = apply_canonical_pose(rig, mapping, pose)
    errors = verify_application(rig, application, pose)
    assert errors, "a standing pose must rotate core bones"
    worst_role, worst = max(errors.items(), key=lambda kv: kv[1])
    assert worst <= ANGLE_TOL_RAD, f"{worst_role} off by {math.degrees(worst):.4f} deg"


def test_pose_json_flag_prints_payload(fake_detect, rig_json, tmp_path, capsys) -> None:
    code = main(["pose", str(_image_file(tmp_path)), str(rig_json), "--json"])
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == 3 and payload["rotations"]


def test_pose_all_figures_embeds_every_figure(fake_detect, rig_json, tmp_path) -> None:
    """--all-figures: every detected figure solved into the payload (B1)."""
    fake_detect["detection"] = _detection(two_figures=True)
    img = str(_image_file(tmp_path))
    out = tmp_path / "payload.json"
    assert main(["pose", img, str(rig_json), "--all-figures", "--out", str(out)]) == EXIT_OK
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert [f["label"] for f in payload["figures"]] == ["figure 1", "figure 2"]
    assert payload["figure"]["label"] == "figure 2"  # largest = default selection
    poses = {f["label"]: CanonicalPose.from_dict(f["pose"]) for f in payload["figures"]}
    assert all(p.reliable for p in poses.values())
    assert poses["figure 1"].positions != poses["figure 2"].positions
    # every embedded figure carries FK rotations for headless consumers
    assert all(f["rotations"] for f in payload["figures"])
    # switching the selection is a pure read on the same payload
    other = payload_mod.pose_for_figure(payload, "figure 1")
    assert CanonicalPose.from_dict(other).positions == poses["figure 1"].positions


def test_pose_summary_is_human_readable(fake_detect, rig_json, tmp_path, capsys) -> None:
    out = tmp_path / "payload.json"
    main(["pose", str(_image_file(tmp_path)), str(rig_json), "--out", str(out)])
    text = capsys.readouterr().out
    assert "figure 1" in text and "confidence" in text and "payload written" in text


# -- figure selection ---------------------------------------------------------------


def test_pose_default_picks_largest_figure(fake_detect, rig_json, tmp_path, capsys) -> None:
    fake_detect["detection"] = _detection(two_figures=True)
    out = tmp_path / "payload.json"
    main(["pose", str(_image_file(tmp_path)), str(rig_json), "--out", str(out)])
    assert json.loads(out.read_text(encoding="utf-8"))["figure"]["label"] == "figure 2"


def test_pose_figure_by_index_and_primary(fake_detect, rig_json, tmp_path) -> None:
    fake_detect["detection"] = _detection(two_figures=True)
    img = str(_image_file(tmp_path))
    rig = str(rig_json)
    out_a, out_b = tmp_path / "a.json", tmp_path / "b.json"
    assert main(["pose", img, rig, "--figure", "1", "--out", str(out_a)]) == EXIT_OK
    assert main(["pose", img, rig, "--figure", "primary", "--out", str(out_b)]) == EXIT_OK
    assert json.loads(out_a.read_text(encoding="utf-8"))["figure"]["label"] == "figure 2"
    assert json.loads(out_b.read_text(encoding="utf-8"))["figure"]["label"] == "figure 1"


def test_pose_figure_index_is_deterministic(fake_detect, rig_json, tmp_path) -> None:
    fake_detect["detection"] = _detection(two_figures=True)
    img = str(_image_file(tmp_path))
    rig = str(rig_json)
    outs = []
    for i in range(2):
        out = tmp_path / f"det{i}.json"
        main(["pose", img, rig, "--figure", "0", "--out", str(out)])
        outs.append(json.loads(out.read_text(encoding="utf-8")))
    assert outs[0] == outs[1]


# -- honest degradation + actionable errors -------------------------------------------


def test_pose_low_confidence_still_yields_payload_with_honest_note(
    fake_detect, rig_json, tmp_path
) -> None:
    detection = _detection()
    detection.figures[0].confidences = [0.2] * KEYPOINT_COUNT
    fake_detect["detection"] = detection
    out = tmp_path / "payload.json"
    assert main(["pose", str(_image_file(tmp_path)), str(rig_json), "--out", str(out)]) == EXIT_OK
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["pose"]["reliable"] is False
    assert any("below the reliable bar" in n for n in payload["notes"])


def test_pose_missing_image_is_actionable(rig_json, tmp_path, capsys) -> None:
    code = main(["pose", str(tmp_path / "nope.jpg"), str(rig_json)])
    captured = capsys.readouterr()
    assert code == EXIT_HANDLED_ERROR
    assert "error: image not found" in captured.err and "hint:" in captured.err
    assert "Traceback" not in captured.err


def test_pose_detect_failure_surfaces_hint(
    fake_detect, monkeypatch: pytest.MonkeyPatch, rig_json, tmp_path, capsys
) -> None:
    def _boom(image_path: str, providers=None):  # noqa: ANN001
        raise InferenceError(
            "model dw-ll_ucoco_384.onnx is not downloaded",
            hint="run: rigpose models download all",
        )

    import riggermortis.inference.dwpose as dwpose

    monkeypatch.setattr(dwpose, "detect_keypoints", _boom)
    code = main(["pose", str(_image_file(tmp_path)), str(rig_json)])
    err = capsys.readouterr().err
    assert code == EXIT_HANDLED_ERROR
    assert "rigpose models download" in err and "Traceback" not in err


def test_pose_no_person_detected_is_actionable(fake_detect, rig_json, tmp_path, capsys) -> None:
    fake_detect["detection"] = Detection(width=640, height=820, figures=[])
    code = main(["pose", str(_image_file(tmp_path)), str(rig_json)])
    err = capsys.readouterr().err
    assert code == EXIT_HANDLED_ERROR
    assert "no person detected" in err and "hint:" in err


def test_pose_bad_figure_selector_is_actionable(fake_detect, rig_json, tmp_path, capsys) -> None:
    code = main([
        "pose", str(_image_file(tmp_path)), str(rig_json), "--figure", "banana",
    ])
    err = capsys.readouterr().err
    assert code == EXIT_HANDLED_ERROR
    assert "banana" in err and "hint:" in err


def test_pose_figure_out_of_range_is_actionable(fake_detect, rig_json, tmp_path, capsys) -> None:
    code = main([
        "pose", str(_image_file(tmp_path)), str(rig_json), "--figure", "7",
    ])
    err = capsys.readouterr().err
    assert code == EXIT_HANDLED_ERROR
    assert "figure 7 does not exist" in err


def test_pose_missing_out_and_json_is_actionable(fake_detect, rig_json, tmp_path, capsys) -> None:
    code = main(["pose", str(_image_file(tmp_path)), str(rig_json)])
    err = capsys.readouterr().err
    assert code == EXIT_HANDLED_ERROR
    assert "--out" in err and "hint:" in err
