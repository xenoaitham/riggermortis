# NEXT SESSION SHOULD …

1. **P5-3: smoothing + the latency/failsafe layer — the close-out of
   Phase 5's buildable surface.** WHY THIS over the launch kit (P7-1/P7-3):
   P5-2 shipped the consumer contract (S18), and P5-3 is the last piece that
   is fully buildable and verifiable WITHOUT the camera — every further
   "live" claim except the real capture→apply number is blocked on the
   DroidCam phone side (NEEDS-HUMAN, silent in S17 AND S18), while the
   launch kit's hero numbers get stronger once Phase 5's buildable halves
   are all in. Scope, in build order:
   - **1€ smoothing between the stream and the apply** — core
     `smoothing.py` (`OneEuroFilter`, `smooth_pose_frames`) already exists
     and is CI-tested; wire it through the P5-2 consumer contract as an
     optional conditioning step ON THE CANONICAL POSE before apply (per
     role, partial observation preserved — the P2-2 semantics), NOT as a
     bone-space hack after apply. Deterministic CI tests with faked jitter
     streams; the defaults stay order-of-magnitude (D-008 — measure,
     publish, never fit; there is still no real-motion stream to tune
     against, so SMOOTHING CLAIMS STAY REPLAY-LABELED).
   - **Latency/smoothing UI in the Live driver panel**: smoothing
     on/off + min_cutoff/beta readouts (or preset row), the existing
     apply/emit→apply readout promoted into a small "latency" block —
     nothing more; no graph, no false precision.
   - **The failsafe proper** (the P5-2 stub keeps the last pose + reports
     STALE): on sustained staleness, drop to a defined safe state —
     proposal: hold N seconds → clear pose to rest with an honest panel
     line (the operator path already exists: `pose_apply.clear_pose`).
     Threshold order-of-magnitude, documented, CI-tested with the faked
     clock. Decide the exact policy in docs/LIVE.md FIRST (design before
     engine, the S18 discipline).
   - Gate: extend `make live-verify` with a smoothing-sweep run (same
     replay frames, smoothing on/off, assert the applied pose curves are
     smoother by the P2-2 variance instrument and fidelity stays within
     the 0.5° bar class) + RM_LIVE lines for both. Grep-test PASS and
     SKIPPED lines before pushing.
2. If P5-3 lands early: start the **launch kit** (P7-1 README hero
   refresh + P7-3 drafts) — by then Phases 0–4 are closed, P5's
   buildable halves are in, and every launch claim still cites a
   gate/number/GIF.

Watch out for:

- **P5-2 facts (new, do not reintroduce)**: the consumer contract is
  `LiveTail` (offset state, torn-final-line safe, restart-safe: size-shrink
  OR non-newline byte before the offset) + `LiveConsumer` (latest-wins per
  poll; a batch ENDING in a miss applies nothing; envelope-seq duplicates
  after a replay are never re-applied; stale = no new line past
  `stale_after`, default 2.0 s). The Blender side is a THIN adapter — the
  ONLY bpy touch is the apply, main-thread; the pump never raises out of
  the timer (apply failures land in the status line with a hint). The
  stream line IS payload-v2: it goes through `pose_apply.apply_payload`
  unmodified, figure label rides through, mirror is the scene toggle.
- **The replay budget definition**: on replayed files the envelope's
  `age_ms` is the frame file's MTIME AGE, not capture latency — the
  published replay end-to-end is EMIT → APPLY (S18 measured: apply p95
  3.8 ms, p50 157 ms, stalls land on the producer's detector frames, first
  line in the ~2 s cold window). With a real camera, capture → apply =
  age_ms + poll lag + apply. Never relabel replay numbers live; the
  Phase-5 <100 ms mid-laptop gate stays UNCLAIMED until a real stream.
- **The camera is still the live blocker**: /dev/video0 (DroidCam
  v4l2loopback) re-verified silent in S18 (ffmpeg timeout, zero packets);
  `xtask/live_capture.sh` ships with the UNTESTED-no-stream label.
  NEEDS-HUMAN: start the DroidCam phone-side stream (or plug a real
  camera), then re-run the capture half and measure the true end-to-end
  budget. S17 AND S18 shipped everything buildable without it.
- **P5-1 facts (still load-bearing)**: the detector CADENCE is the
  realtime lever — input downscale is a dead knob (fixed ONNX input
  sizes); the FIRST stream line carries the ~2 s cold session load in
  `detect_ms` (warm up or drop it); tracked lines carry figure identity
  from the last FULL detection; `Figure.score` is 0.0 on tracked figures —
  judge quality by the body-conf floor (0.3); misses are NORMAL stream
  events (keep the pose, never a crash); envelope timing fields are
  MEASUREMENTS — never assert their values in tests (pose data IS
  byte-identical; the envelope is excluded from determinism).
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
- **Gate regex vs probe line format**: after ANY gate/probe print change,
  grep-test BOTH the PASS and SKIPPED lines locally before pushing.
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
  disclose and move on. S18's one advisory (shell `$REPO` interpolation in
  live_verify.sh) was restructured to an env-var pass.

Blocked / deferred (unchanged unless noted):
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
  instruments and the agent demo re-run unchanged on a real clip.
- Live capture device — NEEDS-HUMAN (DroidCam silent in S17 and S18;
  phone side must stream; P5-2's live + end-to-end measurement halves
  wait on it — everything buildable shipped without it).
- Phase 4 — CLOSED (D-017); manga media regenerates via
  `bash xtask/manga_build.sh` (media-guard pins the 8 files).
- P5-1, P5-2 — DONE (S17/S18); P5-4 (the 5-minute recorded live demo)
  needs the camera: it is the last Phase-5 piece after P5-3.
