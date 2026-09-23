# Motion library retarget (P6-2) — design

Written BEFORE the build (the SECONDARY_MOTION.md/LIVE.md pattern): this page
is the design of record for the motion-library rock — **Mixamo/BVH/FBX clips
→ any mapped rig**. The as-built facts and measured numbers get appended to
their sections as they land; nothing here is a claim until a probe line, CI
test, or gate number cites it.

## What P6-2 is (and is not)

Today the only animation source is the video pipeline: frames → DWPose →
canonical solve → action. But most animators already own animation — a Mixamo
clip, a BVH mocap take, an FBX from any DCC. P6-2 makes those a **second
source for the same canonical action**: import the clip, sample its poses,
convert them to canonical poses, and the entire certified downstream
(condition → contact detect → foot lock → bake) runs unchanged — including
the foot-slide cleaning, which is the point: mocap and Mixamo clips are
notorious for sliding feet, and the certified composition exists to fix
exactly that.

The canonical skeleton stays the hub. There is no direct rig-to-rig transfer
anywhere in this engine, imported or not: source clip → canonical → target
rig, and every guarantee (FK-invariance, lock, determinism) is inherited
because nothing new touches the action after conversion.

NOT in v1 (honest scope, each a deliberate non-goal — see § Out of scope):
root/world translation, blend shapes, constraint-driven source rigs beyond
evaluated-pose reads, a clip library UI, MCP session actions, in-Blender
import buttons.

## Mechanism — conversion, not detection

The video path *estimates* a 3D pose from 2D pixels (D-008's priors, flips,
confidence). An imported clip needs no estimation — the motion is already 3D
and exact, so the converter **measures** instead of solves:

```
clip file (FBX / BVH / GLB)
  → builtin Blender importer (shell glue only, D-009 — import_and_extract.py
    already imports all three formats for the rig gate)
  → armature + action in the open .blend
  → SOURCE-side mapping: the existing mapper maps the clip's skeleton to
    canonical roles (Mixamo is gated since P0-15; BVH naming is a probe item)
  → bridge samples per frame: frame_set → view_layer.update() → read every
    mapped role bone's evaluated head/joint positions (world, armature space)
  → core converts to CanonicalPose:
      positions = (p_source − p_hips) · (0.45 / torso_span_rest)   [hips at origin]
      flips     = measured flexion sign (no ambiguity — it is 3D)
      confidence 1.0 + provenance notes ("measured from 3D clip, not solved")
  → CanonicalAction (action_from_poses — the P2-3 constructor)
  → condition_action → contacts.lock_feet → bake_action     [ALL UNCHANGED]
```

Conversion rules, each stated so a test can pin it:

1. **Positions, not rotations.** A canonical pose IS its role positions;
   the FK apply derives rotations from them (P1-5 from-to math). The
   converter reads evaluated joint positions and never touches rotation
   curves — no euler/quaternion/x-form trap can leak through, whatever the
   source baked.
2. **Scale-free by rest reference.** The video path rescales per frame
   (the "breathing" artifact P2-6 stabilizes). A rig is rigid, so the
   converter uses ONE constant: the source rest pose's torso span
   (hips → mid-shoulders) set against the canonical 0.45-unit girdle span.
   An imported clip is scale-invariant by construction.
3. **Hips-anchored, walk-in-place.** Positions are hips-relative (the solve's
   own contract) and the clip's root translation is dropped — same D-008
   boundary as the video path, same honest label. A clip with root motion
   still converts; it converts to walk-in-place and the notes say so.
4. **Per-clip rest alignment.** Canonical space is Z-up, facing −Y (D-006).
   Clips arrive in any orientation; the converter measures the alignment
   from the source REST pose (minimal rotation carrying measured
   hips→mid-shoulders onto the canonical up, signed forward resolved the
   same way the canonical rest skeleton defines it) and applies it to every
   frame. The probe MEASURES what each importer delivers (glTF's Y-up
   conversion, BVH's import scale) instead of assuming any of it.
5. **Missing roles skip, loudly.** Roles the mapper could not map (or the
   clip's skeleton lacks — a torso-only BVH, a facial-only rig) are absent
   from those frames and the report lists them — the same honest-skip
   ledger every pass keeps.
6. **Timing is the clip's own.** Frames sample 1:1 across the action's
   frame range at the clip's fps (a stride parameter may subsample; never
   interpolates). Deterministic: same file + settings = the same
   CanonicalAction, byte-for-byte.
7. **Confidence is honest metadata.** A measured 3D pose has no detection
   uncertainty: confidence 1.0 with a provenance note — distinguishable
   from a solved pose (which never claims 1.0 on observed roles) and from
   the manual-reassignment convention (which rides a different field).

## What the certified composition does to imported clips

Everything — unchanged, and that is the feature:

- **condition_action** (hip stabilize / 1€ smooth / keyframe reduce) is
  OPTIONAL per bake, exactly as for video jobs. Mocap is typically
  clean-sample-rate noisy in different ways than the detector; the defaults
  stay D-008-untuned and the CI composition keeps smoothing off.
- **contacts.detect** runs on the converted positions and finds real
  contact intervals (the mocap contact problem, solved by the existing
  hysteresis instrument).
- **lock_feet** pins planted feet — turning a sliding Mixamo walk into a
  locked one is the deliverable, measured by the same foot_slide metric.
- **bake_action** keys the TARGET rig (any mapped rig — the P2-8 three-rig
  gate is the template), with the secondary-motion binding available
  afterward exactly as for video actions.

No stage learns that the action came from a clip instead of a video. That
indifference is the design goal and the CI tests pin it: an imported-clip
action and a synthetic action of the same poses must produce byte-identical
bakes.

## What is honestly out of scope (v1)

- **Root motion / world translation.** Canonical actions are walk-in-place
  (D-008); the converter drops clip translation and notes it. Positional
  state is the declared upgrade — it changes the same contract the
  secondary-motion positional upgrade would (they are the same decision,
  deliberately coordinated, not two independent scope creeps).
- **Blend shapes / facial curves.** The canonical skeleton is a 21-role
  body; faces do not exist in it.
- **Constraint-driven source rigs.** The converter reads EVALUATED poses
  (frame_set + update), so simple constrained sources often work, but rigs
  whose action lives on constraint inputs rather than bone curves are not a
  supported source class — the sampled result is honest (it is what Blender
  evaluates) but unsupported. The report says which path produced it.
- **Non-humanoid clips.** The mapper's quadruped detection exists for rig
  MAPPING; there is no quadruped canonical motion. Unmapped skeletons
  refuse with the mapper's own actionable errors.
- **In-repo clip files.** No animation clip ships in the repository ( Mixamo
  downloads are login-bound — recipe, not fixture; licensing for
  redistributing clips is a P6-3-class POLICY call). CI gates on
  synthetic clips GENERATED headlessly (Blender exports BVH and FBX, so
  fixtures are buildable in-CI with zero downloads) and, locally, on the
  already-gated Xbot.glb path if it carries clips (probe item).

## In-repo vs documented recipe (the scope note)

**Lands in-repo:** the converter (bridge sampling + core conversion), the
CI-testable fixture generation (synthetic BVH/FBX exported headlessly), the
probe, and a gate section — only if the probe proves the buildable half.
**Stays a documented recipe:** obtaining Mixamo clips (Adobe login —
NEEDS-HUMAN class, same as the P0-15 export was until the three.js Xbot.glb
path replaced it), converting third-party DCC exports, and any per-engine
quirks users hit on their own files. The engine consumes what Blender
already imported; teaching Blender to import is the user's one command, and
`import_and_extract.py` already demonstrates all three importers headlessly.

## Probe answers (as-built, 2026-09-22 S23 — `xtask/motion_probe.py`,
## RM_MOTION lines, Blender 5.1.0 headless, ALL PASS / exit 0)

- **EXTRACT-RELATION PASS** — `pb = C @ rest @ basis` re-asserted on a posed
  parent (rest@basis delta 0.000000 vs basis@rest 1.408832; a non-commuting
  roll discriminates). The relation P6-1's probe proved is reused, not
  re-derived.
- **BVH-ROUNDTRIP PASS 0.000000 canonical-units** (bar 0.005) and
  **FBX-ROUNDTRIP PASS 0.000000** (bar 0.005) — hips-relative normalized
  joint positions survive exporter→importer exactly at the keyed frames.
  Scale factors measured 1.0000 for both (no hidden rescale).
- **The BVH axis flags are a measured contract**: the 5.1 exporter has NO
  axis params (writes Blender world axes as-is) while the importer defaults
  to a Y-up file convention. Importing an already-Blender-convention file
  needs `axis_forward='Y', axis_up='Z'` (exact). The defaults land a 90°
  axis rotation; `-Y` lands a VERTICAL MIRROR of the rest skeleton — both
  caught by this probe's positions metric. Fixture generation and any BVH
  recipe MUST pin these flags.
- **Positions, not bone axes, are the only convention-free metric**: the
  importer reconstructs bone ROLLS (BVH has no roll channel) and even
  reverses head/tail AXES on BVH reconstruction (joint positions stay
  right). The first probe draft compared bone-axis directions and measured
  phantom 90°/180° errors; the positions metric is exact. This is rule 1
  above, earned the hard way.
- **Posed head = `pb.matrix.to_translation()`** — multiplying the
  armature-space `head_local` by `pb.matrix` double-applies the rest
  rotation (the first draft's own bug, caught by frame-1 identity
  comparisons before it could ship).
- **Sample positions BEFORE any rotation-mode change**: forcing
  `rotation_mode='QUATERNION'` on an imported rig orphans the importer's
  euler fcurves and silently freezes the animation (measured: per-frame
  samples collapse to one static pose).
- **EXTRACT-ROUNDTRIP PASS 0.0000°** (bar 0.5°) — sampled joint positions →
  canonical conversion → FK-apply onto a fresh correctly-topologied target
  rig reproduces the sampled pose at every keyed frame. The apply-back must
  target a rig with sane rest topology (the production direction anyway:
  canonical is the hub, the target's own apply path consumes positions).
- **ROOT-DROP PASS** (max 1.3e-07 canonical-units vs the 1e-06 FP-epsilon
  bar) — hips-relative shape is invariant to source root translation; the
  walk-in-place contract holds mechanically.
- **DETERM PASS** — independent sample passes are byte-identical.
- **GLB-CLIPS: the local Xbot.glb carries SEVEN real Mixamo clips** —
  agree, headShake, idle, run, sad_pose, sneak_pose, walk (670 fcurves
  each) — imported via the stock glTF importer. A REAL Mixamo-animated
  fixture exists locally for the gate, no Adobe login, same status as the
  P0-15 Xbot rig gate.

## Instruments (as-built status)

- **Probe** `xtask/motion_probe.py` — DONE (above), self-contained plus the
  local Xbot.glb (SKIPPED honestly when absent; RM_MOTION_XBOT overrides the
  path). Section order: relation re-assert on a freshly built rig → BVH
  round-trip → FBX round-trip → GLB clip inventory → re-import BVH →
  extract/retarget round-trip → root-drop.
- **CI** `core/tests/test_motion_library.py` — the core conversion contract
  (see the as-built note in § What landed in S23).
- **Gate** `RM_MOTION` section in `xtask/verify_pose_apply.sh` — DONE
  (S24): fixtures are generated at gate time (nothing binary committed),
  the bridge sampler runs as a real per-file spawn, and the convert →
  certified-composition → bake-on-the-metarig → fcurve re-eval half rides
  its own probe with every line grep-tested (the XBOT row PASS|SKIPPED,
  both shapes verified). Numbers live in `docs/BENCHMARKS.md` MOTION.
- **Bridge sampler** `xtask/sample_clip.py` (thin caller) +
  `riggermortis_addon/clip_sample.py` (the loop) — DONE (S24; PROMOTED
  S25): the probe's sampling loop is the add-on-owned library (bpy
  imported inside functions, conftest-shim tested for the pure parts) and
  the standalone script is argv/env glue (shell spawns it, D-009):

  ```bash
  RM_CORE_SRC=core/src blender -b --python xtask/sample_clip.py -- \
      clip.bvh out.clip.json [--action NAME] [--rig NAME] [--stride N] [--fps F]
  ```

  Builtin importers (BVH pins `axis_forward='Y', axis_up='Z'`), the REAL
  core mapper (no name hardcoding; hips must map or it refuses with a
  hint), per-frame `frame_set → view_layer.update() → pb.matrix.to_translation()`
  heads in ARMATURE space, format-1 JSON with the rest-torso-span
  `scale_ref` and the rig fingerprint carried through. A multi-action file
  without `--action` refuses listing the actions (actionable, never a
  silent first pick); a near-static sample is valid input but ships with a
  loud warning + note (the frozen-motion symptom). Two independent sample
  passes must agree byte-for-byte (DETERM, exit 1 otherwise). Promotion
  contract (S25): output proven BYTE-IDENTICAL to the pre-promotion script
  (same fixture → same 57111-byte JSON) and the gate re-verified with every
  RM_MOTION number unchanged.
- **Fixture builder** `xtask/motion_fixture.py` — DONE (S24): the probe's
  humanoid extended with hands + toes (19 roles → only root + shoulders
  ledger-missing), keyed with a 49-frame SYNTHETIC sliding walk (rigid
  ±5°-sweep stance = 0.0143 u/frame of ankle drift, below the detector's
  documented 0.02 enter bar; 50° swing knee flexion; every transition C1).
  Generates BVH + FBX at gate time into the gate's temp dir; nothing
  binary is committed.

## What landed in S23 (honest split)

The work order's opener = design page + probe + the core half the probe
proved. As-built:

- **In-repo, S23**: this page; the probe; core `motion.py` (the converter:
  sampled joint positions → canonical poses → `CanonicalAction` through the
  P2-3 constructor — loud validation, hips-anchored, rest-span scale,
  measured flips, confidence-1.0-with-provenance metadata) + its CI tests,
  including the certified-composition indifference pin EXERCISED CORE-SIDE
  (condition_action → detect → lock runs on a clip-sourced action and the
  foot-lock guarantee holds — pure core, no Blender needed).
- **In-repo, S24 (the probe's code is the recipe)**: the bridge sampler
  (import clip → per-frame role-position JSON — the probe's sampling loop,
  productionized as shell-glue per D-009), synthetic BVH/FBX fixture
  generation, and the RM_MOTION gate section including the Xbot.glb `walk`
  clip as the REAL-Motion gate row.
- **Recipe, not repo**: obtaining Mixamo downloads (login-bound); third-party
  DCC export quirks; per-engine importer flags beyond the measured BVH/FBX/
  glTF trio.

## What landed in S24 (the bridge, as-built)

- **In-repo, S24**: `xtask/sample_clip.py` (the bridge sampler, above),
  `xtask/motion_fixture.py` (the synthetic fixture builder), the
  `RM_MOTION` gate section in `xtask/verify_pose_apply.sh`, and the
  REAL-Motion row (Xbot.glb `walk`) — measured numbers in
  `docs/BENCHMARKS.md` MOTION: fixture lock 0.6140 u → 0.000014 u (44997×
  vs the ≥5× bar), metarig re-eval 0.0000° on both rows, FBX vs BVH
  canonical 0.000005 u.
- **The sampler's measured facts (do not re-learn them the hard way)**:
  the core mapper maps the BVH-conventional fixture names 19/19 with ZERO
  corrections (the probe never tested this — S24 measured it); Xbot maps
  21 canonical roles with 46 bones honestly unmapped (Mixamo fingers);
  Xbot's `scale_ref` measures 40.4154 (cm-scale source) — the scale-free
  contract doing exactly its job. Fixture keys are JOINT angles (each
  basis rotates the bone about its own head in the parent-posed frame):
  keying the shin with the thigh's angle bends the knee — the first
  fixture draft doubled its stance drift to 0.029 u/frame and the
  detector's enter gate (0.02, D-008-untuned) honestly refused it; rigid
  stance (knee 0) is the correct authoring.
- **Instrument finding**: Blender 5.1.0's bundled FBX importer CRASHES on
  any light (`lamp.cycles.cast_shadow` is gone upstream) — fixture scenes
  must be factory-EMPTY (`wm.read_factory_settings(use_empty=True)`, the
  probe's wipe pattern) or the default light rides the export and the
  re-import dies.
- **The REAL-data finding (published, not tuned)**: the Xbot `walk` clip
  carries root motion; hips-anchored (walk-in-place, D-008) it becomes a
  treadmill whose stance feet glide 0.022–0.19 u/frame — above the
  untuned enter_speed 0.02, so the detector honestly reports 0 plants and
  the lock is a verified bit-for-bit no-op. Nothing re-tuned to force a
  pass (D-008); the remedy is the declared coordinated positional/
  root-motion upgrade below. In-place/slow clips plant normally (the
  fixture row IS that shape).

## Future: an MCP session action for clips (DESIGN sketch — refactor half DONE S25)

Declared follow-up from S23/S24; written down so the eventual build is a
deliberate amendment, not scope creep. The tool schema stays v1 (additive
only, per the registry pin); the session action itself is not implemented.

- **Shape**: a new `retarget_clip` session action (enqueue_action kind, the
  P3-5 bridge — additive to the action vocabulary, not the tool table):
  `{action: "retarget_clip", clip: <abs path>, clip_action: "walk",
  stride: 1, contacts: true}` → the add-on-side executor imports the file
  IN-PROCESS (bpy ops inside Blender — no D-009 violation; D-009 bans
  spawning FROM .py, and session actions already run inside Blender), maps
  via the same core mapper, samples per the bridge recipe, converts with
  `action_from_clip`, runs the certified composition, and bakes onto the
  scene's mapped rig through `bake_action` — returning the metrics the
  gate prints (frames, mapped roles, scale_ref, contact intervals,
  slide before/after, re-eval worst deg).
- **The blocker is GONE (S25)**: the import/sample loop now lives in
  `riggermortis_addon/clip_sample.py` (bpy-owning, bpy imported inside
  functions, conftest-shim tested for the pure parts) and
  `xtask/sample_clip.py` is a thin caller (argv + env glue + exit codes).
  Byte-identity was PROVEN at promotion time: the pre-refactor script and
  the promoted library sample the same fixture to the same 57111-byte clip
  JSON, and the gate re-ran with every RM_MOTION number byte-identical
  (BVH/FBX/XBOT rows unchanged). The session executor can call
  `clip_sample.sample_clip(...)` directly — no second copy of the loop
  (the D-016 lockstep lesson applied BEFORE it could bite). What remains
  for the session action: the executor branch + the in-process convert →
  certified composition → bake wiring + gate/session-verify rows.
- **Policy**: clips are files on the artist's disk; the action reads local
  paths only (loopback/local-only lines unchanged, D-003). No new
  capability flag; progress streaming already covers long actions.

## Reproduce (as-built)

```bash
# the capability probe (imports nothing external; builds its own BVH/FBX
# fixtures headlessly; RM_MOTION lines, exit 0 = all answered)
blender -b --python xtask/motion_probe.py

# the unit contract (as-built; only after the probe passes)
cd core && python3 -m pytest tests/test_motion_library.py

# the end-to-end gate (S24; needs the local models + rigs like every
# pose-verify section — RM_MOTION lines; the Xbot row SKIPS without the glb)
BLENDER=/path/to/blender RIGPOSE=rigpose PY=python3 make pose-verify

# the bridge standalone (any imported clip -> format-1 sample JSON)
RM_CORE_SRC=core/src blender -b --python xtask/sample_clip.py -- \
    clip.bvh out.clip.json [--action NAME] [--stride N]
```
