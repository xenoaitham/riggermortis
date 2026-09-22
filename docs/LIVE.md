# Live mode (Phase 5) — design as-built

The Phase-5 source of record (P5-1 side process + P5-2 stream consumer),
same discipline as STYLE.md/EXPORT.md: what shipped, what it measures, what
stays open. Written after the probe (S17) and kept in sync with reality —
the STYLE.md rule applies here too.

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
- Smoothing / the latency readout / the failsafe: P5-3 (section below, on
  top of this contract).
- The probe measures detect+solve+FK (the side-process cost). Capture age
  (`age_ms`) is carried per line so P5-2 can measure the end-to-end budget
  without touching this contract.

## P5-2 — the stream consumer (design as-built, S18)

The consumer half of live mode: a Blender add-on driver that tails the
`rigpose live` stream file and puppeteers a rig through the REAL P1-6 apply
path. No new pipeline, no sockets (D-003/D-009): the producer writes a file,
the consumer reads it. Designed here FIRST; the engine matches this text.

### Topology

```
shell/agent --spawn--> rigpose live (side process) --> stream.jsonl
                                                          ^ poll (~10 Hz)
Blender --bpy.app.timers--> rm live driver --> pose_apply.apply_payload
                                 |
                                 +-- core.live.LiveTail + LiveConsumer
                                     (pure stdlib, CI-tested with fakes)
```

- The producer is unchanged (P5-1). The spawn stays OUTSIDE Python (D-009):
  the user's shell or `xtask/live_capture.sh`.
- The Blender side never blocks and never spawns a thread: the timer
  callback polls the stream file (microseconds-class reads), applies at most
  one pose, and updates panel state. The apply is the only bpy touch, and it
  MUST be main-thread anyway (the session.py precedent).

### The incremental tail (`core.live.LiveTail`)

`latest_pose_line` re-reads the whole file — O(file) per tick is wrong at
10–30 lines/s × ~20–50 KB lines over a long session. `LiveTail` keeps
byte-offset state:

- `poll()` reads from the last committed offset to EOF, splits on newlines,
  and parses COMPLETE lines only. A torn final line (writer killed
  mid-write) is never consumed — the offset stays at its start and the line
  parses once it completes on a later poll.
- Producer restart (the writer reopens with `open("w")`, truncating): a file
  smaller than the remembered offset resets the tail to 0; a file that
  regrew PAST the old offset is caught by a one-byte boundary check — a
  line-oriented stream can only resume at a newline, so a non-newline byte
  before the offset means the file was rewritten (reset; replayed lines
  become the CONSUMER's duplicates, never re-applied).
- Missing file: `poll()` returns `[]` (the producer has not started yet).
- Corrupt COMPLETE lines are counted on `tail.corrupt`, never swallowed
  (a torn tail can only ever be the final line; mid-stream corruption is a
  real problem the panel surfaces).

### The consumer policy (`core.live.LiveConsumer`)

A pure decision engine over a `LiveTail` — injected clock for
deterministic CI tests; the Blender side is a thin adapter that performs the
decision:

- **Latest-wins**: among the new lines of one poll, at most ONE pose is
  applied — the newest `kind=pose` line. Superseded pose lines of the same
  batch count as `skipped` (applying three stale poses back-to-back at 3×
  cost serves nothing in puppeteering).
- **A miss keeps the pose**: if the stream's newest event is a `kind=miss`,
  nothing is applied — the previous pose stays (the stream contract; a miss
  is a NORMAL event, never a crash). Misses are counted and surfaced.
- **Replayed lines after a truncation reset are duplicates**, not new pose
  data: a pose line whose envelope `seq` is not newer than the last applied
  one is counted (`duplicates`) and never applied.
- **Staleness**: `stale` flips when `now - t_last_new_line > stale_after`
  (default 2.0 s — an order-of-magnitude default chosen before any
  measurement, NOT tuned to fixtures, D-008; roughly twenty tracked frames'
  worth of silence at the S17 p50). On stale: keep the last pose, report
  staleness honestly in the panel. The failsafe proper (drop to a safe
  preview pose) is P5-3 — designed in the P5-3 section below.
- The decision returns as a `ConsumerDecision` (the line to apply or None,
  skipped/duplicates/misses counts, total poses seen, stale flag, seconds
  since the last line, last seq, tail corrupt count). The caller does the
  bpy work.

### The Blender driver (addon/riggermortis_addon/live_driver.py)

- Start/Stop operators + a `bpy.app.timers` pump at 0.1 s (order-of-
  magnitude default, documented; the apply is what costs and the gate
  measures it). Stream path + `stale_after` live on the WindowManager —
  session-only state, like the session bridge's port/token.
- Apply = `pose_apply.apply_payload(obj, line, mirror=…)`: the REAL P1-6
  path — `rm_role_*` mapping (fallback live `map_rig`), mirror semantics
  untouched, structured report back. The stream line IS payload-v2 shaped
  (D-009); it is passed as-is. The armature is resolved from the panel's
  rig selection (or the active object) at Start.
- The pump never raises out of the timer: apply failures land in the status
  line, actionable with a hint, and the loop continues — the same
  never-crash-the-pump rule as session.py.
- Panel: a "Live driver (P5-2)" section — stream path, stale_after,
  Start/Stop, and the honest readout: state (live/stale/idle), lines seen
  (poses/misses), applied/skipped/duplicates, last seq, seconds since the
  last line, last apply cost and the last line's end-to-end age. The
  driver's own budget instrumentation measures apply cost per applied line
  and keeps the envelope's `age_ms` + poll lag so the end-to-end replay
  number is per-line measurable. No smoothing/latency UI — P5-3.

### The budget (REPLAY, this box — labeled; the live number stays unclaimed)

The S18 gate instrumented the driver per applied line: the apply cost
(measured around the P1-6 apply), the poll lag (emit → consumer tick), and
the envelope's `age_ms`. **The published replay end-to-end number is
emit → apply** — the first gate run caught that `age_ms` on replayed files
is the frame file's mtime AGE (an hour here), not capture latency; it is
printed per line for provenance and never summed in. With a real camera
(age_ms real), capture → apply = age_ms + poll lag + apply.

Measured by `make live-verify` (REAL `rigpose live` subprocess at
`--detect-every 3`, REAL headless Blender 5.1 driving the add-on's own
driver, 9 replay frames, i5-10400F CPU-only ONNX):

- apply fidelity: **9/9 lines applied, worst FK self-check 0.0000 deg**
  (bar 0.5) — the payload-v2 stream line through the unmodified P1-6 path;
- apply cost: **p95 ≈ 3.8 ms** (p50 ≈ 1.8 ms) — Blender-side posing is
  noise next to the producer;
- emit → apply: **p50 ≈ 157 ms**; the stalls (0.6–0.9 s) land exactly on
  the producer's DETECTOR frames, and the first line's ≈ 2.1 s sits in the
  cold-session window — consumer tick latency degrades under concurrent
  detector load on this CPU (measured as-is, not tuned; D-008). The
  lever stays the detector cadence (P5-1's finding). The S19 gate re-run
  of this same instrument read apply p95 ≈ 2.7 ms / emit → apply
  p50 ≈ 124 ms — run-to-run jitter is normal and is never tuned away;
- staleness: with the producer gone, the driver flips STALE at the
  configured threshold and keeps the last pose;
- misses: a forced all-miss stream (`--conf-floor 0.95`) yields 9 miss
  lines, **0 applies, pose bones byte-unchanged**, 0 corrupt.

**The LIVE capture → apply number and the Phase-5 <100 ms mid-laptop gate
stay UNCLAIMED**: /dev/video0 delivered no frames again in S18 (ffmpeg
timeout re-verified) — the DroidCam phone side still is not streaming
(NEEDS-HUMAN). Nothing replay gets relabeled live (the D-015 discipline).

## P5-3 — smoothing, the latency readout, the failsafe (design as-built, S19)

The last camera-independent Phase-5 piece: condition the stream between the
consumer and the apply (1€ smoothing, P2-2's filter, on the canonical pose),
surface the latency honestly in the panel, and give sustained stream silence
a defined safe state. Designed here FIRST (the S18 discipline); the engine
matches this text. Everything below is REPLAY/synthetic-verified — there is
still no real-motion stream on this box, so smoothing claims stay labeled and
the defaults stay order-of-magnitude (D-008: measure, publish, never fit).

### The smoothing wire point (core-side, on the canonical pose)

Smoothing lives in CORE (`riggermortis.live.LivePoseSmoother`), CI-tested
with deterministic jitter streams — the S18 pattern: policy in core, the
add-on a thin adapter. It filters the CANONICAL POSE, per role per axis,
partial observation preserved (a role absent from a pose stays absent; the
P2-2 semantics) — NOT a bone-space hack after apply:

```
stream line (payload-v2) ──> CanonicalPose.from_dict
                             ──> LivePoseSmoother.smooth(pose, t_emit_wall)   [core]
                             ──> mirror (the scene toggle)                    [if on]
                             ──> pose_apply.apply_pose_object(obj, pose)      [the P1-6 apply core]
```

The payload path (`pose_apply.apply_payload`) and the smoothed path converge
in `apply_pose_object` — the same FK pass, bone-space conversion, and report
shape the P1-6 operator uses. Smoothing OFF is byte-identical to P5-2's
behavior (the driver calls `apply_payload` exactly as before).

What is filtered: `positions` only — three axes per role. `flips` are
discrete decisions (the newest observation's flips ride through);
`confidence`/`scale`/`notes` are solve metadata, not signals (the FK apply is
direction-based and scale-free). One filter state lives in the DRIVER and
persists across applied lines; the producer's cadence gaps therefore simply
mean no update.

### Mirror ordering (decided from the math, then implemented once)

Smooth FIRST, in the stream's own character space; mirror AFTER. The 1€
filter is odd-symmetric — negating every x of a stream negates every internal
derivative estimate, leaves `|dx_hat|` and therefore every alpha unchanged,
so `smooth(mirror(p)) == mirror(smooth(p))` exactly for a consistently
mirrored stream (CI-tested). Given that commutation, smooth-first is chosen
for the state: the mirror toggle is a scene display decision, and with the
filter state in stream space an operator toggling mirror mid-session needs no
filter-state surgery (no side swap, no reset). Mirror-then-smooth would own
that problem for no benefit.

### Time base and gaps

The 1€ timestamps are the envelope's `t_emit_wall` (producer wall-clock
seconds; the `round(...,3)` grid makes dt quantized to 1 ms — harmless). The
P2-2 filter derives `freq` from dt and already guards `dt <= 0` (a wall-clock
step keeps the previous freq). Gaps: a miss line carries no pose, so no
filter update happens — a LONG gap (stall, detector recovery) opens the
filter (alpha → 1 as dt grows), and the next pose effectively snaps through;
that is the wanted behavior after any dropout. A failsafe fire (below) resets
the smoother, so the first post-failsafe pose passes through unfiltered and
recovery starts from the stream, not from pre-failsafe history.

### Defaults (order-of-magnitude, declared before any measurement)

`min_cutoff = 1.0` Hz, `beta = 0.05`, `d_cutoff = 1.0` — the P2-2 filter's
class of starting points, chosen from the 1€ paper's shape (a cutoff around
the stream's useful rate, a small speed coefficient) and NOT tuned against
any fixture: there is still no real-motion stream to tune against. Smoothing
claims stay REPLAY/synthetic-labeled until one exists.

### The latency/smoothing UI (readouts, not instruments)

The Live panel's existing apply / emit→apply readout is promoted into a small
**latency** block: apply cost, emit→apply, and the line's capture age marked
informational (on replayed files `age_ms` is the frame file's mtime age — the
S18 finding — so it is never summed into anything). Smoothing: an ON/OFF
toggle (read fresh per pump tick — the operator's toggle takes effect on the
next line) plus the two constants shown read-only. No graphs, no free numeric
tuning, no false precision.

### The failsafe policy (decided before implementation)

P5-2's stub keeps the last pose through `stale_after` (default 2.0 s) and
reports STALE — brief dropouts are normal at detector cadence. SUSTAINED
silence is different: the producer is gone, and an indefinitely frozen
mid-gesture pose is the stale-puppet trap.

- **Safe state: rest.** Past `failsafe_after` (default 10.0 s — ~5× the
  staleness threshold, an order-of-magnitude choice, NOT tuned; the gate runs
  configured 1.0/2.0 knobs for speed, defaults untouched), the driver drops
  the rig to rest via the existing `pose_apply.clear_pose`, and the panel
  says so: `FAILSAFE — cleared to rest after N s of stream silence`.
- **Decision in core, action in the adapter.** `LiveConsumer` owns the clock:
  `failsafe` fires as an EDGE on the decision (one tick) when
  `since_last_s` crosses `failsafe_after`, and latches (`failsafe_fired`)
  until any new stream event re-arms it. `failsafe_after > stale_after` is
  validated (the safe state must not preempt the stale readout). The driver
  performs the bpy work exactly once per edge and never raises out of the
  pump.
- **Recovery.** When the stream continues (a stalled producer resuming with
  rising seq), the next applicable pose is applied normally, the latch
  clears, and the panel reports recovered. Because the smoother was reset at
  the edge, the first recovery pose passes through unfiltered.
- **Known limit, recorded not hidden**: a producer RESTART reusing a fresh
  seq space (kill + re-run) is suppressed by the P5-2 duplicate floor — its
  lines are replayed data by that contract, so the rig stays at rest and the
  panel shows lines-seen rising while applied stays frozen. The operator
  remedy is Stop/Start (a fresh consumer). The S18 duplicate contract is not
  re-litigated silently here; the revisit trigger is recorded in
  STATE/NEXT.md for the live-demo session.

### Gate: what `make live-verify` now asserts

- **Run A (smoothing OFF)** — unchanged S18 assertions and numbers, kept as
  the control: 9/9 applied, FK self-check ≤ 0.5° per line, budget rows,
  staleness readout, forced-miss stream applies nothing.
- **Jitter sweep** — the gate derives a synthetic stream from run A's first
  REAL pose line: deterministic per-line white jitter (fixed-seed grid) on
  selected role axes, amplitude A = 0.01 canonical units, envelopes at 30 Hz
  emit spacing (the P2-2 instrument's sampling class) with fresh seqs. The
  driver consumes it twice — smoothing OFF (the raw control curve) and ON.
  Assertions, all in the P2-2 instrument's terms: applied-curve variance cut
  ≥ 4× per jittered axis (the published P2-2 bar, reused verbatim — no new
  threshold), the smoothed curve's mean tracking the raw mean within the
  jitter amplitude, and every applied line's FK self-check ≤ 0.5° (the bar
  class). `RM_LIVE SMOOTH-SUMMARY` prints the measured ratios.
- **Constant-stream property (CI)** — a constant stream through smoothing ON
  applies the IDENTICAL pose every line (the filter is a convex combiner on
  constant input; first line passes through). Core-tested, no Blender.
- **Failsafe run** — a driver on a quiet stream (configured stale 1.0 s /
  failsafe 2.0 s): STALE first, then the FAILSAFE edge, pose bones byte-equal
  to their rest capture, the honest panel line; then a continuation line
  (rising seq, fresh emit time) applies automatically, clears the latch, and
  its pose passes through the reset smoother EXACTLY (CI mirror of this with
  the injected clock).
- New RM_LIVE lines are grep-tested on BOTH the PASS and SKIPPED paths
  before pushing (the standing gate rule).


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

# the P5-2 consumer gate (needs models + replay frames + real rigs, local)
make live-verify
```
