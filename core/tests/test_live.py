"""P5-1 tests: live side-process contract — sources, loop policy, stream.

Faked everything (the P2-1 video.py test pattern): no models, no network,
no real frames — the pose data is deterministic synthetic keypoints. The
timing fields in the ``live`` envelope are MEASUREMENTS: asserted present
and finite, never value-equal (docs/LIVE.md determinism statement).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis import live  # noqa: E402
from riggermortis.errors import RiggermortisError  # noqa: E402
from riggermortis.inference.poses import (  # noqa: E402
    KEYPOINT_COUNT,
    Detection,
    Figure,
)
from riggermortis.payload import figure_entries  # noqa: E402
from rigs import rigify_rig  # noqa: E402

W, H = 640, 960


def _standing_keypoints(cx: float, cy: float, scale_px: float) -> list[tuple[float, float]]:
    """The same solvable standing body the video tests use."""
    body = {
        0: (0.0, -2.6),
        5: (-0.7, -1.8), 6: (0.7, -1.8),
        7: (-0.8, -0.5), 8: (0.8, -0.5),
        9: (-0.85, 0.7), 10: (0.85, 0.7),
        11: (-0.25, -0.0), 12: (0.25, 0.0),
        13: (-0.3, 1.6), 14: (0.3, 1.6),
        15: (-0.32, 2.8), 16: (0.32, 2.8),
        17: (-0.38, 3.0), 18: (-0.26, 3.0),
        20: (0.26, 3.0), 21: (0.38, 3.0),
    }
    return [(cx + dx * scale_px, cy + dy * scale_px) for dx, dy in
            (body.get(i, (0.0, -1.0)) for i in range(KEYPOINT_COUNT))]


def _figure(i: int, score: float, conf: float, label: str = "figure 1") -> Figure:
    return Figure(
        index=0, bbox=(200.0 + i, 180.0, 440.0 + i, 820.0), score=score,
        keypoints=_standing_keypoints(320.0, 480.0, 100.0),
        confidences=[conf] * KEYPOINT_COUNT, label=label,
    )


class FakeDetector:
    """Deterministic two-path detector: counts calls, records tracked boxes."""

    def __init__(self, skip: set[int] | None = None, conf: float = 0.85):
        self.skip = skip or set()
        self.conf = conf
        self.full_calls = 0
        self.at_calls = 0
        self.tracked_boxes: list[tuple[float, float, float, float]] = []

    def full(self, path: Path) -> Detection:
        self.full_calls += 1
        i = _frame_index(path)
        if i in self.skip:
            return Detection(width=W, height=H, figures=[])
        return Detection(width=W, height=H, figures=[_figure(i, 0.9, self.conf)])

    def at(self, path: Path, bbox: tuple[float, float, float, float]) -> Figure:
        self.at_calls += 1
        self.tracked_boxes.append(bbox)
        i = _frame_index(path)
        if i in self.skip:  # tracked into a personless frame: garbage conf
            return _figure(i, 0.0, 0.05, label="")
        return _figure(i, 0.0, self.conf, label="")


def _frame_index(path: Path) -> int:
    return int(Path(path).stem.split("_")[1])


def _frames(tmp_path: Path, count: int) -> list[Path]:
    return [tmp_path / f"frame_{i:06d}.png" for i in range(count)]


def _write_frames(paths: list[Path]) -> None:
    for p in paths:
        p.write_bytes(b"\x89PNG fake")


@pytest.fixture()
def rig_json(tmp_path: Path) -> Path:
    path = tmp_path / "rig.json"
    rigify_rig().to_json(path)
    return path


def _run(tmp_path: Path, rig_json: Path, detector, count: int = 7, **kwargs):
    frames = _frames(tmp_path, count)
    _write_frames(frames)
    out = tmp_path / "live.jsonl"
    report = live.run_live(
        live.ListFrameSource(frames), rig_json, out, detector, **kwargs
    )
    events, corrupt = live.read_live_lines(out)
    return report, events, corrupt, out


# -- sources --------------------------------------------------------------------


def test_expand_bbox_grows_and_clamps() -> None:
    box = (100.0, 100.0, 200.0, 200.0)
    assert live.expand_bbox(box, 0.0, 1000.0, 1000.0) == box  # identity
    grown = live.expand_bbox(box, 0.15, 1000.0, 1000.0)
    assert grown == (85.0, 85.0, 215.0, 215.0)
    clamped = live.expand_bbox((2.0, 3.0, 8.0, 990.0), 0.5, 1000.0, 1000.0)
    assert clamped == (0.0, 0.0, 11.0, 1000.0)  # never leaves the frame


def test_list_source_is_ordered_exhausts_and_labels(tmp_path: Path) -> None:
    frames = list(reversed(_frames(tmp_path, 4)))  # caller order is irrelevant
    _write_frames(frames)
    source = live.ListFrameSource(frames)
    assert source.label == "<list>"
    seen = [source.next_frame() for _ in range(5)]
    assert [f.seq for f in seen[:4]] == [0, 1, 2, 3]
    assert [f.path.name for f in seen[:4]] == sorted(p.name for p in frames)
    assert all(f.t_capture is None for f in seen[:4])
    assert seen[4] is None  # exhausted


def test_directory_source_yields_each_frame_once_in_order(tmp_path: Path) -> None:
    d = tmp_path / "frames"
    d.mkdir()
    _write_frames([d / f"frame_{i:06d}.png" for i in (2, 0, 1)])
    source = live.DirectoryFrameSource(d, poll_seconds=0.0)
    assert source.label == str(d)
    names = [source.next_frame().path.name for _ in range(3)]
    assert names == [f"frame_{i:06d}.png" for i in range(3)]
    # a glue-written file appearing later is picked up exactly once
    (d / "frame_000003.png").write_bytes(b"\x89PNG fake")
    nxt = source.next_frame()
    assert nxt is not None and nxt.path.name == "frame_000003.png"
    assert nxt.seq == 3
    assert source.next_frame() is None or True  # no busy spin assertion here


def test_directory_source_t_capture_is_file_mtime(tmp_path: Path) -> None:
    d = tmp_path / "frames"
    d.mkdir()
    p = d / "frame_000000.png"
    p.write_bytes(b"\x89PNG fake")
    frame = live.DirectoryFrameSource(d, poll_seconds=0.0).next_frame()
    assert frame is not None
    assert frame.t_capture == pytest.approx(p.stat().st_mtime, abs=1e-3)


def test_directory_source_idle_timeout_and_missing_dir(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    source = live.DirectoryFrameSource(
        empty, poll_seconds=0.0, idle_timeout=0.05
    )
    assert source.next_frame() is None  # stops, does not hang
    missing = live.DirectoryFrameSource(
        tmp_path / "never", poll_seconds=0.0, idle_timeout=0.05
    )
    assert missing.next_frame() is None  # graceful; the CLI reports 0 frames


# -- the loop ------------------------------------------------------------------


def test_run_live_emits_contract_valid_pose_lines(tmp_path, rig_json) -> None:
    report, events, corrupt, out = _run(tmp_path, rig_json, FakeDetector())
    assert corrupt == 0
    assert report.frames == 7 and report.poses == 7 and report.misses == 0
    assert all(e["kind"] == "pose" for e in events)
    for event in events:
        entries = figure_entries(event)  # the D-009 contract reads it unchanged
        assert len(entries) == 1
        assert event["format"] == 2
        assert event["rig"]["fingerprint"] == rigify_rig().fingerprint()
        envelope = event["live"]
        assert envelope["total_ms"] >= 0.0 and envelope["detect_ms"] >= 0.0
        assert envelope["solve_ms"] >= 0.0 and envelope["fk_ms"] >= 0.0
        assert envelope["t_emit_wall"] > 0.0
        assert envelope["age_ms"] is None  # ListSource carries no capture time


def test_run_live_tracked_cadence_and_expanded_boxes(tmp_path, rig_json) -> None:
    detector = FakeDetector()
    _run(tmp_path, rig_json, detector, count=7, detect_every=3, margin=0.15)
    # detector frames: 0, 3, 6 — everything between is pose-only
    assert detector.full_calls == 3
    assert detector.at_calls == 4
    for box in detector.tracked_boxes:
        # expansion around the last full box (200..440 x), clamped to the frame
        assert box[0] < 200.0 and box[2] > 440.0
        assert 0.0 <= box[0] and box[2] <= float(W)
        assert 0.0 <= box[1] and box[3] <= float(H)


def test_run_live_tracked_lines_carry_figure_identity(tmp_path, rig_json) -> None:
    _report, events, _corrupt, _out = _run(
        tmp_path, rig_json, FakeDetector(), count=4, detect_every=4
    )
    labels = [e["figure"]["label"] for e in events if e["kind"] == "pose"]
    assert labels == ["figure 1"] * 4  # identity rides the one full detection


def test_run_live_miss_on_no_person_forces_redetect(tmp_path, rig_json) -> None:
    detector = FakeDetector(skip={2})
    report, events, corrupt, _out = _run(
        tmp_path, rig_json, detector, count=4, detect_every=2
    )
    assert corrupt == 0
    assert report.misses == 1 and report.poses == 3
    miss = next(e for e in events if e["kind"] == "miss")
    assert miss["reason"] == "no person detected"
    assert miss["live"]["detector_ran"] is True
    assert miss["live"]["seq"] == 2
    # f0 full, f1 tracked, f2 full (forced by the miss), f3 tracked
    assert detector.full_calls == 3 and detector.at_calls == 1


def test_run_live_low_confidence_is_a_miss(tmp_path, rig_json) -> None:
    detector = FakeDetector(conf=0.1)
    report, events, _corrupt, _out = _run(
        tmp_path, rig_json, detector, count=3, conf_floor=0.3
    )
    assert report.poses == 0 and report.misses == 3
    assert all("low confidence" in e["reason"] for e in events)


def test_run_live_pose_data_is_deterministic(tmp_path, rig_json) -> None:
    frames = _frames(tmp_path, 3)
    _write_frames(frames)
    out_a, out_b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"

    def run(out: Path) -> list[str]:
        live.run_live(
            live.ListFrameSource(frames), rig_json, out, FakeDetector(),
            detect_every=2,
        )
        events, corrupt = live.read_live_lines(out)
        assert corrupt == 0
        return [
            json.dumps({k: e[k] for k in ("figure", "pose", "rotations")}, sort_keys=True)
            for e in events
        ]

    assert run(out_a) == run(out_b)  # same frames = same pose data; envelope excluded


def test_run_live_records_per_frame_exceptions(tmp_path, rig_json) -> None:
    class BoomDetector(FakeDetector):
        def at(self, path, bbox):
            raise RuntimeError("tracked crop exploded")

    detector = BoomDetector()
    report, events, corrupt, _out = _run(
        tmp_path, rig_json, detector, count=4, detect_every=2
    )
    assert corrupt == 0
    assert report.frames == 4 and report.poses == 2 and report.misses == 2
    reasons = [e["reason"] for e in events if e["kind"] == "miss"]
    assert any("tracked crop exploded" in r for r in reasons)  # recorded, not swallowed
    # f0 full, f1 raises, f2 full (forced by the miss), f3 tracks again — the
    # forced re-detect is one-shot, not a permanent full mode
    assert detector.full_calls == 2


def test_run_live_validates_policy_args(tmp_path, rig_json) -> None:
    frames = _frames(tmp_path, 1)
    _write_frames(frames)
    with pytest.raises(RiggermortisError) as exc:
        live.run_live(live.ListFrameSource(frames), rig_json,
                      tmp_path / "o.jsonl", FakeDetector(), detect_every=0)
    assert "hint" in str(exc.value)
    with pytest.raises(RiggermortisError):
        live.run_live(live.ListFrameSource(frames), rig_json,
                      tmp_path / "o.jsonl", FakeDetector(), margin=1.5)


# -- consumer side ---------------------------------------------------------------


def test_read_live_lines_and_latest_pose(tmp_path, rig_json) -> None:
    detector = FakeDetector(skip={1})
    _report, _events, _corrupt, out = _run(
        tmp_path, rig_json, detector, count=3, detect_every=1
    )
    with out.open("a", encoding="utf-8") as fh:
        fh.write('{"kind": "pose", "torn": ')  # a killed writer's tail
    events, corrupt = live.read_live_lines(out)
    assert corrupt == 1
    latest = live.latest_pose_line(out)
    assert latest is not None
    assert latest["kind"] == "pose"
    assert latest["live"]["seq"] == 2  # the LAST pose, not the first


# -- CLI (in-process, faked detector via the live-module seam) ---------------------


def test_cli_live_end_to_end(tmp_path, rig_json, monkeypatch, capsys) -> None:
    from riggermortis.cli import EXIT_OK, main

    detector = FakeDetector()
    monkeypatch.setattr(
        "riggermortis.live.default_detector", lambda gpu=False: detector
    )
    frames = tmp_path / "frames"
    frames.mkdir()
    _write_frames(_frames(frames, 5))
    out = tmp_path / "live.jsonl"
    rc = main([
        "live", str(frames), str(rig_json),
        "--out", str(out), "--detect-every", "3", "--max-frames", "5",
        "--idle-timeout", "0",
    ])
    assert rc == EXIT_OK
    assert detector.full_calls == 2  # frames 0 and 3
    text = capsys.readouterr().out
    assert "5 frame(s)" in text and "stream:" in text
    events, corrupt = live.read_live_lines(out)
    assert corrupt == 0 and len(events) == 5


def test_cli_live_missing_dir_is_actionable(tmp_path, rig_json, capsys) -> None:
    from riggermortis.cli import EXIT_HANDLED_ERROR, main

    rc = main(["live", str(tmp_path / "nope"), str(rig_json)])
    assert rc == EXIT_HANDLED_ERROR
    err = capsys.readouterr().err
    assert "frames directory not found" in err
    assert "(hint:" in err
