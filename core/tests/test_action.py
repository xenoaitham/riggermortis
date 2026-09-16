"""P2-3 tests: canonical action model — job sampling, conditioning, honesty.

CI-safe: payloads are hand-written or produced with a faked detector (no
models, no numpy — stdlib only).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pytest  # noqa: E402

from riggermortis import video  # noqa: E402
from riggermortis.action import (  # noqa: E402
    action_from_poses,
    condition_action,
    load_action,
)
from riggermortis.canonical_pose import CanonicalPose  # noqa: E402
from riggermortis.errors import RiggermortisError  # noqa: E402
from riggermortis.inference.poses import KEYPOINT_COUNT, Detection, Figure  # noqa: E402
from riggermortis.payload import figure_entries  # noqa: E402
from rigs import rigify_rig  # noqa: E402


def _pose(z_hips: float = 0.0, scale: float = 30.0) -> dict[str, object]:
    """A small but valid CanonicalPose.to_dict() — roles the FK chain needs."""
    positions = {
        "hips": (0.0, 0.0, z_hips),
        "spine": (0.0, 0.02, z_hips + 0.17),
        "chest": (0.0, 0.04, z_hips + 0.34),
        "neck": (0.0, 0.06, z_hips + 0.45),
        "head": (0.0, 0.08, z_hips + 0.62),
        "upper_arm.L": (-0.18, 0.06, z_hips + 0.42),
        "upper_arm.R": (0.18, 0.06, z_hips + 0.42),
        "forearm.L": (-0.22, 0.04, z_hips + 0.24),
        "forearm.R": (0.22, 0.04, z_hips + 0.24),
        "upper_leg.L": (-0.09, 0.0, z_hips),
        "upper_leg.R": (0.09, 0.0, z_hips),
        "lower_leg.L": (-0.10, -0.02, z_hips - 0.42),
        "lower_leg.R": (0.10, -0.02, z_hips - 0.42),
        "foot.L": (-0.11, -0.04, z_hips - 0.90),
        "foot.R": (0.11, -0.04, z_hips - 0.90),
    }
    return {
        "positions": {r: list(p) for r, p in sorted(positions.items())},
        "flips": {"forearm.L": -1, "forearm.R": -1, "lower_leg.L": 1, "lower_leg.R": 1},
        "confidence": 0.8,
        "reliable": True,
        "scale": scale,
        "anchor": "hips",
        "notes": [],
        "joint_confidence": {"foot.L": 0.9, "foot.R": 0.9},
    }


def _video_payload(index: int, pose_dict: dict[str, object]) -> dict[str, object]:
    """Contract-valid v2 payload in the exact shape video.py writes."""
    entry = {
        "label": "figure 0",
        "index": 0,
        "score": 0.9,
        "bbox": [0.0, 0.0, 10.0, 10.0],
        "pose": pose_dict,
        "rotations": [{
            "bone": "spine", "role": "spine", "axis": [0.0, 0.0, 1.0],
            "angle_rad": 0.01 * index, "angle_deg": 0.573 * index, "depth": 1,
        }],
        "skipped": [],
        "notes": [],
    }
    return {
        "format": 2,
        "frame": index,
        "file": f"frame_{index:06d}.png",
        "figure": {k: entry[k] for k in ("label", "index", "score", "bbox")},
        "pose": entry["pose"],
        "rotations": entry["rotations"],
        "skipped": [],
        "notes": [],
        "figures": [entry],
        "rig": {"name": "rig", "fingerprint": "deadbeef"},
    }


def _fake_job(tmp_path: Path, planned: int, done: set[int]) -> Path:
    """A job dir with job.json + payloads for the done indices only."""
    job = tmp_path / "job"
    (job / "payloads").mkdir(parents=True)
    for i in range(planned):
        if i in done:
            p = job / "payloads" / f"frame_{i:06d}.json"
            p.write_text(
                json.dumps(_video_payload(i, _pose(z_hips=0.01 * i))),
                encoding="utf-8",
            )
    state = {
        "format": 1,
        "source": "frames",
        "rig": "rig.json",
        "stride": 1,
        "frames": [f"frame_{i:06d}.png" for i in range(planned)],
        "done": {str(i): f"payloads/frame_{i:06d}.json" for i in sorted(done)},
        "notes": [f"frame {j} (frame_{j:06d}.png): no person detected"
                  for j in range(planned) if j not in done],
        "updated": "2026-09-16T00:00:00Z",
    }
    (job / "job.json").write_text(json.dumps(state), encoding="utf-8")
    return job


# -- sampling -----------------------------------------------------------------

def test_load_action_samples_sorted_with_failure_ledger(tmp_path: Path) -> None:
    job = _fake_job(tmp_path, planned=4, done={0, 1, 3})
    action = load_action(job)
    assert action.frame_indices == [0, 1, 3]
    assert action.failed == [2]
    assert action.rig_fingerprint == "deadbeef"
    assert any("failed and are NOT in the action" in n for n in action.notes)
    assert any("no person" in n for n in action.notes)  # job notes carried
    # poses actually parsed through the contract: per-frame hip z varies
    assert [af.pose.positions["hips"][2] for af in action.frames] == [0.0, 0.01, 0.03]


def test_load_action_without_state_is_actionable(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(RiggermortisError) as exc:
        load_action(empty)
    assert "pose-video" in str(exc.value)


def test_load_action_missing_payload_file_is_honest(tmp_path: Path) -> None:
    job = _fake_job(tmp_path, planned=2, done={0, 1})
    (job / "payloads" / "frame_000001.json").unlink()
    action = load_action(job)
    assert action.frame_indices == [0]
    assert action.failed == [1]
    assert any("file is gone" in n for n in action.notes)


def test_video_writer_roundtrips_through_the_contract(tmp_path: Path) -> None:
    """The P2-1 writer's payload must parse through payload.py (D-009)."""
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(2):
        (frames / f"frame_{i:06d}.png").write_bytes(b"\x89PNG fake")
    rig_json = tmp_path / "rig.json"
    rigify_rig().to_json(rig_json)

    def _detect(image_path: str, providers=None):  # noqa: ANN001
        kps = [(320.0, 480.0)] * KEYPOINT_COUNT
        fig = Figure(
            index=0, bbox=(200.0, 180.0, 440.0, 820.0), score=0.9,
            keypoints=kps, confidences=[0.85] * KEYPOINT_COUNT,
        )
        return Detection(width=640, height=960, figures=[fig])

    job = tmp_path / "job"
    video.run_video_job(frames, rig_json, job, detect_fn=_detect)
    payload = json.loads(
        (job / "payloads" / "frame_000000.json").read_text(encoding="utf-8")
    )
    entries = figure_entries(payload)  # raises if the writer broke the contract
    assert len(entries) == 1
    action = load_action(job)
    assert action.frame_indices == [0, 1]
    assert action.frames[0].pose.reliable


# -- conditioning --------------------------------------------------------------

def _linear_action(n: int = 21) -> object:
    """A straight-line ramp in every channel — perfectly reducible."""
    frames = []
    for i in range(n):
        pose_dict = _pose(z_hips=0.01 * i)
        frames.append((i, CanonicalPose.from_dict(pose_dict)))
    return action_from_poses(frames)


def _jitter_action(n: int = 21) -> object:
    """Same ramp but foot.R carries deterministic alternating jitter."""
    frames = []
    for i in range(n):
        pose_dict = _pose(z_hips=0.01 * i)
        jitter = 0.05 * (1 if i % 2 == 0 else -1)
        pose_dict["positions"]["foot.R"][2] += jitter  # type: ignore[index]
        frames.append((i, CanonicalPose.from_dict(pose_dict)))
    return action_from_poses(frames)


def test_condition_action_reduces_straight_lines_keeps_endpoints() -> None:
    action = _linear_action()
    conditioned = condition_action(action, min_cutoff=None, tolerance=0.02)
    assert conditioned.frame_indices == [0, len(action.frames) - 1]
    assert any("keyframe reduction" in n for n in conditioned.notes)
    assert conditioned.failed == action.failed  # ledger untouched
    # tolerance 0 keeps every frame
    everything = condition_action(action, min_cutoff=None, tolerance=0.0)
    assert everything.frame_indices == action.frame_indices


def test_condition_action_smoothing_damps_jitter_without_touching_input() -> None:
    action = _jitter_action()
    original = copy.deepcopy(action.frames[1].pose.positions)
    smoothed = condition_action(action, min_cutoff=1.0, tolerance=None)
    z_in = [af.pose.positions["foot.R"][2] for af in action.frames]
    z_out = [af.pose.positions["foot.R"][2] for af in smoothed.frames]
    def _rng(vals: list[float]) -> float:
        return max(vals) - min(vals)
    assert _rng(z_out) < _rng(z_in)  # alternating jitter is damped
    assert action.frames[1].pose.positions == original  # input untouched
    assert any("smoothing" in n for n in smoothed.notes)


def test_condition_action_disabled_is_identity() -> None:
    action = _jitter_action()
    same = condition_action(action, min_cutoff=None, tolerance=None)
    assert [af.pose.positions for af in same.frames] == \
        [af.pose.positions for af in action.frames]
    assert same.notes == action.notes  # no conditioning notes appended


def test_condition_action_is_deterministic() -> None:
    action = _jitter_action()
    a = condition_action(action, min_cutoff=1.0, tolerance=0.02)
    b = condition_action(action, min_cutoff=1.0, tolerance=0.02)
    assert a == b


def test_action_from_poses_sorts_by_frame() -> None:
    poses = [(2, CanonicalPose.from_dict(_pose())), (0, CanonicalPose.from_dict(_pose())),
             (1, CanonicalPose.from_dict(_pose()))]
    action = action_from_poses(poses)
    assert action.frame_indices == [0, 1, 2]
