"""P2-1 tests: video job container — planning, per-frame payloads, resume."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis import video  # noqa: E402
from riggermortis.errors import RiggermortisError  # noqa: E402
from riggermortis.inference.poses import KEYPOINT_COUNT, Detection, Figure  # noqa: E402
from rigs import rigify_rig  # noqa: E402


def _standing_keypoints(cx: float, cy: float, scale_px: float) -> list[tuple[float, float]]:
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


def _frames_dir(tmp_path: Path, count: int, personless: set[int] | None = None) -> Path:
    personless = personless or set()
    d = tmp_path / "frames"
    d.mkdir()
    for i in range(count):
        (d / f"frame_{i:06d}.png").write_bytes(b"\x89PNG fake")
    return d


def _detect_factory(skip: set[int]):
    """Deterministic fake detection; frames in `skip` detect no person."""

    def _detect(image_path: str, providers=None):  # noqa: ANN001
        name = Path(image_path).stem
        index = int(name.split("_")[1])
        if index in skip:
            return Detection(width=640, height=960, figures=[])
        # vary the figure size so the solved canonical pose differs per frame
        # (the solver is translation-invariant, so a pure walk would cancel out)
        kps = _standing_keypoints(320.0, 480.0, 100.0 + index)
        fig = Figure(
            index=0, bbox=(200.0, 180.0, 440.0, 820.0), score=0.9,
            keypoints=kps, confidences=[0.85] * KEYPOINT_COUNT,
        )
        return Detection(width=640, height=960, figures=[fig])

    return _detect


@pytest.fixture()
def rig_json(tmp_path: Path) -> Path:
    path = tmp_path / "rig.json"
    rigify_rig().to_json(path)
    return path


def test_plan_frames_is_sorted_and_strided(tmp_path: Path) -> None:
    d = _frames_dir(tmp_path, 10)
    plan = video.plan_frames(d, stride=3)
    assert [p.name for p in plan] == [f"frame_{i:06d}.png" for i in (0, 3, 6, 9)]
    assert video.plan_frames(d) == video.plan_frames(d)  # deterministic


def test_plan_frames_empty_is_actionable(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RiggermortisError) as exc:
        video.plan_frames(empty)
    assert "extract_frames.sh" in str(exc.value)  # points at the shell glue


def test_video_job_writes_per_frame_payloads_and_state(tmp_path: Path, rig_json: Path) -> None:
    d = _frames_dir(tmp_path, 5)
    job = tmp_path / "job"
    progress: list[tuple[int, int]] = []
    report = video.run_video_job(
        d, rig_json, job, detect_fn=_detect_factory(set()),
        progress=lambda done, total: progress.append((done, total)),
    )
    assert report.planned == 5 and report.done_this_run == 5 and not report.failed
    assert progress, "progress callback must fire"
    state = json.loads((job / "job.json").read_text(encoding="utf-8"))
    assert len(state["done"]) == 5
    first = json.loads((job / "payloads" / "frame_000000.json").read_text(encoding="utf-8"))
    assert first["format"] == 2 and first["frame"] == 0 and first["rotations"]
    # the fake varies the figure per frame, so poses differ
    fourth = json.loads((job / "payloads" / "frame_000003.json").read_text(encoding="utf-8"))
    assert fourth["pose"]["positions"] != first["pose"]["positions"]


def test_video_job_records_failures_without_dying(tmp_path: Path, rig_json: Path) -> None:
    d = _frames_dir(tmp_path, 4, personless={2})
    job = tmp_path / "job"
    report = video.run_video_job(d, rig_json, job, detect_fn=_detect_factory({2}))
    assert report.planned == 4 and len(report.failed) == 1
    assert report.failed[0].index == 2 and "no person" in (report.failed[0].error or "")
    assert not (job / "payloads" / "frame_000002.json").exists()
    state = json.loads((job / "job.json").read_text(encoding="utf-8"))
    assert "2" not in state["done"] and any("frame 2" in n for n in state["notes"])


def test_video_job_resume_skips_done_frames(tmp_path: Path, rig_json: Path) -> None:
    d = _frames_dir(tmp_path, 4)
    job = tmp_path / "job"
    calls = {"n": 0}

    def counting_detect(image_path: str, providers=None):  # noqa: ANN001
        calls["n"] += 1
        return _detect_factory(set())(image_path)

    video.run_video_job(d, rig_json, job, detect_fn=counting_detect, resume=False)
    assert calls["n"] == 4
    report = video.run_video_job(d, rig_json, job, detect_fn=counting_detect, resume=True)
    assert calls["n"] == 4  # nothing re-detected
    assert report.skipped_resumed == 4 and report.done_this_run == 0


def test_video_job_resume_restarts_on_plan_mismatch(tmp_path: Path, rig_json: Path) -> None:
    d = _frames_dir(tmp_path, 4)
    job = tmp_path / "job"
    video.run_video_job(d, rig_json, job, detect_fn=_detect_factory(set()), resume=False)
    # the plan changes (new frame extracted) -> state no longer matches
    (d / "frame_000004.png").write_bytes(b"\x89PNG fake")
    report = video.run_video_job(d, rig_json, job, detect_fn=_detect_factory(set()), resume=True)
    assert report.planned == 5 and report.skipped_resumed == 0
    assert report.done_this_run == 5  # re-ran everything under the new plan


def test_cli_pose_video_end_to_end_with_fake_detect(
    tmp_path: Path, rig_json: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import riggermortis.inference.dwpose as dwpose
    from riggermortis.cli import EXIT_OK, main

    monkeypatch.setattr(dwpose, "detect_keypoints", _detect_factory({1}))
    d = _frames_dir(tmp_path, 3)
    job = tmp_path / "job"
    code = main([
        "pose-video", str(d), str(rig_json),
        "--out", str(job), "--stride", "1",
    ])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "2 solved this run" in out and "1 failed" in out
    assert (job / "payloads" / "frame_000000.json").exists()
