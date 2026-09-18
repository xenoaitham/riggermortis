# NEXT SESSION SHOULD …

1. **P4-5 speech bubbles** (or P4-6 export — P4-5 first is the plan's
   order): bubbles will likely reuse the GPv3 surface (the add-operator
   enum EMPTY/STROKE paths — the P4-2 probe's layer/frames/drawing API
   notes apply) plus a text-object or GP text approach; PROBE FIRST
   (the S12/S13 discipline keeps paying: page_probe caught three
   would-be-shipped bugs). The tail is the page: bubble placement data
   can hang off the P4-4 page preset schema (a `bubbles` field or a
   panel-level field — design in docs/STYLE.md first).
2. **P4-6 export** (PDF/EPUB/PNG): the P4-4 page PNG is the unit —
   PDF assembly must stay OUTSIDE Blender (D-009/D-003: no subprocess in
   .py; shell glue or a stdlib writer; probe what exists honestly).
3. **P4-8 pre-work if either closes early**: the 6-page manga + 3-style
   hero now has ALL its ingredients verified (P4-1 materials, P4-2 line
   art, P4-3 tones, P4-4 pages incl. mixed-style, animated stability
   RM_TT PASS) — character framing re-tune of the lineart radii is a
   data edit (docs/STYLE.md P4-2 notes).
4. **Doc cross-checks**: docs/STYLE.md after P4-5; mcp/README.md +
   DESIGN.md after any action-kind change (S13 added apply_style to both
   + the walkthrough); BENCHMARKS.md untouched by style work.

Watch out for:
- **5.1 API facts the probes keep earning (do not reintroduce the old
  ways)**: compositor graph = `scene.compositing_node_group` (node_tree
  GONE); unified ShaderNode classes in compositor trees but NO combine
  node; NO UV pass — coordinates from the rm_tones_uv view layer; GPv3
  LineArt only through ops LINEART_OBJECT + renames; created objects
  captured by DATABLOCK DIFF; EXACTLY ONE Group Output AFTER the
  interface socket; SUBTRACT operand order load-bearing; **5.1
  Translate takes SEPARATE X/Y value inputs (the Vector input is GONE)
  and AlphaOver's inputs are Background/Foreground**; **the compositor
  CENTERS sub-buffer images before Translate applies — offsets need
  t = desired - (page - img)//2**; **a bare RGB node has no spatial
  extent — page backgrounds are full-page solid images**; **the
  byte-identity round-trip is default-sRGB loads + Standard view
  transform + dither 0 (Non-Color loads FAIL — Standard still
  encodes)**.
- **Style semantics (S13, load-bearing)**: per-panel/action style
  application is PERSISTENT in the scene — `render_panels` renders
  UNSTYLED panels first, styled after; the page-level `style` field is
  the base look. Don't "simplify" that order.
- **Pixel-diff baselines must share the pipeline**: compositor-FREE
  frames differ from compositor-ACTIVE ones at the anti-aliased
  silhouette (the black rim ring evaluates 2-3px wider without the
  compositor) — RM_TT's first baselines lied until this was measured.
- **Gates' env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — otherwise they 127.
- **D-014 revisit trigger keeps approaching**: P4-2/P4-3/P4-4 are all
  5.1-class features (CI exercises only their SKIPPED halves on apt
  4.0.2). If P4-5 continues the trend, bumping CI to a 5.x tarball is a
  deliberate documented decision — one commit, actions/cache.
- **Style gate in CI**: the P4-2/P4-3/P4-4 halves legitimately report
  SKIPPED on apt 4.0.2 — do NOT "fix" CI by loosening the dev-box PASS
  expectations (dev box shows LINEART: PASS / TONES GRAPH: PASS / PAGES:
  PASS with real pixels).
- Windowed Blender GL is flaky on this box (~1-in-4): S13's screenshot
  attempt MISSED (prior genuine capture stands, never staged).

Blocked / deferred (unchanged unless noted):
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P1-8a fallback estimator — parked (D-011/D-012).
- CI Blender bump — DECIDED (D-014); see the revisit-trigger note above.
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
  instruments and the agent demo re-run unchanged on a real clip.
