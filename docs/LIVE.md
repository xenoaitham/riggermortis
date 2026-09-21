# Live mode (Phase 5) — design as-built

P5-1's source of record, same discipline as STYLE.md/EXPORT.md: what shipped,
what it measures, what stays open. Written after the probe (S17) and kept in
sync with reality — the STYLE.md rule applies here too.

## What P5-1 is

A realtime-class pose **side process**: it owns the ONNX sessions and a frame
source, runs detect → solve → FK per frame, and writes **one JSON line per
frame** into a stream file. Lines embed the SAME payload-v2 shape the offline
pipeline writes (D-009), so the add-on's own apply path consumes them
unchanged — P5-2 (webcam → rig puppeteer) is a consumer of this stream, not a
new pipeline.

- Entry: `rigpose live <frames_dir> <rig.json> --out live.jsonl [--detect-every N …]`
  — the process IS the side process. **It is spawned by the user's shell or
  `xtask/live_capture.sh`, never by a `.py` file** (D-009: the spawn lives
  outside Python; the frontends consume payloads).
- Core module: `riggermortis/live.py` — pure stdlib up to the injected
  detector (the real one lazy-imports numpy/onnxruntime via `[inference]`,
  exactly like the video pipeline). CI tests run fakes; no models needed.
- Stream consumers: `live.read_live_lines(path)` / `live.latest_pose_line(path)`

## The detector decision (made on measured numbers, not vibes)

The honest fork from the work order: reuse the pinned DWPose stack with a
**detector-cadence policy** vs. add a lighter MediaPipe-class ONNX (new pinned
download, new keypoint mapping, new failure surface). The probe
(`xtask/live_probe.py`, `RM_LIVE` lines — raw numbers in
`out/live_probe/probe_measurements.json`) measured all three regimes on THIS
box (i5-10400F, 12 threads, onnxruntime 1.25.1 **CPU provider only** — an
RTX 3060 is present but no GPU ORT provider is installed, so CPU is both the
measured path and the mid-laptop-relevant baseline):

| regime | per-frame time | quality vs full |
|---|---|---|
| full (detector every frame) | **~550–610 ms** mean — the YOLOX-L detector IS the cost (`detect_mean_ms` ≈ total) | baseline |
| tracked (detector every 5th) | p50 **85–105 ms**, mean ~170 ms, p95 ~560–700 ms (the detector stalls land here) | **identical** (kp>0.3 and body-conf within noise) |
| pose-only (no detector, whole-frame box) | **80–115 ms flat**, p50 ≈ p95 (no spikes) | body-conf within 0.01 on 2/3 images; one image 0.68 vs 0.78 |

Two findings settled it:

1. **Input downscale is a dead knob here**: `native` vs 640w differs by
   ~2–4% — the ONNX inputs are fixed-size, so only the numpy preprocessing
   scales. The realtime lever is the detector CADENCE, not resolution.
2. **Pose-only quality holds** on single-person frames: the 288×384 crop
   stage does not need the YOLOX box when the person fills a known region.
   The tracked regime keeps detector-anchored boxes on a cadence and costs
   ~10 fps sustained (p50) between sub-100 ms pose-only frames.

**Decision: reuse the pinned DWPose models (manifest untouched, zero new
downloads, licenses unchanged). A MediaPipe-class model stays a P5-2+ option
only if the end-to-end budget (capture → apply) misses its gate with the
cadence policy — this box's numbers say the detector side is not the
blocker.** The 0.85 s P1-2 baseline is beaten ~1.5× by the full regime
(single-person frame) and ~5–10× at p50 by tracked/pose-only.

## Process boundary (D-009, twice)

- **Producer spawn**: shell/agent/`xtask/live_capture.sh`. No `.py` in this
  repo spawns the side process. No sockets in core (D-003): the stream is a
  **file**, written line-buffered with a flush per line so consumers tail it.
- **Frame producer**: also shell glue. `xtask/extract_frames.sh` for recorded
  video (P2-1); `xtask/live_capture.sh` for a capture device (ffmpeg v4l2 →
  numbered PNGs into the watched dir). Core never opens a device.
- **Consumer**: add-on/MCP/tests read the stream through the two helpers —
  P5-2's Blender driver polls `latest_pose_line` on a timer and feeds the
  payload through the EXISTING apply path (P1-6). No new apply machinery.

## Frame-source contract (`core/live.py`, pure stdlib)

- `Frame(seq, path, t_capture)` — `t_capture` is the source's wall-clock
  epoch (file mtime) or None. A MEASUREMENT, never pose data.
- `FrameSource.next_frame() -> Frame | None` — each frame exactly once, in a
  deterministic order; `None` = stop.
- `ListFrameSource(paths)` — explicit list (replay/tests/probe), name-sorted.
- `DirectoryFrameSource(dir, poll_seconds=0.05, idle_timeout=10.0)` — polls a
  glue-written directory, yields new files in name order, stops after the
  idle timeout. The deterministic core the live loop shares with CI fakes.

## Stream-line contract

Every line is one JSON object, `sort_keys`-serialized:

- `kind=pose` — the D-009 payload-v2 shape (`format`, `frame`, `file`,
  `figure`, `pose`, `rotations`, `skipped`, `notes`, `figures` — exactly one
  figure entry, the video writer's shape) plus `"kind"` and a `"live"`
  envelope. Passes `payload.figure_entries()` — CI-asserted.
- `kind=miss` — `"reason"` + the envelope, NO pose data. A miss is a NORMAL
  live event (person out of frame, detection loss, low confidence, a
  per-frame exception — reason says which). The consumer keeps its previous
  pose; the offline pipeline's "failed frame ledger" semantics intentionally
  do not apply to a stream.
- `live` envelope (both kinds): `seq`, `t_emit_wall`, `t_capture_wall`,
  `age_ms`, `detect_every`, `detector_ran`, `detect_ms`, `solve_ms`, `fk_ms`,
  `total_ms`.

**Determinism statement**: same frames + same settings → same pose data
(figure/pose/rotations byte-identical, CI-tested). The envelope timing fields
are wall-clock MEASUREMENTS and are excluded from determinism assertions —
they are the product here, not noise to scrub.

## Loop policy (`run_live`)

- The detector runs on the first frame, after ANY miss, and every
  `detect_every`-th frame otherwise (1 = full regime; >1 = tracked).
- Between detector runs the pose stage crops the previous box expanded by
  `margin = 0.15` of the box per side (`expand_bbox`, clamped to the frame).
  Order-of-magnitude default chosen before any measurement, NOT fitted (D-008).
- Miss floor: mean confidence over the 17 COCO body keypoints
  (`mean_body_confidence`) under `conf_floor = 0.3` → miss + forced re-detect.
- **Figure identity rides the last full detection** — a tracked figure is the
  same person the detector last named (label + index are stamped from the
  full path; `estimate_keypoints_at` cannot know labels, returns `score=0.0`:
  `Figure.score` is a DETECTOR score and the tracked path runs no detector).
- Per-frame exceptions become miss lines with their reason — recorded, never
  swallowed. The loop stops on source exhaustion, `max_frames`, or idle
  timeout; Ctrl-C exits 130 with every completed line already flushed.

## The measured budget (S17, this box)

Machine: i5-10400F @ 2.90 GHz (12 threads), onnxruntime 1.25.1
CPUExecutionProvider with ≤4 intra/inter-op threads (the P1-2 deterministic
configuration), Python 3.13.12. Frames: STATIC REPLAYS of three single-person
benchmark photos (P1-9 set, Apache-2.0, git-ignored) at native and 640w-long-
side sizes; 2 warmup + 6 timed frames per config; percentiles nearest-rank.
Published in the `BENCHMARK:LIVE` block of docs/BENCHMARKS.md — written by
the probe itself, never hand-transcribed; raw per-config JSON in
`out/live_probe/probe_measurements.json` (git-ignored).

The aggregate over 18 configs: **full ≈ 552 ms mean; tracked ≈ 170 ms mean /
88 ms p50 (worst p95 ≈ 700 ms — the detector stalls); pose-only ≈ 90 ms flat
(p50 ≈ p95)**. Quality holds across regimes (kp>0.3 ≈ 127–128 of 133; body
conf min 0.62 vs the 0.3 miss floor). **P5-1's accept is this measured budget
plus the clean contract — the Phase-5 <100 ms mid-laptop gate is P5-2's**,
measured end-to-end (capture → apply) on mid-laptop hardware, not here.

### Real side-process smoke (live-verified, the P2-1 standard)

`rigpose live` spawned from a shell (the production spawn path) over a
9-frame replay directory (3 photos × 3 repeats, `--detect-every 3`) against
the REAL pinned models and the real metarig rig JSON: **9/9 pose lines,
0 misses**, stream parse-back contract-valid through
`payload.figure_entries()` + `entry_for_label`, 16 rotations, conf 0.71,
reliable. The envelope told the true story: seq 0 paid the **cold session
load (~2 s)** — a normal deployment fact, visible in `detect_ms`, worth a
warmup frame in any consumer — tracked frames landed **78–120 ms**, detector
frames 530–670 ms, matching the probe. Two real bugs caught on the way (the
gate earned its keep): the `_sessions` attribute shadowed the `_sessions()`
method (instant `NoneType is not callable` misses — fixed by renaming the
cache), and `total_ms` initially timed only solve+FK instead of the whole
frame (fixed; `total_ms` = detect + solve + FK).

## The camera on this box (honest)

`/dev/video0` EXISTS (DroidCam v4l2loopback) but delivered **no frames** when
probed with ffmpeg (timeout, no packets — the phone side of DroidCam was not
streaming). Consequences, labeled not hidden:

- `xtask/live_capture.sh` (the v4l2 → frames-dir glue) ships but is
  **UNTESTED against a streaming device** — the replay path (files) is what
  P5-1 verified. NEEDS-HUMAN: start the DroidCam stream (or plug a real
  camera) and re-run the capture half.
- P5-2's end-to-end latency stays unmeasurable until a stream exists; the
  side-process half of the budget is the S17 table above.

## Honest limits

- **Static-replay quality**: the tracked regime's bbox feedback under real
  inter-frame MOTION is untested (needs the stream). Motion faster than the
  margin can lose the person — that is what the miss → forced re-detect path
  is for; it is CI-tested with fakes, not yet proven on live pixels.
- Single figure per frame (largest) — the video pipeline's semantics. No
  cross-figure tracking.
- No smoothing/latency UI/failsafe — that is P5-3, on top of this contract.
- The probe measures detect+solve+FK (the side-process cost). Capture age
  (`age_ms`) is carried per line so P5-2 can measure the end-to-end budget
  without touching this contract.

## Reproduce

```bash
# the probe (needs models + out/benchmark/images/photo/, else honest SKIPPED)
PY=/home/potato/miniconda3/bin/python3
$PY xtask/live_probe.py

# a live run over recorded frames (decode via the P2-1 glue)
bash xtask/extract_frames.sh clip.mp4 out/live_probe/frames 15
rigpose live out/live_probe/frames out/real_rigs/metarig.rig.json \
    --out out/live_probe/live.jsonl --detect-every 5

# capture-device glue (UNTESTED on this box — no stream; see above)
bash xtask/live_capture.sh out/live_probe/frames 15
```
