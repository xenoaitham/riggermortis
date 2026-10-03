# Auto-sculpt, P9-1 proportion matching — design of record

Phase 9's opener, designed BEFORE any measurement (the SCENE_TEST.md
sibling pattern — a sibling design page, never a fork). The roadmap's
honest physics, verbatim: **body keypoints give SKELETON positions, not
VOLUME.** P9-1 therefore matches SKELETON proportions only — segment
lengths and girdle widths as ratios to the torso span; volume (hips/
waist/bust/thighs) is unobservable-from-keypoints and is **P9-2's
separate third-model decision**, never a P9-1 claim.

NOTHING on this page is a claim until a probe line, test, or gate
number cites it. The pre-declared SELECTION BAR (roadmap P9-1 + Annex
A.1) is LAW. No payload format change (any new pose field would be
additive with its DECISIONS entry WRITTEN at the landing — D-025 is the
next free number; the design as declared needs NO new pose field, so
D-025 stays unwritten unless the probe proves otherwise).

## The one structural fact each candidate rides on

The reference pose payload already carries the solved canonical
skeleton (`positions`, D-008 semantics: a role's position = the joint
at the HEAD of that role's bone). From it the engine measures the
reference's PROPORTION RATIOS (segment length / torso span, girdle
width / torso span). The base rig's rest skeleton gives the same
ratios rig-side. The sculpt's job: deform the rig so its rest skeleton
ratios match the reference's — then every subsequent pose apply (the
certified FK path) renders the character WITH the reference's
proportions. The three candidate mechanisms differ ONLY in HOW the rig
is made to carry the new skeleton.

**The shared target math (pure core, all three candidates consume
it)** — `build_proportion_target`:

- **Rulers** (declared, the D-008 observed set): torso span
  (hips→neck, the P8-5 ruler, ANCHOR — fixed at 1.0 by construction,
  the scale carrier is the payload's own `scale` field per CAMERA.md
  A1); shoulder girdle width `|upper_arm.L − upper_arm.R|`; hip girdle
  width `|upper_leg.L − upper_leg.R|`; four limb segments per side,
  symmetrized to one ratio by mean (upper_arm, forearm, thigh, shin).
- **Reference ratios** from the payload positions; **base ratios**
  from the rig's mapped rest heads normalized by the rig's own torso
  span (the scale-pairing law: rig-side numbers live in the rig's
  units, ratios are unit-free).
- **Intended skeleton**: hips and neck heads FIXED (the torso anchor
  — no proportion is introduced into the torso line; spine/chest ride
  it at the unchanged D-008 fractions). Shoulder/hip girdle joints
  move along the base girdle axis to the target width. Each limb
  chain re-places its distal joints along the BASE chain directions
  at the scaled segment lengths (the sculpt adjusts LENGTHS; the pose
  is applied AFTER sculpt by the certified path, which derives
  rotations — direction lives in the pose, not the rest).
- Output: `dict[role, (x, y, z)]` of intended joint positions in the
  base rig's own space + the ratio report (reference vs base vs
  target, per ruler — **the proportion REPORT ships as data
  regardless of the mechanism verdict**, the roadmap's refuse branch
  keeps its value).

## The three candidate mechanisms (declared BEFORE measurement)

### (a) `lattice` — a rig-bound lattice driven by proportion deltas

A Lattice datablock encloses the rig (declared grid 4×4×8, control
points world-arranged around the base skeleton — the compact-class
lesson from SCENE_TEST.md A2: arms HANGING, no wide T-pose spread for
the fixture). Each control point's displacement is the
inverse-distance-weighted mean (power 2, all joints, deterministic
keyed order) of the joint deltas — a smooth spatial warp that carries
every grid region's intended stretch. The lattice is bound to BOTH the
armature object and the mesh (lattice deform parent). **The Blender
unknown this probe exists to answer**: does 5.1 lattice-deform an
ARMATURE object (bone heads moving with the cage)? If the armature
half is structurally unavailable, (a) degenerates to a mesh-only
deform — the (b) failure class — and the probe records the measured
capability refusal. If it works, the joints land at the trilinear
interpolation of the intended warp — a REAL error the 5% bar judges,
never assumed zero.

- Required rig-side artifacts: **0** (the engine creates + binds the
  lattice on any skinned rig).
- Side effects (published, not the selection count): +1 persistent
  scene object (the lattice).

### (b) `shape_key_binding` — the P8-4 facial pattern generalized to body regions

Shape keys by documented naming convention, keys named == region param
(`prop.shoulder_w`, `prop.hip_w`, `prop.upper_arm`, `prop.forearm`,
`prop.thigh`, `prop.shin` — proportions apply symmetrically; the
single view symmetrizes sides by mean), key value = the ratio delta.
Exactly the FACE.md apply-(b) class. **The honest physics meets the
mechanism here**: shape keys deform MESHES, never armature data — the
skeleton stays where it was while the skin moves. The joint-position
bar is therefore expected to read the FULL intended delta as error
(the surface leaves the bone) for every class whose delta exceeds the
5% bar. The probe MEASURES this rather than asserting it: per-region
key values applied, joint errors published, AND the skin–skeleton
separation made numeric (mesh-surface displacement vs the same
region's joint displacement of 0.0). A rig WITHOUT the convention
keys cannot run this mechanism at all — the loud capability line (the
P8-4 verbatim pattern), and the REQUIRED authored artifact is the
whole point of the count.

- Required rig-side artifacts: **6 authored shape keys** (one per
  region param) per rig, PLUS their sculpted shapes (the artist's
  manual work this candidate exists to avoid).

### (c) `armature_scale_correctives` — the positions-surgery class

The SPINE.md arch class applied to the rest skeleton: the intended
joint positions are written into the armature's EDIT bones
(parent-first keyed order; bones sharing a joint move together — one
write per joint, every affected head/tail updated; the armature data
IS the skeleton, so the joints land where intended by construction,
FP-epsilon). The skinned mesh follows through its existing armature
deform weights (the fixture's weights are engine-built deterministic
nearest-bone — the deformation QUALITY of real production weights is
exactly what a real rig already carries; the probe verifies the mesh
follows the girdle/limb deltas and publishes the follow-through).

- Required rig-side artifacts: **0** (works on any armature-deformed
  mesh with the roles mapped).
- Side effects (published, not the selection count): the rest state
  is edited (persistent, artist-visible in Edit Mode — the same
  class of edit a rigger makes fitting a base mesh; undo/restore by
  re-running from the recorded base).

## The SELECTION BAR (verbatim, roadmap P9-1 + Annex A.1)

> **SELECTION BAR (round-4 strike 4.3)**: the mechanism holding the
> 5% Annex A.1 bar on BOTH the metarig and a Mixamo-class rig with the
> fewest required rig-side artifacts (tie-break: deterministic
> application — the keyed-sort law of CONVENTIONS, i.e. the candidate
> name ascending breaks equal scores); ALL candidates missing the bar
> on either rig ends Phase 9 REFUSED-with-evidence — the
> reference-proportion REPORT still ships as data, the auto-sculpt
> claim is never made.

Annex A.1, the bar itself: **post-sculpt joint positions within 5% of
the segment's length vs intent** — per adjusted segment, `|achieved
joint − intended joint| <= 0.05 × base segment length`. The girdle
rulers use the torso span as their length reference (a girdle is one
segment, hip-to-hip).

**The selection arithmetic is pre-declared (no vibes)**: candidates
holding the bar on BOTH rig classes advance; among them the fewest
REQUIRED rig-side artifacts wins; a tie on that count breaks by
candidate name ascending — `armature_scale_correctives` < `lattice` <
`shape_key_binding`. The artifact counts are declared above (0 / 0 /
6-authored), so if (a) and (c) both hold the bar, the tie-break lands
on (c) — but the NUMBERS decide which candidates advance, and a
repair cycle (DEFAULT one, Annex A.2) may re-run a candidate that
missed its bar before the verdict is recorded.

**The REFUSED branch**: every candidate missing the bar on either rig
→ Phase 9 ends REFUSED-with-evidence; the proportion REPORT still
ships as data; the auto-sculpt claim is never made; P9-2's volume
decision is NOT reached through this branch (it is its own
third-model ritual either way).

## The benchmark fixture set (the A.3 fixture law, made concrete)

- **Rig classes**: (1) metarig-class — engine-built canonical-layout
  armature + skinned mesh (the spine_gate/camera_gate two-pass fixture
  recipe, canonical bone names, rm_role props); (2) Mixamo-class — the
  same skeleton in mixamorig naming at the 0.01 armature scale (the
  finger gate's FINGER-MIXAMO convention). BOTH carry a skinned mesh
  (engine-built: a subdivided box bound with DETERMINISTIC nearest-
  bone vertex weights — no heat solver, no randomness).
- **Base skeleton** (declared, meters, Z-up, facing −Y, the compact
  class): hips head z 0.98, neck 1.42 (torso 0.44), shoulders x ±0.18
  at z 1.38, upper arm 0.26 hanging, forearm 0.24, hand 0.17; hip
  joints x ±0.14 at z 0.94, thigh 0.42, shin 0.40, ankle 0.12.
- **Reference classes** (declared untuned D-008 constants; the GT
  reference pose payload is authored ON the declared family — the
  spine-arch GT protocol, prior-consistent, SYNTHETIC-labeled):

| class | shoulder_w | hip_w | upper_arm | forearm | thigh | shin |
|---|---|---|---|---|---|---|
| heavy | +25% | +20% | 0 | 0 | 0 | 0 |
| slender | −15% | −12% | 0 | 0 | 0 | 0 |
| tall | +5% | +5% | +15% | +15% | +15% | +15% |

(deltas are ratio changes relative to the base rig's own ratio; the
torso is the fixed 1.0 anchor in every class.)

- **Nothing committed**: fixtures, payloads, and meshes are generated
  at probe/gate time in a temp dir; the committed artifact is the
  SCORED numbers, never media. Optimism caveat verbatim on every
  synthetic-derived claim: *measured on synthetic prior-consistent
  ground truth; real-detector noise is not in these numbers; the
  Annex A.1 re-validation trigger applies when real labeled fixtures
  enter the workflow.*

## The instruments (declared BEFORE measurement — RM_ASCULPT rows)

- **ASC-FIXTURE** — both rig classes × base + 3 reference classes
  build; skinned meshes present; the GT ratios round-trip the declared
  deltas (pure-math check, no Blender semantics).
- **ASC-TARGET** — the pure target math: reference ratios → intended
  positions; the authored-GT recovery within FP epsilon core-side;
  determinism.
- **ASC-LATTICE** — candidate (a) on BOTH rig classes × all 3
  reference classes: the armature-lattice capability answered FIRST
  (works / structurally unavailable — measured, never assumed); per-
  joint errors vs the 5% bar; max error published.
- **ASC-SHAPEKEY** — candidate (b): the convention keys authored on
  the fixture (the counted artifact), values applied, joint errors
  published (the structural skin–skeleton separation made numeric:
  mesh vertices move, joints do not), the no-keys rig loud-refused
  with the capability line.
- **ASC-SCALE** — candidate (c) on BOTH rig classes × all 3 classes:
  per-joint errors vs the 5% bar (expected FP-epsilon — measured,
  not asserted); mesh follow-through published (evaluated vertices
  track the girdle/limb deltas).
- **ASC-SELECT** — the pre-declared selection arithmetic over the
  measured rows: bar-holders on both rigs → fewest authored artifacts
  → name-ascending tie-break → the winner (or the REFUSED verdict)
  printed as the row's value.
- **ASC-NOTARGET** — a rig missing mapped roles (no leg chain): the
  loud capability line verbatim, the rest state byte-unchanged.
- **ASC-DETERM** — twin runs byte-identical (edit-bone positions,
  key values, lattice points, reports).

Final row `RM_ASCULPT GATE: PASS` (the crash-proof contract — Blender
masks crashed scripts with exit 0; grep-tested both shapes before
push; no `: FAIL` row may exist on a green run).

## Policy (D-019)

Proportions carry no content by themselves — no new policy surface;
the existing subject checks apply unchanged; MCP gains no new tool and
stays SFW (test-pinned). Fixtures are engine-built clothed-class
geometry (the A.3 law); LO-authored references stay LOCAL, never
committed.

## What P9-1 deliberately does NOT do

- **No volume claim** — hips/waist/bust/thigh VOLUME is unobservable
  from keypoints; P9-2's separate third-model decision (license,
  checksum, CPU budget, DECISIONS entry) either way. A P9-1 volume
  sentence is a named session failure.
- No payload format change (the target is derived from the payload at
  apply time; the report is a returned object, the camera-solve
  pattern).
- No new model, no new dependency (the P6-6 never-list untouched).
- No per-frame soft-tissue dynamics (P9-3 declares it OUT —
  simulation is a different product).
- No panel/operator wiring claimed this session (P9-3 wires the
  static sculpt into the user-facing flow; the S31 unit-boundary
  precedent — this session lands the mechanism core + the REAL-apply
  gate). *Landed since: P9-3 wires the apply into the product flow —
  `rigpose solve-sculpt` + the Apply Sculpt operator + the `sculpt`
  session action; design of record `docs/WIRING.md`, gate rows RM_WIRE
  (the proportion apply itself is untouched — this module's functions
  run unchanged underneath the wiring).*
- No edits to the certified FK/pose-apply path (the sculpt edits the
  REST; the apply path consumes rests as-is — zero apply-path
  changes, the spine-arch property).

## Probe plan (xtask/auto_sculpt_probe.py — BEFORE the core build)

One Blender-headless script (`blender -b --python
xtask/auto_sculpt_probe.py`; env `RM_CORE_SRC`, `RM_ADDON_DIR`),
emitting the RM_ASCULPT rows above. The three candidate mechanisms
live FIRST as probe-local functions (the coupling/finger/face recipe:
the probe contains the drafts; core lifts the winner, tests pin it).
Every bar-adjacent number published next to its bar; twins
byte-identical; the selection row's verdict is the probe's OUTPUT, not
its input.

The gate (xtask/auto_sculpt_gate.py, the sibling file) re-runs the
SELECTED mechanism through the REAL addon apply path on BOTH rig
classes + the loud no-target + the untouched-path byte-identity +
twins, wired into verify_pose_apply.sh + the Makefile lint list, all
prior gate numbers byte-identical (the S35 RST rows included).

## Probe answers (as-built, 2026-09-29 — `xtask/auto_sculpt_probe.py`,
### RM_ASCULPT lines; 9/9 PASS exit 0, Blender 5.1.0, engine fixtures)

- **Amendment A1 (probe-earned, recorded before the core build) — the
  rest-edit delivery is REFUTED; the corrective delivers as
  POSE-translation offsets.** The declared (c) model said "the skinned
  mesh follows through its existing armature deform weights" after an
  EDIT-mode rest re-placement. Measured: it does NOT — armature skinning
  RE-BINDS to the new rest (the deform is pose·rest⁻¹ = identity at
  rest pose), so the skeleton lands FP-exactly while the mesh stays
  behind (follow fraction ~0.00 at a real threshold; the first draft's
  0.94 was float32 noise crossing a 1e-9 threshold — the instrument's
  threshold moved to 1e-6·scale and caught it). The corrected delivery,
  same mechanism family: per-joint offsets as POSE-bone locations —
  rigid offsets in parent frames, persistent without an action, FK
  rotations compose over them, and the skinned mesh follows via real
  LBS. The head response to a location is linear and is MEASURED per
  bone (three axis perturbations), then solved exactly — no
  API-semantics betting.
- **The lattice capability answer (amendment A2 — the first reading was
  an instrument artifact, corrected by measurement)**: the REAL bind
  path (bpy.ops.object.parent_set LATTICE) adds a genuine Lattice
  MODIFIER to the MESH but only plain OBJECT-parents the ARMATURE —
  5.1 gives armatures no lattice deform. A 20% uniform lattice stretch
  moves armature evaluated heads EXACTLY 0.0 (measured; the first
  probe draft's "heads move" was float32 parent-inverse noise crossing
  a 1e-9 threshold — the threshold moved to 1e-6 and the capability
  flipped). Candidate (a) therefore degenerates to the MESH-ONLY
  deform class: the skin warps while the skeleton stays — the same
  structural failure as (b), with the separation made numeric. Worst
  fracs 0.1875 (heavy) / 0.1125 (slender) / 0.3147 (tall) — the full
  intended deltas — on BOTH rig classes; no repair cycle applies (the
  refusal is structural, not a grid-resolution miss).
- **The shape-key structural verdict, measured**: convention keys move
  the SURFACE (hundreds of vertices) while every joint stays
  byte-unchanged — the skin–skeleton separation made numeric. Worst
  fracs 0.1875 / 0.1125 / 0.3147 (the full intended deltas; the girdle
  delta propagates down each chain and the bar references each
  segment's own length). The 6-key authored artifact requirement is
  the counted rig-side cost.
- **The scale-correctives verdict (corrected delivery)**: worst frac
  **0.0000** on BOTH rig classes across all three reference classes
  (FP-exact joint placement), real mesh follow through the LBS path,
  zero required rig-side artifacts. The pre-declared selection
  arithmetic lands: sole bar-holder, fewest artifacts (0), no
  tie-break needed — **verdict: `armature_scale_correctives`**.

## As-built (S36, 2026-09-29) — the landing

The whole stack, in the camera-solve shape (pure core + bpy apply half):

- **Core** (`core/src/riggermortis/auto_sculpt.py`): the ruler set
  (torso anchor + 6 rulers), `measure_proportion_ratios`,
  `build_proportion_target` (the intended skeleton), `validate_sculpt`
  (the Annex A.1 5% bar instrument, EVERY role vs intent),
  `sculpt_capability_lines` (the P8-4 verbatim pattern),
  `ProportionReport` + `proportion_report` (the proportion REPORT that
  ships as data regardless of any verdict — a starved rig is refused
  BEFORE measurement, the lines are the report). Stdlib, deterministic,
  `AutoSculptError` in the errors module. 11 CI tests
  (`test_auto_sculpt.py`, 645 total) including the addon module's
  bpy-free import (the conftest shim).
- **Add-on** (`addon/riggermortis_addon/auto_sculpt.py`):
  `apply_proportion_sculpt` — the pose-translation correctives through
  the linear response solve (three measured axis perturbations per
  bone, closed-form solve), PARENT-FIRST keyed order (depth from the
  rig's OWN bone topology, ties by bone name), **absolute-target**
  solves (each bone's location is ZEROED before its solve — a
  re-sculpt lands the target, never composes with a previous offset;
  the gate's sequential-sculpt class caught the draft's relative solve
  leaking R·L_old into every re-run), loud capability refusals that
  touch nothing, and the structured report (worst frac + role,
  per-role fracs, pose locations, notes). `measure_mesh_follow` is the
  follow instrument at the 1e-6·scale threshold.
- **Gate** (`xtask/auto_sculpt_gate.py`, 8 RM_ASCULPT GATE rows, wired
  into verify_pose_apply.sh after the RST block + the Makefile lint
  list): GATE-SCALE (the addon apply on BOTH rig classes × 3 reference
  classes — **worst frac 0.0000 everywhere**, through sequential
  re-sculpts on ONE fixture per class, the re-sculpt idempotence for
  free), GATE-FOLLOW (LBS follow 0.76 metarig / 0.82 mixamo at the
  real threshold), GATE-COMPOSE (sculpt → the REAL payload apply: FK
  **0.0000°** (bar 0.5°) AND the sculpted girdle width SURVIVES the
  pose, drift 1.5e-06 m — locations are rigid offsets; the apply
  writes rotations only: the product claim "a pose on a proportioned
  rig stays proportioned"), GATE-NOTARGET (the capability line
  verbatim), GATE-UNTOUCHED (a zero-delta target writes nothing, pose
  state byte-identical), GATE-TWIN (19 pose bones byte-identical).
  FULL battery PASS with every prior gate number byte-identical
  (RM_BAKE 0.0242°, RM_FOOT_LOCK 0.0371→0.0000, RM_MOTION 44997×,
  RM_COUPLE 0.00016/0.00035, RM_FINGER 10.30°, RM_FACE, RM_CAM,
  RM_SPINE, RM_ROOT, RM_SANIM, RM_RUX, the 12 RST rows).
- **NOT landed (declared)**: the operator/panel wiring and the
  user-facing solve-flow integration are P9-3's (the S31
  unit-boundary precedent — this session lands the mechanism core +
  the REAL-apply gate); the volume decision is P9-2's separate
  third-model ritual.
- **No payload format change** and **no new pose field** — the target
  derives from an existing payload at apply time and the report is a
  returned object, so **D-025 stays the next free number** (the
  roadmap's additive-field rule was conditional; its condition never
  fired).
