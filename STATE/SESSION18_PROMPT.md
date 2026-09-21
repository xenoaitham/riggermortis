# Session 18 prompt (riggermortis)

**Project (30-second context)**
riggermortis — local, free, rig-agnostic posing & animation engine: (1)
Blender add-on, (2) MCP server so AI agents drive Blender. Drop a rigged
model + reference image → pose applied. Drop a video → animation,
retargeted, foot-slide-cleaned. Toon renders, manga pages. No cloud, no
accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).
Phases 0–4 CLOSED (D-017). Phase 5 OPEN — **P5-1 DONE in S17** (commits
94b467b + bf46366): the realtime ONNX pose side process shipped on measured
numbers. CI at handoff: the S17 runs are 35648744966 (P5-1) and 35649029315
(STATE addendum) — tests 3.11/3.13 + media-guard were GREEN and the
blender-gate was still in flight when this prompt was written; STEP 0 for
S18 includes verifying both runs ended green (`gh run view`) and, if red,
downloading the log and fixing the real substance FIRST (the
S12/S14/S15/S16 discipline).

**P5-1's numbers (the facts S18 builds on)** — docs/LIVE.md is the Phase-5
source of record, the BENCHMARK:LIVE block is the instrument output: reuse
of the pinned DWPose models was DECIDED BY PROBE (18 configs, RM_LIVE
lines): full ≈ 550 ms/frame (detector-dominated), tracked-every-5 p50 ≈
88 ms, pose-only ≈ 90 ms flat, quality identical across regimes; input
downscale is a dead knob (fixed ONNX input sizes) — the detector CADENCE is
the lever. `rigpose live <frames_dir> <rig.json>` emits one D-009
payload-v2 JSON line per frame (`kind=pose` / `kind=miss`) into a stream
FILE (no sockets in core); core `live.py` holds the contract (frame
sources, `run_live`, `read_live_lines`/`latest_pose_line`, `expand_bbox`,
body-conf miss floor 0.3); `estimate_keypoints_at` is the public pose-only
wrapper entry; 16 faked-detector CI tests (327 total); REAL smoke: 9/9 pose
lines on real models + real metarig through the production spawn path
(cold session load ~2 s lands on line 0's `detect_ms`; tracked frames
78–120 ms in-loop).

**STEP 0 — Session protocol (do this first, always)**
Read, in order: STATE/NEXT.md (authoritative for S18 — its top item IS this
prompt's work order A), STATE/TASKS.md, STATE/PROGRESS.md (S17 entries),
STATE/DECISIONS.md (esp. D-008, D-009, D-011/012, D-017 — all EXECUTED,
don't re-litigate), STATE/CONVENTIONS.md, STATE/SESSIONS.md, docs/LIVE.md
(EXTEND it with the P5-2 section — never fork a second live doc),
docs/BENCHMARKS.md (LIVE block) + docs/POLICY.md. docs/STYLE.md stays the
style source of record — untouched unless style behavior changes.

Register yourself in STATE/SESSIONS.md as Session 18. Claim tasks in
STATE/TASKS.md by ticking + tagging [S18] before working. Append
timestamped PROGRESS lines per meaningful unit (real UTC via `date -u`).

Verify baseline: `cd core && /home/potato/miniconda3/bin/python3 -m pytest
tests` (expect **327 passed**) and `make lint
PY=/home/potato/miniconda3/bin/python3` from repo root (lint list includes
xtask/live_probe.py).

**Environment facts (verified through S17)**
Blender 5.1.0 at /home/potato/blender-5.1.0-linux-x64/ is the REAL install.
Gates need explicit env or they 127 on PATH:
BLENDER=/home/potato/blender-5.1.0-linux-x64/blender,
RIGPOSE=/home/potato/miniconda3/bin/rigpose,
PY=/home/potato/miniconda3/bin/python3. conda BASE is the project env.
onnxruntime 1.25.1 CPU provider ONLY (an RTX 3060 exists but no GPU ORT
provider is installed — the honest mid-laptop-relevant baseline); the
pinned DWPose models are downloaded and live; local ruff 0.16.7 == CI's.

**The camera**: /dev/video0 exists (DroidCam v4l2loopback) but delivered NO
frames in S17 (ffmpeg timeout — the phone side was not streaming).
RE-VERIFY FIRST, one command:
`timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480
-i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`
If frames land, the live halves (capture glue + end-to-end budget) UNLOCK
this session; if silent again, everything buildable stays on replay frames,
honestly labeled — exactly like S17.

**S15/S16/S17 facts (do not reintroduce)**
- **Never render a VSE movie from any .py** (racy segfault, D-009); movie
  assembly is shell-glue ffmpeg + ffprobe parse-back.
- **Panels inherit the SCENE view transform** (render_panels doesn't stage
  it): stage Standard + dither 0 explicitly in any page-scene.
- **primitive_add deselects** (explicit select_set on every part + active);
  **canonical T-pose arm pivots sit wide** (narrow BEFORE hang poses);
  elbow bends need a pose-relative Rodrigues axis; **wide panels need a
  35 mm lens**; pose bones default QUATERNION; a SPHERE is rotationally
  symmetric; Bright=0.15 changes ZERO channels (use Contrast); compositor
  graph = `scene.compositing_node_group`; GPv3 strokes via
  `drawing.add_strokes`, closed = `cyclic`; LineArt only via ops
  LINEART_OBJECT + renames; created objects captured by DATABLOCK DIFF.
- **Bisect verdicts need run counts** (3 runs minimum per config).
- **Gate regexes**: grep-test BOTH the PASS and SKIPPED lines locally
  before pushing.
- Mimosa intercepts bash writes of ANY source-looking file — use
  Write/Edit; .py-side artifact MOVES live in xtask/*.sh (D-009). Known FP
  on record: "command injection" on `import struct` in pagedoc.py (D-003,
  no process-execution interface in core) — expect it at every commit,
  disclose, move on.
- **S17 live-mode facts (new)**: the stream envelope's timing fields are
  MEASUREMENTS — never assert their values in tests (docs/LIVE.md
  determinism statement; pose data IS byte-identical, envelope excluded).
  The FIRST stream line carries the ~2 s cold session load in `detect_ms`
  — consumers warm up or drop it. Tracked figures carry identity from the
  last FULL detection; `Figure.score` is 0.0 on tracked figures (it is a
  DETECTOR score) — the quality signal is mean body confidence (17 COCO
  body kps, floor 0.3). `kind=miss` lines are NORMAL stream events (reason
  recorded; consumers keep the last pose, never treat as a crash).
  Per-frame exceptions in the loop become miss lines — the loop never
  raises out. Do not "optimize" resolution — optimize cadence.

**Work order (claim in this sequence; stop cleanly wherever you run out)**

A. **P5-2's buildable half — the add-on stream consumer (webcam → rig
   puppeteer, driver side).**
   DESIGN FIRST in docs/LIVE.md (a P5-2 section in the source of record):
   consumer topology, the staleness policy, the incremental-tail design —
   BEFORE any engine code. The honest forks to decide in the design:
   - **Incremental tail**: `latest_pose_line` re-reads the whole file —
     O(file) per tick is wrong at 10–30 lines/s × ~20–50 KB lines. Design
     the offset-state reader in core/live.py FIRST (a `LiveTail.poll()`
     returning NEW events since the last call, torn-final-line safe,
     deterministic), CI-tested with fakes — then let the add-on use it.
   - **Apply path**: the latest `kind=pose` line applies through the REAL
     P1-6 apply path (pose_apply, rm_role_* mapping, mirror semantics
     untouched). Miss lines keep the last pose. A stale stream (no new
     lines past a threshold) keeps the last pose and REPORTS staleness
     honestly in the panel — the failsafe proper is P5-3, but the honest
     readout basis lands now.
   - **Blender timer**: `bpy.app.timers` pump, the P3-5 session.py
     precedent (background work never touches bpy; the main-thread pump
     applies). Panel: a small "Live driver" section (stream path,
     start/stop, staleness/conf readout) — no smoothing/latency UI yet.
   - **Budget instrumentation**: stream `age_ms` + apply cost = the
     REPLAY end-to-end number on THIS box; publish it labeled replay
     (capture → apply stays NEEDS-HUMAN until a camera stream; the
     Phase-5 <100 ms mid-laptop gate stays UNCLAIMED — never relabel).
   Then GATE: a new `xtask/live_*` gate (shell glue spawns `rigpose live`
   over a replay frames dir as a REAL subprocess; headless Blender runs
   the add-on driver against the stream; asserts apply fidelity at the
   0.5° bar class, miss handling, staleness reporting; per-line budget
   printed as RM_LIVE lines). Label every claim replay-not-live if the
   camera stayed silent. Deterministic consumer tests with a faked stream
   file (the P2-1/test_live.py pattern).

B. **If A lands early**: P5-3 skeleton (1€ smoothing wired between the
   stream and the apply — the P2-2 filter class already exists in core —
   plus the latency readout UI) OR the launch-kit start (P7-1 README hero
   refresh + P7-3 drafts) — your call by what's verifiable; never fake the
   live half.

C. **Cheap wins while gates run**
- Windowed UI screenshot attempt (best-effort ~1-in-4; S10..S17 all
  missed — replaces docs/media/ui_screenshot.png ONLY if genuine; never
  staged).
- Doc cross-checks: README status line (Phase 5 bullet now names P5-2),
  AGENT_DEMO.md numbers (still citing the P3-7 run — unchanged until the
  demo re-runs).
- Keep docs/LIVE.md and docs/BENCHMARKS.md in sync with reality as you go
  (the STYLE.md rule applies to every source of record).

**Non-negotiables (locked, from mission + CONVENTIONS)**
QUALITY ABOVE ALL. Anything 80% done is 0% shipped. LOCAL OR NOTHING
(zero outbound in default use; loopback 127.0.0.1 ONLY, opt-in).
Rig-agnostic or fake — ambiguity reported, never swallowed. Honest
claims: every claim cites a test, number, or GIF; synthetic/replay stays
labeled; media rule — allowlist extension in the SAME commit as the
media, visual check before shipping any image. Deterministic ops: keyed
sorts, same input = same output (tested). No subprocess strings in any
.py; no sockets in core (D-003); core dependency-free except lazy
[inference]. Conventions: Python ≥3.10-compat, Z-up / facing −Y /
character-left = +X, canonical roles frozen API, refusal codes public
API, ruff + pytest green before commits (status check, not a piped
tail). STATE logs append-only, timestamps REAL via `date -u`. Errors are
actionable — `(hint: ...)`, never trace dumps. Do NOT tune solve priors,
contact thresholds, or latency budgets against fixtures (D-008 —
measure, publish, never fit). Do not loosen gate thresholds to move
numbers. The style gate's expectation (dev box AND CI on 5.1): LINEART /
TONES / PAGES / FRAMES / EXPORT PDF+EPUB / ANIMATIC: PASS + the ffmpeg
assembly PASS — a SKIPPED in CI means the bump broke, not an honest
degradation. 18+ module stays default-OFF, Phase 6 scope.

**End of session (non-negotiable)**
Tick claimed tasks in STATE/TASKS.md (completed vs partially-done with
what remains). Append PROGRESS lines (real UTC via `date -u`). Top of
STATE/NEXT.md: "NEXT SESSION SHOULD:" — write it for Session 19 (P5-3 vs
the launch kit; say which and why). Update STATE/SESSIONS.md row. Commit
+ push (routine commits authorized; CI runs — keep it green, fix inline
like S12/S14/S15/S16/S17 did: download the run log, root-cause, fix the
real substance). If a Mimosa finding blocks: verify it's real, fix
inline, re-scan focused, commit again — and expect the pagedoc.py
import-struct FP every time.

**Known blockers (parked — do not burn time on them)**
Live capture device — NEEDS-HUMAN (DroidCam silent in S17; re-verify at
session start; the phone side must stream). PyPI + Blender Extensions +
MCP registry submissions — account-bound (LO); docs/PUBLISHING.md
runbooks. Windowed Blender GL stability — best-effort only (~1-in-4);
never fake media to compensate. P1-8a fallback estimator — parked
(D-011/D-012). P2-8 real walking clip — NEEDS-HUMAN
(out/video_smoke/SOURCES.md).
