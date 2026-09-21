# NEXT SESSION SHOULD …

1. **The launch kit (P7-1 README hero refresh + P7-3 docs/LAUNCH.md drafts)
   — the honest fork while the camera stays silent.** WHY THIS over P5-4:
   P5-4 (the 5-minute recorded live demo) NEEDS a real camera stream —
   /dev/video0 (DroidCam v4l2loopback) has delivered ZERO frames in S17,
   S18, AND S19 (re-verified at every session start: ffmpeg timeout, no
   packets; the phone side is not streaming — NEEDS-HUMAN), and with P5-3
   DONE every camera-independent Phase-5 piece is shipped and gate-verified.
   The launch kit compounds regardless of the camera: every claim it needs
   now cites a gate/number/GIF (Phases 0–4 closed, P5-1/P5-2/P5-3 shipped
   on the buildable path, all replay/synthetic-labeled honestly). Scope:
   - **P7-1**: refresh the README hero + honest-limitations block against
     the CURRENT numbers (pose-verify ≤0.5°, walk lock ratios ≥12x, manga
     pipeline, live budget table + the P5-3 sweep numbers — every one
     already published in docs/BENCHMARKS.md; cite, never embellish; the
     <100 ms live gate stays UNCLAIMED in launch copy too).
   - **P7-3**: docs/LAUNCH.md drafts (Show-HN, BlenderNation, r/blender,
     tweet thread, 60s video script) — each claim in each draft cites its
     test/gate/GIF; label the live half as "measured on replay, real-camera
     number pending" exactly like the repo does.
   - If the camera COMES ALIVE first (check at STEP 0 with the one-liner
     below), flip the order: P5-4 demo prep (record capture → apply,
     measure the true end-to-end budget, claim or retire the <100 ms
     mid-laptop gate) — that would also un-block the launch copy's live
     claims.
2. Camera re-verify FIRST, one command:
   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`
   Frames landing = the live halves unlock; silence = launch kit, exactly
   as planned above.

Watch out for:

- **P5-3 facts (new, do not reintroduce)**: smoothing is CORE-side
  (`live.LivePoseSmoother`) on the CANONICAL POSE per role per axis — the
  driver path is payload → `CanonicalPose.from_dict` → filter (STREAM
  space) → mirror → `pose_apply.apply_pose_object`; smoothing OFF is
  `pose_apply.apply_payload` byte-identical P5-2. Mirror order is PROVEN
  (the 1€ filter is odd-symmetric: smooth(mirror(p)) == mirror(smooth(p))
  exactly, CI-tested); smooth-first was chosen so a mid-session mirror
  toggle needs no filter-state surgery. Timestamps are the envelope's
  `t_emit_wall`; gaps mean no update, long gaps open the filter (snap
  through). Defaults min_cutoff 1.0 Hz / beta 0.05 are DECLARED untuned
  starting points (D-008) — there is still no real-motion stream, so
  smoothing claims stay replay/synthetic-labeled; do not tune them against
  the gate fixture.
- **P5-3 failsafe contract**: stale_after keeps the last pose (P5-2
  semantics unchanged); SUSTAINED silence past failsafe_after (default
  10 s, must be > stale_after — core validates) fires a ONE-TICK edge in
  `LiveConsumer` (re-armed by any new event) and the driver clears to REST
  via `pose_apply.clear_pose`, resets the smoother (recovery passes the
  first pose through EXACTLY), and the panel says FAILSAFE; a continuing
  stream re-applies automatically. **Known limit, documented in LIVE.md**:
  a producer RESTART with a fresh seq space is suppressed by the P5-2
  duplicate floor (replayed-data semantics) — operator remedy is Stop/Start
  on the panel. Revisit trigger: if the P5-4 demo shows this hurts real
  recovery, amend the S18 duplicate contract deliberately (D-018 class:
  new tests + LIVE.md amendment), never silently.
- **The gate's sweep instrument**: run A stays the UNsmoothed P5-2 control
  (budget rows carry a smoothed flag now, asserted 0 there); J1/J2 are
  gate-fed (no producer) from a fixture derived from run A's first REAL
  payload line — variance bars are the P2-2 ≥4x instrument reused
  verbatim, NOT a new threshold. Constant-channel stillness is asserted
  with an epsilon (1e-20), not ==0.0 — summing identical floats rounds
  (the gate caught this pre-ship). After ANY gate/probe print change,
  grep-test BOTH the PASS and SKIPPED lines before pushing (done in S19:
  missing frames and missing Blender both answer `RM_LIVE GATE:
  SKIPPED (...)`, exit 0).
- **P5-2 facts (still load-bearing)**: `LiveTail` (offset state, torn-line
  safe, restart-safe via size-shrink AND newline-boundary check) +
  `LiveConsumer` (latest-wins; a batch ENDING in a miss applies nothing;
  envelope-seq duplicates never re-applied; stale = no new line past
  stale_after, default 2.0 s). The Blender side is a THIN adapter — the
  only bpy touches are the apply, the failsafe clear, and the readout, on
  the main thread; the pump never raises. The stream line IS payload-v2.
- **The replay budget definition**: the published replay end-to-end is
  EMIT → APPLY (S19 run: apply p95 ≈ 2.7 ms, emit→apply p50 ≈ 124 ms,
  stalls land on the producer's detector frames, first line in the ~2 s
  cold window — run-to-run jitter is normal, never tune it away). On
  replayed files the envelope's age_ms is the frame file's MTIME AGE —
  printed informationally, never summed in. The Phase-5 <100 ms
  mid-laptop gate stays UNCLAIMED until a real stream.
- **P5-1 facts (still load-bearing)**: the detector CADENCE is the
  realtime lever — input downscale is a dead knob; the FIRST stream line
  carries the ~2 s cold session load; tracked lines carry identity from
  the last FULL detection; `Figure.score` is 0.0 on tracked figures; the
  quality signal is mean body confidence (17 COCO kps, floor 0.3); misses
  are NORMAL stream events; envelope timing fields are MEASUREMENTS —
  never assert their values in tests.
- **5.1 API facts the probes keep earning (do not reintroduce the old
  ways)**: compositor graph = `scene.compositing_node_group` (node_tree
  GONE); GPv3 strokes = `drawing.add_strokes([n,...])`, closed flag is
  `cyclic`; GPv3 LineArt only through ops LINEART_OBJECT + renames;
  created objects captured by DATABLOCK DIFF; EXACTLY ONE Group Output
  AFTER the interface socket; page backgrounds are FULL-PAGE solid images;
  byte-identity = default-sRGB loads + Standard view transform + dither 0.
- **PANELS INHERIT THE SCENE VIEW TRANSFORM** (render_panels does not
  stage it): a page-scene author stages Standard + dither 0 explicitly.
- **S15 animatic facts (still load-bearing)**: NEVER render a VSE movie
  from any .py (racy segfault, D-009); movie assembly = shell-glue ffmpeg
  + ffprobe parse-back. Pose bones default QUATERNION (euler keys no-op);
  a SPHERE is rotationally symmetric; Bright=0.15 changes ZERO channels
  (use Contrast for compositor A/B checks). Animatic builder = per-frame
  STILLS through the caller's certified bake; re-apply the base look
  before a re-render.
- **S16 build facts**: primitive_add deselects (explicit select_set on
  every part + active); canonical T-pose arm pivots sit wide (narrow
  BEFORE hang poses); elbow bends need a pose-relative Rodrigues axis;
  wide panels need a 35 mm lens.
- **Bisect verdicts need run counts**: 3 runs minimum per config before
  believing a crash/flake mitigation (the S15 burn).
- **Gates' env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — otherwise they 127. The live gate also needs
  the pinned models + out/live_probe/smoke_frames + out/real_rigs/
  metarig.rig.json (git-ignored; answers RM_LIVE GATE: SKIPPED honestly
  without — grep-tested both paths).
- **CI runs 5.1.0 (D-14 bump, green)**: the style gate's LINEART/TONES/
  PAGES/FRAMES/EXPORT/ANIMATIC halves must show PASS in CI — SKIPPED
  there means the bump broke. The assembly half PASSES on the runner.
- **Style semantics**: per-panel/per-shot style application is PERSISTENT
  — pages/animatics render base-look units first; a re-render re-applies
  the base look first.
- **Mimosa**: expect the pagedoc.py `import struct` FP at every commit;
  disclose and move on. S18's shell-interpolation advisory was
  restructured to an env-var pass; S19 had no new findings.
- **STATE timestamps are REAL**: `date -u` before every PROGRESS append
  (S19 caught itself stamping guessed times mid-session and re-stamped
  before commit — do not write a clock value you did not read).

Blocked / deferred (unchanged unless noted):
- Live capture device — NEEDS-HUMAN (DroidCam silent in S17, S18 AND S19;
  phone side must stream; P5-4 and the live capture→apply measurement
  wait on it — everything buildable shipped without it).
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md).
- Phase 4 — CLOSED (D-017); manga media regenerates via
  `bash xtask/manga_build.sh` (media-guard pins the 8 files).
- P5-1, P5-2, P5-3 — DONE (S17/S18/S19); P5-4 (the 5-minute recorded live
  demo) needs the camera: it is the last Phase-5 piece.
