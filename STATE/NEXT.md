# NEXT SESSION SHOULD …

1. **Open Phase 5 — P5-1 realtime ONNX pose (MediaPipe-class) in a side
   process.** Phase 4 is CLOSED (D-017: the Paper Dart manga shipped and
   reads end to end; the hero triptych shows all three styles on one
   moment; every claim cites a gate). Phase 5 is the last big
   capability gap before the launch kit (P7) — live puppeteering is the
   demo that sells the tool, and P5-1 is its foundation: the realtime
   detector side-process with a latency budget, feeding the EXISTING
   payload contract (D-009) so the add-on consumes it unchanged.
   Design-first in docs/ (detector choice + the process boundary + the
   latency budget), probe the chosen ONNX runtime headless before
   building, keep core dependency-free (the runtime enters as an
   optional extra, never a hard dep), and reuse the DWPose wrapper's
   faked-session test pattern for CI. If P5-1 lands early, P5-2
   (webcam → rig puppeteer) is the natural follow-on; alternatively the
   launch-kit start (P7-1/P7-3 drafts) is the honest fallback while any
   realtime piece is NEEDS-HUMAN (a webcam).

Watch out for:

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
- CI Blender bump — REMOVED (executed S15, green).
- Phase 4 — CLOSED (D-017); the manga media regenerates via
  `bash xtask/manga_build.sh` (media-guard pins the 8 files).
