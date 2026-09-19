# Style system

Presets are DATA FILES, looks are DETERMINISTIC builders, and every claim
cites the gate (`make style-verify`) or a probe. No hand-drawn media is ever
shipped as pipeline output.

## P4-1 — toon materials (shipped)

`presets/{anime,manga,western}.json` + `addon/style.py::build_toon_material`:
banded N·L diffuse through a double-stop ColorRamp (hard cel edges), optional
rim via Layer Weight facing (the rim COLOR lives in the Mix's B input, so a
dark ink contour works like a bright rim), Emission strength 1 = unlit by
construction (the look is scene-independent). Rebuild is byte-deterministic
(remove-then-create, fixed node names/order — the `.001`-suffix and slot-0
hijack traps are recorded in the module docstring).

## P4-2 — Grease Pencil line art (design, probe-verified 2026-09-18 S12)

The capability question was a real unknown (Grease Pencil was rewritten —
GPv3 — across 4.3→5.x). Probe first, design second; findings from
`xtask/lineart_probe.py` on Blender 5.1.0 headless (`RM_LINEART` lines):

- **YES, scriptable line art exists — the GPv3 `LINEART` modifier.**
  `bpy.types.GreasePencilLineartModifier` is present; every GP object is the
  new type (`GREASEPENCIL`, no `grease_pencil_modifiers` stack — the legacy
  GPv2 object class is GONE in 5.1). The modifier carries the full classic
  property set (`source_object`/`source_type`, `use_contour`, `use_crease`,
  `crease_threshold`, `radius`, `opacity`, `target_layer`, `target_material`,
  chaining, levels, overscan, cache).
- **The one proven wiring is the ops preset** `grease_pencil_add(
  type='LINEART_OBJECT')`: it creates the GP object with a layer that owns
  an initial frame, a `Black` material, and a `LINEART` modifier with
  `target_layer`/`target_material`/`source_object` all resolved → 2 strokes
  evaluated on a sphere, `frames->drawing->strokes`.
- **Data-API replication is BLOCKED by Blender, recorded honestly**: a bare
  `bpy.data.grease_pencils.new()` datablock with a hand-made layer+frame and
  every prop wired still evaluates 0 strokes; assigning `target_material`
  raises `RuntimeError: Cannot assign material '…', it has to be used by the
  Grease Pencil object already` even when the material IS in the GP's
  material list. The ops preset does whatever internal registration we
  cannot. Therefore the builder OPS-CREATES, then RENAMES everything to
  canonical `rm_*` names (deterministic, remove-first discipline as P4-1).
- **Freestyle is a dead end in 5.1, recorded so it is never faked**: the
  only engine enum entry is `BLENDER_EEVEE`; enabling Freestyle draws ZERO
  changed pixels and Blender's internal Freestyle Python stage crashes
  (`'NoneType' object has no attribute 'use_chaining'`).
- **Composition over P4-1 is proven, headless**: manga toon material on the
  sphere + the LineArt ink overlay in the SAME scene renders bands + ink in
  ONE EEVEE frame — 167,321 changed / 165,623 darkened channels vs the
  material-only render, visuals checked (ink ring over 2-band fills; the
  probe's `radius=3.0` was deliberately scene-absurd, which is exactly why
  radius is preset DATA).

### Line-art preset data (additive `"lineart"` field, schema format 1)

```json
"lineart": {
  "radius": 0.005,          // stroke HALF-width, WORLD METERS (scene-scale!)
  "opacity": 1.0,           // 0..1
  "contour": true,          // silhouette contours
  "crease": true,           // crease edges above the threshold
  "crease_threshold": 1.57, // radians, pi/2 = only sharp edges
  "color": "#000000"        // ink color (#rrggbb, like all preset colors)
}
```

Optional field on the EXISTING preset files (one style = one file; P4-3
tones will extend the same schema additively). Unknown fields still fail
loudly. `radius` is meters — a character rig at ~1.7 m wants ~0.002–0.005;
the probe's auto value for a 1 m sphere scene was 0.0025. Shipped values
were chosen BY EYE on the gate sphere's framing (manga 0.005 bold,
western 0.0035 medium, anime 0.004 thin-but-legible): at that framing a
silhouette contour centers on the edge, so its outer half falls over the
dark background and the legible weight comes from the inner half — expect
to re-tune on real character framing in P4-8 (data edit, no code change).

### Builder contract — `addon/style.py::build_lineart(source_obj, preset)`

- Validates the `lineart` section (absent → actionable error, never a
  silent no-op).
- REMOVE-FIRST: any previous `rm_lineart` object/data and
  `rm_ink_<style>` material are removed before creation (no `.001`
  suffixes, clean rebuilds).
- Ops-creates `LINEART_OBJECT` against the active `source_obj`, then
  renames to canonical names: object/data `rm_lineart`, modifier
  `rm_lineart`, layer `Lines`, material `rm_ink_<style>`; sets
  `target_layer`/`target_material`, re-points `source_object`, applies every
  preset value; restores the previously active object. The created object is
  captured by DATABLOCK DIFF, not `bpy.context.object` (after a render the
  context still points at the previous active object — gate-caught).
- Returns a REPORT (names + all applied values + ink color as hex) that the
  gate asserts; rebuilding must produce an equal report (determinism, same
  rule as P4-1).
- The gate additionally evaluates the depsgraph and asserts
  `strokes > 0` at frame 1 (the build being non-empty is the whole point),
  and — when renders happen — pixel-diffs the composed frame against the
  material-only frame (`darkened` channels must be > 0: ink that evaluates
  but renders invisibly is a FAIL, the empty-shell class at render level).

### Honest scope

- Verified: single-frame composition, headless EEVEE, on the gate sphere.
- **Per-frame stability VERIFIED (2026-09-18 S13)**: the styled turntable
  probe (`xtask/styled_turntable_probe.py`, `RM_TT` lines) ran the full
  manga stack (bands + ink + tones) under a 360°/12-frame ORBITING camera
  — `RM_TT STABLE: PASS`: the LineArt modifier re-traced the contour on
  EVERY orbit angle (strokes=2 ×12 frames, depsgraph-evaluated), the tone
  machinery (view layer + compositor group) stayed present, no frame went
  black, and the dark fraction moved smoothly with the orbit
  (0.0710 → 0.0781 → 0.0721) = the styled look genuinely follows the
  view. Ink contribution measured WITHIN the same compositor-active
  pipeline (frame 0: 12335 dark vs 12168 baseline at the identical
  angle; mean +636 across the orbit). Instrument finding recorded:
  compositor-FREE frames differ from compositor-ACTIVE ones at the
  anti-aliased silhouette (the material's black rim ring evaluates
  2-3px wider without the compositor) — baselines for pixel-diff claims
  must share the pipeline. This unlocks the P4-8 hero material.
- Line art over the bone-proxy visualizer vs skinned meshes (gate sphere
  only so far), performance on production meshes: still open scope.
- No "hand-inked" language ever: these lines are generated by the LineArt
  modifier from preset data, and every media asset says so.

## P4-3 — screentones as compositor node groups (design, probe-verified 2026-09-18 S12)

The capability question was probed first again (`xtask/tone_probe.py`,
`RM_TONE` lines). Findings on Blender 5.1.0 headless:

- **Background compositing WORKS** — but through the 5.1 API: the graph is
  a node group on ``scene.compositing_node_group`` (``scene.node_tree`` is
  GONE; unset group = nothing composited). The sink is the group-output
  INTERFACE (a BrightContrast graph changed 230,400 channels headless).
- **Node inventory quirk**: the Python-subclass enumeration returns NOTHING
  in 5.1; by construct-testing, the compositor accepts the UNIFIED
  shader/generic classes (``ShaderNodeMath``, ``ShaderNodeMix``,
  ``ShaderNodeSeparateXYZ``, ``ShaderNodeValToRGB``, ``ShaderNodeVectorMath``
  — the P4-1 identifier-socket lesson applies to ``ShaderNodeMix`` here too)
  but NOT ``ShaderNodeCombineColor`` ("not a shader node tree") and there is
  NO combine node of any flavor in the compositor set.
- **NO UV pass under 5.1's EEVEE** (Render Layers lists only Image/Alpha;
  enabling ``use_pass_uv`` changes nothing) — the coordinate source is a
  SECOND VIEW LAYER with a material override whose shader emits Generated
  coordinates (P4-1's UNLIT trick); the coordinate map arrives as an
  ordinary Image from that layer's Render Layers node (probe render: a clean
  r=[0.21, 0.81] / g=[0.08, 0.58] gradient on the sphere).
- **The full halftone math chain is PROVEN rendering**: luminance → dot
  radius, Generated coords → tiled cell distance, ``dist < radius`` → ink
  dot mask — 22,017 dark / 54,783 light pixels headless, visuals checked
  (a real manga-style dot grid wrapping the sphere). The bisect caught two
  instrument bugs worth remembering: an existing Group Output node NEVER
  refreshes after an interface change (and the interface gets rewritten
  behind the scenes — recreate the node), and SUBTRACT operand order is
  load-bearing (``bw - 1.0`` silently kills the whole chain; the scene
  looks identical until you render the intermediate).

### Tone preset data (additive `"tones"` field, schema format 1)

```json
"tones": {
  "cells": 40,        // grid frequency across the object's Generated space
  "dot_scale": 0.42,  // max dot radius, fraction of a cell (0.71 = corners)
  "ink": "#101010"    // dot color
}
```

Manga and western carry tones; **anime deliberately has none** (clean cel
look — a data choice, not an omission). The builder:
``addon/style.py::build_screentones(scene, preset)`` — remove-first
determinism over the view layer (``rm_tones_uv`` + override material), the
node group (``rm_tones``) and ``scene.compositing_node_group``; returns the
report the gate asserts (names + cells + dot_scale + ink + node list), and
rebuilding must produce an equal report. The dots composite OVER the render
(A = the image itself, B = ink, Fac = dot mask): highlights keep radius → 0
and stay clean, shadows grow toward solid ink — the manga behavior.

### Honest scope

- Tone grids live in each object's GENERATED space: per-object scale
  mismatch (a small prop gets denser screen-space dots than a character)
  is a known v1 limit; a screen-space unified grid is future work.
- **Animated tone stability VERIFIED (2026-09-18 S13)**: the styled
  turntable probe (above, `RM_TT STABLE: PASS`) exercised the tone view
  layer + compositor group on all 12 orbit frames — the machinery stayed
  present and the dots rendered on every frame; no per-frame limitation
  to record.

## P4-4 — multi-camera panel pages (design + probe-verified 2026-09-18 S13)

A manga/comics page is a LAYOUT over renders: N rectangles ("panels"), each
showing the SAME scene through a DIFFERENT camera. P4-4 makes the layout
DATA (same discipline as P4-1..P4-3) and the assembly a DETERMINISTIC
builder. Two shipped layouts prove RTL vs LTR is layout data, not a code
fork.

### Probe findings (`xtask/page_probe.py`, `RM_PAGE` lines, Blender 5.1.0 headless)

The mechanism was chosen before probing; the probe answered the open
questions and CAUGHT THREE ASSUMPTIONS THAT WOULD HAVE SHIPPED A BROKEN
BUILDER (the first page render came out as a top sliver + black — bisected
stage by stage):

- **Q-PANELS — YES**: per-render `scene.camera` + `resolution_x/y` +
  `filepath` swapping yields one PNG per panel at the exact expected pixel
  size, headless EEVEE, styled subject (manga bands + ink + tones in the
  panel PNGs). Two cameras proven to produce distinct frames (mean channel
  diff 0.1614 on the sampled stride).
- **Q-COMPOSE — YES, with two traps**: `CompositorNodeImage` (file-loaded
  PNG) + `Translate` + `AlphaOver` work inside the 5.1 scene node group.
  BUT (1) **the compositor CENTERS images smaller than the render buffer
  before `Translate` applies** — every offset must be corrected:
  `t = desired - (page - img) // 2` per axis (uncorrected offsets
  overshoot by exactly the centering term — the sliver+black render);
  (2) **a bare `RGB` node does not work as the page background**: outside
  any image's footprint the chain carries no data and goes
  transparent-black — the background is a FULL-PAGE solid generated image.
  Socket shapes recorded: 5.1 `Translate` takes SEPARATE `X`/`Y` value
  inputs (the old single `Vector` input is gone); `AlphaOver`'s inputs are
  named `Background`/`Foreground` (+ `Factor`).
- **Q-FIDELITY — YES, via the sRGB/Standard identity**: panel PNGs survive
  the compositor round-trip BYTE-FAITHFUL (5/5 computed samples exact)
  when panel images load with the DEFAULT sRGB colorspace and the page
  renders with view transform `Standard` + dither 0 — Standard's write
  encode is the same curve the loader decodes with, so
  decode(encode(bytes)) is the identity. The "obvious" `Non-Color` loads
  FAIL (Standard still encodes → every value lifted by the sRGB curve:
  0.227 read back as 0.514) — bisect-recorded.
- Positioning proven by computed pixel samples: gutter white
  (600,1101)=(1,1,1), border-ring ink (609,819)=(0.063³), page corner
  white — panels sit at the preset's exact pixel offsets.

### Mechanism (as built)

1. **Per-panel renders** — a panel is one camera's full frame at the
   panel's own pixel size: the builder swaps `scene.camera` +
   `render.resolution_x/y` + `render.filepath` per panel and renders,
   staging + RESTORING each. No border-render: each panel shows its
   camera's complete frame (v1 semantics — a panel that crops INTO a
   camera frame is later scope). Per-panel `style` (optional) restyles
   the subject through the P4-1/2/3 builders BEFORE that panel's render,
   so mixed-style pages (the P4-8 3-style hero) are the same mechanism as
   single-style pages. A panel with no `style` keeps whatever is applied.
2. **Compositor page assembly** — the page is a second compositor node
   group on the same scene (5.1 `scene.compositing_node_group`): the
   full-page solid background image, then per panel a loaded panel image +
   `Translate` (centering-corrected pixel offset) + `AlphaOver` chain
   (panel borders = solid-color "under-rects" images offset by
   `-border_px`, generated deterministically, NOT hand-drawn frames), one
   group-output INTERFACE sink (the P4-3 rule: exactly one, created after
   the interface socket), rendered once at page resolution with
   `Standard` + dither 0 (the byte-identity contract above). This
   REPLACES the tones graph on the scene — the two are sequential stages:
   panels render styled+toned FIRST, then the page graph takes over for
   assembly.

### Page preset data (schema format 1, `presets/pages/*.json`)

```json
{
  "format": 1,
  "name": "manga_koma3",
  "reading_direction": "rtl",   // "rtl" | "ltr" — DATA for panel order
                                // and P4-6 export; the builder never branches on it
  "style": "manga",             // optional page-level BASE look for unstyled panels
  "page": {
    "width_px": 1200, "height_px": 1800,
    "background": "#ffffff",
    "bleed": 0.0,               // panels may extend to [-bleed, 1+bleed]
    "border": {"width_px": 6, "color": "#101010"}   // 0 = borderless
  },
  "gutter": 0.02,               // MIN gap between panel rects (fraction of
                                // the respective page axis, checked in px)
  "panels": [
    {"rect": [0.0, 0.62, 1.0, 0.38], "camera": "rm_cam_1"},
    {"rect": [0.51, 0.31, 0.49, 0.29], "camera": "rm_cam_2", "style": "anime"},
    {"rect": [0.0, 0.0, 1.0, 0.29], "camera": "rm_cam_3"}
  ],
  "notes": "..."
}
```

- `rect` = `[x, y, w, h]` normalized page fractions, origin BOTTOM-LEFT
  (Blender image convention; y up). Pixel math is edge-based
  (`panel_px`: `x0 = round(x0f·W)`, `x1 = round((x0f+wf)·W)`, `w = x1-x0`)
  so gutters stay exact in pixels.
- `camera` is a SCENE OBJECT NAME — the page is scene-independent
  layout data; a missing camera is an actionable error listing the
  scene's cameras. Cameras are authored in the scene (the gate creates
  `rm_cam_*` aimed at the subject).
- `style`: the page-level field is the BASE look for unstyled panels;
  a per-panel `style` (a shipped style preset name, validated at load
  time) restyles that panel only. Style application is PERSISTENT in the
  scene, so `render_panels` renders UNSTYLED panels first (they carry
  the base look) and styled panels after (each restyled for its own
  render) — the report is in reading order regardless. The shipped
  manga page's beat panel carries `anime` (no tones, cooler bands): the
  mixed-style showcase AND the per-panel tone-removal path in one page
  (visual-check-verified distinct).
- Panels are listed in READING ORDER; for RTL the first panel is the
  top-RIGHT one. The validator enforces GEOMETRY (rects within the
  bleed-extended page, positive sizes, pairwise gaps ≥ `gutter` in
  pixels), never reading direction.
- Page presets live in a `pages/` SUBDIRECTORY of the presets dir —
  `known_presets()` globs only the top level, so a page can never be
  mistaken for a style preset and vice versa.

### Builder contract — `addon/riggermortis_addon/pages.py`

- `load_page(name_or_path)` validates loudly (unknown fields fail, like
  every preset loader here); `panel_px(page, panel)` is pure pixel math
  (unit-tested WITHOUT bpy in CI, like the payload contract).
- `render_panels(scene, page, out_dir, subject=None)` → one PNG per
  panel (list order, deterministic names `rm_panel_XX.png`) + report
  (files + pixel sizes + cameras). Missing camera / unknown style /
  `style` without a `subject` = actionable errors. Render staging
  (camera/resolution/filepath/view transform/dither) is RESTORED.
- `build_page_graph(scene, page, panel_files)` → remove-first
  (`rm_page` group, `rm_page_*` images), fixed node names/order,
  exactly-one Group Output AFTER the interface socket; returns the
  report the gate asserts (rebuild must be report-equal). Replaces the
  scene's compositor group (sequential stages, above).
- `render_page(scene, page, out_path)` stages + RESTORES
  resolution/percentage/filepath/view transform/dither.
- `remove_page(scene)` → group + generated/loaded images removed; an
  unrelated compositor group is never touched (the `remove_screentones`
  rule).

### Honest scope

- Panels are SINGLE FRAMES: no per-panel camera animation, no panel
  transitions (P4-7 animatic is separate).
- Borders are compositor under-rects (deterministic generated images) —
  not hand-drawn frames; no "hand-lettered"/"hand-inked" claims, ever.
- Verified single-page headless on the gate sphere; production framing
  and per-page composition tuning is P4-8 (data edits, no code change).
- PDF/EPUB export of pages is P4-6; speech bubbles are P4-5; the 6-page
  manga that exercises all of it is P4-8.

## P4-5 — speech bubbles as page DATA (design 2026-09-19 S14; probe + build below)

Bubbles are PAGE-LEVEL DATA attached to the P4-4 page preset schema — a
per-panel `"bubbles"` list — because their placement semantics are panel
semantics: a bubble is positioned relative to a panel's rectangle, the
same coordinate system the page graph already composites in. Three
candidate mechanisms existed (3D GP scene placement in front of each
camera / text-as-texture / compositor overlay); the third is chosen by
the same argument that chose P4-4's assembly:

- **Placement must be deterministic from preset data alone.** 3D scene
  placement would make a bubble's page position camera- and
  scene-dependent (two scenes, same page preset, different bubble
  positions) — that breaks the determinism discipline every P4 builder
  is held to. Overlay placement is pure page-pixel math.
- **The page graph already does exactly this.** P4-4's `Translate` +
  `AlphaOver` chain composites images at preset pixel offsets with the
  centering correction; a bubble RGBA overlay is one more layer over
  its panel (panels stay byte-faithful outside the bubble footprint —
  alpha 0 foreground returns the background exactly in the over
  operator).
- **Bubbles render OUTSIDE the page pipeline** as one RGBA PNG per
  bubble (a mini-scene: GPv3 ellipse + tail + TEXT object lettering
  under an orthographic camera, `film_transparent` on), so the look is
  style-independent data rendered by its own deterministic builder —
  the tones compositor never dots the lettering and the persistent
  style semantics (P4-4) never leak into it.

Honest labeling rule (unchanged): bubbles are GENERATED GEOMETRY +
TYPESET TEXT (GPv3 strokes + a Blender font object). No "hand-lettered"
claim, ever, anywhere.

### Bubble preset data (additive per-panel `"bubbles"` field, schema format 1)

```json
"panels": [
  {"rect": [...], "camera": "rm_cam_1",
   "bubbles": [
     {"pos":  [0.42, 0.72],   // bubble CENTER, panel fractions (x, y)
      "size": [0.62, 0.34],   // bubble footprint, PANEL fractions — the
                              // full rect incl. the tail's band
      "tail": "se",           // "n"|"ne"|"e"|"se"|"s"|"sw"|"w"|"nw"|"none"
      "text": "KA-BOOM!"}     // typeset lettering; "\n" = line break
   ]}
]
```

- The bubble RECT (`pos` center, `size` extents, panel fractions) is the
  FULL FOOTPRINT: the ellipse body and the tail both fit inside it (a
  tailed bubble's ellipse occupies the upper portion; the tail hangs in
  the reserved band toward its direction). The validator maps the rect
  to page pixels (`bubble_px`) and requires it inside the bleed-extended
  page and strictly positive — same edge-based px discipline as panels.
- `tail` positions the triangle tip at the footprint edge midpoint
  (cardinal) or corner bisector (diagonal) of the named direction;
  `none` is a plain ellipse. Default `none` (data says what it wants).
- `text` is typeset centered in the ellipse interior, auto-fit
  deterministically (the builder measures the font object's bounding box
  and scales to fit a fixed interior box — same string, same layout,
  always). An empty string is a wordless bubble.
- Validation follows the house rules: unknown fields fail loudly
  (page, panel AND bubble level), `bubbles` must be a list of objects,
  numbers are numbers (bools are not numbers), every bubble validates
  against the page it sits on. The shipped pages keep format 1 — the
  field is additive and the shipped pages gain it as DATA where a bubble
  belongs.

### Builder contract — `addon/riggermortis_addon/bubbles.py`

- `build_bubble_object(name, w_m, h_m, tail, text)` — remove-first
  creation of the bubble stage: GPv3 object (deterministic 64-point
  closed ellipse + closed 3-point tail stroke, point radius =
  outline world width, opacity 1) + font object (centered, auto-fit) +
  orthographic camera framing the footprint exactly; ink + fill are the
  classic two GP materials (black stroke / white fill, unlit by
  construction like P4-1's Emission trick). Everything canonically named
  `rm_bubble*` (the P4-1 rename discipline).
- `render_bubbles(scene, page, out_dir)` — one RGBA PNG per bubble in
  deterministic global order (panel order, then bubble index; names
  `rm_bubble_XX.png`), rendered at the footprint's exact pixel size.
  Stages + RESTORES: camera, resolution, `film_transparent`, view
  transform (`Standard` + dither 0 — the ink/white identity transform),
  filepath, compositor group (UNSET during bubble renders — the tones
  graph must never dot the lettering; a stale page graph must never
  composite them), and `hide_render` on every non-bubble object (no
  photobombing). Returns the report the gate asserts.
- `remove_bubbles()` — all `rm_bubble*` objects/data/materials/images.
- `pages.build_page_graph(scene, page, panel_files, bubble_files=None)`
  composites bubbles AFTER panels (bubbles overlay panels and may cross
  gutters; borders stay under panels). A page with bubbles but no
  bubble files — or the reverse — is an actionable error, never a
  silent no-op. Bubble-less pages build byte-identical graphs to the
  pre-P4-5 builder (the report grows no key).

### Probe findings (`xtask/bubble_probe.py`, `RM_BUBBLE` lines, Blender 5.1.0 headless)

The mechanism above is the POST-probe design — the probe changed it twice
(the S12/S13 discipline paying for itself again):

- **The GPv3 fill is a dead end for data-authored bubbles, recorded so it
  is never faked.** Probed exhaustively: material fills (``show_fill`` +
  SOLID + white) DO NOT render on lit layers — they render ONLY on
  ``use_lights=False`` layers (lit fills are the broken path in 5.1);
  stroke-level ``fill_color``/``fill_opacity`` never render; per-point
  ``vertex_color`` drives only the STROKE (color from it, opacity from
  ``point.opacity`` — the material color does not tint strokes at all);
  the only fill ops are interactive cursor tools (``grease_pencil.fill``
  needs a click); the MONKEY preset's authored fills render black-unlit /
  vanish-lit. **The body is therefore a MESH** (ellipse n-gon + tail
  triangle, z-layered, unlit Emission — the P4-1 house trick), which also
  z-orders the tail join explicitly instead of relying on GP stroke-order
  fill semantics.
- **Stroke authoring works through `drawing.add_strokes([n, ...])`** (the
  GPv3 write API; `stroke.points.add` does not exist). The closed flag is
  named **`cyclic`** (not `closed`). The ops `EMPTY` preset creates the GP
  with one layer/one frame/a 'Black' material; a fresh
  `bpy.data.materials.new()` carries `grease_pencil == None` — the ink
  material is the ops material RENAMED (the P4-2 capture-by-datablock-diff
  discipline, since `bpy.context.object` is stale after a render).
- **Q-TEXT — YES**: a TEXT object with an unlit Emission black material
  renders legible typeset lettering into the RGBA (1070 dark pixels in
  the auto-fit band on the probe bubble).
- **Q-COMPOSE — YES**: the RGBA overlay composites over the panel via the
  P4-4 mechanics; the panel is byte-faithful OUTSIDE the bubble footprint
  (alpha-0 foreground returns the background exactly), the body reads
  white and the ring inked ON the page.
- **Q-DET — YES at pixel level**: same inputs re-render pixel-identical
  (0 differing channels). File bytes differ ONLY in Blender's
  `tEXt RenderTime` metadata stamp (chunk-located) — the IDAT pixel data
  is byte-identical; pixel-level determinism is the standard (same as the
  P4-4 page round-trip).
- **Placement — YES**: the composite position is `pages.bubble_px` math
  alone; shifting the offset moves the ink exactly.
- Visual check (probe + gate page): white ellipse body, black ink outline,
  legible "KA-BOOM!", tail join reads clean (the tail mesh covers the
  ellipse ink), tail inked on its two long edges.

### Gate results (S14)

`make style-verify` PAGES section: pages carrying bubbles render their
overlays (re-render pixel-identity asserted per bubble), composite them
(``build_page_graph(..., bubble_files=...)`` — rebuild-report-deterministic),
and pixel-check the assembled page (ring ink / white body / dark lettering
per bubble; the panel byte-fidelity roundtrip samples SKIP bubble-covered
points — a fully covered panel skips that check with a note). The shipped
manga page's beat panel carries the bubble; the western page stays
bubble-less and builds a graph byte-identical to the pre-P4-5 builder
(back-compat is gated, not assumed). Honest SKIPPED degradation on
pre-4.3-class Blenders (no GPv3 drawings API). Bubble stage objects are
removed after rendering (scene left as found, plus the PNGs).
