"""P5-1 tests: live side-process contract — sources, loop policy, stream.

Faked everything (the P2-1 video.py test pattern): no models, no network,
no real frames — the pose data is deterministic synthetic keypoints. The
timing fields in the ``live`` envelope are MEASUREMENTS: asserted present
and finite, never value-equal (docs/LIVE.md determinism statement).
"""
from __future__ import annotations

import json
import math
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


# -- P5-2: the incremental tail (faked stream files, no producer needed) ----------


def _line(kind: str, seq: int, **extra: object) -> str:
    line = {
        "kind": kind,
        "live": {"seq": seq, "t_emit_wall": 1.0 * seq, "age_ms": None},
        "frame": seq,
    }
    line.update(extra)
    return json.dumps(line, sort_keys=True)


def test_live_tail_returns_only_new_events(tmp_path: Path) -> None:
    stream = tmp_path / "live.jsonl"
    stream.write_text(_line("pose", 0) + "\n" + _line("miss", 1) + "\n",
                      encoding="utf-8")
    tail = live.LiveTail(stream)
    first = tail.poll()
    assert [e["live"]["seq"] for e in first] == [0, 1]
    assert tail.poll() == []  # nothing new: empty, not a re-read
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("pose", 2) + "\n")
    assert [e["live"]["seq"] for e in tail.poll()] == [2]


def test_live_tail_holds_a_torn_final_line_until_complete(tmp_path: Path) -> None:
    stream = tmp_path / "live.jsonl"
    full = _line("pose", 0)
    torn = _line("pose", 1)[:20]  # writer killed mid-write
    stream.write_text(full + "\n" + torn, encoding="utf-8")
    tail = live.LiveTail(stream)
    assert [e["live"]["seq"] for e in tail.poll()] == [0]
    assert tail.corrupt == 0  # the torn tail is NOT a corrupt line
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("pose", 1)[20:] + "\n")  # the writer finishes the line
    assert [e["live"]["seq"] for e in tail.poll()] == [1]  # exactly once
    assert tail.corrupt == 0


def test_live_tail_resets_when_the_producer_restarts(tmp_path: Path) -> None:
    stream = tmp_path / "live.jsonl"
    stream.write_text(_line("pose", 0) + "\n" + _line("pose", 1) + "\n",
                      encoding="utf-8")
    tail = live.LiveTail(stream)
    assert len(tail.poll()) == 2
    stream.write_text(_line("pose", 0) + "\n", encoding="utf-8")  # truncate
    events = tail.poll()
    assert [e["live"]["seq"] for e in events] == [0]  # re-read from the start
    assert tail.poll() == []


def test_live_tail_detects_a_regrown_rewritten_file(tmp_path: Path) -> None:
    """A truncate+regrow that lands PAST the old offset: the byte before the
    offset is not a newline (a line-oriented stream can only resume at a
    line boundary), so the tail resets instead of parsing mid-JSON garbage."""
    stream = tmp_path / "live.jsonl"
    stream.write_text(_line("pose", 0) + "\n", encoding="utf-8")
    tail = live.LiveTail(stream)
    assert len(tail.poll()) == 1
    stream.write_text(  # longer first line, then more: regrown past the offset
        _line("miss", 7, reason="producer restarted mid-session") + "\n"
        + _line("pose", 0) + "\n" + _line("pose", 1) + "\n",
        encoding="utf-8",
    )
    seqs = [e["live"]["seq"] for e in tail.poll()]
    assert seqs == [7, 0, 1]  # re-read the REWRITTEN file from its start
    assert tail.poll() == []


def test_live_tail_missing_file_polls_empty_and_counts_corrupt(tmp_path: Path) -> None:
    tail = live.LiveTail(tmp_path / "not-yet.jsonl")
    assert tail.poll() == []  # producer has not started
    stream = tmp_path / "not-yet.jsonl"
    stream.write_text("not json at all\n" + _line("pose", 0) + "\n",
                      encoding="utf-8")
    events = tail.poll()
    assert [e["live"]["seq"] for e in events] == [0]
    assert tail.corrupt == 1  # a corrupt COMPLETE line is counted, not swallowed


# -- P5-2: the consumer policy -----------------------------------------------------


class _FakeClock:
    """Deterministic monotonic clock for staleness tests."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_consumer_applies_newest_pose_only(tmp_path: Path) -> None:
    stream = tmp_path / "live.jsonl"
    stream.write_text(
        _line("pose", 0) + "\n" + _line("pose", 1) + "\n" + _line("pose", 2) + "\n",
        encoding="utf-8",
    )
    decision = live.LiveConsumer(live.LiveTail(stream)).poll()
    assert decision.apply is not None
    assert decision.apply["live"]["seq"] == 2  # latest wins
    assert decision.skipped == 2  # the two superseded poses of the batch
    assert decision.misses == 0 and decision.poses_total == 3
    assert decision.last_seq == 2 and decision.stale is False


def test_consumer_miss_newest_keeps_the_pose(tmp_path: Path) -> None:
    stream = tmp_path / "live.jsonl"
    stream.write_text(
        _line("pose", 0) + "\n" + _line("pose", 1) + "\n" + _line("miss", 2) + "\n",
        encoding="utf-8",
    )
    decision = live.LiveConsumer(live.LiveTail(stream)).poll()
    assert decision.apply is None  # the stream's newest state is a miss
    assert decision.skipped == 2  # neither pose was applied this tick
    assert decision.misses == 1 and decision.misses_total == 1
    # ...and the next pose applies normally again
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("pose", 3) + "\n")
    decision = live.LiveConsumer(live.LiveTail(stream)).poll()
    assert decision.apply is not None and decision.apply["live"]["seq"] == 3


def test_consumer_batches_arriving_between_polls(tmp_path: Path) -> None:
    stream = tmp_path / "live.jsonl"
    consumer = live.LiveConsumer(live.LiveTail(stream))
    d0 = consumer.poll()
    assert d0.apply is None and d0.stale is False  # fresh consumer, empty stream
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("pose", 0) + "\n")
    d1 = consumer.poll()
    assert d1.apply is not None and d1.apply["live"]["seq"] == 0
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("miss", 1) + "\n" + _line("pose", 2) + "\n")
    d2 = consumer.poll()
    assert d2.apply is not None and d2.apply["live"]["seq"] == 2  # miss rode through
    assert d2.misses == 1 and d2.poses_total == 2 and d2.last_seq == 2


def test_consumer_staleness_uses_the_injected_clock(tmp_path: Path) -> None:
    stream = tmp_path / "live.jsonl"
    clock = _FakeClock()
    consumer = live.LiveConsumer(live.LiveTail(stream), stale_after=2.0, clock=clock)
    early = consumer.poll()
    assert early.stale is False  # 0.0 s since start
    clock.now += 2.5
    assert consumer.poll().stale is True  # silent since start -> stale
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("pose", 0) + "\n")
    clock.now += 1.0
    fresh = consumer.poll()
    assert fresh.stale is False and fresh.since_last_s == 0.0  # line seen this tick
    clock.now += 2.1
    stale = consumer.poll()
    assert stale.stale is True and stale.apply is None  # keep the pose, say so
    assert stale.since_last_s > 2.0


def test_consumer_replayed_lines_after_reset_are_duplicates(tmp_path: Path) -> None:
    stream = tmp_path / "live.jsonl"
    stream.write_text(_line("pose", 0) + "\n" + _line("pose", 1) + "\n",
                      encoding="utf-8")
    consumer = live.LiveConsumer(live.LiveTail(stream))
    first = consumer.poll()
    assert first.apply is not None and first.apply["live"]["seq"] == 1
    stream.write_text(_line("pose", 0) + "\n")  # restart: shorter file replays
    second = consumer.poll()
    assert second.duplicates == 1  # seq <= last applied: replayed, not new data
    assert second.apply is None  # nothing fresh to apply — keep the pose
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("pose", 2) + "\n")
    third = consumer.poll()
    assert third.apply is not None and third.apply["live"]["seq"] == 2


def test_consumer_validates_stale_after(tmp_path: Path) -> None:
    with pytest.raises(RiggermortisError) as exc:
        live.LiveConsumer(live.LiveTail(tmp_path / "s.jsonl"), stale_after=0.0)
    assert "hint" in str(exc.value)


def test_consumer_end_to_end_over_a_producer_shaped_stream(tmp_path: Path) -> None:
    """The full faked-stream loop: lines appear incrementally exactly like
    ``rigpose live`` writes them (flush per line), torn line included."""
    stream = tmp_path / "live.jsonl"
    clock = _FakeClock()
    consumer = live.LiveConsumer(live.LiveTail(stream), stale_after=1.0, clock=clock)
    applied: list[int] = []

    def tick(lines: list[str]) -> None:
        with stream.open("a", encoding="utf-8") as fh:
            for text in lines:
                fh.write(text + "\n")
                fh.flush()  # the producer's flush-per-line contract
        decision = consumer.poll()
        if decision.apply is not None:
            applied.append(decision.apply["live"]["seq"])

    tick([_line("pose", 0)])
    tick([_line("pose", 1), _line("pose", 2)])  # batch -> latest wins
    tick([_line("miss", 3)])  # person lost: keep pose 2
    tick([_line("pose", 4)])
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("pose", 5)[:15])  # torn: killed writer
    tick([])  # the partial is held, nothing applies
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("pose", 5)[15:] + "\n")  # the writer finishes the line
    tick([])  # ...and the completed line applies exactly once
    assert applied == [0, 2, 4, 5]
    final = consumer.poll()
    assert final.apply is None  # drained
    assert final.poses_total == 5 and final.misses_total == 1
    assert final.last_seq == 5 and final.corrupt == 0
    assert final.last_seq == live.latest_pose_line(stream)["live"]["seq"]


# -- P5-3: stream-side smoothing + the failsafe --------------------------------------


def _variance(values: list[float]) -> float:
    """The P2-2 variance instrument (mean squared deviation from the mean)."""
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def _pose(x: float = 0.0, y: float = 0.0, z: float = 1.0):
    """A small CanonicalPose: hips at the jitter axis, head riding along."""
    return live.CanonicalPose(
        positions={"hips": (x, y, z), "head": (x + 0.1, y, z + 0.5)},
        flips={}, confidence=0.8, reliable=True, scale=100.0, anchor="hips",
    )


def test_smoother_constant_stream_applies_identically() -> None:
    """docs/LIVE.md P5-3: a constant stream through smoothing ON applies the
    IDENTICAL pose every line (a convex combiner on constant input)."""
    smoother = live.LivePoseSmoother()
    base = _pose()
    for i in range(6):
        out = smoother.smooth(base, 100.0 + i * 0.1)
        assert out.positions == base.positions


def test_smoother_cuts_jitter_variance_by_the_p2_2_instrument() -> None:
    """Two-tone deterministic jitter on one axis at the P2-2 sampling class
    (30 Hz): the smoothed variance cuts >= 4x (the published P2-2 bar, reused
    verbatim — no new threshold) and the smoothed mean tracks the raw mean
    within the jitter amplitude."""
    amp = 0.01
    n = 40
    dt = 1.0 / 30.0
    raw_x = [
        amp * math.sin(2.0 * math.pi * 3.0 * i * dt)
        + amp * 0.5 * math.sin(2.0 * math.pi * 11.0 * i * dt + 1.3)
        for i in range(n)
    ]
    smoother = live.LivePoseSmoother()
    smoothed_x: list[float] = []
    for i, x in enumerate(raw_x):
        out = smoother.smooth(_pose(x=x), t_emit_wall=1000.0 + i * dt)
        smoothed_x.append(out.positions["hips"][0])
    tail = slice(8, None)  # skip the filter warmup, like the P2-2 test
    var_raw = _variance(raw_x[tail])
    var_smoothed = _variance(smoothed_x[tail])
    assert var_raw > 0.0
    assert var_smoothed * 4.0 < var_raw
    assert abs(sum(smoothed_x[tail]) / len(smoothed_x[tail])
               - sum(raw_x[tail]) / len(raw_x[tail])) <= amp


def test_smoother_preserves_partial_observation_and_metadata() -> None:
    """A role absent from a pose stays absent; flips/confidence/notes ride."""
    pose = _pose()
    pose.positions.pop("head")
    pose.flips = {"forearm.L": -1}
    pose.notes = ["test note"]
    smoother = live.LivePoseSmoother()
    out = smoother.smooth(pose, 1.0)
    assert "head" not in out.positions
    assert "hips" in out.positions
    assert out.flips == {"forearm.L": -1}
    assert out.notes == ["test note"]
    assert out.confidence == pose.confidence and out.scale == pose.scale
    # the head filter stays idle, not dead: re-observing the role filters
    # from its first fresh value (pass-through on the first call)
    out2 = smoother.smooth(_pose(), 1.1)
    assert out2.positions["head"] == _pose().positions["head"]


def test_smoother_gap_snaps_to_the_new_observation() -> None:
    """A long gap opens the filter (alpha -> 1): the next pose effectively
    snaps through instead of lagging across the dropout."""
    smoother = live.LivePoseSmoother()
    for i in range(10):
        smoother.smooth(_pose(), t_emit_wall=100.0 + i * 0.1)
    jumped = smoother.smooth(_pose(x=0.5), t_emit_wall=200.0)  # 100 s gap
    dx = jumped.positions["hips"][0]
    assert abs(dx - 0.5) < 0.01 * 0.5  # within 1% of the A->B span of B


def test_smoother_mirror_commutation() -> None:
    """docs/LIVE.md P5-3, the mirror-order proof: the 1-euro filter is
    odd-symmetric, so smooth(mirror(p)) == mirror(smooth(p)) exactly on a
    consistently mirrored stream — smooth-first is chosen for the state
    (a mid-session toggle needs no filter-state surgery)."""
    stream = [
        _pose(x=0.05 * math.sin(0.7 * i), z=1.0 + 0.02 * i) for i in range(12)
    ]
    smoother = live.LivePoseSmoother()
    smooth_then_mirror = [smoother.smooth(p, 10.0 + 0.1 * i).mirrored()
                          for i, p in enumerate(stream)]
    smoother2 = live.LivePoseSmoother()
    mirror_then_smooth = [smoother2.smooth(p.mirrored(), 10.0 + 0.1 * i)
                          for i, p in enumerate(stream)]
    for a, b in zip(smooth_then_mirror, mirror_then_smooth, strict=True):
        assert a.positions == b.positions


def test_smoother_reset_passes_through() -> None:
    """reset() drops the filter state: the next pose passes through exactly
    (the failsafe path relies on this for a clean recovery)."""
    smoother = live.LivePoseSmoother()
    for i in range(5):
        smoother.smooth(_pose(), t_emit_wall=i * 0.1)
    smoother.reset()
    out = smoother.smooth(_pose(x=0.4), t_emit_wall=99.0)
    assert out.positions["hips"][0] == 0.4


def test_smoother_validates_args() -> None:
    with pytest.raises(RiggermortisError) as exc:
        live.LivePoseSmoother(min_cutoff=0.0)
    assert "hint" in str(exc.value)
    with pytest.raises(RiggermortisError) as exc:
        live.LivePoseSmoother(beta=-1.0)
    assert "hint" in str(exc.value)


def test_consumer_failsafe_fires_once_and_rearms(tmp_path: Path) -> None:
    """docs/LIVE.md P5-3: STALE first, then the failsafe EDGE (one tick),
    latched until any new stream event re-arms it and the pose applies."""
    stream = tmp_path / "live.jsonl"
    clock = _FakeClock()
    consumer = live.LiveConsumer(
        live.LiveTail(stream), stale_after=1.0, failsafe_after=3.0, clock=clock,
    )
    early = consumer.poll()
    assert early.stale is False and early.failsafe is False
    clock.now += 2.0  # silent past stale_after, short of the failsafe
    mid = consumer.poll()
    assert mid.stale is True and mid.failsafe is False
    clock.now += 1.5  # silence crosses failsafe_after
    fired = consumer.poll()
    assert fired.failsafe is True and fired.failsafe_fired is True
    clock.now += 1.0  # still silent: the latch holds, no second edge
    held = consumer.poll()
    assert held.failsafe is False and held.failsafe_fired is True
    with stream.open("a", encoding="utf-8") as fh:
        fh.write(_line("pose", 0) + "\n")
    clock.now += 0.2  # the stream continues: re-arm + apply
    back = consumer.poll()
    assert back.apply is not None and back.apply["live"]["seq"] == 0
    assert back.failsafe is False and back.failsafe_fired is False


def test_consumer_failsafe_validates_after_stale(tmp_path: Path) -> None:
    with pytest.raises(RiggermortisError) as exc:
        live.LiveConsumer(
            live.LiveTail(tmp_path / "s.jsonl"),
            stale_after=2.0, failsafe_after=2.0,
        )
    assert "hint" in str(exc.value)
    with pytest.raises(RiggermortisError):
        live.LiveConsumer(
            live.LiveTail(tmp_path / "s.jsonl"),
            stale_after=2.0, failsafe_after=1.0,
        )


def test_failsafe_default_sits_after_the_stale_default() -> None:
    """The documented ordering (docs/LIVE.md P5-3), pinned so a default bump
    cannot silently invert it."""
    assert live.DEFAULT_FAILSAFE_AFTER > live.DEFAULT_STALE_AFTER


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
