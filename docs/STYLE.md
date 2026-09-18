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
- NOT yet verified (no claim made): per-frame re-evaluation under an
  ORBITING camera (a styled turntable re-checks this before any claim),
  line art over the bone-proxy visualizer vs skinned meshes (gate sphere
  only so far), performance on production meshes.
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
- Verified single-frame headless; animated tone stability re-checks with
  the styled turntable before any claim.
