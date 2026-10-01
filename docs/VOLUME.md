# Volume from silhouette, P9-2 — design of record

Phase 9's second rock, designed BEFORE any measurement (the AUTO_SCULPT.md
sibling — a sibling design page, never a fork). The third-model decision is
MADE: **D-025 adopts `u2net.onnx` as the segmentation pass** (the scan
evidence, license, checksum, and measured CPU budget live in STATE/
DECISIONS.md; the P6-6 never-list amends to three). The roadmap's honest
physics, extended one step: P9-1 proved keypoints give SKELETON, not
VOLUME — the silhouette mask gives the VISIBLE-VIEW widths (hips/waist/
chest/thigh), and DEPTH is unobservable from a single view. So the volume
claim is scoped exactly as Annex A.1 strike S10 declared: **single-view
silhouette IoU >= 0.85 on the benchmark, visible-view scoped**; depth
follows the DECLARED circular-cross-section prior (regions treated as
cylinders whose depth tracks their width) — a declared D-008 prior, never
a fitted one, and never a depth claim.

Per-frame soft tissue stays OUT (P9-3's declared limit; simulation is a
different product). The volume sculpt is STATIC: applied once to the rest
character, before any animation drives the rig.

NOTHING on this page is a claim until a probe line, test, or gate number
cites it. The A.1 bar is LAW. No payload format change (the volume solve
consumes an existing payload's projections at apply time; the report is a
returned object — the camera-solve pattern); **D-025 is consumed by the
adoption decision itself, not by a pose field** — the volume apply adds no
new pose field (shape keys are mesh-side data).

## The one structural fact each candidate rides on

S36 measured it and it flips from bug to feature here: **shape keys deform
the SURFACE and structurally cannot move joints** (RM_ASCULPT: joints
byte-unmoved under convention keys on every class). Volume is exactly the
surface-without-skeleton job: P9-1's pose-translation correctives own the
skeleton; the volume layer must leave every joint byte-identical and move
only the skin. The skeleton-invariance instrument (VOL-APPLY) enforces it
on both rig classes — a mechanism that drifts a joint fails the bar
regardless of its IoU.

## The region language (declared)

Four region params — the roadmap's NSFW-relevant set, symmetrized (the
single view symmetrizes sides by mean, the P9-1 law):

| param | band anchor (image space) | body meaning |
|---|---|---|
| `vol.hip_w` | the hips head's projected y | hip girdle width |
| `vol.waist_w` | the mid-torso projected y ((hips+neck)/2) | waist width |
| `vol.chest_w` | the chest projected y (hips + 0.85·torso span) | bust/chest width |
| `vol.thigh_w` | the thigh heads' projected y (mean of the two upper_leg heads) | thigh width |

All band anchors come from the EXISTING payload skeleton (projections of
solved role positions — no new detection); the mask supplies the flesh
between the anchors. Region width = the horizontal extent of the mask at
the anchor row, median-filtered over ±3 rows (declared k=3, untuned).
Ratios normalize by the projected torso span (|hips−neck| in image space),
so every number is unit-free and both sides of the comparison measure with
the SAME function.

## The solve (declared)

- Reference side: u2net mask (the ADOPTED model — the product path) →
  region widths at the payload anchors → ratios.
- Rig side: the rig's own render, alpha = the EXACT silhouette (the
  engine measures itself, no model in this half) → the same measurement.
- Per region: `factor = ref_ratio / rig_ratio`, clamped to [0.5, 2.0]
  (declared, untuned; a clamp fires a loud note in the report — never a
  wild solve silently truncated).
- **ABSOLUTE-TARGET semantics (the S36 law)**: shape-key VALUES are set
  to the solved value (a re-solve overwrites, never composes — a re-solve
  after an artist tweak is a deliberate overwrite, reported as such).

## The delivery candidates (declared BEFORE measurement)

### (a) `shape_key_inflate` — engine-authored convention keys

The engine builds each region's shape key ON THE SKINNED MESH from its
base rest geometry: a deterministic tent-band radial inflate. Vertex v's
delta = `w_band(v) · radial_unit(v) · amplitude` where the band weight is
a tent function of v's distance along the body axis (hips→neck line)
around the band center (half-width declared per region: hips ±0.14·torso,
waist ±0.12, chest ±0.12, thigh ±0.10 — untuned), `radial_unit` is v's
horizontal direction away from the body axis (the XZ-plane radial, hips-
depth anchored), and the displacement is horizontal-only (X and Y world
plane) — the declared circular prior makes depth follow width; the
vertical (Z) component is zero. Key VALUE = the solved relative delta
(factor − 1, signed). The keys persist with the convention names — the
artist-exit rule: every result lands on editable targets.

- Required rig-side artifacts: **0** (the engine creates + shapes + sets
  the keys on any armature-deformed mesh).
- Side effects (published): +4 shape keys on the mesh.

### (b) `region_lattice` — mesh-bound lattice bands

One mesh-bound Lattice enclosing the torso region, control points
displaced by the band deltas (the S36-measured mesh-only lattice half —
which for volume is the RIGHT half, surface-without-joints). Required
artifacts: 0; side effects: a persistent scene object + modifiers. The
S36 lesson predicts the surface behaves; the probe measures whether the
band localization beats or loses to (a) on the IoU bar and determinism.

### (c) `armature_scale` — declared structurally suspect, measured for the record

The P9-1 mechanism family (girdle-bone widening) moves JOINTS — the
double-counting hazard against P9-1 and a violation of the
skeleton-invariance requirement. The probe measures it anyway (the
P9-1 discipline: measured, never assumed) and expects the invariance
instrument to refuse it.

## The SELECTION BAR (the P9-1 verbatim pattern)

> Candidates holding the A.1 IoU bar (>= 0.85, visible-view scoped) on
> BOTH rig classes WITH byte-identical joints advance; among them the
> fewest required rig-side artifacts wins; a tie breaks by candidate
> name ascending (`shape_key_inflate` < `region_lattice` < `armature_scale`).
> ALL candidates missing the bar on either rig (or any candidate moving a
> joint) ends Phase 9 REFUSED-with-evidence — the volume REPORT still
> ships as data, the auto-volume claim is never made.

Repair cycle: DEFAULT one (Annex A.2) — a candidate that misses may
re-run once before the verdict is recorded.

## The benchmark fixture set (the A.3 fixture law, made concrete)

- **Rig classes**: the P9-1 two (metarig-class canonical naming +
  Mixamo-class at the 0.01 scale), now with a PERSON-SHAPED engine-built
  mesh (the slab lesson: P9-1's fixtures tested joint positions; volume
  benchmarks must test SILHOUETTES — a box-person mesh: head, neck,
  torso, hip band, arms, legs as one deterministic from_pydata grid,
  nearest-bone weights, the S36 recipe generalized).
- **Reference classes** (declared untuned D-008 deltas, engine-rendered
  with the SAME deterministic WORKBENCH recipe, 640x960, level frontal
  camera at the Scene Test class):

| class | hip_w | waist_w | chest_w | thigh_w |
|---|---|---|---|---|
| wide_hip | +20% | 0 | 0 | 0 |
| thick_thigh | 0 | 0 | 0 | +20% |
| heavy | +15% | +15% | +15% | +15% |
| slender | −12% | −12% | −12% | −12% |

- **The masks**: the reference side runs THROUGH THE ADOPTED MODEL
  (u2net.onnx from the P1-1 manifest flow, `RM_U2NET_ONNX` env for
  probe/gate runs — never committed, zero default-use outbound, rows
  print SKIPPED honestly when the artifact is absent, the XBOT pattern);
  the sculpted side measures its own render's alpha EXACTLY. The A.1
  comparison (sculpted alpha vs reference u2net mask) therefore carries
  the model's real boundary error INSIDE the bar — the product claim,
  end to end. The model's own error is published as a decomposition row
  (IoU of u2net vs alpha on the reference render).
- **Nothing committed**: fixtures, renders, masks at probe/gate time in
  a temp dir; the committed artifact is the SCORED numbers. Optimism
  caveat verbatim on every synthetic-derived claim: *measured on
  synthetic prior-consistent ground truth; real-detector noise is not
  in these numbers; the Annex A.1 re-validation trigger applies when
  real labeled fixtures enter the workflow.*

## The instruments (declared BEFORE measurement — RM_VOL rows)

- **VOL-FIXTURE** — both rig classes x the 4 reference classes build;
  person-shaped meshes skinned; alpha GTs non-degenerate (coverage in a
  declared sane band, 1%–40% of frame).
- **VOL-MODEL** — the adopted artifact verified against its D-025 pin
  (sha256 + bytes), contract probed (input/output shapes), the
  reference masks produced; the blind-guard decomposition row: IoU
  (u2net vs alpha) >= 0.75 on the reference render (derivation: the
  adoption measured 0.8699 on this class; a mask below 0.75 means the
  artifact regressed or went blind — the tier-2 lesson — and the run
  refuses rather than solving toward a broken mask). This is a GUARD,
  not the product bar.
- **VOL-SOLVE** — the pure solve: authored-GT width recovery within FP
  epsilon core-side; clamp behavior loud; determinism.
- **VOL-APPLY** — the REAL addon apply on BOTH rig classes: keys created
  by convention name, values set absolutely, and **every joint
  byte-identical** pre/post (the skeleton-invariance instrument, the
  S36 pose-state bytes pattern).
- **VOL-BAR** — THE A.1 row: per rig class x reference class,
  IoU(sculpted render alpha, reference u2net mask) >= 0.85; worst case
  published. The visible-view scope is part of the row's label, never
  dropped.
- **VOL-EDITABLE** — the artist exit: setting every key to 0.0 restores
  the base mesh (evaluated-vertex drift <= 1e-4 m — an order above the
  S36 float32 evaluated-mesh noise band, 0.1 mm beneath notice at
  posing distance); keys persist with convention names (editable
  targets).
- **VOL-NOTARGET** — a rig whose mesh is absent (or armature-deform
  missing): the loud capability line verbatim, nothing created.
- **VOL-DETERM** — twin runs byte-identical (solve factors, key values,
  reports).

Final row `RM_VOL GATE: PASS` (the crash-proof contract — grep-tested
both shapes; no `: FAIL` row may exist on a green run; SKIPPED shapes
are grep-pinned beside PASS shapes where the model artifact may be
absent, the RM_OVERLAY/XBOT precedent).

## Policy (D-019)

The segmentation model is an input-side tool: it segments whatever the
user's reference contains and generates nothing; the existing subject
checks apply unchanged; MCP gains no new tool and stays SFW
(test-pinned). The model download rides the P1-1 manifest flow
(checksum-pinned, user-initiated, zero default-use outbound — the
network-audit test extends over the new entry). Fixtures are
engine-built clothed-class geometry; LO-authored references stay LOCAL,
never committed; nothing from the scan dir commits.

## What P9-2 deliberately does NOT do

- No depth claim beyond the declared circular prior; the visible-view
  scope is part of every bar (strike S10).
- No per-frame soft tissue, no video masks (P9-3's declared limits).
- No operator/panel wiring and no user-facing solve-flow integration
  (P9-3's declared scope — the S31/S36 unit-boundary precedent).
- No edits to the certified FK/pose-apply path and NO joint motion (the
  invariance instrument is the proof).
- No payload format change, no new pose field (shape keys are mesh data;
  D-025 is consumed by the adoption decision).
- No fine-tune, no retraining, no scraped data — adopted weights only
  (the D-024 ritual law).

## Probe plan (xtask/volume_probe.py — BEFORE the core build)

Two-world instrument, the D-009 shape (the driver is an xtask python
script; Blender stages run headless via subprocess; the mask stage runs
onnxruntime in the driver's interpreter — Blender's bundled python has
no onnxruntime and never gains it):

1. Blender stage A — build BOTH rig-class fixtures + the 4 reference-
   class variant meshes; render all with alpha (deterministic
   WORKBENCH, fixed camera); report projected anchors + joint bytes.
2. Driver stage — u2net over the reference renders (the reference
   masks); the solve (reference widths vs fixture-self widths); the
   candidates' drafts live HERE first (the coupling/finger recipe: the
   probe contains the drafts, core lifts the winner, tests pin it).
3. Blender stage B — apply each candidate's delivery, verify joint
   invariance, re-render, report key values + vertices.

Rows: RM_VOL as declared above, the selection verdict PRINTED from the
numbers, twins byte-identical. The gate (xtask/volume_gate.py, the
sibling file) re-runs the SELECTED mechanism through the REAL addon
apply on BOTH rig classes + the guard + the editable exit + the loud
no-target + twins, wired into verify_pose_apply.sh after the
auto-sculpt block + the Makefile lint list, all prior gate numbers
byte-identical (the S35/S36 RST/RM_ASCULPT rows included).

## As-built (S37, 2026-09-30) — the landing

**The probe's verdict: `shape_key_inflate` SELECTED** — worst region IoU
**0.9499** vs the 0.85 bar over 8 cases (both rig classes x 4 reference
classes), every case improving over the published no-solve counterfactual
(0.8907); the lattice class measured OUT (region IoU 0.0000: the draft's
radial cage displacement shrinks the figure out of the region — the class
is not region-faithful); the armature class moved joints and is out by
the invariance contract regardless (its record case: region IoU 0.9016
with joints moved). The REAL-apply gate (xtask/volume_gate.py, 7 RM_VOL
GATE rows) passes on both rig classes: joints byte-identical through the
key warp, all 16 mid-band width ratios within the 10% bar of their
factors, the artist exit at 1.19e-07 m, the loud no-mesh refusal
verbatim, twins byte-identical.

- **Amendment A1 (fixture repair, measured)**: the first fixture class
  (arms +-0.24..0.32, legs +-0.08..0.21, camera 4.0 m) failed its own
  premises — u2net BRIDGED the 7 px arm-torso gap on widened-pelvis
  classes (randomly per render, poisoning the hip rows: solved
  wide-hip-class hip factors read 1.797 on an authored 1.15) and FILLED
  the 26 px crotch gap (poisoning the thigh sums). The landed class:
  arms +-0.34..0.42 (slight A-pose), legs closed to touching
  (+-0.02..0.17), camera 2.5 m. The blind-guard then passed (min
  0.7738 >= 0.75).
- **Amendment A2 (anchor placement)**: the thigh anchor moved to
  mid-band (T = -0.70): at -0.43 it sat 2 px under the pelvis bottom
  edge and a widened pelvis bled into the thigh rows (wide_hip's thigh
  read 1.16 on an authored 1.0).
- **Amendment A3 (the binding bar's form, probe-earned BEFORE the
  verdict)**: the model-mediated IoU cannot discriminate a solved sculpt
  from an unsolved base — candidate b, provably not at the reference,
  scored model-mediated 0.82-0.91 (indistinguishable from the solved
  sculpt): the u2net shape prior compresses silhouette differences. The
  BINDING A.1 form is therefore the model-free exact-alpha IoU (sculpt
  vs reference silhouettes); the model-mediated number ships as
  published information (final: worst 0.8592). The model's product role
  — measuring the reference's region widths — is certified separately
  by the SOLVE row (measured factors track the authored deltas within
  ~3%: heavy 1.147/1.15, slender 0.882/0.88, wide_hip 1.176/1.20,
  thick_thigh 1.176/1.20).
- **Amendment A4 (fixture skin ownership)**: nearest-bone weighting
  starves the hip band — the hips bone is a short center-line segment,
  so the pelvis's outer columns bind to the LEG bones and the band's
  warp never reaches its extent carriers. The volume fixture declares
  PER-BOX skin ownership (pelvis to hips, waist to spine, chest to
  chest, legs to upper_leg, arms to upper_arm, head/neck to
  head/neck) — the groups must match the region semantics. Product
  rigs keep their artist weights; the capability line covers starved
  rigs.
- **Amendment A5 (region-scoped IoU + the counterfactual)**: whole-frame
  IoU cannot discriminate (the UNSOLVED base already scores
  0.8838-0.9744 against the references — the box-person silhouette
  changes little frame-wide). The A.1 IoU is computed over the FOUR
  BANDS' row ranges (the volume claim's actual scope) and the row
  publishes the no-solve counterfactual alongside; the pass requires
  BOTH sculpted >= 0.85 AND sculpted > counterfactual.
- **The 5.1 product lessons (measured, do not re-learn)**:
  (a) shape-key `slider_min` defaults to 0.0 — NEGATIVE key values
  (slender references, the shrink direction) are silently dead until
  `slider_min` is widened; the apply sets [-1, 1] at key creation.
  (b) ALL geometry math must run in ONE unit system: a Mixamo-class
  rig's mesh-local units are the armature's data units (x100), NOT
  world meters — mixing them puts every zt outside the tents and the
  apply becomes a silent no-op on that rig class (the addon now derives
  hips/neck/span/axis entirely in mesh space).
  (c) `shape_key_add(from_mix=True)` (the ops default) seeds new keys
  with the MIXED state of already-valued keys — cross-band
  contamination; the apply uses `from_mix=False`.
  (d) accumulated scenes poison renders AND evaluated-extent
  instruments: every case renders in a CLEAN scene, and the gate's
  width cases rebuild in fresh scenes (the two-pass fixture rule's
  sibling).
  (e) measurement windows must cover the CLAMP ceiling's widest warp,
  not just the solved factor (a 0.09 radius sat exactly at the x1.2
  warp and float-excluded the widened edge verts — an all-ratio-1.0
  lie), and x-windows alone re-include neighbouring boxes — the gate
  measures the band's OWNED vertex groups.
- **The landing shape (the S31/S36 unit-boundary precedent)**: core
  `volume.py` (the pure bits: band params, the clamp law, the
  absolute-target value law, the loud capability line, VolumeReport; 9
  CI tests, 654 total, including the addon module's bpy-free import),
  addon `volume.py` (apply_volume_sculpt + measure_zero_restore — the
  generic, role-mapped, unit-safe apply), the probe pipeline
  (volume_common/volume_probe/volume_measure/volume_rows — the two-world
  instrument; the u2net artifact rides the P1-1 manifest flow,
  `rigpose models download u2net`, and every model row prints SKIPPED
  honestly when it is absent), the gate (volume_gate.py, model-free,
  CI-runnable) wired into pose-verify after the auto-sculpt block + the
  Makefile lint list.
- **NOT landed (declared)**: the operator/panel wiring and the
  user-facing solve-flow integration (P9-3's declared scope); per-frame
  soft tissue (P9-3's declared limit); video masks. Optimism caveat,
  verbatim: *measured on synthetic prior-consistent ground truth;
  real-detector noise is not in these numbers; the Annex A.1
  re-validation trigger applies when real labeled fixtures enter the
  workflow.*
