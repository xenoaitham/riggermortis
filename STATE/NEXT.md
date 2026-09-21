# NEXT SESSION SHOULD …

1. **P5-2's buildable half: the add-on stream consumer (webcam → rig
   puppeteer, driver side).** P5-1 shipped the side process (docs/LIVE.md
   is the Phase-5 source of record): `rigpose live` emits one D-009
   payload-v2 line per frame; measured budget full ≈ 550 ms / tracked-every-5
   p50 ≈ 88 ms / pose-only ≈ 90 ms flat (BENCHMARK:LIVE block, i5 CPU, honest
   no-GPU-provider note). S18 builds the CONSUMER: an add-on timer that
   tails the stream file (`riggermortis.live.latest_pose_line` /
   read_live_lines — the torn-tail-tolerant reader exists and is
   CI-tested), applies the latest pose line through the REAL P1-6 apply
   path, and instruments the end-to-end budget (the stream's `age_ms`
   carries capture age already). Fully buildable and verifiable against a
   RECORDED stream (replay a frames dir through `rigpose live`, drive
   Blender headless, gate on apply fidelity + per-frame budget); the LIVE
   capture half stays gated on the camera (below). If the stream consumer
   lands early: P5-3's smoothing/latency UI is the next buildable half;
   the launch-kit drafts (P7-1/P7-3) are the honest fallback.

Watch out for:

- **P5-1 facts (new, do not reintroduce)**: the detector CADENCE is the
  realtime lever — input downscale is a dead knob (the ONNX inputs are
  fixed-size; native vs 640w differed ~2–4%); a `rigpose live` consumer
  must expect the FIRST line to carry the ~2 s cold session load in
  `detect_ms` (warm up or drop it); tracked lines carry figure identity
  from the last FULL detection (labels ride through — apply by label
  stays correct); `Figure.score` is 0.0 on tracked figures (it is a
  DETECTOR score) — judge quality by the body-conf floor (0.3, the
  17 COCO body kps); misses are NORMAL stream events (kind=miss with a
  reason — keep the previous pose, never treat as a crash); the stream
  envelope's timing fields are MEASUREMENTS — never assert values on
  them in tests (docs/LIVE.md determinism statement).
- **The camera is still the live-mode blocker**: /dev/video0 exists
  (DroidCam v4l2loopback) but delivered NO frames (S17 ffmpeg probe,
  timeout); `xtask/live_capture.sh` ships with the UNTESTED-no-stream
  label. NEEDS-HUMAN: start the DroidCam phone-side stream (or plug a
  real camera), then re-run the capture half and measure P5-2's
  end-to-end budget for real. Until then nothing live gets labeled live
  (the P2-8/D-015 discipline).
- **5.1 API facts the probes keep earning (do not reintroduce the old
  ways)**: compositor graph = `scene.compositing_node_group` (node_tree
  GONE); GPv3 strokes = `drawing.add_strokes([n,...])`, closed flag is
  `cyclic`, the GPv3 FILL is a dead end for data-authored shapes (bubble
  bodies are the z-layered unlit MESH); GPv3 LineArt only through ops
  LINEART_OBJECT + renames; created objects captured by DATABLOCK DIFF;
  EXACTLY ONE Group Output AFTER the interface socket; 5.1 Translate
  takes SEPARATE X/Y value inputs; the compositor CENTERS sub-buffer
  images before Translate (`t = desired - (page - img)//2`); page
  backgrounds are FULL-PAGE solid images; byte-identity = default-sRGB
  loads + Standard view transform + dither 0.
- **PANELS INHERIT THE SCENE VIEW TRANSFORM** (render_panels does not
  stage it — S16 finding): the default AgX crushes light worlds into
  dark grey; a page-scene author stages Standard + dither 0 explicitly
  (the manga driver does; see docs/STYLE.md P4-8 as-built).
- **S15 animatic facts (still load-bearing)**: the 5.1 VSE MOVIE-APPEND
  is a recorded DEAD END (racy ~2/3 segfault, config-independent — never
  render a VSE movie from any .py; a segfault cannot be caught); movie
  assembly = shell-glue ffmpeg + ffprobe parse-back (D-009). 5.0+ movie
  output = `render.image_settings.media_type='VIDEO'` (file_format=
  'FFMPEG' assignment FAILS on 5.x). Pose bones default QUATERNION
  (euler keys silently no-op); a SPHERE is rotationally symmetric (~no
  pixel motion); Bright=0.15 changes ZERO channels through a dark scene
  (use Contrast for compositor A/B checks — the group is ACTIVE in
  stills AND animation renders). Animatic builder = per-frame STILLS
  through the caller's certified bake; `rm_page` refusal; re-apply the
  base look before a re-render (persistent-style semantics).
- **S16 build facts (new)**: primitive_add selection semantics — a loop
  of mesh creations then `join()` needs EXPLICIT select_set on every
  part plus a chosen active (the one-eyed-character catch); canonical
  T-pose arm pivots sit wide of the torso — narrow the arm chain BEFORE
  authoring hang poses or the arms float; elbow bends need a
  pose-relative axis (Rodrigues about forearm×pull), not a world-axis
  guess; wide panels (≈2:1) need a wide lens (35 mm) or heads/ground
  props leave the ±13.5° vertical field at 50 mm.
- **Bisect verdicts need run counts**: S15 burned rounds on single-run
  "passes" that were statistical escapes. Any crash/flake claim: 3 runs
  minimum per config before believing a mitigation.
- **Gate regex vs probe line format**: after ANY probe print change,
  grep-test BOTH the PASS and SKIPPED lines locally before pushing (the
  S12/S14/S15 discipline; the FRAMES check joined the grep-tested set).
- **Gates' env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — otherwise they 127.
- **CI runs 5.1.0 (D-014, green) + ffmpeg since S16's 4138b82**: the
  style gate's LINEART/TONES/PAGES/FRAMES/EXPORT/ANIMATIC halves must
  show PASS in CI — SKIPPED there means the bump broke. The assembly
  half should now PASS on the runner (record the job-time delta vs the
  measured 34m27s). The SKIPPED degradation paths STAY in the gate code
  (older-Blender honesty).
- **Style semantics**: per-panel/per-shot style application is
  PERSISTENT — pages/animatics render base-look units first; a re-render
  re-applies the base look first. Don't "simplify" that order.
- **Pixel-diff baselines must share the pipeline** (compositor-free vs
  compositor-active AA silhouettes differ).
- Windowed Blender GL is flaky on this box (~1-in-4): S16's screenshot
  attempt MISSED (the S5 genuine capture stands, never staged).

Blocked / deferred (unchanged unless noted):
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
  instruments and the agent demo re-run unchanged on a real clip.
- NEW (S17) — live capture device: /dev/video0 (DroidCam) delivers no
  frames; phone-side stream needed for P5-2's live + end-to-end
  measurement halves (see the camera bullet above).
- Phase 4 — CLOSED (D-017); the manga media regenerates via
  `bash xtask/manga_build.sh` (media-guard pins the 8 files).
- P5-1 — DONE (S17): side process + measured budget + contract tests;
  the <100 ms Phase-5 gate is deliberately unclaimed until P5-2 measures
  end-to-end.
