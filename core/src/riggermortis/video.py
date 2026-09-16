"""Video -> per-frame pose payloads (P2-1): the job container, not the decoder.

D-009 keeps the process boundary: core never spawns anything. Video DECODING
therefore lives in shell glue (``xtask/extract_frames.sh`` — ffmpeg) that
produces a directory of numbered still frames; this module consumes that
directory deterministically:

- ``plan_frames`` — sorted, stride-sampled frame list (same input = same plan);
- ``run_video_job`` — per-frame detect -> solve -> FK -> payload JSON, with a
  ``job.json`` state file written after EVERY frame so long jobs survive
  interruption (``resume=True`` skips already-done frames);
- honest bookkeeping: failed frames are recorded, never swallowed.

Everything is pure stdlib up to the injected ``detect_fn`` (the real one lazy-
imports numpy/onnxruntime exactly like ``rigpose detect``; CI passes fakes).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .canonical_pose import observations_from_keypoints, solve_pose
from .errors import RiggermortisError
from .fk_apply import apply_canonical_pose
from .inference.figures import FigureBoard
from .io import load_rig
from .mapper import map_rig
from .payload import FORMAT as PAYLOAD_FORMAT

#: State file name inside a job directory.
STATE_NAME = "job.json"

FRAME_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


@dataclass
class FrameResult:
    """Outcome of one frame (honest: failures carry their reason)."""

    index: int
    file: str
    payload: str | None  # payload path relative to the job dir, None on failure
    confidence: float
    reliable: bool
    figures: int
    error: str | None = None


@dataclass
class VideoJobReport:
    """Summary of a (possibly resumed) run."""

    source: str
    planned: int
    done_this_run: int
    skipped_resumed: int
    failed: list[FrameResult] = field(default_factory=list)
    payloads_dir: str = ""

    def summary(self) -> str:
        lines = [
            f"video job: {self.planned} frame(s) planned, "
            f"{self.done_this_run} solved this run, {self.skipped_resumed} resumed, "
            f"{len(self.failed)} failed",
            f"payloads: {self.payloads_dir}",
        ]
        for failure in self.failed[:5]:
            lines.append(f"  frame {failure.index}: {failure.error}")
        if len(self.failed) > 5:
            lines.append(f"  … and {len(self.failed) - 5} more failures")
        return "\n".join(lines)


def plan_frames(frames_dir: Path, stride: int = 1, max_frames: int | None = None) -> list[Path]:
    """Deterministic, stride-sampled frame plan from an extracted-frames dir."""
    if stride < 1:
        raise RiggermortisError(
            f"stride must be >= 1, got {stride}",
            hint="stride 1 = every frame, 2 = every second frame, …",
        )
    frames = sorted(
        p for p in frames_dir.iterdir()
        if p.is_file() and p.suffix.lower() in FRAME_SUFFIXES
    )
    frames = frames[::stride]
    if max_frames is not None:
        frames = frames[:max_frames]
    if not frames:
        raise RiggermortisError(
            f"no frames found in {frames_dir}",
            hint="extract frames first: bash xtask/extract_frames.sh <video> <dir> "
                 "(D-009: decode lives in shell glue, core never spawns)",
        )
    return frames


def payload_name(index: int) -> str:
    return f"frame_{index:06d}.json"


def load_state(job_dir: Path) -> dict | None:
    state_path = job_dir / STATE_NAME
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_state(
    job_dir: Path, frames: list[str], stride: int, source: str, rig: str,
    done: dict[int, str], notes: list[str],
) -> None:
    state = {
        "format": 1,
        "source": source,
        "rig": rig,
        "stride": stride,
        "frames": frames,
        "done": {str(k): done[k] for k in sorted(done)},  # JSON keys are strings
        "notes": notes,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (job_dir / STATE_NAME).write_text(
        json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
    )


def _default_detect_fn():
    from .inference.dwpose import detect_keypoints  # noqa: PLC0415 (lazy: [inference])

    return detect_keypoints


def _solve_frame(frame_path: Path, rig, mapping, detect_fn):
    """One frame -> (pose, application, figure_count). Raises on detection loss."""
    detection = detect_fn(str(frame_path))
    board = FigureBoard.from_detection(detection)
    figure = board.largest()
    if figure is None:
        raise RiggermortisError(
            "no person detected",
            hint="the frame is recorded as failed; keep going or drop the frame "
                 "in cleanup (P2-6)",
        )
    pose = solve_pose(observations_from_keypoints(figure.keypoints, figure.confidences))
    application = apply_canonical_pose(rig, mapping, pose)
    return pose, application, figure, len(board.figures)


def run_video_job(
    frames_dir: Path,
    rig_path: Path,
    job_dir: Path,
    stride: int = 1,
    max_frames: int | None = None,
    resume: bool = True,
    detect_fn=None,
    progress=None,
) -> VideoJobReport:
    """Detect -> solve -> FK per planned frame; crash-safe via ``job.json``.

    ``detect_fn``: ``path -> Detection`` (defaults to the real lazy DWPose
    call; tests inject fakes). ``progress``: ``f(done, planned)`` callback for
    frontends. Per-frame payloads land in ``job_dir/payloads/``.
    """
    if detect_fn is None:
        detect_fn = _default_detect_fn()
    frames = plan_frames(frames_dir, stride=stride, max_frames=max_frames)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "payloads").mkdir(exist_ok=True)

    rig = load_rig(rig_path)
    mapping = map_rig(rig)

    done: dict[int, str] = {}
    failed: list[FrameResult] = []
    notes: list[str] = []
    resumed = 0
    planned = len(frames)

    state = load_state(job_dir) if resume else None
    resumable: dict[int, str] = {}
    if state is not None and state.get("frames") == [p.name for p in frames]:
        resumable = {int(k): v for k, v in state.get("done", {}).items()}
    elif state is not None:
        notes.append("state plan mismatch — restarting job from scratch")
        state = None

    for index, frame in enumerate(frames):
        rel_payload = f"payloads/{payload_name(index)}"
        if index in resumable and (job_dir / rel_payload).exists():
            done[index] = rel_payload
            resumed += 1
            continue
        try:
            pose, application, figure, figures = _solve_frame(frame, rig, mapping, detect_fn)
        except Exception as exc:  # noqa: BLE001 — recorded, never swallowed
            reason = str(exc) or exc.__class__.__name__
            failed.append(FrameResult(
                index=index, file=frame.name, payload=None,
                confidence=0.0, reliable=False, figures=0, error=reason,
            ))
            notes.append(f"frame {index} ({frame.name}): {reason}")
            save_state(job_dir, [p.name for p in frames], stride,
                       str(frames_dir), str(rig_path), done, notes)
            continue
        entry = {
            "label": figure.label, "index": figure.index,
            "score": round(figure.score, 4),
            "bbox": [round(v, 2) for v in figure.bbox],
            "pose": pose.to_dict(),
            "rotations": [r.to_dict() for r in application.rotations],
            "skipped": list(application.skipped),
            "notes": list(application.notes),
        }
        meta = {k: entry[k] for k in ("label", "index", "score", "bbox")}
        # Contract-valid v2 (payload.py is the single contract): the v1-shaped
        # top-level mirrors plus a one-entry figures list — the video pipeline
        # always solves exactly the largest figure.
        payload = {
            "format": PAYLOAD_FORMAT,
            "frame": index,
            "file": frame.name,
            "figure": meta,
            "pose": entry["pose"],
            "rotations": entry["rotations"],
            "skipped": entry["skipped"],
            "notes": entry["notes"],
            "figures": [entry],
            "rig": {"name": rig.name, "fingerprint": rig.fingerprint()},
        }
        (job_dir / rel_payload).write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        done[index] = rel_payload
        if math.floor(index / max(planned, 1) * 20) != math.floor(
                (index - 1) / max(planned, 1) * 20) and progress:
            progress(index + 1, planned)
        save_state(job_dir, [p.name for p in frames], stride,
                   str(frames_dir), str(rig_path), done, notes)

    return VideoJobReport(
        source=str(frames_dir),
        planned=planned,
        done_this_run=planned - resumed - len(failed),
        skipped_resumed=resumed,
        failed=failed,
        payloads_dir=str(job_dir / "payloads"),
    )
