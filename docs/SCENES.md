# Scenes (P8-1) — design

Written BEFORE the build (the SECONDARY_MOTION.md pattern): this page is the
design of record for Phase 8's first rock — the CanonicalScene, the Casting
Desk, and camera v0. As-built facts and measured numbers get appended to
their sections as they land; nothing here is a claim until a test, probe
line, or gate number cites it. P8-2 (coupling), P8-3 (fingers), and P8-4
(facials) EXTEND this page later; it is never forked.

**As-built status (S26, 2026-09-24): LANDED.** The probe answered all nine
unknowns (§ Probe answers), the core + add-on + session surfaces match this
design with two recorded amendments (§ Casting, subset-casting; § The
Casting Desk, pins display), and the RM_SCENE gate rows are green — see
docs/BENCHMARKS.md SCENE block for the numbers.

## What P8-1 is (and is not)

Today the engine poses ONE rig per operation: a payload carries N figure
solves (v2, P1-11 B1), but only one of them lands on one armature at a time.
P8-1 makes the SCENE a first-class object: N named figures (each a full
`CanonicalPose`) applied to N armatures in ONE operation, with authored
contact pins carried as DATA, and an approximate scene camera staged from
the reference's framing.

NOT in v1 (each a deliberate non-goal — see § Out of scope): pin
ENFORCEMENT (P8-2's coupling pass — v1 carries pins, never moves a bone
because of one), the suggestion ENGINE (proximity inference lands with
P8-2's coupling work; v1 carries `origin: "suggested"` pins as data), the
measured camera solve (P8-5 — v0 is the approximate front-prior camera),
fingers/facials (P8-3/P8-4), scene animation from video (P8-8).

## The honesty law (from the roadmap — binding on every line)

The engine may ENFORCE what the artist AUTHORED (pins, from P8-2 on) and
SUGGEST what it inferred; it never presents inferred contact or camera as
ground truth. Every inferred thing carries confidence + residual; every
gate publishes its error bars. Camera v0 is labeled APPROXIMATE in its
custom property, its report, and the docs — and it REFUSES TO STAGE below
the confidence floor instead of staging a wrong silent camera.

## Data model (core `scene.py`, scene-format 1)

Three frozen dataclasses, loud-validated at construction — the ChainSpec
discipline (ONE validator implementation, unknown fields refuse with an
actionable hint, deterministic output shapes):

``SceneFigure`` — one named figure:

| field | type | meaning |
|---|---|---|
| ``label`` | str | unique non-empty scene id ("A", "left figure", a detector label) |
| ``pose`` | CanonicalPose | the FULL solved pose (positions, flips, confidence, notes) |

``ContactPin`` — one authored-or-suggested contact link:

| field | type | meaning |
|---|---|---|
| ``figure_a`` / ``figure_b`` | str | the two figures; MUST differ (self-contact within one figure is not a scene pin — author the pose directly; refusal says so) |
| ``role_a`` / ``role_b`` | str | canonical roles (``hand.R``, ``chest`` …) — the frozen 22-role API, nothing new |
| ``origin`` | str | ``"authored"`` (the artist's word) or ``"suggested"`` (inferred — DATA the artist confirms, NEVER auto-enforced) |
| ``confidence`` | float | 0..1; suggested pins carry the inference's confidence; authored pins default 1.0 (the artist does not doubt their own pin) |
| ``note`` | str, optional | free text that travels with the pin |

Pins are stored in AUTHORED ORDER, never sorted — P8-2's conflict rule
resolves them in authored order, and reordering file output would silently
rewrite the artist's precedence. (Figures, by contrast, are stored sorted by
label — the keyed-sort law; every output path iterates the sorted order.)

``ScenePose`` — the scene:

| field | type | meaning |
|---|---|---|
| ``format`` | int | scene format, 1; unknown values refused |
| ``name`` | str | scene id |
| ``figures`` | list[SceneFigure] | labels unique; stored label-sorted |
| ``pins`` | list[ContactPin] | authored order; every endpoint references an existing figure label and a known canonical role |

`ScenePose.from_dict` / `to_dict` round-trip exactly (floats included —
`CanonicalPose.to_dict` rounds to 4 dp already, so the scene inherits its
stability). `to_dict` output is byte-stable for identical scenes
(determinism: sorted figures, authored-order pins, sorted dict keys).

`scene_from_payload(payload) -> ScenePose` is the ONE builder the add-on,
session executor, and CLI share (the payload.py discipline): it reads a v3
payload's `figures` (through `payload.figure_entries` — v1/v2 payloads
synthesize entries the same way) + `pins` (each through
`ContactPin.from_dict`). A v2 payload IS a valid scene: N figures, zero
pins.

## Payload v3 — the additive contract

The D-009 pose payload bumps FORMAT 2 → 3 with ADDITIVE fields only:

- **Write**: `build_pose_payload` gains an optional `pins` argument — a list
  of `ContactPin.to_dict()` dicts written as the TOP-LEVEL `"pins"` key
  (empty/None → the key is omitted, so a pins-free v3 payload is
  byte-identical to today's v2 output modulo the `format` integer).
- **Read**: readers accept 1, 2, 3. `figure_entries` treats format 3
  exactly like format 2 (the `figures` list is required and unchanged in
  shape). Format 1 stays read-only-synthesized. Unknown fields stay
  ignore-with-note (the standing policy — readers never refuse fields they
  do not know).
- **`pins` reading**: `payload.pins_of(payload)` returns the parsed pin
  dicts (empty list when absent); validation happens in core
  (`ContactPin.from_dict` — the ONE validator). A malformed pin refuses
  with a hint naming the offending entry index.
- **Back-compat pin (the contract test)**: a v2 payload applied through the
  v3 code produces BYTE-IDENTICAL pose-bone rotations — the apply path is
  shared (`apply_payload`), the format check widens, nothing else moves.
  Pinned core-side (figure_entries/pose_for_figure identity) AND addon-side
  (the gate's apply-fidelity rows re-run on a v2 file).
- **Old builds facing v3 files**: refuse loudly with the unsupported-format
  hint — the preset-format-2 house pattern (a new FILE read by an OLD build
  refuses; an old FILE read by a NEW build keeps working byte-identically).
  The PyPI 0.0.1 artifact keeps serving v2 payloads; the next release
  ships v3.

## The apply-scene contract

**Core (pure)**: `scene_from_payload` + the pairing validator —
`validate_casting(scene, assignments, available)` where `assignments` maps
figure label → armature name: **SUBSET-CASTING (the S26 as-built
amendment, gate-earned)** — the artist may pair any SUBSET of the scene's
figures; only the paired figures are posed and the apply REPORTS the uncast
labels (sorted, never silent). The original strict "cast EVERY figure" rule
blocked the real 12-figure detector payload on the gate's first run, so it
was amended before ship. Unchanged loud refusals: unknown figure labels,
an armature cast twice (two figures on one rig = the second silently
overwrites the first — refused), armature names missing from the offered
set. The desk NEVER guesses identity — the artist pairs.

**Add-on (bpy)**: `apply_scene_payload(payload, assignments)` — for each
(label → armature) in SORTED label order: the REAL per-figure apply path
(`pose_apply.apply_payload(obj, payload, figure=label)` — the D-009
recompute per rig, tails repair INCLUDED, exactly what `apply_pose` runs
singly) + `push_undo` once at the end. Returns an aggregated report:
per-figure rows (the apply report verbatim + the armature name),
`figures_uncast` (the sorted labels NOT paired — reported, never silent),
the pins carried (labels + roles + origin + confidence — reported, never
acted on), and the worst per-figure `worst_deg` across the scene. Applying
a scene twice is idempotent and apply order cannot change the outcome —
probe-proven BEFORE the build (RM_SCENE ORDER/IDEMPOTENT/CLEANUP:
byte-identical rotations either way).

**Session action** `apply_scene` (v1 additive — `KNOWN_ACTION_KINDS` grows
on BOTH sides of the bridge; the MCP tool table does NOT: it rides
`enqueue_action`, schema stays v1): params `payload_path`,
`assignments` (figure label → armature name), optional `mirror`
(applied per figure — the mirror toggle semantics of the single apply).
Executor: load payload (actionable error when missing), validate casting
(core), `apply_scene_payload`, structured result or structured error —
never a traceback over the socket.

## The Casting Desk (add-on UX)

One N-panel section ("Casting Desk", under the existing pose section):

- **Rows**: one per payload figure (payload from the existing
  `rm_settings.payload_path` picker — the desk adds no second file picker),
  each row: figure label + confidence + a per-row armature EnumProperty
  (dynamic items = the scene's armatures; stored per-row so the pairing
  survives panel redraws). Rows rebuild from the payload via a Refresh
  operator (draw code never mutates state — the Blender rule); existing
  assignments survive a refresh by label.
- **One action**: "Apply Scene" — validates the casting (double-cast or
  unknown-label refusals surface verbatim), runs `apply_scene_payload`,
  reports per-figure worst_deg + the pins carried, and pushes the scene
  report line into `rm_settings.last_report`.
- **Camera v0 button** ("Stage Scene Camera ~APPROXIMATE~") — § Camera v0.
- **As-built (S26)**: the operators live in `addon/casting_desk.py`
  (rows via a `RM_CastSlot` CollectionProperty on the scene settings —
  the pairing saves with the .blend; refresh is APPEND-ONLY: it adds rows
  for new payload figures and keeps every existing pairing, and stale
  labels refuse loudly at apply time in core). Pins display through the
  Last Report panel block (the apply report carries the origin-labeled pin
  line) instead of a draw-time payload read — draw code never does file
  IO. The desk NEVER guesses identity: rows start unassigned.

## Camera v0 — approximate staging, refuse-to-stage

**Semantics**: stage a scene camera whose framing of the POSED SUBJECT
matches the reference's subject framing, from the subject bounding box +
declared solve priors. APPROXIMATE, labeled everywhere, one button, manual
keyframing supported from day one (the measured solve is P8-5).

**Inputs**: the active payload's figure bboxes (pixel coords + the image
`width`/`height` already in the payload — normalized to the reference
frame), and the cast rigs' POSED joint positions (pose-bone heads after
apply + `view_layer.update()`; the subject = the union over cast rigs).

**Solve priors (declared untuned, D-008)**: the camera looks down +Y at the
subject (characters face −Y; front-on framing is the v0 prior — the P8-5
solve replaces it with measurement), 50 mm lens on the 36 mm sensor,
subject centered on the reference bbox CENTER, distance solved so the
subject's projected WIDTH fills the reference bbox's width fraction of the
frame (a 1-D closed-form solve through the pinhole model — no iteration,
no fitting).

**Measurement (the floor is measured, not asserted)**: project every
subject point through the staged camera (`world_to_camera_view` — the
probe confirms the API headless) → the frame-space subject bbox →
**IoU vs the reference subject bbox** (union of the payload's figure
bboxes, normalized). The CONFIDENCE FLOOR is **IoU >= 0.75** (Annex A.1):
at/above it the camera stages (created-or-updated `rm_scene_camera`,
made the scene camera, custom prop `rm_camera_v0 = "APPROXIMATE"` + the
measured IoU stored on the camera as `rm_camera_iou`); below it the
operator REFUSES TO STAGE — loud report with the measured IoU and the
hint (move rigs / adjust the reference framing / frame manually), and
NOTHING in the scene changes. A wrong silent camera is the failure this
button exists to prevent.

**The floor's derivation (published THIS session, strike S12)**: measured
on the gate's synthetic two-figure benchmark. Two distributions: (a) the
v0-solved camera across the benchmark references (the "intended framing"
class), (b) deliberately degraded cameras — distance off by ±50%, target
off by half a subject width, single-figure framing (the "visibly wrong
shot" class). The published gap between the distributions is the
derivation; 0.75 sits inside it with margin. Scope labeled: SYNTHETIC
benchmark derivation (the P8-5 GT set re-derives it on real references;
Annex A.1's re-validation trigger applies).

## Contact coupling (P8-2) — design (written BEFORE the build)

P8-1 carries pins as DATA; P8-2 is the enforcer: after the per-figure
solves, a deterministic COUPLING PASS moves the canonical figures so
AUTHORED pins close. This section is the design of record (the
SECONDARY_MOTION pattern: constants pre-declared untuned, honesty lines
binding, as-built numbers appended only when a probe/gate cites them).

### The one architectural fact everything rides on

`CanonicalPose` carries POSITIONS only — per-rig rotations are DERIVED at
apply time (`fk_apply.bone_target_direction` reads
`positions[child] - positions[role]`). So the coupling pass is pure
position-space surgery: move joints in `pose.positions` and the certified
apply path derives the coupled rotations on ANY rig with zero apply-path
changes. No rotation algebra in the solver, no payload format change
(pins already ride v3), no new bars for the apply itself — per-figure
fidelity stays the 0.5° family by construction.

### Scene space and placements

Canonical poses are hips-anchored and unit-less (canonical units, hip
height = 1). Coupling solves in a SHARED scene space: each pinned figure
carries a placement `(R, t, s)` — `scene_p = t + s·(R·canonical_p)`.

- **Core** (`coupling.couple_scene(scene, placements)`): placements are an
  explicit argument (pure function, explicit inputs). Every figure named by
  an enforceable pin MUST have a placement — missing ones refuse with a
  hint (the pin reports `no placement`, it is never silently skipped).
  Placement components validate loud (unit quaternion, s > 0).
- **Add-on**: placements are MEASURED from the posed rigs, not guessed —
  apply first (poses the rigs per the solved figures), `view_layer.update()`
  (the stale-matrix lesson), then per cast figure: `t` maps the pose's
  canonical ORIGIN — `t = world(anchor joint) − s·R·canonical(anchor
  joint)` (detector-solved poses anchor AT the origin — hips sits at
  (0,0,0) — so the second term is zero there and `t` is simply the posed
  anchor joint's world position; the general formula keeps engine-built
  poses whose anchor sits off-origin correct), `R` = the armature object's
  world rotation (scale-stripped via row normalization; uniform-scale
  assumption, the camera-v0 class), `s` = posed world torso span (hips
  joint → neck joint) ÷ `TORSO_SPAN` (0.45). This is the same
  approximation class the camera v0 staging already uses (rig rest
  orientation ≈ canonical axes after apply), labeled APPROXIMATE-class,
  and it is measured — never a constant.

### Enforcement gate (the honesty law, made numeric)

A pin is ENFORCED iff `origin == "authored"` AND `confidence >= 0.55`.
The floor reuses the published ambiguity bar (CONVENTIONS: geometry-only
confidence caps 0.75, ambiguity flags < 0.55) — declared untuned, not
chosen to pass a fixture. Everything else is REPORTED LOUD and moves
nothing: `suggested` pins (inference data awaiting the artist's
confirmation in the Casting Desk), below-floor authored pins, pins whose
figures are uncast (subset casting) or carry no placement. Reasons are
per-pin report fields, never a silent no-op.

### What moves — the movable-chain table (declared v1)

A role's position is the HEAD of its bone (D-008), so rotating a joint
moves its DESCENDANTS, never itself. The joints that may rotate for a
pinned endpoint are fixed by anatomy — the distal limb chains only, the
girdle/anchor joints stay rigid (D-008's solve anchors):

| endpoint role | movable joints (rotate, in this keyed order) |
|---|---|
| `hand.X`, `forearm.X` | `upper_arm.X`, `forearm.X` |
| `lower_leg.X`, `foot.X`, `toe.X` | `upper_leg.X`, `lower_leg.X` |
| `chest` | `spine` |
| `neck`, `head` | `spine`, `chest` |
| `upper_arm.X`, `shoulder.X`, `upper_leg.X`, `spine`, `hips`, `root` | none (girdle/anchor-rigid endpoint) |

An immovable endpoint contributes weight 0 — the OTHER endpoint carries
the full correction; both immovable → the pin is unclosable by
construction and reports so immediately. Spine/chest never move for hand
pins (no torso swing to chase an arm contact — the artist moves the rig;
P8-6's arch solve is the later, separately-gated torso articulation).

### The solve — deterministic iterative redistribution

Per iteration, per ENFORCEABLE pin in AUTHORED order (the conflict rule's
precedence order — the scene model already stores pins unsorted):

1. **Gap split (confidence-weighted)**: `gap = p_a − p_b` (scene space);
   weights `w ∝ (1 − confidence)` per endpoint — the better-observed role
   is trusted more and moves less; both confidence 1.0 → 0.5/0.5
   (declared edge rule); immovable endpoints take weight 0.
   Targets: `t_a = p_a − w_a·gap`, `t_b = p_b + w_b·gap`.
2. **Chain carry (the redistribution)**: for each endpoint with movable
   joints, process them root→leaf (keyed: chain depth, then name — the
   house sort). Each joint rotates its whole subtree about its OWN
   position by `1/n` of the carry angle that would take the endpoint from
   its CURRENT position to its target (recomputed after every joint — a
   sequential fixed-point pass, which bends the chain instead of swinging
   it rigidly). Descendant positions ride the rotation exactly.
3. **Iterate** up to `MAX_ITERS = 32`, early exit when the pin's residual
   drops below `1e-4` canonical units. Convergence is geometric for
   reachable targets; unreachable ones straighten the chain toward the
   target and stop improving (clamped-by-reach, reported — the 2-bone IK
   ladder's honesty, P2-5 precedent).

**Over-determined sets (competing pins)**: the damped authored-order
iteration converges to the confidence-weighted compromise (the
least-squares-family fixed point of the declared iteration); the keyed
order makes it byte-deterministic; every pin REPORTS its final residual
and any pin at/over the bar is flagged unclosable — loud, never silently
absorbed. The conflict case is a gate row, not a footnote.

**Residual bar (Annex A.1, pre-declared)**: `residual_frac = residual /
mean(scene torso span of the two pinned figures) < 0.02` — the scale-free
2% torso-span bar. Roles OUTSIDE any pinned limb's subtree are untouched
by construction (byte-exact positions, pinned core-side). Descendants of
a moved joint RIDE it as a rigid body — their positions AND segment
directions rotate together (physically unavoidable: rotating the torso
swings the arms; the gate-earned correction of this page's first draft,
which claimed directions stay at rest under a ride). What the bar then
decomposes into, as built: byte-exact non-subtree positions core-side
(unit-pinned) + live apply fidelity ≤ 0.5° vs the coupled targets
Blender-side (the scene_gate instrument) — the composition the RM_COUPLE
NONCHAIN row gates.

### The report (structured, loud)

`CoupleReport`: per-pin rows in authored order — labels, roles, origin,
confidence, `enforced` + `reason` (why not: `suggested` / `below
confidence floor` / `figure not cast` / `no placement` / `immovable both
ends`), `residual` (scene units), `residual_frac`, `closed` (frac <
0.02), `iterations`; plus `unclosable` (the loud list, authored order),
`moved_roles` per figure (sorted), and notes. Purity: `couple_scene`
NEVER mutates its input (returns coupled figure copies + the report) —
pinned by test like the certified composition. No enforceable pins →
byte-identical passthrough (zero-pins scenes are unaffected).

### Where it hooks (the addon path)

`apply_scene_payload` gains the coupling step: apply per figure exactly
as P8-1 (sorted-label order, tails repair, the real `apply_payload`) →
`view_layer.update()` → measure placements from the posed rigs →
`couple_scene` → write the coupled positions into the in-memory payload's
figure entries at FULL precision (not the file's 4 dp — riding roles keep
byte-exact segment directions so their derived rotations are untouched;
the file format is never written by the apply) → RE-APPLY per figure
(the apply is idempotent and order-insensitive, probe-proven S26) → the
report gains a `coupling` block. Scenes without enforceable pins never
enter this path — byte-identical behavior. The session action
`apply_scene` gains an optional `couple` param (default true) — additive,
the action-kind table and MCP tool schemas are untouched.

### Contact coupling as-built (S27, 2026-09-24) — probe, gate, amendments

Landed as designed, with three gate-earned amendments recorded above and
here: (1) the **placement origin** — `t` maps the pose's canonical ORIGIN
through `t = world(anchor) − s·R·canonical(anchor)` (the first draft read
`world(anchor)` directly, which displaces any pose whose anchor sits
off-origin; detector-solved poses are unaffected — hips already sits at
the canonical origin); (2) the **full-precision write-back** (§ Where it
hooks — riding roles keep byte-exact segment directions); (3) the
**rigid-ride correction** (§ The solve — riding subtrees swing their
segment directions; the Annex A.1 "unchanged" bar lives core-side on
byte-exact non-subtree positions + the 0.5° apply family, not on world
directions).

- **Probe** (`xtask/coupling_probe.py`, pure core + the REAL
  `apply_canonical_pose`, 7/7 RM_COUPLE rows PASS): CONVERGE — both pins
  of the hold-from-behind-class fixture close at fracs 0.000158/0.000189
  (bar 0.02) in 27 iterations; NONCHAIN — positions outside the pinned
  arms byte-identical, no torso swing for hand pins, and through the REAL
  apply every non-chain role's derived rotation is byte-identical while
  the chains move; CONFLICT — competing pins converge to the
  confidence-weighted compromise (residuals 0.111/0.059 reported, both
  flagged unclosable), twin byte-identical; DETERM, NOENFORCE
  (suggested + below-floor move nothing, reasons reported), REACH
  (unreachable target: unclosable loud, chain straightens toward it)
  all PASS. Probe catch pinned as a regression test: enforcement gates
  on the PIN's confidence; role joint confidence feeds the weights.
- **Gate** (`xtask/couple_gate.py` via `make pose-verify`, RM_COUPLE
  lines, Blender 5.1.0, engine-built canonical-exact fixture rigs per
  Annex A.3, the REAL scene-apply path with placements MEASURED from the
  posed rigs): COUPLE-RESIDUAL — both authored pins close at rig-space
  fracs **0.00016/0.00035** (bar 0.02), report rows closed, coupled-apply
  fidelity worst **0.0000°**; COUPLE-NONCHAIN — non-subtree positions
  byte-equal, live apply fidelity worst **0.014°** (bar 0.5°);
  COUPLE-TWIN — 42 bones byte-identical; COUPLE-CONFLICT — compromise
  reported (fracs 0.2486/0.1292), both unclosable loud, apply succeeds;
  COUPLE-NOENFORCE — a suggested pin moves nothing (byte-equal) and
  reports its reason.
- **Gate-earned fixture lesson** (the S9 class, again): the gate's first
  fixture builder created bones alphabetically and fell back silently to
  `parent=None` for children whose parents sort later (forearm →
  upper_arm) — disconnected limbs pass the core simulation while the real
  rig ignores chain rotations. The builder is two-pass now and a missing
  parent REFUSES. Only a real-Blender gate catches this class.
- All prior gate numbers byte-identical; battery green; **482 tests**
  (+23 coupling contract tests); lint clean.

## What coupling does NOT do (v1 honesty lines)

- **Joints, not skin**: pins close JOINT-to-JOINT distances (the canonical
  skeleton has no surface). The 2% bar is joint-space; surface contact is
  not claimed anywhere.
- **No figure placement**: the solver moves LIMBS, never translates or
  rotates a whole figure — rigs stand where the artist put them, and an
  unreachable pin reports `move the rigs` instead of dragging a body
  across the floor.
- **Suggested pins are never enforced**: the proximity inference (P8-2
  work, feeds the desk as DATA) proposes; only the artist's confirmation
  (origin → `authored`) disposes.
- **No torso articulation for hand pins** (the movable-chain table); spine
  motion arrives with P8-6's gated arch solve, not as a coupling
  side effect.

## Where it hooks — nothing certified is touched

`apply_scene_payload` COMPOSES the existing apply path; it does not fork
it. Per figure: the same `apply_payload` the single-rig operator runs
(mapping from `rm_role_*` props → fallback live map; FK conversion;
`verify_application` report). The certified bake/composition, the payload
contract's apply semantics, and the review overlay are untouched — the
scene is a NEW consumer of the SAME primitives, which is why per-figure
fidelity inherits the 0.5° family bar instead of declaring a new one.
The P8-2 coupling step is the same pattern one level up: a NEW pure core
consumer of the scene model, hooked between the per-figure solves and the
final apply — the apply primitives themselves are untouched.

## Determinism (pinned by tests)

- Scene dict round-trips are byte-stable (sorted figures, authored-order
  pins, sorted keys — the CanonicalPose rules inherited).
- `apply_scene_payload` iterates figures in sorted-label order; the report
  rows come out in that order; two runs on the same scene produce
  identical reports (module the frame-rate-free float reports, which are
  round-trip stable by the existing apply path's rounding).
- Camera staging is a pure function of (posed joints, payload bboxes,
  render resolution): same inputs → same camera, same IoU, same verdict.

## Probe answers (as-built, 2026-09-24 — `xtask/scene_probe.py`, RM_SCENE
lines, Blender 5.1.0 headless; all 9 PASS, exit 0)

- **MULTI-RIG-RECOMPUTE**: 0.0087° / 0.0246° worst FK error (bar 0.5°) — ONE
  payload's two figures applied to two DIFFERENT rigs (offset / rotated 12° /
  scaled 1.05×) through the real `apply_payload`; no shared-state leak.
- **ORDER / IDEMPOTENT / CLEANUP**: A-then-B vs B-then-A byte-identical (38
  bones, exact float equality); a second full apply identical; `clear_pose`
  on one rig leaves the other byte-unchanged.
- **CAMERA-PINHOLE**: measured vs hand-derived err 1.09e-07 (bar 1e-4). The
  probe caught the first draft's factor-2 error: the correct denominators
  are the FULL sensor sizes — `u = 0.5 − Δx/d·f/sensor_w`,
  `v = 0.5 + Δz/d·f/sensor_h`, `sensor_h = sensor_w·res_y/res_x` (AUTO fit,
  landscape), view depth `d = cam_y − py` for the 90°/0°/180° level camera.
- **CAMERA-YFLIP**: `world_to_camera_view` returns v-UP and does NOT clamp
  out-of-frame coordinates (a point 1 m above the axis projects to v = 2.35);
  detector bboxes are pixel v-down and frame-clamped — normalize with the
  flip, clamp AFTER.
- **CAMERA-SOLVE**: the closed-form v0 solve staged a camera measuring
  IoU 0.9657 against a deliberately off-prior reference (35 mm lens, yawed
  12°, low) — the front prior reaches beyond exact-front references.
- **CAMERA-FLOOR**: degraded cameras measure far below the solved class —
  distance ×1.5 → IoU 0.4684; single-figure framing → 0.1324. The 0.75 floor
  sits inside this gap with margin on both sides (the strike-S12 derivation,
  SYNTHETIC-labeled; published in docs/BENCHMARKS.md SCENE).
- **CAMERA-DETERM**: two solves identical (pure function of subject + ref).

## As-built (S26, 2026-09-24) — gate numbers and the two amendments

Landed as designed, with the gate earning two amendments (recorded in the
sections above and in STATE/PROGRESS): the stale-matrix lesson —
`stage_scene_camera` measures AFTER `view_layer.update()` (place, UPDATE,
then measure; `world_to_camera_view` reads a stale `matrix_world`
otherwise, and the gate honestly failed at IoU 0.07-0.65 until this was
fixed) — and SUBSET-CASTING (§ The apply-scene contract). The RM_SCENE gate
rows (real multi-figure detector payload, real models, the REAL session
executor): CASTING refusals 3/3 + subset valid; APPLY2 0.0198°/0.0063° (bar
0.5°) one 12-figure payload → 2 rigs in one action; V2-BACKCOMPAT
byte-identical (38 bones); CAMERA-REFUSE IoU 0.3388 < 0.75 with nothing
staged; CAMERA-STAGE IoU 0.8279 ≥ 0.75, APPROXIMATE-labeled, scene camera
set. All prior gate numbers byte-identical. Full battery green.

## Reproduce (as-built)

## Instruments (planned — filled with as-built numbers at close)

- **CI** `core/tests/test_scene.py`: schema validation (every refusal
  shape: unknown fields, duplicate labels, unknown roles, self-figure
  pins, endpoint-mismatch, origin/confidence bands), determinism
  (round-trip byte-identity, keyed orders), `scene_from_payload` on v1/v2
  synthesized entries, the payload v3 writer (pins carried; omitted when
  empty), the back-compat pin (a committed v2 fixture through the v3
  readers — figure_entries/pose_for_figure identity), the casting
  validator (uncast/double-cast/unknown-armature refusals).
- **Gate** — an `RM_SCENE` section in `xtask/verify_pose_apply.sh` (the
  house print-shape): 2-rig apply fidelity from ONE payload (the
  0.5° family, re-evaluated per figure), the v2 byte-identity apply row,
  camera STAGE (IoU >= floor) and REFUSE (below floor, nothing staged)
  both demonstrated, grep-tested like every RM_ section.
- **Benchmark block** — docs/BENCHMARKS.md gains the SCENE block: the
  camera floor derivation (both IoU distributions + the floor's place in
  the gap), per-figure apply numbers, SYNTHETIC-labeled.

## What is honestly out of scope (v1)

- **Pin enforcement** — P8-2's coupling pass; v1 pins are carried and
  reported, never solved against.
- **The suggestion engine** — keypoint-proximity pin inference lands with
  P8-2 (the same proximity analysis feeds both); v1 carries
  `origin: "suggested"` pins as display data.
- **The measured camera solve** — P8-5 (yaw/pitch/distance from kps, GT
  error bars). v0 is the front-prior bbox camera with the IoU floor.
- **Scene animation** — per-frame multi-figure payloads + coupling + bake
  is P8-8; v1 scenes are STATIC poses.
- **Casting persistence beyond the session** — the desk's pairing lives on
  the scene (Blender scene data, saved with the .blend); auto-pairing
  heuristics are out (the desk NEVER guesses identity — the artist pairs).
- **Camera animation** — v0 stages a STATIC camera; keyframing it is the
  artist's manual work by design (declared in the roadmap).

## Reproduce (as-built)

```bash
# the capability probe (self-contained, no models — RM_SCENE lines, 9 rows)
/home/potato/blender-5.1.0-linux-x64/blender -b --python xtask/scene_probe.py

# the unit contract (schema, determinism, payload v3, back-compat, casting)
cd core && /home/potato/miniconda3/bin/python3 -m pytest tests/test_scene.py

# the real-scene gate rows (inside the pose-apply gate; RM_SCENE lines:
# needs the real models/payloads the gate already builds)
BLENDER=/home/potato/blender-5.1.0-linux-x64/blender \
RIGPOSE=/home/potato/miniconda3/bin/rigpose \
PY=/home/potato/miniconda3/bin/python3 make pose-verify
```
