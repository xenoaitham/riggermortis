# NEXT SESSION SHOULD …

1. **Camera re-verify FIRST, one command** (it decides everything):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly). The failsafe/duplicate-floor revisit trigger in LIVE.md
     becomes live-relevant. The launch copy's live halves
     (README live bullet, docs/LAUNCH.md, docs/TUTORIALS.md VTuber track)
     then get their first REAL number — update all of them in the same
     session, they are written to make that swap easy.
   - **Silent again (6th session)** → **Phase-6 openers: P6-4 + P6-5, the
     18+ enforcement pair.** WHY over P6-3 (benchmark packaging): the
     enforcement pair is camera-independent, self-contained, and closes the
     policy story the launch copy now leans on — "opt-in module off by
     default, proven via tests in both frontends" is currently only half
     true (SFW default + refusal plumbing are tested; the MODULE and its
     fresh-install/refusal-path enforcement tests are unwritten). P6-3
     collides with licensing/redistribution decisions only LO can make
     (the benchmark images are git-ignored Apache-2.0 locals; a PUBLIC
     suite is a policy call first, a packaging job second). P7-4/P7-5
     publishing stays account-bound (LO). Phase 7 remaining after S20:
     P7-4 (Blender Extensions listing), P7-5 (PyPI), P7-6 (the 60s cut +
     CI media-regen gate — the script in docs/LAUNCH.md is its shot list).

2. **Then read, in order**: STATE/TASKS.md, STATE/PROGRESS.md (S20 entries),
   STATE/DECISIONS.md, STATE/CONVENTIONS.md, STATE/SESSIONS.md,
   docs/LIVE.md, docs/BENCHMARKS.md, docs/POLICY.md. Register as
   **Session 21**, claim tasks with [S21], PROGRESS stamps via `date -u`
   ONLY (S20 caught itself writing placeholder minutes and replaced them
   with read values before commit — do not write a clock value you did not
   read).

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m pytest
   tests` (349 expected) + `make lint PY=/home/potato/miniconda3/bin/python3`,
   and verify the latest main CI run green (`gh run list --branch main`).
   Verify STEP 0 includes `gh run view` on the latest run if it is red:
   download the log, root-cause, fix the real substance FIRST.

Watch out for:

- **S20 launch-surface facts (new)**: docs/LAUNCH.md and docs/TUTORIALS.md
  are claim-bearing surfaces now — when a number changes, grep BOTH plus
  the README (three places carry the live numbers: README live bullet,
  LAUNCH.md drafts, TUTORIALS VTuber track). The 60s script in LAUNCH.md
  is P7-6's shot list — keep it cut-only-from-existing-footage. TUTORIALS
  commands were verified against cli.py + the registered add-on operators;
  re-verify if the CLI or panel changes.
- **P5-3 facts (do not reintroduce)**: smoothing is CORE-side
  (`live.LivePoseSmoother`) on the CANONICAL POSE per role per axis — the
  driver path is payload → `CanonicalPose.from_dict` → filter (STREAM
  space) → mirror → `pose_apply.apply_pose_object`; smoothing OFF is
  `pose_apply.apply_payload` byte-identical P5-2. Mirror order is PROVEN
  (odd-symmetric filter commutes; smooth-first for state stability).
  Timestamps are the envelope's `t_emit_wall`; gaps mean no update, long
  gaps open the filter. Defaults min_cutoff 1.0 Hz / beta 0.05 are
  DECLARED untuned (D-008) — never tune them against the gate fixture.
- **P5-3 failsafe contract**: stale_after keeps the last pose; SUSTAINED
  silence past failsafe_after (default 10 s, > stale_after validated)
  fires a ONE-TICK edge in `LiveConsumer` (re-armed by any new event) →
  driver clears to REST via `pose_apply.clear_pose`, resets the smoother
  (first recovery pose passes through EXACTLY), panel says FAILSAFE.
  Known limit (documented LIVE.md): producer RESTART with fresh seq space
  is suppressed by the P5-2 duplicate floor — remedy Stop/Start. Revisit
  only via a deliberate D-018-class amendment, never silently.
- **The gate's sweep instrument**: run A is the UNsmoothed control;
  J1/J2 gate-fed from run A's first REAL payload line; the variance bar is
  the P2-2 ≥4x instrument REUSED verbatim; constant-channel stillness is
  an epsilon (1e-20) assertion, NOT ==0.0. After ANY gate print change,
  grep-test BOTH the PASS and SKIPPED lines before pushing.
- **P5-2 facts (load-bearing)**: `LiveTail` (offset tail, torn-line safe,
  restart-safe via size-shrink AND newline-boundary) + `LiveConsumer`
  (latest-wins; batch ENDING in a miss applies nothing; envelope-seq
  duplicates never re-applied; stale = no new line past stale_after,
  default 2.0 s). Blender side is a THIN adapter; the pump never raises.
- **The replay budget definition**: published replay end-to-end is
  EMIT → APPLY — apply p95 ≈ 2.7–3.8 ms, emit→apply p50 ≈ 124–157 ms
  across gate runs (S18/S19; jitter normal — stalls land on the producer's
  DETECTOR frames, first line in the ~2 s cold window, never tuned away).
  On replayed files `age_ms` is the frame file's MTIME AGE — printed,
  never summed in. The <100 ms mid-laptop gate stays UNCLAIMED until a
  real stream; never relabel replay numbers live.
- **P5-1 facts (load-bearing)**: the detector CADENCE is the realtime
  lever — input downscale is a dead knob; the FIRST stream line carries
  the ~2 s cold load; `Figure.score` is 0.0 on tracked figures; the
  quality signal is mean body confidence (17 COCO kps, floor 0.3);
  kind=miss lines are NORMAL; envelope timing fields are MEASUREMENTS —
  never assert their values in tests.
- **5.1 API facts the probes keep earning**: compositor graph =
  `scene.compositing_node_group`; GPv3 strokes = `drawing.add_strokes`,
  closed = `cyclic`; LineArt only via ops LINEART_OBJECT + renames;
  created objects captured by DATABLOCK DIFF; EXACTLY ONE Group Output
  AFTER the interface socket; page backgrounds are FULL-PAGE solid images;
  byte-identity = default-sRGB loads + Standard view transform + dither 0.
- **PANELS INHERIT THE SCENE VIEW TRANSFORM**: stage Standard + dither 0
  explicitly in any page-scene.
- **Never render a VSE movie from any .py** (racy segfault, D-009); movie
  assembly is shell-glue ffmpeg + ffprobe parse-back. Primitive_add
  deselects (explicit select_set); T-pose arm pivots sit wide (narrow
  BEFORE hang poses); elbow bends need a pose-relative Rodrigues axis;
  wide panels need a 35 mm lens; pose bones default QUATERNION; a SPHERE
  is rotationally symmetric; Bright=0.15 changes ZERO channels (use
  Contrast). Bisect verdicts need run counts (3 runs minimum per config).
- **Gates' env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose,
  PY=/home/potato/miniconda3/bin/python3 — else they 127. The live gate
  needs out/live_probe/smoke_frames + out/real_rigs/metarig.rig.json
  (git-ignored) or it answers `RM_LIVE GATE: SKIPPED (...)` honestly,
  exit 0. The style gate on 5.1 must show LINEART/TONES/PAGES/FRAMES/
  ANIMATIC/EXPORT PASS in CI (SKIPPED there = the bump broke).
- **Media rules**: existing launch media (boom.gif, walk GIFs,
  agent_turntable.gif, ui_screenshot.png, manga set) are
  pipeline-generated — reference, never hand-edit; ANY new media ships
  with the allowlist extension in the SAME commit + a visual check. The
  WALKRIGS block is generator-owned (xtask/walk_docs.py + out/p28
  manifests): S20 corrected its stale D-015 text via the GENERATOR, then
  regenerated (rows byte-identical) — keep that discipline.
- **Mimosa**: intercepts bash writes of ANY source-looking file — use
  Write/Edit; expect the pagedoc.py `import struct` FP at every commit;
  S20 caught one compound-command FP (backup+diff pipeline misread as a
  source write) — restructure the command and move on.
- **STATE timestamps are REAL**: `date -u` before every PROGRESS append.

Blocked / deferred (unchanged unless noted):

- Live capture device — NEEDS-HUMAN (DroidCam silent in S17–S20; the phone
  side must stream; P5-4 and the live capture→apply measurement wait on
  it — everything buildable shipped without it).
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md).
- Phase 4 — CLOSED (D-017); manga media regenerates via
  `bash xtask/manga_build.sh` (media-guard pins the 8 files).
- P5-1..P5-3 DONE (S17/S18/S19); P5-4 (recorded demo) needs the camera.
- Phase 7 after S20: P7-1/P7-2/P7-3 DONE; P7-4/P7-5 account-bound; P7-6
  waits on a recorded-cut session (shot list exists in docs/LAUNCH.md).
