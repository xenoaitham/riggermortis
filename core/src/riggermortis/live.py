"""Live mode (P5-1): the realtime pose side-process contract.

D-009 keeps the process boundary, and live mode keeps it twice over:

- The SIDE PROCESS is ``rigpose live`` — spawned by the user's shell or shell
  glue (``xtask/live_capture.sh``), never by a ``.py`` file. It owns the model
  sessions and a frame source, runs detect -> solve -> FK per frame, and
  writes ONE JSON LINE per processed frame into a stream file.
- The CONSUMER (P5-2's add-on driver, MCP tools, tests) reads the stream
  through :func:`read_live_lines` / :func:`latest_pose_line`. A ``kind=pose``
  line embeds the same payload-v2 shape the offline pipeline writes (one
  solved figure, D-009), so the add-on's own apply path consumes it unchanged.

Frame sources are pure stdlib and path-level: the frame PRODUCER is shell glue
(``xtask/extract_frames.sh`` for recorded video, ``xtask/live_capture.sh`` for
a capture device) — core never spawns, never opens a device, never opens a
socket (D-003). Determinism: the same frames through the same loop produce the
same pose data; the ``live`` envelope timing fields are MEASUREMENTS and are
excluded from determinism assertions (documented in docs/LIVE.md).
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .canonical_pose import observations_from_keypoints, solve_pose
from .errors import RiggermortisError
from .fk_apply import PoseApplication, apply_canonical_pose
from .inference.figures import FigureBoard
from .inference.poses import BODY_KEYPOINT_COUNT, Detection, Figure
from .io import load_rig
from .mapper import RigMapping, map_rig
from .payload import FORMAT as PAYLOAD_FORMAT
from .types import RigData

#: Stream file suffix (one JSON object per line, no trailing comma structure).
STREAM_SUFFIX = ".jsonl"

#: Frame files accepted from a source (same set as the video pipeline).
FRAME_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

#: Re-run the detector every N-th frame (1 = every frame = the ``full`` regime;
#: >1 = the ``tracked`` regime — pose-only crops between detector runs).
DEFAULT_DETECT_EVERY = 1

#: Crop expansion around the previous box between detector runs (fraction of
#: box width/height per side, clamped to the frame). Order-of-magnitude
#: default chosen before any measurement, NOT fixture-fitted (D-008).
DEFAULT_MARGIN = 0.15

#: A frame whose mean BODY-keypoint confidence falls under the floor is a miss
#: (no pose data on the line); tracked mode forces a detector re-run next.
DEFAULT_CONF_FLOOR = 0.3

#: Default seconds without a new frame before a directory source stops.
DEFAULT_IDLE_TIMEOUT = 10.0

#: Default seconds without a NEW stream line before the consumer reports the
#: stream stale (P5-2). Order-of-magnitude default chosen before any
#: measurement, NOT fixture-fitted (D-008) — roughly twenty tracked frames'
#: worth of silence at the S17 p50.
DEFAULT_STALE_AFTER = 2.0


# -- frame sources ---------------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    """One frame from a source. ``t_capture`` is wall-clock epoch seconds when
    the source knows it (file mtime) — a MEASUREMENT, never pose data."""

    seq: int
    path: Path
    t_capture: float | None


class FrameSource(Protocol):
    """Yields frames exactly once, in a deterministic order; ``None`` = stop."""

    def next_frame(self) -> Frame | None: ...


class ListFrameSource:
    """Explicit frame list — replay, tests, the probe. Deterministic."""

    def __init__(self, paths: Iterable[Path]) -> None:
        self._paths = sorted(paths, key=lambda p: p.name)  # keyed, stable for dupes
        self._next = 0

    @property
    def label(self) -> str:
        return "<list>"

    def next_frame(self) -> Frame | None:
        if self._next >= len(self._paths):
            return None
        path = self._paths[self._next]
        self._next += 1
        return Frame(seq=self._next - 1, path=path, t_capture=None)


class DirectoryFrameSource:
    """Watches a frames directory written by shell glue and yields each new
    frame exactly once, in filename order. Pure stdlib polling — no devices,
    no sockets (the capture device lives behind the glue script). Stops after
    ``idle_timeout`` seconds without a new frame (None = wait forever)."""

    def __init__(
        self,
        frames_dir: Path,
        *,
        poll_seconds: float = 0.05,
        idle_timeout: float | None = DEFAULT_IDLE_TIMEOUT,
        suffixes: tuple[str, ...] = FRAME_SUFFIXES,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if poll_seconds < 0:
            raise RiggermortisError(
                f"poll_seconds must be >= 0, got {poll_seconds}",
                hint="0 polls as fast as the loop allows (tests); 0.05 is the live default",
            )
        self._dir = Path(frames_dir)
        self._poll = poll_seconds
        self._idle = idle_timeout
        self._suffixes = tuple(s.lower() for s in suffixes)
        self._sleep = sleep
        self._seen: set[str] = set()
        self._pending: list[Path] = []
        self._seq = 0

    @property
    def label(self) -> str:
        return str(self._dir)

    def _scan(self) -> None:
        if not self._dir.is_dir():
            return
        found = [
            p for p in self._dir.iterdir()
            if p.is_file() and p.suffix.lower() in self._suffixes and p.name not in self._seen
        ]
        self._pending.extend(sorted(found, key=lambda p: p.name))  # keyed

    def next_frame(self) -> Frame | None:
        deadline = None if self._idle is None else time.monotonic() + self._idle
        while True:
            if not self._pending:
                self._scan()
            if self._pending:
                path = self._pending.pop(0)
                self._seen.add(path.name)
                self._seq += 1
                try:
                    t_capture = float(path.stat().st_mtime)
                except OSError:
                    t_capture = None  # frame vanished between scan and stat
                return Frame(seq=self._seq - 1, path=path, t_capture=t_capture)
            if deadline is not None and time.monotonic() >= deadline:
                return None
            self._sleep(self._poll)


# -- detection policy ------------------------------------------------------------


def expand_bbox(
    bbox: tuple[float, float, float, float],
    margin: float,
    width: float,
    height: float,
) -> tuple[float, float, float, float]:
    """Expand an xyxy box by ``margin`` of its size per side, clamped to the
    frame. Pure math — the tracked regime's only spatial update between
    detector runs (no optical flow, no state beyond the box)."""
    x1, y1, x2, y2 = (float(v) for v in bbox)
    dx = (x2 - x1) * margin
    dy = (y2 - y1) * margin
    return (
        max(0.0, x1 - dx),
        max(0.0, y1 - dy),
        min(float(width), x2 + dx),
        min(float(height), y2 + dy),
    )


def mean_body_confidence(figure: Figure) -> float:
    """Mean confidence over the 17 COCO body keypoints — the miss-floor signal
    (face/hand keypoints are noisier and not load-bearing for the solve)."""
    vals = figure.confidences[:BODY_KEYPOINT_COUNT]
    return sum(vals) / len(vals) if vals else 0.0


class PoseDetector(Protocol):
    """The two detection paths the loop needs. ``full`` runs detector + pose;
    ``at`` runs pose-only at a known box (tracked regime)."""

    def full(self, path: Path) -> Detection: ...

    def at(
        self, path: Path, bbox: tuple[float, float, float, float]
    ) -> Figure: ...


class DwposeDetector:
    """Real detector over the pinned DWPose models. Lazy imports — numpy/
    onnxruntime enter only via the ``[inference]`` extra, never at module
    import, exactly like every other inference surface in core."""

    def __init__(
        self,
        *,
        providers: list[str] | None = None,
        root: Path | None = None,
    ) -> None:
        self._providers = providers
        self._root = root
        self._loaded: object | None = None

    def _sessions(self) -> object:
        if self._loaded is None:
            from .inference.dwpose import load_sessions  # noqa: PLC0415 (lazy)

            self._loaded = load_sessions(providers=self._providers, root=self._root)
        return self._loaded

    def full(self, path: Path) -> Detection:
        from .inference.dwpose import detect_keypoints  # noqa: PLC0415 (lazy)

        return detect_keypoints(
            str(path), providers=self._providers, sessions=self._sessions()
        )

    def at(self, path: Path, bbox: tuple[float, float, float, float]) -> Figure:
        from .inference.dwpose import estimate_keypoints_at  # noqa: PLC0415 (lazy)

        return estimate_keypoints_at(
            str(path), bbox, providers=self._providers, sessions=self._sessions()
        )


def default_detector(gpu: bool = False) -> DwposeDetector:
    """CPU by default; GPU is opt-in and never initialized silently."""
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"] if gpu else None
    )
    return DwposeDetector(providers=providers)


# -- stream lines ------------------------------------------------------------------


def _envelope(
    frame: Frame,
    t_emit_wall: float,
    total_ms: float,
    *,
    detector_ran: bool,
    detect_every: int,
    detect_ms: float,
    solve_ms: float,
    fk_ms: float,
) -> dict[str, object]:
    return {
        "seq": frame.seq,
        "t_emit_wall": round(t_emit_wall, 3),
        "t_capture_wall": (
            round(frame.t_capture, 3) if frame.t_capture is not None else None
        ),
        "age_ms": (
            round((t_emit_wall - frame.t_capture) * 1000.0, 1)
            if frame.t_capture is not None
            else None
        ),
        "detect_every": detect_every,
        "detector_ran": detector_ran,
        "detect_ms": round(detect_ms, 1),
        "solve_ms": round(solve_ms, 1),
        "fk_ms": round(fk_ms, 1),
        "total_ms": round(total_ms, 1),
    }


def _pose_line(
    frame: Frame,
    rig: RigData,
    mapping: RigMapping,
    figure: Figure,
    *,
    t_emit_wall: float,
    t_start: float,
    detector_ran: bool,
    detect_every: int,
    detect_ms: float,
) -> dict[str, object]:
    t0 = time.perf_counter()
    pose = solve_pose(observations_from_keypoints(figure.keypoints, figure.confidences))
    t1 = time.perf_counter()
    application: PoseApplication = apply_canonical_pose(rig, mapping, pose)
    t2 = time.perf_counter()
    total_ms = (t2 - t_start) * 1000.0  # the whole frame: detect + solve + fk
    entry = {
        "label": figure.label,
        "index": figure.index,
        "score": round(figure.score, 4),
        "bbox": [round(v, 2) for v in figure.bbox],
        "pose": pose.to_dict(),
        "rotations": [r.to_dict() for r in application.rotations],
        "skipped": list(application.skipped),
        "notes": list(application.notes),
    }
    meta = {k: entry[k] for k in ("label", "index", "score", "bbox")}
    return {
        "kind": "pose",
        "live": _envelope(
            frame,
            t_emit_wall,
            total_ms,
            detector_ran=detector_ran,
            detect_every=detect_every,
            detect_ms=detect_ms,
            solve_ms=(t1 - t0) * 1000.0,
            fk_ms=(t2 - t1) * 1000.0,
        ),
        "format": PAYLOAD_FORMAT,
        "frame": frame.seq,
        "file": frame.path.name,
        "figure": meta,
        "pose": entry["pose"],
        "rotations": entry["rotations"],
        "skipped": entry["skipped"],
        "notes": entry["notes"],
        "figures": [entry],
        "rig": {"name": rig.name, "fingerprint": rig.fingerprint()},
    }


def _miss_line(
    frame: Frame,
    *,
    t_emit_wall: float,
    total_ms: float,
    detector_ran: bool,
    detect_every: int,
    detect_ms: float,
    reason: str,
) -> dict[str, object]:
    return {
        "kind": "miss",
        "live": _envelope(
            frame,
            t_emit_wall,
            total_ms,
            detector_ran=detector_ran,
            detect_every=detect_every,
            detect_ms=detect_ms,
            solve_ms=0.0,
            fk_ms=0.0,
        ),
        "frame": frame.seq,
        "file": frame.path.name,
        "reason": reason,
    }


# -- the loop ------------------------------------------------------------------


@dataclass
class LiveReport:
    """Summary of one live run (the CLI prints this; tests assert on it)."""

    source: str
    frames: int
    poses: int
    misses: int
    elapsed_s: float
    pose_ms: list[float] = field(default_factory=list)
    out_path: str = ""

    def latency(self) -> tuple[float, float, float]:
        """(mean, p50, p95) of per-pose-frame total_ms; (0, 0, 0) with no poses."""
        if not self.pose_ms:
            return (0.0, 0.0, 0.0)
        ordered = sorted(self.pose_ms)  # keyed
        n = len(ordered)

        def p(fraction: float) -> float:
            rank = max(1, min(n, round(fraction * n)))
            return ordered[rank - 1]

        return (sum(ordered) / n, p(0.50), p(0.95))

    def summary(self) -> str:
        mean_ms, p50_ms, p95_ms = self.latency()
        lines = [
            f"live: {self.frames} frame(s), {self.poses} pose line(s), "
            f"{self.misses} miss line(s) in {self.elapsed_s:.1f}s",
            f"pose latency ms: mean {mean_ms:.1f} / p50 {p50_ms:.1f} / p95 {p95_ms:.1f}",
            f"stream: {self.out_path}",
        ]
        if self.poses == 0:
            lines.append(
                "(hint: no pose lines — check the frames directory has person "
                "frames, or raise --conf-floor tolerance)"
            )
        return "\n".join(lines)


def run_live(
    source: FrameSource,
    rig_path: Path,
    out_path: Path,
    detector: PoseDetector,
    *,
    detect_every: int = DEFAULT_DETECT_EVERY,
    margin: float = DEFAULT_MARGIN,
    conf_floor: float = DEFAULT_CONF_FLOOR,
    max_frames: int | None = None,
    on_line: Callable[[dict[str, object]], None] | None = None,
) -> LiveReport:
    """The side-process loop: frame -> detect -> solve -> FK -> one JSON line.

    Policy (documented in docs/LIVE.md): the detector runs on the first frame,
    after any miss, and every ``detect_every``-th frame otherwise; between
    detector runs the pose stage crops the previous box expanded by ``margin``.
    A frame whose largest figure's mean body confidence is under ``conf_floor``
    emits a ``kind=miss`` line (no pose data) and forces a detector re-run.
    Per-frame exceptions become miss lines with their reason — recorded, never
    swallowed; the loop itself only stops on source exhaustion, ``max_frames``,
    or a directory idle timeout.
    """
    if detect_every < 1:
        raise RiggermortisError(
            f"detect_every must be >= 1, got {detect_every}",
            hint="1 = detector every frame (the `full` regime), 5 = pose-only "
                 "crops between detector runs (the `tracked` regime)",
        )
    if not 0.0 <= margin <= 1.0:
        raise RiggermortisError(
            f"margin must be in [0, 1], got {margin}",
            hint="margin is the per-side crop expansion as a fraction of the box",
        )
    if not 0.0 <= conf_floor <= 1.0:
        raise RiggermortisError(
            f"conf_floor must be in [0, 1], got {conf_floor}",
            hint="mean body confidence under the floor marks a frame a miss",
        )

    rig = load_rig(rig_path)
    mapping = map_rig(rig)
    out_path = Path(out_path)
    if out_path.parent != Path(""):
        out_path.parent.mkdir(parents=True, exist_ok=True)

    report = LiveReport(source=source.label, frames=0, poses=0,
                        misses=0, elapsed_s=0.0, out_path=str(out_path))
    prev_bbox: tuple[float, float, float, float] | None = None
    prev_label = ""
    prev_index = 0
    frame_w = frame_h = 0.0
    since_detect = detect_every  # forces the first-frame detection
    must_detect = True
    started = time.perf_counter()

    with out_path.open("w", encoding="utf-8") as fh:
        while max_frames is None or report.frames < max_frames:
            frame = source.next_frame()
            if frame is None:
                break
            report.frames += 1
            t_emit_wall = time.time()
            t_start = time.perf_counter()
            detect_ms = 0.0
            detector_ran = (
                must_detect or prev_bbox is None or since_detect >= detect_every - 1
            )
            try:
                if detector_ran:
                    t_det = time.perf_counter()
                    detection = detector.full(frame.path)
                    detect_ms = (time.perf_counter() - t_det) * 1000.0
                    board = FigureBoard.from_detection(detection)
                    figure = board.largest()
                    since_detect = 0
                    if figure is None:
                        prev_bbox = None
                        must_detect = True
                        line = _miss_line(
                            frame, t_emit_wall=t_emit_wall,
                            total_ms=(time.perf_counter() - t_start) * 1000.0,
                            detector_ran=True, detect_every=detect_every,
                            detect_ms=detect_ms,
                            reason="no person detected",
                        )
                    else:
                        prev_bbox = figure.bbox
                        prev_label = figure.label
                        prev_index = figure.index
                        frame_w, frame_h = float(detection.width), float(detection.height)
                        line = _pose_or_low_conf_line(
                            frame, rig, mapping, figure,
                            t_emit_wall=t_emit_wall, detector_ran=True,
                            detect_every=detect_every, detect_ms=detect_ms,
                            t_start=t_start, conf_floor=conf_floor,
                        )
                        must_detect = line["kind"] == "miss"
                else:
                    since_detect += 1
                    assert prev_bbox is not None  # detector_ran covers this
                    box = expand_bbox(prev_bbox, margin, frame_w, frame_h)
                    t_det = time.perf_counter()
                    figure = detector.at(frame.path, box)
                    detect_ms = (time.perf_counter() - t_det) * 1000.0
                    # figure identity rides the last FULL detection: a tracked
                    # figure is the same person the detector last named
                    # (estimate_keypoints_at cannot know labels).
                    figure.label = prev_label
                    figure.index = prev_index
                    line = _pose_or_low_conf_line(
                        frame, rig, mapping, figure,
                        t_emit_wall=t_emit_wall, detector_ran=False,
                        detect_every=detect_every, detect_ms=detect_ms,
                        t_start=t_start, conf_floor=conf_floor,
                    )
                    must_detect = line["kind"] == "miss"
            except Exception as exc:  # noqa: BLE001 — recorded as a miss line
                reason = str(exc) or exc.__class__.__name__
                line = _miss_line(
                    frame, t_emit_wall=t_emit_wall,
                    total_ms=(time.perf_counter() - t_start) * 1000.0,
                    detector_ran=detector_ran, detect_every=detect_every,
                    detect_ms=detect_ms,
                    reason=reason,
                )
                must_detect = True
            fh.write(json.dumps(line, sort_keys=True) + "\n")
            fh.flush()  # consumers tail the file line-by-line
            if on_line is not None:
                on_line(line)
            if line["kind"] == "pose":
                report.poses += 1
                report.pose_ms.append(float(line["live"]["total_ms"]))  # type: ignore[index]
            else:
                report.misses += 1

    report.elapsed_s = time.perf_counter() - started
    return report


def _pose_or_low_conf_line(
    frame: Frame,
    rig: RigData,
    mapping: RigMapping,
    figure: Figure,
    *,
    t_emit_wall: float,
    detector_ran: bool,
    detect_every: int,
    detect_ms: float,
    t_start: float,
    conf_floor: float,
) -> dict[str, object]:
    body_conf = mean_body_confidence(figure)
    if body_conf < conf_floor:
        return _miss_line(
            frame, t_emit_wall=t_emit_wall,
            total_ms=(time.perf_counter() - t_start) * 1000.0,
            detector_ran=detector_ran, detect_every=detect_every,
            detect_ms=detect_ms,
            reason=f"low confidence: mean body {body_conf:.2f} < floor {conf_floor:.2f}",
        )
    return _pose_line(
        frame, rig, mapping, figure,
        t_emit_wall=t_emit_wall, t_start=t_start, detector_ran=detector_ran,
        detect_every=detect_every, detect_ms=detect_ms,
    )


# -- consumer side (P5-2 reads through here too) -----------------------------------


def read_live_lines(path: Path) -> tuple[list[dict[str, object]], int]:
    """Parse a live stream file; returns ``(events, corrupt_count)``.

    A corrupt line is normal ONLY as a torn final line (the writer was killed
    mid-write); more than one, or corruption mid-file, is a real problem the
    caller must surface.
    """
    events: list[dict[str, object]] = []
    corrupt = 0
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            corrupt += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            corrupt += 1
    return events, corrupt


def latest_pose_line(path: Path) -> dict[str, object] | None:
    """The most recent ``kind=pose`` event — the line P5-2's driver applies.
    Tolerates a torn tail (see :func:`read_live_lines`)."""
    events, _corrupt = read_live_lines(path)
    for event in reversed(events):
        if event.get("kind") == "pose":
            return event
    return None


# -- incremental consumer (P5-2) ----------------------------------------------------
#
# latest_pose_line re-reads the whole file — O(file) per tick is wrong at
# 10–30 lines/s × ~20–50 KB lines over a long puppeteering session. The
# design lives in docs/LIVE.md (P5-2 section); the two classes here are the
# whole contract: LiveTail owns byte-offset state, LiveConsumer owns the
# latest-wins / miss-keeps-pose / staleness policy. Both are pure stdlib and
# CI-tested with faked streams; the Blender add-on is a thin adapter.


class LiveTail:
    """Incremental reader over a live stream file.

    ``poll()`` returns the COMPLETE, well-formed events appended since the
    last call. A torn final line is never consumed — the offset stays at its
    start until the writer finishes the line (then it parses exactly once).
    A producer restart (truncating reopen) is detected two ways: a file
    smaller than the remembered offset, or — for a regrown file — the byte
    before the remembered offset not being a newline (a line-oriented stream
    can only resume at a line boundary). Either resets the tail to the new
    file's start; replayed lines are the CONSUMER's duplicate problem, not
    the tail's. A missing file simply polls empty. Corrupt COMPLETE lines
    increment ``corrupt`` — a torn line can only ever be the final one, so
    mid-stream corruption is a real problem the caller must surface.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._offset = 0
        self.corrupt = 0

    @property
    def path(self) -> Path:
        return self._path

    def poll(self) -> list[dict[str, object]]:
        try:
            size = self._path.stat().st_size
        except OSError:
            return []  # producer has not created the stream yet
        if size < self._offset:
            self._offset = 0  # truncated/restarted by a new producer run
        events: list[dict[str, object]] = []
        with self._path.open("rb") as fh:
            if self._offset > 0:
                fh.seek(self._offset - 1)
                if fh.read(1) != b"\n":
                    self._offset = 0  # regrown file: no line boundary here
            fh.seek(self._offset)
            chunk = fh.read()
        start = 0
        while True:
            nl = chunk.find(b"\n", start)
            if nl < 0:
                break  # the trailing partial stays unconsumed (torn-line safe)
            raw = chunk[start:nl]
            start = nl + 1
            self._offset += len(raw) + 1
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                self.corrupt += 1
                continue
            if isinstance(event, dict):
                events.append(event)
            else:
                self.corrupt += 1
        return events


@dataclass(frozen=True)
class ConsumerDecision:
    """What one consumer tick decided (the caller performs the apply).

    ``apply`` is the newest applicable pose line (payload-v2 shaped) or None
    — None means "keep the current pose" (a miss is newest, nothing new
    arrived, or only duplicate/replayed lines arrived). Counters are honest
    per-tick deltas plus the running totals the panel shows.
    """

    apply: dict[str, object] | None
    skipped: int  # pose lines of this batch superseded or invalidated (not applied)
    duplicates: int  # replayed lines after a truncation reset (seq not newer)
    misses: int  # miss lines seen this tick
    poses_total: int  # running total of pose lines seen
    misses_total: int  # running total of miss lines seen
    stale: bool  # no new line for longer than stale_after
    since_last_s: float  # seconds since the last new line (or since start)
    last_seq: int | None  # envelope seq of the last event seen (None = none yet)
    corrupt: int  # running corrupt complete lines from the tail


class LiveConsumer:
    """The P5-2 puppeteer policy over a :class:`LiveTail` (docs/LIVE.md).

    Pure stdlib, no bpy, no I/O beyond the tail's file reads. ``clock`` is
    injectable (monotonic seconds) so CI tests staleness deterministically;
    production uses ``time.monotonic``.
    """

    def __init__(
        self,
        tail: LiveTail,
        *,
        stale_after: float = DEFAULT_STALE_AFTER,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if stale_after <= 0:
            raise RiggermortisError(
                f"stale_after must be > 0, got {stale_after}",
                hint="seconds of stream silence before the panel reports STALE; "
                     "the default 2.0 is an order-of-magnitude choice (D-008), "
                     "not a tuned threshold",
            )
        self._tail = tail
        self._stale_after = stale_after
        self._clock = clock
        self._started_at = clock()
        self._last_event_at: float | None = None
        self._last_seq: int | None = None
        self._last_applied_seq: int | None = None
        self.poses_total = 0
        self.misses_total = 0

    def poll(self) -> ConsumerDecision:
        now = self._clock()
        events = self._tail.poll()
        if events:
            self._last_event_at = now

        poses = [e for e in events if e.get("kind") == "pose"]
        misses = sum(1 for e in events if e.get("kind") == "miss")
        self.poses_total += len(poses)
        self.misses_total += misses

        fresh: dict[str, object] | None = None  # newest non-duplicate pose line
        last_seq = self._last_seq
        duplicates = 0
        for event in events:
            seq = _envelope_seq(event)
            if seq is not None:
                last_seq = seq
            if event.get("kind") != "pose":
                continue
            if (
                seq is not None
                and self._last_applied_seq is not None
                and seq <= self._last_applied_seq
            ):
                duplicates += 1  # replayed after a truncation reset — not new data
                continue
            fresh = event

        apply_line = fresh
        if apply_line is not None and events[-1].get("kind") == "miss":
            apply_line = None  # the stream's NEWEST state is a miss: keep the pose
        non_dup_poses = len(poses) - duplicates
        if apply_line is not None:
            seq = _envelope_seq(apply_line)
            self._last_applied_seq = seq if seq is not None else self._last_applied_seq
            skipped = non_dup_poses - 1  # the other pose lines were superseded
        else:
            skipped = non_dup_poses  # seen but not applied (miss-newest or dupes)

        self._last_seq = last_seq
        since_last = now - (
            self._last_event_at if self._last_event_at is not None else self._started_at
        )
        return ConsumerDecision(
            apply=apply_line,
            skipped=max(0, skipped),
            duplicates=duplicates,
            misses=misses,
            poses_total=self.poses_total,
            misses_total=self.misses_total,
            stale=since_last > self._stale_after,
            since_last_s=since_last,
            last_seq=last_seq,
            corrupt=self._tail.corrupt,
        )


def _envelope_seq(event: dict[str, object]) -> int | None:
    live = event.get("live")
    if isinstance(live, dict):
        seq = live.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            return seq
    return None
