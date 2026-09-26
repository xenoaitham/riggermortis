# Camera (P8-5) — design of record

The P8-5 measured reference-camera solve, designed BEFORE the build (the
docs/FACE.md sibling pattern — a sibling design page, never a fork). It
extends docs/SCENES.md § Camera v0: the APPROXIMATE v0 stager (landed P8-1,
stages at IoU 0.8279 on the benchmark) KEEPS DOING ITS JOB and stays as the
fallback path; P8-5 adds the measured solve that fits yaw/pitch/distance/
height from the body keypoints with the canonical skeleton's proportions as
the known ruler.

NOTHING on this page is a claim until a test, probe line, or gate number
cites it. The pre-declared bars (Annex A.1) are LAW: **GT-set yaw MAE ≤
7.5°, pitch MAE ≤ 5°, distance MAE ≤ 12%; framing IoU ≥ 0.75; low
confidence REFUSES to stage.** Refuse branch (Annex A.2): GT-set yaw MAE
> 15° ends the full solve; camera v0 remains and L4 ends CLOSED-v0.

## The one structural fact (what makes a measured solve possible at all)

A single view of an UNKNOWN pose of a KNOWN skeleton is underdetermined —
the roadmap says so. The solve therefore consumes the ALREADY-SOLVED
canonical pose (`CanonicalPose.positions`, the P1-4 lift) as its 3D depth
estimate and reads the CAMERA evidence from quantities that survive the
front-prior lift: the IN-PLANE lengths of the canonical rulers (they come
straight off the image, D-008 role semantics) and the figure's framing box
(the detector bbox, already in the payload). The canonical skeleton's
declared proportions are the RULER: apparent-length / canonical-length is
the foreshortening × scale product, and the ruler PATTERN (lateral vs
vertical vs forward) separates yaw from pitch from distance.

## The declared camera model (extends the pinned v0 pinhole)

World: Z up, subject faces −Y, character-left = +X (the house convention).
Lens 50 mm on a 36 mm sensor (v0's pinned values, reused); sensor height
AUTO-fit: `sensor_h = 36 · res_y/res_x`. The v0 level-camera projection is
pinned to 1.1e-07 (scene_probe CAMERA-PINHOLE); P8-5 composes yaw+pitch by
building the view basis from the camera position C and target T:

    forward = normalize(T − C)            # camera looks at the target
    right   = normalize(up_world × forward)   # up_world = (0,0,1)
    up_cam  = normalize(forward × right)

    d   = (P − C)·forward                  # view depth
    u   = 0.5 − (P − C)·right / d · f/sensor_w    (viewer-right convention
    v   = 0.5 + (P − C)·up_cam / d · f/sensor_h    matches v0 at yaw=pitch=0)

At level front this reduces to the pinned v0 model verbatim. The PROBE
verifies the composed model against Blender's own `world_to_camera_view`
over a yawed+pitched grid (err ≤ 1e-4 bar) before anything else consumes it
— the CAMERA-PINHOLE pattern one rotation richer (that row is where a sign
flip dies, not in a review).

**Parameter conventions (declared):**
- `yaw Δ` — the RELATIVE viewing azimuth: the angle between the subject's
  facing axis and the camera ray, horizontal. **Δ > 0 = the camera views
  the subject's RIGHT flank.** Image signature (derived from the model
  above, probe-pinned): the nose proxy sits at POSITIVE x relative to the
  mid-shoulder point exactly when Δ > 0 (`sign(Δ) = sign(nose_x −
  mid_shoulder_x)` in the pose's plane coords).
- `pitch θ` — the camera's elevation: **θ > 0 = the camera looks UP at the
  subject** (camera below the target). Solved GEOMETRICALLY from the ruler
  system, never from the aim convention (an aim-derived pitch would be
  identically right by construction against GT cameras aimed at the target
  — a rigged bar; the honest evidence is the horizontal-vs-vertical ruler
  mismatch, § The solve).
- `distance D` — horizontal camera-to-subject-axis distance, CANONICAL
  units (hip height = 1). The addon converts to world meters by the posed
  rigs' measured scale (the coupling-pass placement precedent:
  `s = world torso span / 0.45`).
- `height H` — camera z above the pose's lowest observed joint (the
  ankle class), canonical units. Reported; feeds the staging and the
  pitch cross-check; no Annex bar (the pitch bar covers the pair).

## The rulers (derived from the declared skeleton — one source of truth)

All in canonical units (hip height 1), derived at import from
`canonical.py` / the solved-pose role semantics — never re-typed literals:

| ruler | roles | canonical length (derivation) |
|---|---|---|
| `R_SHOULDER` | `upper_arm.L ↔ upper_arm.R` | 2·0.13 = **0.26** (the shoulder kps sit at the upper-arm bone HEADS — the D-008 role semantics) |
| `R_HIP` | `upper_leg.L ↔ upper_leg.R` | 2·0.08 = **0.16** (rest_skeleton leg offset) |
| `R_TORSO` | `hips ↔ neck` (in-plane) | **0.45** (`TORSO_SPAN`: 0.09+0.17+0.19) |
| `R_STAND` | nose-class `head` z minus `foot` z | 0.56 − (−0.97) = **1.53** (head role = mid-shoulders + neck 0.11; ankle = hips − upper 0.50 − lower 0.47) |

(The rulers derive at import from `rest_skeleton` — the declared skeleton
is the one source of truth; the table documents the derivations.)

**The scale carrier (the A1 amendment, earned before the core build)**: the
pose solve fits its scale FROM the torso span, so the in-plane canonical
torso length is canonical BY CONSTRUCTION — it carries shape (the
foreshortening pattern), never the absolute scale. The absolute scale k —
apparent-normalized length per canonical unit — rides the payload's own
`solve.scale` field: `k = scale/img_w`. The grid therefore fits ONLY the
shape unknowns `(Δ, |θ|)` with k closed-form; the torso equation drops out
of the grid (it defined k circularly — the first draft's bug, caught by
the probe's first run before any core code existed: every GT case refused
pose-class because the in-pose distance read 1.39 at a true 4.0).

## The solve (per figure — pure core, stdlib, deterministic)

Inputs: one figure's `CanonicalPose` (positions + joint_confidence),
detector `bbox` (pixels), image `width`/`height` (all already in the v3
payload — **no payload format change, no new additive field; the payload
contract stays byte-identical**, pinned by the existing tests).

Observables (in-plane = the pose's (x, z); each consumed kp must clear the
confidence floor else the component LEDGERS):

| observable | reads | encodes |
|---|---|---|
| `sh = |upper_arm.L − upper_arm.R|` in-plane | 2 girdle kps | lateral foreshortening: `S·sqrt(1 − cos²θ·sin²Δ)` |
| `hp = |upper_leg.L − upper_leg.R|` in-plane | 2 hip kps | the SAME lateral class — redundancy for confidence, not a new unknown |
| `k = pose.scale/img_w` | the payload's scale field | the absolute scale: `k = f/(d_axis·sensor_w)` → distance |
| `nose_dx = head_x − (upper_arm.L_x + upper_arm.R_x)/2` | nose + girdles | facing SIGN of Δ (sign only — the magnitude prior is too soft to trust) |
| `v_extent = bbox_h_px / img_h` | the payload bbox | the standing-class ruler (§ below) |

with the weak-perspective factors above (lateral lines: `sqrt(1 − cos²θ·
sin²Δ)`; vertical lines: `cos θ`).

**Yaw+pitch+scale: the joint grid solve.** Yaw and pitch are COUPLED in the
lateral equation (a 20° elevation reads a 30° yaw as ~20° if pitch is
ignored — the decoupled estimate would blow the 7.5° bar, so it is not the
design). The solve fits `(Δ, θ, k)` jointly: minimize over a DETERMINISTIC
coarse grid (`Δ ∈ [−80°, 80°] step 5°`, `|θ| ∈ [0°, 35°] step 5°`, k
closed-form from the payload's own scale field — see the A1 amendment
below) the squared residuals of the
shoulder equation + the torso equation + the hip equation, then a FIXED
local refine (3 rounds of coordinate descent at ±2°/±0.5°/±0.1°, axes in
keyed order Δ→θ, best-cell start, fixed round counts). No randomness, no
data-dependent iteration counts — byte-deterministic by construction
(DETERM row pins it).

**The pitch-sign rule (declared, probe-planned)**: the ruler equations are
EVEN in θ — a centered subject's kp geometry pins |θ| but not its sign
(the first-order pitch-sign evidence — perspective size gradation or
vertical-line convergence — is ~3% at close distance and vanishes with
framing; not a v1 signal, documented). The sign resolves through the
declared CAMERA-BAND prior (D-008 untuned, order-of-magnitude): the camera
frames a standing subject from between ankle level and head height —
`cam_z ∈ [z_min − 0.1, z_max + 0.1]` pose units. Both sign hypotheses
produce a cam_z from the height arithmetic (§ below); exactly one inside
the band → that sign (ledgered "sign from camera-band prior"); both → the
one nearer the subject mid (center-framing prior, ledgered); neither →
the candidate NEARER THE BAND wins (ledgered "sign by band proximity" —
the sign rule never refuses by itself; pose-class refusal stays the
D_stand ruler's job). Small-|θ| mis-signs cost a few degrees; large-|θ|
mis-signs are exactly the cases the band resolves — the GT sweep measures
the residual class and publishes it.

**Distance**: `D = f·cos θ/(k·sensor_w)` — k is the axis-depth scale, D
the horizontal distance (the cos θ axis-depth correction; the GT sweep's
per-distance-class errors verify it).

**Height** (the exact pitched inversion, not a level approximation): the
anchor's frame position is RECOVERED from the payload's own fields — the
kps-extent center in pose coords is `z_mid·scale` px below the anchor
pixel, and the bbox center approximates the kps extent (declared
approximation; the detector box fits the person), so
`v_anchor = 1 − (bbox_cy + z_mid·scale)/img_h`. With
`β = (v_anchor − 0.5)·sensor_h/f` (the bbox-center ray slope) and the
solved θ:

    cam_z_above_anchor = −D·(β + tan θ) / (1 − β·tan θ)     (exact under
                                                the composed model; the
                                                level case reduces to the
                                                classic (0.5−v_anchor)·D·
                                                sensor_h/f)

`H = cam_z_above_anchor − min_z_pose` (above the lowest observed joint).
`|β·tan θ| ≥ 0.99` → refuse (degenerate inversion). The GT sweep's
per-elevation-class height errors verify the sign of every term — the
MODEL-SIGN probe row exists precisely to kill a sign flip here.

**Standing-class check**: the bbox-ruler distance
`D_stand = f·cos θ·R_STAND/(v_extent·sensor_h)` must agree with the
in-pose distance — `D_stand/D ∈ [0.75, 1.33]` declared band; outside it
the pose class (sitting, crouching, arms dominating the box) is outside
the standing-prior solve → **REFUSE** (loud, ledgered), never a staged
guess.

**Solve envelope (declared)**: `|Δ| ≤ 80°`, `|θ| ≤ 35°` — at/over the
envelope edge the figure REFUSES (the ruler system is out of its solved
class; a profile or top-down view is not v1's claim). Torso ruler
degenerate (`tn` below half its canonical length, or hips/neck unobserved)
→ REFUSE — the heavily-foreshortened/sitting class, named in the work
order.

## Confidence + refuse-to-stage (the honesty law, made numeric)

`confidence = 0.4·ruler_agreement + 0.3·lateral_agreement + 0.3·obs_strength`

- `ruler_agreement` — `|D_stand/D − 1|` mapped through the declared band
  (≤ 0.15 → 1.0, ≥ 0.35 → 0.0, linear between): the pose-class check IS
  the primary confidence signal.
- `lateral_agreement` — shoulder vs hip equation residuals through the
  same band shape (two rulers of the same class agreeing).
- `obs_strength` — min confidence of the consumed kps (the
  chain-is-as-strong-as-its-weakest-joint rule).

**REFUSE-TO-STAGE (loud, never a wrong silent camera)**: the stage gate is
BOTH of — (a) the solve's `confidence ≥ CAMERA_CONF_FLOOR 0.55` (the
CONVENTIONS ambiguity bar, reused untuned — the coupling/finger/face floor
precedent), and (b) the MEASURED framing `IoU ≥ CAMERA_IOU_FLOOR 0.75`
(Annex A.1, unchanged — the staged camera is still measured by projecting
the posed subject, the v0 machinery verbatim). Either failing: the operator
stages NOTHING, reports the measured values + the per-component ledger
(reason strings with the exact numbers), and the scene is untouched. A
refused component (missing girdles, envelope breach, pose-class breach) is
a refusal with its reason string — never silently dropped.

## Multi-figure scenes: the consensus

Each CAST figure solves independently (its own Δ is relative to ITS facing
— figures may face different ways). One camera must satisfy all:
confidence-weighted consensus with per-figure residuals — `D`, `θ`, `H`
weighted means; `Δ` a weighted CIRCULAR mean (`atan2(Σw·sinΔ, Σw·cosΔ)` —
+175° and −175° must never average to 0). Figures disagreeing beyond the
declared band hit the confidence (their residuals are LOUD report rows);
no usable figure → refuse. Never auto-enforced beyond the report: the
camera stages or refuses as a whole.

## The addon staging composition (additive; v0 preserved verbatim)

New `stage_scene_camera_measured(payload, assignments, core=None)` in
`addon/riggermortis_addon/scene_camera.py` (the sibling-function pattern —
`stage_scene_camera` v0 is untouched, the RM_SCENE CAMERA-* rows keep
exercising it unchanged). Flow: solve per cast figure (core, pure) →
consensus → build the camera position from the POSED rigs' measured world
geometry: subject target = the posed-joint bbox center (the v0 subject
points), world scale `s` = posed torso span / 0.45, facing = the rigs'
world orientation (canonical −Y rotated by the armature's world rotation),
camera at `target + s·D·(facing rotated by Δ) + s·H above the rigs' lowest
ankle` aimed at the target → place, `view_layer.update()` (the stale-matrix
lesson), project the posed subject → **IoU vs the reference bbox union
(unchanged v0 measurement)** → BOTH floors (§ above) → stage:
created-or-updated `rm_scene_camera`, scene camera set, props
`rm_camera_solve = "MEASURED"`, `rm_camera_conf`, `rm_camera_iou`,
`rm_camera_params` (yaw/pitch/dist/height, rounded, the report's numbers) —
or the loud refuse report with the measured ledger and nothing staged.
The Casting Desk button calls the measured path; the report carries both
the solve's numbers and the framing measurement.

## The GT-set protocol (SYNTHETIC-labeled, engine-built per Annex A.3)

**KNOWN camera → render → re-solve through the pipeline's own deterministic
renderer.** The GT generator: engine-built canonical-exact fixture poses
(two poses: rest-class + one asymmetric posed class), GT cameras on a
declared grid — `Δ ∈ {−40, −20, 0, 20, 40}° × D ∈ {2.6, 4.0, 6.0} ×
elevation offsets e ∈ {−1.0, −0.35, 0, +0.35, +1.0}` (camera z = target z
+ e; the GT camera aims at the subject target — operator behavior) — 75
cameras × 2 poses = 150 GT rows per sweep. Every claim from this set is
labeled **SYNTHETIC** and ships with the optimism caveat VERBATIM: *measured
on synthetic prior-consistent ground truth; real-detector noise is not in
these numbers; the Annex A.1 re-validation trigger applies when real
labeled fixtures enter the workflow.*

Three evidence tiers, in increasing honesty:
1. **Projection GT** (the identifiability class): fixture joints projected
   through the composed model → pose-solve → camera-solve → error bars vs
   the Annex bars. Deterministic, pure, the sweep the bars bind on.
2. **Render + REAL detector** (the end-to-end class): the same GT cameras
   render the bone-proxy fixture headless (workbench, deterministic), the
   PINNED DWPose detects the render, the full pipeline (solve_pose →
   camera solve) runs on the DETECTED kps → the detector-noise-inclusive
   rows, published next to tier 1. If the detector refuses the proxy
   fixture, the finding is LOUD (the row fails until the fixture detects
   or the limitation is documented — a silent skip is illegal).
3. **REAL rows** (no GT exists): the P1-9 photos — the solve publishes
   `(Δ, θ, D, H, confidence, staged/refused + reasons)` per photo. Never a
   prose claim; the outputs and their confidences ARE the data.

## Accept bars (Annex A.1, pre-declared — the gate implements these)

1. **GT-set error bars** (tier 1, the sweep): yaw MAE ≤ 7.5°, pitch MAE
   ≤ 5°, distance MAE ≤ 12%.
2. **Framing IoU ≥ 0.75** for the solved cameras over the sweep
   distribution; the gate's REAL-Blender stage row additionally measures
   the staged camera through `world_to_camera_view` (the v0 machinery).
3. **Refuse-to-stage on degraded inputs**: kp-starved (girdle kps below
   the floor), foreshortened/torso-degenerate, pose-class breach (the
   D_stand band), envelope breach — 100% loud refusals with reasons,
   zero staged cameras, zero guessed parameters.
4. **Twin byte-identity** (DETERM), the payload contract unchanged
   (hands-free face-free byte-identity pins hold), all prior gate numbers
   byte-identical, the full battery green.

Refuse branch (Annex A.2): GT-set yaw MAE > 15° → the full solve is
REFUSED; camera v0 remains, L4 = CLOSED-v0, documented in DECISIONS. Never
cut P8-3 fingers or P8-2 coupling (Annex A cut order); the full solve is
itself the cut-order item after P8-9 time-to-fix — a park here produces
its evidence and the ledger row ends REFUSED-with-evidence, never unknown.

## Policy (D-019)

Cameras carry no content — no new policy surface; the existing subject
checks apply unchanged; MCP gains no new tool and stays SFW (test-pinned).
The camera solve consumes geometry (kps, boxes) only.

## What P8-5 deliberately does NOT do

- No payload format change (the solve reads the v3 fields that already
  exist; the byte-identity contracts are pinned).
- No per-frame camera TRACK yet (video → a camera track rides P8-8's
  per-frame scene work after the static path is proven).
- No lens/sensor estimation (declared 50 mm/36 mm, the v0 values — a
  wrong lens reads as a distance bias, inside the 12% bar's class).
- No roll estimation (detector kps carry no roll evidence; world up is
  the declared prior).
- No camera KEYFRAMING (v0's manual-keyframing note stands; P8-5 stages a
  STATIC measured camera).

## Probe plan (xtask/camera_probe.py — BEFORE the core build, RM_CAM lines)

- (a) MODEL — the composed yaw+pitch projection vs Blender's
  `world_to_camera_view` over the grid (err ≤ 1e-4); sign conventions
  pinned (the nose-sign rule, the v-up rule).
- (b) SOLVE-GT — the tier-1 sweep: per-parameter MAE vs the Annex bars +
  the full distributions.
- (c) IOU — the solved cameras' framing IoU distribution vs the 0.75
  floor (projection-space).
- (d) REFUSE — the degraded classes (kp-starved, torso-degenerate,
  pose-class breach, envelope breach) → 100% loud refusals, ledger
  verbatim.
- (e) RENDER-DETECT — tier 2: headless proxy renders + the REAL pinned
  DWPose → end-to-end rows published (or the loud finding).
- (f) REAL — tier 3 on the P1-9 photos: outputs + confidences published,
  refusal counts honest.
- (g) DETERM — twin solves byte-identical.

The probe contains the DRAFT solve (the coupling/finger/face recipe): core
`camera.py` lifts it, tests pin it, the gate wires the REAL Blender path.

## Amendment record (probe-earned, recorded before the core build)

- **A1 — the pose scale is the absolute-scale carrier.** The pose solve
  fits its scale FROM the torso span, so the in-plane canonical torso
  length is canonical BY CONSTRUCTION — it carries shape only, never the
  absolute scale. k = scale/img_w (the first probe run refused every GT
  case pose-class: the in-pose distance read 1.39 at a true 4.0).
- **A2 — the pitch-sign rule** (the ruler equations are even in θ; the
  camera-band prior resolves the sign — see § Confidence for the band).
- **A3 — the nose-offset magnitude is destroyed by the payload's derived
  head placement; its DIRECTION survives** — rho = head_dx/head_dz inverts
  in closed form: sin(Δ) = 2.2·rho/(1 − rho²) (the pipeline's own declared
  head-placement model, the 0.10/0.11 ratio — not a soft prior). Yaw is
  closed-form; the grid collapsed to a 1-D pitch fit (later to
  closed-form; see A5/A7).
- **A4 — the shoulder kp sits at the upper-arm bone HEAD**: R_SHOULDER =
  2·0.13 = 0.26, not the 0.90 the first draft asserted (the LAYOUT row
  caught it — the declared-ruler value must match the role positions).
- **A5 — the depth gradient across the body is FIRST-order at close
  distance** (the scaled-ortho closure breaks): kappa(z) =
  k0·(1 + z·sinθcosθ/D)⁻¹. The gradient is pure signal: with the hip
  girdle at the anchor and the shoulders at z = 0.45,
  **g = (hp/H − sh/S)/(0.45·hp/H) = sinθcosθ/D in closed form — and
  sign(g) IS the pitch sign** (D > 0). The torso ruler is structurally
  dead through the real pose solve (its scale fits FROM the torso — tn/T
  pins to 1.0), so pitch closes elsewhere (A6/A7).
- **A6 — the vertical ruler is the NOSE-TO-ANKLE span** (pose units) with
  a measured first-order depth-mix term: a(Δ) = 0.083·cos²Δ (0.083 at yaw
  0, 0.035 at yaw 40 on the noiseless sweep); the bbox extent carries
  MORE mixing (nose + toe forward offsets) and stays a class check only.
- **A7 — dual-regime pitch magnitude**: the gradient has the leverage
  high, the vertical at the front — |2gD| ≥ GRADIENT_SWITCH 0.15 (i.e.
  |sin 2θ| ≥ 0.15) → θ = asin(2gD)/2; below → the vertical estimate
  (R-inverted per sign branch), CLAMPED to the regime's own bound
  |θ| ≤ asin(0.15)/2 = 4.3° (2gD = sin 2θ exactly — D cancels; a vertical
  read past the bound contradicts the regime premise). A gradient read
  disagreeing with the vertical by > 7° while |2gD| < 0.4 is contaminated
  (near-level cameras read fake gradients through the pose solve's
  second-order terms) → the clamped vertical wins.
- **A8 — fixture law (the girdle kps are rulers)**: a fixture pivot that
  moves a SHOULDER off the torso plane reads as a fake depth gradient;
  arms swing about the shoulder kp (elbow moves, girdle fixed), legs
  about the hip kp. The first `posed` fixture hunched its left shoulder
  and 57 sweep cases refused on the fake pitch — the honesty law worked;
  the fixture was wrong.
- **A9 — MODEL-SIGN floors redeclared from the measurement**: pitch-sign
  ≥ 60% (the sign is genuinely unresolvable below the regime switch — the
  per-row coin lands in the SOLVE-GT MAE; a systematic FLIP still dies
  at ~0-30%); height MAE ≤ 0.45 canon (no Annex bar; feeds staging).
- **A10 — the projection sign convention (caught by CAM-MODEL against
  Blender)**: `right = fw × world-up` IS the screen-right axis, so the
  model reads `u = 0.5 + (rel·right)/d·f/sw` and
  `v = 0.5 + (rel·up)/d·f/sh` with `up = right × fw` — the v0 page's
  unrolled minus belonged to v0's specific mirrored euler camera
  (screen-right = −X); the general form carries the sign in `right`.
  Under this basis the facing sign is the page's original rule:
  sign(Δ) = sign(head_dx). The Blender-side quaternion is built FROM the
  basis (no track_quat ambiguity) and CAM-MODEL measures the match at
  2.3e-07.
- **A11 — the sensor AUTO fit is general**: the sensor's LONG edge
  (36 mm) fits the frame's LONG side — landscape 36 × 36·h/w, portrait
  36·w/h × 36 (Blender's default fit). The v0 landscape-only formula
  mis-modeled portrait references; the stager additionally sets the
  scene render res to the reference dims for the measurement (restored
  on refuse) so the framing transfer is exact.

## Probe answers (as-built, 2026-09-26 — `xtask/camera_probe.py`, RM_CAM
### lines; 8/8 PASS exit 0, pure core + the pinned DWPose + Blender)

- **SOLVE-GT** (the Annex bars, tier-1 deterministic GT set, 150 GT
  cameras = {yaw −40..40 step 20} × {D 2.6/4/6} × {elev −1..+1} × 2
  poses, noiseless projections through the REAL pipeline):
  **yaw MAE 2.58° (bar 7.5), pitch MAE 4.83° (bar 5), distance MAE
  3.42% (bar 12), 0 refused, 150/150 solved** [SYNTHETIC, prior-
  consistent GT; the optimism caveat verbatim: measured on synthetic
  prior-consistent ground truth; real-detector noise is not in these
  numbers; the Annex A.1 re-validation trigger applies when real labeled
  fixtures enter the workflow].
- **IOU**: solved-camera framing IoU median 0.9621, 99% ≥ the 0.75
  floor (n=150, projection space, the declared staging placement).
- **REFUSE**: 5 degraded classes (kp-starved girdles, torso-degenerate,
  crouch fixture, cropped-bbox, profile) → 100% loud refusals with
  verbatim reasons; zero guessed cameras.
- **MODEL-SIGN**: the nose-sign rule 120/120 (a systematic flip dies
  here — the CAMERA-PINHOLE pattern one rotation richer); pitch-sign
  82/120 ≥ the 60% floor; height MAE 0.363 canon.
- **RENDER (tier 2 NOT MET with evidence — the D-015 decomposition,
  measured)**: the pinned DWPose person detector is BLIND to the
  engine's mannequin fixture class — 0 detections / 36 renders across
  three fixture generations (workbench stick, workbench thick, EEVEE
  sun-lit). The renders exist and the detector ran; the answer is no.
  The Annex bars bind on the tier-1 deterministic GT set + the tier-3
  real rows; the A.3 re-validation trigger applies to any future
  detector-visible fixture path. Never relabeled as real.
- **REAL** (tier 3, the P1-9 photos, no GT exists): 10 figures on 10
  photos, 9 refused with verbatim reasons (cropped/crouched/starved
  classes — the honesty law on real data), 1 solved and published with
  its confidence. The outputs ARE the data; never a prose claim.
- **DETERM**: twin solves byte-identical.
- Blender-side cross-check of the composed projection model: the GATE's
  CAM-MODEL row (world_to_camera_view, err ≤ 1e-4).

## As-built

(appended at the core/gate landing — nothing above is a claim until a
test, probe line, or gate number cites it)
