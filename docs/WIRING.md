# Sculpt + animation wiring, P9-3 — design of record

Phase 9's third rock, designed BEFORE any code (the VOLUME.md sibling — a
sibling design page, never a fork). The declared unit-boundary debt (the
S31/S36/S37 precedents) comes due: P9-1's proportion sculpt and P9-2's
volume sculpt are MEASURED and LANDED mechanisms with no user-facing
surface. This session wires them into the product flow and lands the
honest-physics proof that the wiring's order is the right order.

## The user-facing flow (declared)

```
reference image --rigpose pose--> payload.json          (exists, P1-4)
reference image + payload --rigpose solve-sculpt--> sculpt.json   (NEW)
payload + sculpt.json --[Blender: Apply Sculpt]-->  the sculpted rig  (NEW)
the sculpted rig --[the certified pose/animation paths]--> unchanged
```

The order IS the honest physics (the roadmap's P9-3 sentence, made
structural):

1. The sculpt edits REST-side data only — the proportion correctives are
   POSE-bone locations (S36), the volume warp is shape-key DATA with the
   solved value (S37). Neither touches the certified FK/apply/bake paths:
   **zero apply-path changes** (the S36 property, restated as the wiring's
   acceptance).
2. The static sculpt applies ONCE, at frame one, BEFORE animation drives
   the rig. There is no per-frame soft tissue, no simulation, no
   per-frame sculpt channel in any baked action (proven structurally by
   WIRE-FLOW's fcurve audit — see the instruments).
3. After the sculpt, the pose/animation consumes the sculpted character
   unchanged: poses key ROTATIONS; the sculpt's locations and shape-key
   values are not keyed, so they ride under every frame.

Per-frame soft tissue stays OUT (declared; simulation is a different
product). Video masks stay OUT (the volume solve is single-image; the
video path would re-solve per clip — not this phase).

NOTHING on this page is a claim until a gate row or test cites it. No
payload format change (the reference-side measurement rides a SEPARATE
solve artifact — the payload contract, v1/v2/v3 byte-identities and the
D-021/D-022/D-023 additive namespaces are untouched; **D-026 stays the
next free number** — the wiring adds no pose field). No new model (u2net
is D-025's adopted segmentation pass, already pinned; the wiring only
CALLS it through the P1-1 manifest flow).

## The sculpt solve artifact (`sculpt.json`, format 1)

The volume solve needs the ADOPTED segmentation model (onnxruntime) —
which Blender's bundled Python does not have and never gains (the D-009
law: heavy compute lives in the CLI; Blender consumes artifacts). The
proportion solve needs only the payload's solved positions. Both
reference-side measurements land in ONE deterministic artifact written by
the NEW CLI command:

    rigpose solve-sculpt <image> <payload.json> --out sculpt.json [--figure LABEL]

- **Proportion half (pure core, no model)**: reference ruler ratios from
  the payload's solved canonical positions via
  `core.measure_proportion_ratios` (the S36 function, unchanged).
- **Volume half (the D-025 pass)**: re-detect the image with the pinned
  DWPose (the payload carries no 2D keypoints — amendment A1 below), build
  the ANCHOR SET from the detected body keypoints, mask the image with
  `u2net.onnx` (the P1-1 manifest flow, `rigpose models download u2net`),
  measure region widths with the S37-certified instrument, and store the
  ratios.
- Refusals are LOUD and actionable: no person detected (the detector's
  own message), anchor keypoints below the 0.55 confidence floor (the
  CONVENTIONS bar — a bad anchor would fabricate widths), the u2net
  artifact absent (the download hint), payload/figure mismatches. A
  refused solve writes nothing.

```json
{
  "format": 1,
  "figure": "figure 1",
  "reference_image": "ref.jpg",
  "image_size": [w, h],
  "proportions": {"reference_ratios": {"torso": 1.0, "shoulder_w": ...}},
  "volume": {"ref_ratios": {"vol.thigh_w": ..., "vol.hip_w": ...}},
  "notes": []
}
```

Readers validate LOUD: unknown format refuses; unknown band params refuse
(`validate_factors`' law); a missing half reports the loud line and the
other half still applies (the halves are independent); `from_dict` never
guesses. The contract (write/read/validate) is pure stdlib in core
(`riggermortis.sculpt`) and test-pinned.

**Amendment A1 (declared before code — the product anchors)**: the probe
pipeline projected FIXTURE skeleton anchors through the fixture camera;
the product reference side has no camera — the anchors are the DETECTOR's
own keypoint positions in image space (the D-008 role semantics already
say a role's position is the joint at its bone's head, and the detector's
hips/shoulder keypoints ARE those joints). The anchor set: hips = mean
(body kps 11, 12); neck = mean (body kps 5, 6) — the DWPose demo's own
neck derivation, pinned in inference/poses.py; waist/chest = the torso
line hips→neck interpolated at the S37-certified fracs (ANCHOR_FRACS:
0.25 / 0.80); thigh anchor = the line extended to −0.70 (the A2 mid-band
anchor), leg centers at the two hip keypoints' x. The measurement
(normalized by the projected torso span, median band k=3) is the S37
instrument VERBATIM, lifted into core so the product path and the probe
pipeline share ONE copy (the D-016 lockstep law; the volume gate re-run
proves the lift byte-identical).

## The apply half (the add-on)

ONE shared addon module (`riggermortis_addon.sculpt_wire`) with TWO
entry points: the operator (`rm.apply_sculpt`) and the session executor
(`sculpt` action) — same function, same report, the P1-6/apply_pose
pattern.

- **Proportion apply**: reference ratios from `sculpt.json`
  (`proportions.reference_ratios`); base ratios from the rig's mapped
  REST heads (`bone.matrix_local`, armature space — ratios are unit-free,
  the scale-pairing law); `build_proportion_target` →
  `apply_proportion_sculpt` (the S36 apply, UNCHANGED). The response-step
  scale is derived from the rig (`1 / uniform object scale` — 1.0 for the
  metarig class, 100.0 for the Mixamo class at 0.01), the S36 gate's
  `space_scale` parameter with a product-side derivation declared HERE.
- **Volume apply — the rig-side base measurement (the engine measures
  itself)**: factors need the RIG's own region ratios. The instrument is
  the S37-certified one — the rig's exact-alpha silhouette measured with
  the same `region_widths` — made SCULPT-INVARIANT by measuring a staged
  REST snapshot: pose-bone transforms saved and cleared, shape-key values
  saved and zeroed, a level-frontal WORKBENCH frame rendered
  (film-transparent; camera fit = declared constant x the rig's world
  torso span, lens 35 — the fixture class), anchors projected from the
  REST heads, widths measured, then EVERY touched setting restored (the
  turntable/pages stage+restore discipline). Measuring the current
  sculpted state instead would compose factors — the S36 sequential-sculpt
  failure class; the staged rest snapshot is what makes
  `factor = ref / base` absolute-target on every re-apply.
  factors = `solve_factors(ref_ratios, base_ratios)` (the clamp law
  [0.5, 2.0], clamps land in the report notes, loud) →
  `apply_volume_sculpt` (the S37 apply, UNCHANGED: convention keys,
  mesh-space units, `from_mix=False`, slider [−1, 1], absolute values).
- **Idempotence** (the S36/S37 law, BOTH sculpts): the proportion target
  is absolute in armature space and the volume keys are set absolutely —
  a re-apply re-lands the same state. Proven by WIRE-RESCULPT at
  animation scale.
- **Capability lines** (the P8-4 verbatim pattern): no payload →
  proportions skipped loud with the `rigpose pose` hint; no sculpt.json →
  volume skipped loud with the `rigpose solve-sculpt` hint; a starved rig
  (missing movable roles / no armature-deformed mesh) is refused by the
  S36/S37 apply functions' own verbatim lines. The operator reports the
  lines in the panel; the session action returns them in the report.
- **Editable targets** (the artist exit): the proportion correctives are
  visible pose-bone locations; the volume keys are convention-named shape
  keys with the full [−1, 1] slider — every result is artist-tweakable,
  and zeroing the keys restores the basis (the S37 measure_zero_restore).

## The session action (`sculpt`) — additive, SFW

`KNOWN_ACTION_KINDS` gains `"sculpt"` on BOTH sides (addon
`session.py` + `mcp/session_bridge.py`) in the SAME commit as the
golden-schema test extension (the P8-1 apply_scene pattern). Params:

```json
{"kind": "sculpt",
 "params": {"payload_path": "...", "sculpt_path": "...",
            "armature_name": "...", "proportions": true, "volume": true}}
```

`payload_path` is required when `proportions` is true; `sculpt_path` is
required when `volume` is true; missing inputs are structured actionable
errors, never silent skips. The MCP TOOL TABLE is untouched (session-only
surface, like apply_scene); **the sculpt carries no content by itself**
— it adjusts mesh/pose data on an existing rig, generates nothing — so
D-019's SFW pin holds unchanged and stays test-pinned.

## The instruments (declared BEFORE measurement — RM_WIRE rows)

The gate (`xtask/wiring_gate.py`, the volume_gate sibling, run INSIDE
headless Blender, model-free) re-uses the S37 fixture builders (ONE copy
— the motion_fixture rule) on BOTH rig classes:

- **WIRE-FIXTURE** — both rig classes build; volumes and bands sane.
- **WIRE-MEASURE** — the wiring's staged rest-snapshot measurement on the
  PRISTINE base fixtures reproduces the S37 pipeline's own alpha
  measurement (region ratios within a declared 2e-2 relative tolerance —
  same instrument, different plumbing; the tolerance absorbs pixel-vs-
  render plumbing, not solve error).
- **WIRE-SOLVE** — authored reference ratios → factors →
  `apply_volume_sculpt`: mid-band evaluated extents scale by the factors
  (the S37 GATE-WIDTH pattern, 10% bar) and every pose bone is
  byte-identical through the key warp (the invariance contract).
- **WIRE-FLOW — THE animation-order proof**: proportion + volume applied
  at the rest state → a REAL multi-frame action baked through the add-on
  bake path → assertions: (a) shape-key values and pose-bone locations
  byte-identical pre/post bake (the animation keys nothing sculpt-side);
  (b) the frame-one evaluated band width matches the pre-bake width
  (drift <= 1e-05 m, the S36 GATE-COMPOSE bar family); (c) FK re-eval
  worst <= 0.5 deg across frames (the RM_BAKE instrument, locked-chain
  deviation reported separately, honest); (d) the baked action's fcurves
  carry ROTATION channels only — no per-frame sculpt channel exists (the
  per-frame-soft-tissue-OUT declaration made structural).
- **WIRE-RESCULPT** — re-apply the sculpt AFTER the animation: the staged
  rest snapshot measures the same base, the factors re-solve identically,
  key values and pose locations re-land BYTE-IDENTICAL (the absolute-
  target law at animation scale), and the artist's pose is restored
  untouched (pose bytes identical around the measurement).
- **WIRE-OPS** — the REAL operator (`bpy.ops.rm.apply_sculpt`) produces
  the direct path's state exactly (the S34 OPS pattern; {'REGISTER',
  'UNDO'} + {'FINISHED'}, poll, ERROR-report classes).
- **WIRE-SESSION** — the session executor's `sculpt` action returns the
  direct path's report (same function underneath; kinds table additive
  both sides pinned by test in the same commit).
- **WIRE-NOTARGET** — starved rigs: the loud lines verbatim, nothing
  applied; a missing sculpt file reports the solve-sculpt hint.
- **WIRE-DETERM** — twin wiring runs byte-identical (values, locations,
  reports).

Final row `RM_WIRE GATE: PASS` (the crash-proof contract — Blender masks
crashed scripts with exit 0; grep-tested both shapes; no `: FAIL` row may
exist on a green run). Wired into `verify_pose_apply.sh` after the volume
gate block + the Makefile lint list, all prior gate numbers
byte-identical.

## Policy (D-019)

The wiring adds no content-carrying surface: it adjusts an existing rig's
mesh/pose data from the user's own reference measurement. The
segmentation pass stays input-side (D-025's lines unchanged); MCP gains
no new tool and stays SFW (test-pinned); the model download rides the
P1-1 manifest flow only (checksum-pinned, user-initiated, zero
default-use outbound — the network-audit test extends unchanged).
Fixtures are engine-built clothed-class geometry (the A.3 law);
LO-authored references stay LOCAL, never committed.

## What P9-3 deliberately does NOT do

- No per-frame soft tissue, no simulation, no video masks (declared OUT).
- No payload format change, no new pose field (D-026 stays free).
- No new model, no new dependency (u2net is D-025's; onnxruntime never
  enters Blender).
- No edits to the certified FK/pose-apply/bake paths (the S36 property is
  the acceptance, not a hope).
- No scene-level sculpt wiring (multi-rig scenes sculpt per-figure by
  running the action per armature; a scene-wide action is later work —
  measured first, per the standing law).
- No claims beyond the gate rows: the wiring claim cites RM_WIRE; the
  volume claim's scope stays VOLUME.md's (visible-view, four bands,
  static); the proportion claim's scope stays AUTO_SCULPT.md's.
- Optimism caveat verbatim on every synthetic-derived claim: *measured on
  synthetic prior-consistent ground truth; real-detector noise is not in
  these numbers; the Annex A.1 re-validation trigger applies when real
  labeled fixtures enter the workflow.*

## As-built (S38, 2026-10-03) — the landing

The wiring shipped exactly as declared above, with the gate rows green on
both rig classes (11 RM_WIRE grep rows, `xtask/wiring_gate.py`, wired into
pose-verify after the volume gate block; FULL battery PASS with every prior
gate number byte-identical — the volume pipeline's certified rows re-ran
EXACT under the lifted measurement, BAR 0.9499 / counterfactual 0.8907 /
model-mediated 0.8592):

- **WIRE-MEASURE 0.0000** worst relative band deviation on BOTH classes
  (bar 2e-2) — the staged rest-snapshot measurement reproduces the S37
  pipeline's exact-alpha instrument exactly.
- **WIRE-SOLVE** factors land EXACT at the authored delta on both classes;
  every pose bone byte-identical through the key warp.
- **WIRE-FLOW (THE order proof)**: the sculpt survives the animation
  BYTE-IDENTICALLY (key values + pose locations), frame-one band width
  drift **0.00e+00** m (bar 1e-05), bake re-eval **0.0000 deg** AND the
  independent re-eval **0.0000 deg** over 70 checks (bar 0.5), and the
  baked action carries ROTATION channels only — the per-frame-soft-tissue-
  OUT declaration is structural.
- **WIRE-RESCULPT** (the artist exit at the sculpt frame): volume values
  byte-identical, the proportion target re-lands within its bar (worst
  0.000029 metarig / 0.047085 mixamo vs 0.05), the action stays assigned.
- **WIRE-OPS / WIRE-SESSION**: the real operator (the addon enabled the
  checkbox way) and the session executor land the direct path's state
  EXACTLY (key values + pose locations byte-identical, {'FINISHED'}).
- **WIRE-NOTARGET / WIRE-DETERM**: the loud refusals verbatim; twins
  byte-identical.

Tests: 15 new CI tests (669 total): the sculpt solve contract (round-trip,
loud validation), the product anchors (A1), the lifted measurement (GT
rectangles + the pipeline alias identity — `volume_common`'s helpers ARE
the core objects), the solve/clamp laws, the addon wiring module's
bpy-free import + the loud missing-input lines, the session kinds mirrored
both sides, and the executor's pre-bpy input validation.

**Gate-earned amendments (recorded with the numbers, the honest-fight
record):**

- **A2 (the scene law's second earn)**: the two rig-class fixtures share
  one world position; the first draft ran both classes in one scene and
  WIRE-SOLVE read factors 0.9895-1.0127 instead of 1.15 — the METARIG
  fixture had been sculpted first, and the mixamo fixture's render-based
  base measurement measured the WIDENED UNION of the two overlapping
  figures. Every render-adjacent case now runs in a FRESH scene containing
  exactly its fixture (the S37 lesson, verbatim: accumulated scenes poison
  renders AND instruments).
- **A3 (the re-eval frame)**: the bake's default frame_offset 1 maps
  source frame f to Blender frame f+1; a re-eval reading `frame_set(f)`
  measures exactly the frame spacing as error (the first draft's
  20.0000 deg "FK error" was one frame of the 20-deg swing). The gate's
  re-eval reads `frame_set(f + 1)` — matching the bake's mapping.
- **A4 (the re-sculpt semantics, made honest)**: a re-solve on an
  ANIMATED rig compensates the current frame's rotation BY DESIGN (the
  absolute TARGET is the joint position, not the pose-bone location), so
  byte-comparing locations across an animation is the wrong instrument;
  the landed checks are the ones that carry the claim: volume values
  byte-identical, the evaluated target re-landed within its bar, the
  action intact. `measure_volume_base_ratios` additionally MUTES the
  assigned action during the rest snapshot (fcurves override
  matrix_basis at evaluation — without the mute a re-measure mid-
  animation would read the current frame, not the rest).

The solve artifact's u2net-dependent half (`rigpose solve-sculpt`) is
exercised live-verified through the adopted artifact's managed path (the
P1-1 flow); the CI gate stays model-free by construction (the gate
authors the reference ratios; the model rows print SKIPPED honestly where
the artifact is absent, the XBOT pattern).

Optimism caveat, verbatim: *measured on synthetic prior-consistent ground
truth; real-detector noise is not in these numbers; the Annex A.1
re-validation trigger applies when real labeled fixtures enter the
workflow.*
