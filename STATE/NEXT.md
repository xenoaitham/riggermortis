# NEXT SESSION SHOULD …

1. **P4-8 — the 6-page manga + 3-style hero** (Phase 4's close-out): every
   ingredient is verified AND shipped (P4-1..P4-7, animated stability RM_TT
   PASS, export parse-back, animatic timing). Pre-work notes: the
   character-framing lineart radii re-tune is a DATA edit (docs/STYLE.md
   P4-2 — the gate frames render ink sub-pixel at 4 m; real character
   framing wants the per-style re-tune the note promises); the hero
   material list is per-panel `style` DATA on the existing page schema
   (mixed-style pages are gate-proven); the 6-page story + layouts design
   in docs/STYLE.md first (wordless, readable, charming — the Phase-4
   gate), then DATA + renders into docs/manga/ + the media-guard
   allowlist extension in the same commit as any shipped media.

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
- **S15 animatic facts (new)**: the 5.1 VSE MOVIE-APPEND is a recorded
  DEAD END (racy ~2/3 segfault, config-independent — never render a VSE
  movie from any .py; a segfault cannot be caught); movie assembly =
  shell-glue ffmpeg + ffprobe parse-back (D-009). 5.0+ movie output =
  `render.image_settings.media_type='VIDEO'` (file_format='FFMPEG'
  assignment FAILS on 5.x; animation output is named
  `<base><start>-<end><ext>`). Pose bones default QUATERNION (euler keys
  silently no-op); a SPHERE is rotationally symmetric (~no pixel motion);
  Bright=0.15 changes ZERO channels through a dark scene (use Contrast
  for compositor A/B checks — the group is ACTIVE in stills AND
  animation renders). Animatic builder = per-frame STILLS through the
  caller's certified bake; `rm_page` refusal; re-apply the base look
  before a re-render (persistent-style semantics).
- **Bisect verdicts need run counts**: S15 burned rounds on single-run
  "passes" that were statistical escapes (13 crashes / 16 runs only
  showed the pattern after 3x-per-config re-runs). Any crash/flake
  claim: 3 runs minimum per config before believing a mitigation.
- **Gate regex vs probe line format**: after ANY probe print change,
  grep-test BOTH the PASS and SKIPPED lines locally before pushing (the
  S12/S14 class — S15 grep-tested before pushing, keep it that way).
- **Gates' env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — otherwise they 127.
- **CI runs 5.1.0 now (D-014 executed, S15)**: the style gate's
  LINEART/TONES/PAGES/EXPORT/ANIMATIC halves must show PASS in CI —
  SKIPPED there means the bump broke, not an honest degradation. First
  bump run: 10m20s (includes the one-time tarball download; cache
  restores afterwards). The SKIPPED degradation paths STAY in the gate
  code (older-Blender honesty).
- **Style semantics**: per-panel/per-shot style application is
  PERSISTENT — pages/animatics render base-look units first; a re-render
  re-applies the base look first. Don't "simplify" that order.
- **Pixel-diff baselines must share the pipeline** (compositor-free vs
  compositor-active AA silhouettes differ).
- Windowed Blender GL is flaky on this box (~1-in-4): S15's screenshot
  attempt MISSED (the S5 genuine capture stands, never staged).

Blocked / deferred (unchanged unless noted):
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
  instruments and the agent demo re-run unchanged on a real clip.
- CI Blender bump — REMOVED (executed S15, green).
