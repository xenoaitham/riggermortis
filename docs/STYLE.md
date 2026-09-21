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
**RE-TUNED S16 as promised**: the P4-8 character renders read the shipped
values thin at ~2–4 m, so the per-style radii moved to **manga 0.008,
anime 0.006, western 0.0055** — chosen BY EYE on real character framing
(visual-check loop over the manga pages), never tuned against a gate
number (the ink checks are `> 0` thresholds; the measured darkened counts
moved with the radii as expected and all gates re-PASSed).

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
- PDF/EPUB export of pages SHIPPED as P4-6 (docs/EXPORT.md, the style
  gate's EXPORT section); the 6-page manga that exercises all of it is
  P4-8.

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

## P4-7 — animatic mode: timed panel sequences from pose actions (shipped 2026-09-21 S15)

An animatic is a TIMED ROUGH of a sequence: the panel cameras of P4-4,
but sequential in TIME instead of spatial on a page — each SHOT points a
camera at the posed subject for a preset duration while the subject plays
its canonical action (the P2/P3 pose-sequence machinery). The output is a
movie (plus the per-frame PNGs it is encoded from). It is an animatic in
the production sense: a timing/boarding rough, NOT a final render — every
claim, filename, and doc line labels it as a rough (no "final render"
language, ever).

Design decisions, in the house order:

- **Separate preset family** — ``presets/animatics/*.json``, a SUBDIRECTORY
  of the presets dir like ``pages/`` (so ``known_presets()`` can never
  mistake an animatic for a style preset and vice versa). An animatic is
  not a page and gains nothing from hanging off the page schema: its
  semantics are temporal (shots + fps), while a page's are spatial (rects
  + gutters). Same discipline as every preset here: ``format`` field,
  loud validation, unknown fields fail at every level.
- **The motion is a CanonicalAction through the CERTIFIED bake path** —
  the animatic builder takes the baked armature as given (``bake_action``
  is the P2-3/P3-7 gate-verified transport) and does ``frame_set(n)`` per
  output frame; the animatic owns TIMING (which action frame plays when),
  never posing math. Action frames are consumed EVENLY and IN ORDER:
  output frame ``k`` of ``T`` total plays action index
  ``(k * len(action)) // T`` (integer math, deterministic, loops the
  action naturally when the shots outrun it). The report records the
  exact action-frame index used per output frame — auditable, never
  implied. A 1-frame action degenerates to a held panel (the traditional
  static animatic) — same code path, documented, not special-cased.
- **Rendered frames, not a sequencer** — per output frame the builder
  swaps ``scene.camera`` (the shot's camera) and renders one STILL PNG at
  the preset resolution. The determinism standard (P4-4/P4-5:
  pixel-identical re-renders) carries over unchanged — the PNG sequence
  IS the deterministic artifact. Movie ASSEMBLY is shell glue
  (``xtask/style_verify.sh``, ffmpeg — D-009: the spawn lives outside
  any ``.py``), and movie CONTAINER bytes are NOT claimed deterministic
  (encoder metadata); the claim is frame-level, and the assembly
  parse-back asserts structure (frame count at the preset fps).
- **Style semantics reuse the page rules** — a preset-level ``style`` is
  the base look (applied by the caller like ``render_panels``); a
  per-shot ``style`` restyles the subject for that shot's frames.
  Application is persistent in the scene, so frames render in
  style-groups (base-look frames first in time order, then each styled
  shot's frames in time order), report in TIME order regardless — the
  exact P4-4 order discipline. Because the last styled shot persists, a
  RE-RENDER requires the caller to re-apply the base look first (the
  pages precedent). The screentones compositor group stays ACTIVE
  during animatic renders (tones honor per-frame stills — the RM_TT
  precedent); an active PAGE group is refused with an actionable error
  (a static page must not composite over moving frames — remove it
  first; the gate exercises the refusal as its negative path).
- **Honest SKIPPED degradation** — the animatic renders SKIP loudly on
  boxes without a render context (the bake + timing checks still gate
  inside the probe); the ffmpeg assembly half SKIPS honestly when
  ffmpeg/ffprobe are absent or no frames exist — a WRONG assembled
  result is a FAIL, never a skip.

### Probe findings (`xtask/animatic_probe.py`, `RM_ANIMATIC` lines, Blender 5.1.0 headless; S15)

The mechanism was probed BEFORE building (six dbg bisect rounds back the
findings; the traps are in the probe docstrings so they are never
re-learned):

- **Q-TIME — YES**: a keyframed action evaluates per ``frame_set`` and
  reaches EEVEE stills; re-renders are pixel-identical (the animatic
  builder consumes the CERTIFIED bake output — this proves the time
  machinery bake-output-independent). Probe traps recorded: pose bones
  default to QUATERNION (keying ``rotation_euler`` silently animates
  nothing unless ``rotation_mode`` switches to XYZ); a SPHERE is
  rotationally symmetric (a 0.5-rad swing moves ~no pixels — the probe
  subject is a CUBE); frames 1 and 5 of a sin cycle are both zero
  crossings.
- **VSE MOVIE-APPEND — DEAD END, recorded so it is never faked**: the
  5.1.0 sequencer strip stack -> FFMPEG render SEGFAULTS racy (~2/3
  crash rate across 16 bisect runs; garbage ``imb_alloc_buffer`` calloc
  with a deterministic garbage length) INDEPENDENT of source file class
  (rendered PNGs / tEXt-stripped / 16-bit / bpy-resaved / shutil-copied
  data PNGs all crash 3/3 in at least one round), of strip config, of
  armature presence, of world, of ``use_sequencer``, and of container
  (MKV/MPEG4). Several single-run "passes" of candidate mitigations
  were statistical escapes — caught only by re-running each config 3x
  (the S15 lesson: bisect verdicts need run counts). No ``.py`` path
  ever renders a VSE movie (a segfault cannot be caught and would kill
  the gate); the work order's pre-authorized fallback is taken: per-
  frame PNGs + shell-glue ffmpeg assembly.
- **Strip AUTHORING works (unused by the builder, kept as evidence)**:
  ``scene.sequence_editor.strips`` (the legacy ``sequences`` is GONE in
  5.1), ``new_image`` + ``elements.append``, contiguous preset-shaped
  timing, rebuild-report-deterministic.
- **5.0+ movie API (recorded, unused)**: video output is
  ``render.image_settings.media_type = 'VIDEO'``; the old
  ``file_format = 'FFMPEG'`` assignment FAILS on 5.x (the enum item is
  hidden from assignment though present in the static RNA list).
  ``render(animation=True)`` names its output
  ``<base><start:04d>-<end:04d><ext>``.
- **Instrument trap (recorded)**: the scene compositor group IS active
  for stills AND animation-mode renders — a ``Bright=0.15`` knob
  provably changes ZERO channels through the dark probe scene's
  pipeline and once masqueraded as "the compositor is inactive";
  ``Contrast=5.0`` changes the full frame.

### Animatic preset data (schema format 1, `presets/animatics/*.json`)

```json
{
  "format": 1,
  "name": "demo_shots",
  "resolution": {"width_px": 480, "height_px": 360},
  "fps": 12,
  "style": "manga",             // optional base look for unstyled shots
  "shots": [
    {"camera": "rm_cam_1", "frames": 12},
    {"camera": "rm_cam_2", "frames": 8, "style": "anime"}
  ],
  "notes": "..."
}
```

- ``shots`` is the TIMELINE in play order: shot k occupies output frames
  ``[start_k, start_k + frames_k)`` where ``start_k = Σ frames_{<k})`` —
  timing is fully determined by the data, no overlaps possible by
  construction, and the validator requires every ``frames`` to be a
  positive int. ``fps`` is a positive int (the animatic standard is
  8–15 fps; this is a rough, and the low fps IS the look).
- ``camera`` is a SCENE OBJECT NAME (page rule): scene-independent data,
  a missing camera is an actionable error listing the scene's cameras.
- ``style`` fields follow the page rules verbatim (base look + per-shot
  overrides validated against shipped style preset names at load time).
- Unknown fields fail loudly at preset, shot, and resolution level
  (house rule; 12 CI contract tests pin the schema). There is NO
  container field by design: assembly is shell glue, and the container
  belongs to the shell's ffmpeg invocation, not to the scene data.

### Builder contract — `addon/riggermortis_addon/animatics.py`

- ``load_animatic(name_or_path)`` / ``known_animatics()`` — the pages
  loader pattern (loud validation, sorted names, explicit-path escape
  hatch); the module imports WITHOUT bpy so the CI suite exercises the
  schema + timing contract directly (12 tests).
- ``animatic_frames(animatic, action_len)`` — pure deterministic timing
  plan: per output frame, the shot index, camera, style, and the
  action-frame index (the ``(k * action_len) // T`` mapping). The
  builder and the report both consume it, so timing can never drift
  between plan and render; a 1-frame action degenerates to a held panel.
- ``render_animatic_frames(scene, animatic, out_dir, action_len,
  subject=None)`` — one STILL PNG per output frame
  (``rm_animatic_0000.png``, 0-based). The CALLER bakes the canonical
  action first (``bake_action`` — the certified transport) and passes
  its length; the builder owns TIMING only (``frame_set(action_frame +
  1)`` + camera swap; the +1 is ``bake_action``'s documented default
  offset). Staged + RESTORED: camera, resolution, filepath, scene
  frame. Refuses an active ``rm_page`` group (actionable error); keeps
  tones machinery as found; hides nothing (scene curation is the
  caller's job — the gate stages ``hide_render`` around the call, the
  bubbles precedent inverted). Re-renders re-apply the base look first
  (persistent-style semantics, pages precedent).

### Gate (S15)

`make style-verify` gained two halves:

- **Probe** (`RM_STYLE ANIMATIC`): the shipped ``demo_shots`` preset
  renders end-to-end on a tiny mappable rig + deformed cube — the
  8-frame canonical action bakes through the REAL ``bake_action``, the
  page-graph refusal fires (negative path), 20 frames render in style
  groups (manga base, anime second shot), the render plan equals the
  pure ``animatic_frames`` output, TWO full sweeps are pixel-identical
  (det), the shot cut and the within-shot swing are visible in the
  pixels (channel-count checks; the sphere trap is why the subject is a
  cube), and the first gate run's bug is recorded (reusing the page
  cameras' sphere aim rendered 20 identical empty frames — the animatic
  section re-aims the preset's cameras at its own subject). SKIPPED
  honestly on renderless boxes; bake + timing still gate there.
- **Shell assembly** (ffmpeg): glues the probe's frames into a movie at
  the probe's reported fps and parse-backs the frame count (ffprobe,
  writer-shaped). SKIPPED honestly without ffmpeg/ffprobe or frames;
  a wrong count is a FAIL.

### Honest scope

- An ANIMATIC IS A TIMED ROUGH — deterministic per-frame PNGs assembled
  by shell glue; no "final render" language anywhere, ever.
- Verified on the gate cube (proxy geometry, 9-bone rig); production
  characters and framing are P4-8 (the lineart radii are per-style DATA
  re-tuned there, the P4-2 note).
- Movie container bytes are NOT claimed deterministic (encoder
  metadata); frame-level determinism is the claim and is gated.
- No audio, no per-shot transitions, no camera animation within a shot
  (static cameras are the P4-4 data rule); bubbles do not ride animatic
  frames (they are PAGE data — a bubble overlay is future scope,
  recorded, not faked).

## P4-8 — the 6-page manga + 3-style hero (design 2026-09-21 S16; Phase-4 close-out)

Every ingredient above is verified and shipped; this section is the
DESIGN of the Phase-4 gate deliverable, written before any build (the
house order). The deliverable: **"Paper Dart"** — a 6-page WORDLESS
manga in ``docs/manga/`` (readable + charming, the phase gate), plus a
**hero page: the same scene/framing in all three styles side-by-side**,
plus the assembled manga PDF (``rigpose export-pdf``, parse-back
verified). Every asset is GENERATED and labeled so; no bubbles carry
text (wordless), no hand-drawn/hand-lettered claims anywhere.

### Story and board (wordless, one character + one prop)

Cast: the **Mannequin** (the scene's character, below) and a **paper
dart** (a grey folded-paper prism — solid mid-grey so it reads on the
light sky WITHOUT its own line art; the single LineArt build belongs to
the protagonist). Beating heart: find → take → throw → crash → repair
→ soar. 20 story beats; each beat is ONE pose + ONE dart position + a
bound camera, and beats map 1:1 to panels:

| page | beats | panels (RTL layouts, 1200×1800) | beat |
|---|---|---|---|
| 1 FIND | b1–b3 | wide / medium-right / close-reach | notices the dart lying ahead; looks down; crouch + reach |
| 2 TAKE | b4–b6 | right tall / left tall / bottom wide | dart in hand; holds it up to the face; head up, dart to chest |
| 3 THROW | b7–b9 | right / left / bottom WIDE | wind-up; release (dart just past the fingertips); dart high in the sky, mannequin pointing |
| 4 CRASH | b10–b13 | wide dive / rush / close CRASH / slump | dart nose-dives; run; frozen stare at the crashed dart; slumped shoulders |
| 5 REPAIR | b14–b16 | close / low close / medium | both hands at the dart; dart lifted overhead; second wind-up |
| 6 SOAR | b17–b20 | wide / SKY panel / medium jump / final wide | release again; dart climbs steeply (mostly sky in frame); jump of joy; waving after the dart |

The b12 crash close-up carries ``style: anime`` (one deliberate beat
panel — the mixed-style machinery IN the story, and fewer dots reads
as a tone shift) and ONE **empty bubble** (``"text": ""`` — wordless
speechlessness, the classic beat; the fallback if empty-text rendering
verifies badly is dropping the bubble, noted honestly, never faked).
The hero beat is **b19 (the jump)**.

### The character + scene (deterministic, asset-free, CI-safe)

The story must render anywhere the gates do — no local rigs, no
downloads, every builder deterministic:

- **Rig**: a code-built humanoid armature whose bones carry the
  canonical lexicon names (``hips spine chest neck head shoulder.L/R
  upper_arm.L/R forearm.L/R hand.L/R upper_leg.L/R lower_leg.L/R
  foot.L/R``) so the live ``map_rig`` path maps 1:1 and the CERTIFIED
  ``bake_action`` transport works unchanged (the animatic-gate rig
  pattern, scaled up).
- **Body**: rigid primitive parts (head sphere + eye dots, torso boxes,
  limb capsules, foot boxes) JOINED into ONE mesh with per-bone vertex
  groups + an armature modifier — one ``subject`` object for the style
  builders (one material set, one LineArt source, artist-mannequin
  charm). Eyes are part of the mesh (wordless expression = pose +
  gaze).
- **Props**: the dart (its own mesh + its own object-level keyframes at
  the beat frames — carried beats key it to the hand's world position,
  flight beats key it along its arc) and a ground plane (flat light
  unlit) under a flat light sky (world color; final values tuned in
  the visual loop).
- **Poses**: hand-authored ``CanonicalPose`` positions built by small
  deterministic transforms of ``core.rest_skeleton()`` (bend angles,
  leans) — never raw magic dicts; hips anchor like every canonical
  pose. The 20 beats bake through ``bake_action`` (Blender frame =
  beat index + 1, ``bake_action``'s documented offset); the dart's
  object action is keyed by the DRIVER at the same frames, so one
  ``frame_set(n)`` moves the whole scene deterministically.
- **Cameras**: one static camera per panel framing (the P4-4 data
  rule), built from a beat table; page presets bind them by name.

### The one engine extension: per-panel ``frame`` (additive, schema format 1)

A story page needs per-panel MOMENTS — poses are per-panel scene state,
and the page schema had none (a page rendered whatever the scene held).
The animatic already proved the honest mechanism (``frame_set`` over
the certified bake); pages gain the same lever as DATA:

```json
{"rect": [...], "camera": "rm_cam_p3_c", "frame": 9}
```

- Optional non-negative int per panel; absent = the scene frame as
  found (back-compat: frame-less pages behave and render byte-identically).
- ``render_panels`` stages ``scene.frame_current`` alongside
  camera/resolution/filepath, does ``frame_set(frame)`` before that
  panel's render, and restores in the ``finally`` — the exact staging
  discipline of every render entry point here. The report entries gain
  ``"frame"`` (value or null), the same always-present pattern as
  ``"style"``.
- ALL motion data (armature bake, dart keyframes, anything else keyed)
  stays in the SCENE, built deterministically by the driver — the page
  preset references a moment, it never contains motion. This is the
  line that keeps pages pure layout data.
- The animatic's ``rm_page`` refusal is untouched (pages render stills
  through their own graph stage; an active page graph during
  ``render_panels`` is pre-existing behavior, unchanged).
- Validation: loud unknown-field failure stays; ``frame`` must be an
  int ≥ 0 (bools are not ints, house rule). CI tests extend
  ``test_style_pages`` (accept, reject non-int/negative, back-compat
  parse).
- Gate coverage is DELIBERATELY small: the style probe's PAGES loop
  gains one tiny frame-carrying page (two panels, same camera, frames
  1 vs 3 over a keyed swing — distinct pixels asserted, re-render
  identity asserted). The FULL manga is NOT re-rendered in CI (20+
  large panels would dominate the llvmpipe gate for zero new mechanism
  coverage — the animatic half already gates per-frame stills); the
  manga renders are a LOCAL media pipeline like the walk GIFs
  (committed + media-guarded + driver-side parse-back).

### The manga pipeline (local media, driver-owned)

``bash xtask/manga_build.sh`` (D-009: the shell glue spawns Blender;
the ``.py`` is the Blender-side script) — builds the scene, bakes the
20 beats, renders the 20 story panels + 6 page assemblies + the hero
page into ``out/manga/``, assembles ``docs/manga/paper_dart.pdf`` via
``core.pagedoc.write_pdf`` with in-process parse-back (page sizes =
the presets), and copies the checked pages into ``docs/manga/``.
Visual checks gate every shipped image (the media rule); the
media-guard gains the pinned ``docs/manga/`` set in the SAME commit.

The story page presets live at ``xtask/manga_pages/*.json`` (version-
controlled DATA, loaded by EXPLICIT PATH — ``load_page`` has always
accepted paths) and deliberately NOT in ``presets/pages/``: the gate's
PAGES loop renders every SHIPPED page preset, and 7 full-size story
pages would dominate the llvmpipe gate for zero new mechanism coverage
(the shipped two stay the layout demos; the frame extension is gated
by a tiny probe-constructed page, above).

- **Radii re-tune** (the P4-2 note, honored here): the shipped
  ``lineart.radius`` values were eyeballed on the 4 m sphere framing;
  the character framing is closer (a ~1.7-unit mannequin at 1.2–4 m).
  Re-tune is a DATA edit on the three presets' ``lineart`` values,
  chosen BY EYE on real character renders, recorded here with the
  final numbers, never tuned to move a gate number (the ink checks are
  thresholds, not targets).
- **Hero page**: ``docs/manga/hero_3styles.png`` — a landscape
  triptych (1800×1200), three equal panels, ONE camera, the b19 jump
  pose, per-panel styles ``manga`` ``anime`` ``western`` (panel order
  LTR on the sheet; mixed-style pages are gate-proven, this is the
  showcase the phase gate names).
- **Story pages**: ``docs/manga/page_01.png`` … ``page_06.png``;
  **PDF**: ``docs/manga/paper_dart.pdf`` (write_pdf + parse-back in
  the driver; byte-determinism already gate-proven in EXPORT).
- An optional TIMED ROUGH animatic of the board (the P4-7 machinery
  over the same bake) may be rendered to ``out/`` as an inspection
  artifact — labeled a rough, never shipped as final media.

### As built (S16) — findings the visual loop earned

- **Panels inherit the SCENE's view transform** (``render_panels``
  deliberately does not stage it — the page assembly stages its own).
  The first page render came out with a heavy DARK sky and muted
  ground: Blender 5.1's default AgX transform crushed the 0.855 world
  into mid-dark grey. The fix is caller-side and now documented by
  use: the manga driver stages ``Standard`` + dither 0 in its base
  look — the SAME contract the page assembly already uses, so panels
  and page agree. Any future page-scene author must make this choice
  explicitly.
- **The empty bubble VERIFIED** (the design's fallback never fired):
  ``"text": ""`` skips the text object entirely (``has_text = bool
  (text)``) and renders a clean white body + tail — the wordless
  "speechless" beat on the crash page reads exactly as intended.
- **Lineart radii re-tuned on character framing** (the P4-2 note,
  honored): manga 0.008 / anime 0.006 / western 0.0055 — see the P4-2
  section for the record.
- **ops join trap (driver-side, recorded so it is not re-learned)**:
  each ``primitive_*_add`` makes ITS object the selection; joining
  parts created in a loop needs EXPLICIT ``select_set(True)`` on every
  part plus a chosen active — the first eye join silently produced a
  one-eyed character (visual-check-caught, of course).
- **A 35 mm lens on every story camera**: the wide manga panels have a
  narrow vertical field at 50 mm (±13.5°), which cropped heads and
  pushed ground-level props out of frame at medium distances; the
  wider lens is the systemic fix (per-camera aim nudges kept losing
  the dart).
- Gate coverage shipped as designed: ``RM_STYLE FRAMES: PASS`` (two
  panels at frames 1 and 3 over a keyed swing — distinct pixels,
  re-render identity, preset-sized assembly; SKIPPED honestly where
  renders skip), grep-tested on both line formats before pushing.

### Deliverables (all GENERATED by ``xtask/manga_build.sh``)

``docs/manga/page_01.png`` … ``page_06.png`` (the story, RTL, 1200×1800),
``docs/manga/hero_3styles.png`` (the triptych, 1800×1200),
``docs/manga/paper_dart.pdf`` (``write_pdf`` + in-process parse-back:
6 pages at 1200×1800; the same writer the EXPORT gate proves). The
media-guard pins exactly these 8 files; the story page presets live at
``xtask/manga_pages/*.json``. Visual check: the story reads end to end
(find → take → throw → crash → repair → soar), the styles differ
plainly on the hero, and no panel claims anything hand-made.

### Honest scope

- The mannequin is rigid-part geometry (no skinning): big bends can
  gap a joint — the poses are authored within its range, and that is
  the character's look (an artist's wooden mannequin), not a defect
  to hide.
- Wordless means ZERO lettering anywhere (the empty bubble carries no
  text); sound effects are absent by design.
- Panel crops show the camera's full frame (P4-4 v1 semantics — no
  crop-into-frame panels); composition works within that rule.
- The dart's flight is keyframed by the driver at beat frames (no
  physics); determinism is the claim, never realism. The dart carries
  NO line art by design — the single LineArt build belongs to the
  protagonist, and the dart's grey value carries its silhouette.
- The full manga is NOT re-rendered in CI (deliberate: 20+ large
  panels would dominate the llvmpipe gate for zero new mechanism
  coverage — the frame extension is gated by the tiny probe page, the
  writer by EXPORT, the per-frame machinery by ANIMATIC); the media is
  a local pipeline like the walk GIFs, committed and guarded.


