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

## Where it hooks — nothing certified is touched

`apply_scene_payload` COMPOSES the existing apply path; it does not fork
it. Per figure: the same `apply_payload` the single-rig operator runs
(mapping from `rm_role_*` props → fallback live map; FK conversion;
`verify_application` report). The certified bake/composition, the payload
contract's apply semantics, and the review overlay are untouched — the
scene is a NEW consumer of the SAME primitives, which is why per-figure
fidelity inherits the 0.5° family bar instead of declaring a new one.

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
