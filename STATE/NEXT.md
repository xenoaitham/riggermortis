# NEXT SESSION SHOULD …

1. **P4-7 animatic mode** (or P4-8 if the manga ingredients feel urgent —
   the plan's order is P4-7 first): animatic from pose sequences — the
   page/bubble/bake machinery is all in place; probe-first anything the
   compositor/sequencer uncertain on 5.1 (the S12–S14 probe discipline
   keeps paying: page_probe caught three would-be-shipped bugs,
   bubble_probe killed the GPv3-fill assumption before it shipped).
2. **P4-8 pre-work if P4-7 closes early**: the 6-page manga + 3-style
   hero now has ALL ingredients verified AND SHIPPED (P4-1 materials,
   P4-2 line art, P4-3 tones, P4-4 pages incl. mixed-style, P4-5
   bubbles, P4-6 PDF/EPUB export, animated stability RM_TT PASS) —
   character-framing re-tune of the lineart radii is a data edit
   (docs/STYLE.md P4-2 notes); the hero material list is the remaining
   pre-work.
3. **Doc cross-checks**: docs/STYLE.md + docs/EXPORT.md after any
   change; mcp/README.md + DESIGN.md only if action kinds change;
   AGENT_DEMO.md numbers vs current gates (untouched by style work).

Watch out for:
- **5.1 API facts the probes keep earning (do not reintroduce the old
  ways)**: compositor graph = `scene.compositing_node_group` (node_tree
  GONE); unified ShaderNode classes in compositor trees but NO combine
  node; NO UV pass — coordinates from the rm_tones_uv view layer; GPv3
  LineArt only through ops LINEART_OBJECT + renames; created objects
  captured by DATABLOCK DIFF; EXACTLY ONE Group Output AFTER the
  interface socket; SUBTRACT operand order load-bearing; 5.1 Translate
  takes SEPARATE X/Y value inputs (the Vector input is GONE) and
  AlphaOver's inputs are Background/Foreground; the compositor CENTERS
  sub-buffer images before Translate applies — offsets need
  t = desired - (page - img)//2; a bare RGB node has no spatial extent
  — page backgrounds are FULL-PAGE solid images; the byte-identity
  round-trip is default-sRGB loads + Standard view transform + dither 0
  (Non-Color loads FAIL — Standard still encodes).
- **P4-5 API facts (S14 probes, do not regress)**: GPv3 stroke authoring
  = `drawing.add_strokes([n,...])` (points.add does not exist); the
  closed flag is `cyclic`; the GPv3 FILL is a dead end for data-authored
  shapes — material fills render ONLY on `use_lights=False` layers, the
  body is the unlit MESH (z-layered tail join); point `vertex_color`
  drives only the STROKE; bubble ink = open tail polyline so no ink edge
  inside the body; re-renders are PIXEL-identical but PNG file bytes
  differ in Blender's `tEXt RenderTime` stamp — pixel-level determinism
  is the standard (P4-4 precedent).
- **Style semantics (S13, load-bearing)**: per-panel/action style
  application is PERSISTENT in the scene — `render_panels` renders
  UNSTYLED panels first, styled after; the page-level `style` field is
  the base look. Don't "simplify" that order.
- **Pixel-diff baselines must share the pipeline**: compositor-FREE
  frames differ from compositor-ACTIVE ones at the anti-aliased
  silhouette — baselines for pixel-diff claims must share the pipeline.
- **Gates' env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — otherwise they 127.
- **D-014 revisit trigger is NOW MET in substance**: P4-2..P4-5 are all
  5.1-class (CI exercises only their SKIPPED halves on apt 4.0.2).
  Bumping CI to a 5.x tarball (actions/cache, one deliberate commit) is
  the documented decision to raise — Session 15 should do this FIRST so
  every subsequent gate runs with real pixels in CI.
- **Style gate in CI**: the P4-2..P4-6 halves legitimately report
  SKIPPED on apt 4.0.2 — do NOT "fix" CI by loosening the dev-box PASS
  expectations (dev box shows LINEART/TONES/PAGES/EXPORT: PASS with real
  pixels).
- Windowed Blender GL is flaky on this box (~1-in-4): S14's screenshot
  attempt MISSED (prior genuine capture stands, never staged).

Blocked / deferred (unchanged unless noted):
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- CI Blender bump — DECIDED (D-014); trigger met in substance (above).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
  instruments and the agent demo re-run unchanged on a real clip.
