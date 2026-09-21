# Benchmarks

Every performance/quality claim in the README will have a number here, with
the harness that produced it. No claim without a benchmark.

## Phase 0 — rig mapping gate

Five rigs, headless, deterministic. "Corrections" = roles the review UI would
need a human to reassign; the gate allows ≤2 per rig.

| Rig family | Source | Core roles mapped | Ambiguities flagged | Corrections needed | Status |
|---|---|---|---|---|---|
| Rigify-style | synthetic (tests/rigs.py) | 23/23 mapped, core complete | 0 | 0 | pending CI run |
| Mixamo-style | synthetic, incl. LeftLeg trap + Spine2 | core complete, Spine2 honestly unmapped | 0 | 0 | pending CI run |
| VRM (J_Bip) | synthetic | core complete | 0 | 0 | pending CI run |
| Opaque custom (b00..) | synthetic, geometry-only mapping | core complete | review items flagged | 0–1 | pending CI run |
| Quadruped | synthetic, deliberately ambiguous | torso/head mapped, legs flagged | ≥2 (front-leg remap) | ≤2 | pending CI run |

(Filled automatically by CI once the benchmark harness lands; the synthetic
suite backing this table runs on every commit via `make test`.)

### Real-rig gate (P0-15, session 2, local Blender 4.0.2 headless)

Proved on real rigs, not just synthetic fixtures. "Corrections" = reassignments
a human must make in the review UI; review-confirm flags are listed separately.

| Rig | Source + license | Bones | Roles | Core | Corrections | Flags |
|---|---|---|---|---|---|---|
| Rigify human meta-rig | Blender 4.0.2 factory metarig add-on (bundled) | 159 | 21 | complete | 0 | 1 review-confirm (structural hips) |
| Rigify generated rig | same metarig via `rigify_generate` | 706 (220 ctl / 160 DEF- / 167 MCH- / 159 ORG-) | 22/22 | complete | 0 | 0 |
| VRM 1.0 sample | Seed-san by VirtualCast, Inc. — [VRM Public License 1.0](https://vrm.dev/en/licenses/1.0/index); kept unmodified in git-ignored `out/` | 55 | 21 | complete | 0 | 0 |
| Mixamo export | **Xbot.glb** — a REAL Mixamo export (mixamorig:* names, 67 bones), sourced from mrdoob/three.js `examples/models/gltf/Xbot.glb` (MIT repo; Mixamo character terms permit project use; kept unmodified, git-ignored `out/real_rigs/`, never redistributed by this repo). No Adobe login needed | 21/22 | complete | 0 | 2 (upper_arm conf 0.50 review flags — no correction needed) |
| Xbot mapping detail | hips→mixamorig:Hips, spine→mixamorig:Spine, chest→mixamorig:Spine1 (chain promotion), lower_leg.→mixamorig:LeftLeg/RightLeg (the shin trap, handled), Spine2 honestly unmapped; `mixamorig:*_End` leaf bones skipped | — | — | — | — |

Reproduce (all local, no uploads):

```bash
blender -b --python xtask/build_rigify_rigs.py          # writes out/real_rigs/*.blend
bash xtask/extract_blend.sh out/real_rigs/metarig.blend out/real_rigs/metarig.rig.json
bash xtask/extract_blend.sh out/real_rigs/rigify_generated.blend out/real_rigs/rigify_generated.rig.json rig
blender -b --python xtask/import_and_extract.py -- out/real_rigs/Seed-san.vrm out/real_rigs/seedsan.rig.json
rigpose map out/real_rigs/metarig.rig.json --strict
rigpose map out/real_rigs/rigify_generated.rig.json --strict
rigpose map out/real_rigs/seedsan.rig.json --strict
```

Mapping fixes this gate forced (details in STATE/DECISIONS.md D-007): hips
flank rule (`pelvis.L` ≠ hips), structural-fork hips pre-pass with a
both-sides discriminator, prefix-duplicate barring from `spine`, pose-target
prefix preference (control > DEF- > ORG-), `MCH-`/`parent` skip tokens,
duplicate-limb-view filtering, review-feed completeness.

## Phase 1 — pose engine (P1-2, session 3)

### DWPose wrapper timing (accept: <2 s CPU per image — PASS)

Method: in-process `dwpose.load_sessions()` once (cold load timed separately),
then 5 timed `detect_keypoints()` runs on the same image; mean/median over the
5 runs. Machine: Intel Core i5-10400F @ 2.90 GHz (12 threads), onnxruntime
1.25.1 CPU ExecutionProvider with SessionOptions capped at 4 intra/inter-op
threads (fixed thread count = deterministic runs). numpy 2.4.4, Python 3.13.

| Scenario | Time |
|---|---|
| Cold session load (both models, once per process) | 1.21 s |
| Full pipeline, 3060x1721 image, 4 figures (det + 4 pose runs) | **0.85 s mean** (median 0.82, max 0.91) |
| Full pipeline, 700x1400 crop, 1 figure | 0.52 s |

Correctness cross-check on the same image (the DWPose repo's own ControlNet UI
screenshot with four people): 4 figures detected, all with anatomically sane
keypoints (nose above shoulders, ankles below hips) and correct laterality
(person-left keypoints on image-right). The pose sketch in the screenshot is
correctly not detected as a person.

Preprocessing is a faithful re-implementation of the official DWPose ONNX demo
(IDEA-Research/DWPose branch `onnx`): letterboxed 640x640 YOLOX-L detector
(NMS 0.45 / final cut 0.3), 1.25-padded aspect-fixed affine crop to 288x384,
ImageNet mean/std on BGR channels, SimCC argmax decode with split ratio 2.0.
cv2 is replaced by pure numpy (3-point affine solve + inverse-mapped bilinear
warp); image input is RGB, converted to BGR once at the boundary.

Determinism: fixed thread count via SessionOptions + numpy-only decode steps;
`tests/test_dwpose.py::test_detect_keypoints_determinism` asserts identical
payloads. GPU is opt-in via `rigpose detect --gpu`; CPU-only by default.

### Pose solve flip accept (P1-4, >=18/20 — PASS at 18/20)

20 synthetic posed figures with known ground truth (exact canonical bone
lengths, orthographic projection, `core/tests/poses_fixtures.py`): 18/20
solve with correct elbow/knee flips. The 2 misses are documented single-view
limitations, reported through confidence/notes rather than hidden:

- `kick_front_r` — a forward-foreshortened shank is geometrically identical
  to a standing pose under the depth prior (the 2D cannot see the bend).
- `arms_back` — wrists held behind the back violate the elbows-flex-forward
  anatomical prior (out of v1 scope; the review UI exposes manual flips).

Reproduce (pure stdlib, no models needed):
`python3 -m pytest core/tests/test_canonical_pose.py -s` (the honest
per-pose report prints each pose's flips and misses).

### FK apply accept (P1-5, same pose on 3 rigs, <=1-2 deg — PASS at <=0.5 deg)

The `arms_down_relaxed` canonical pose applied through the live mapper to
the three real extracted rigs; verification simulates Blender's FK
(parent-space axis-angle accumulation) and measures per-role angle error:

| Rig | Bones | Rotations | Worst angle error |
|---|---|---|---|
| Rigify meta-rig | 159 | 16 | 0.0000 deg |
| Rigify generated | 706 | 16 | 0.0000 deg |
| Seed-san VRM | 55 | 16 | 0.0000 deg |

Tolerance: 0.5 degrees (asserted in `test_same_pose_on_real_rigs_within_tolerance`).
Reproduce: `python3 -m pytest core/tests/test_fk_apply.py`.

### End-to-end smoke (real models, real rig, one command chain)

DWPose detect on the 4-person ControlNet-UI screenshot -> largest figure ->
solve (confidence 0.80, reliable) -> FK apply to the real metarig: 16
rotations, worst error 0.0000 deg, sensible values (spine 14.5 deg, thighs
~60 deg for the wide stance in the photo).

## Phase 2 — video pipeline instruments (session 6)

Not benchmark numbers yet — the *instruments* Phase 2's gate will be measured
with, plus their verification status. The gate itself (dance + fight clips × 3
rigs, foot-slide metric improving ≥5× under IK foot lock) lands in P2-5/P2-8.

### Keyframed retarget (P2-3)

- Canonical action model (`core/action.py`): per-frame poses sampled from a
  video job through the single payload contract; failed frames are carried in
  a ledger and never interpolated (CI-tested with faked payloads).
- Optional bake-time conditioning in the documented cleanup order (P2-6):
  1. hip stabilization (`action.stabilize_hips`, strength/window documented
     below),
  2. 1€ smoothing per canonical channel (min_cutoff=1.0, beta=0.0 defaults),
  3. keyframe reduction with tolerance defined as joint-position error in
     canonical units (P2-2 code, now wired; determinism + input-immutability
     CI-tested).
- Add-on bake: rotations keyed per frame into a NEW Blender action (mapping
  computed once, `B = M⁻¹LM` conversion reused from the proven apply path).
  Root motion is deliberately not baked — the single-view solve is
  hip-anchored, so world translation would be fabricated.
- **2-frame bake gate** (in `xtask/verify_pose_apply.sh`, real Blender 4.0.2
  metarig): pose A keyed at frame 1, its mirror at frame 2, then BOTH frames
  re-evaluated purely from the fcurves and measured against the canonical
  targets — worst **0.0242° / 0.0242°** across 16 roles each (bar 0.5°).

### Foot contact detection + slide metric (P2-4 / P2-5 instrument)

- Detector (`core/contacts.py`): per-ankle speed + height-vs-ground
  (nearest-rank percentile, self-normalizing) with Schmitt-trigger hysteresis
  (enter 0.02 u/frame & 0.08 u; exit 0.06 u/frame or 0.20 u; order-of-magnitude
  choices on the canonical scale, NOT fixture-fitted — D-008 discipline).
  Gap frames split intervals honestly.
- CI ground truth: synthetic 70-frame walk with known phases — **exact
  interval match** when clean; precision/recall ≥ 0.9 each with realistic
  wobble; determinism + scale-field invariance asserted; airborne → 0
  contacts; missing frame → interval split with a note.
- Slide metric (`contacts.foot_slide`): ankle path length traveled while in
  contact (canonical units). This is P2-5's number to beat (gate: ≥5×
  improvement under IK foot lock). Baseline instrument verified: planted
  synthetic foot reads 0.0, drift reads nonzero and interval-bounded.
- Live instrument smoke (git-ignored local data, NOT a benchmark): the S5
  person clip re-run through the fixed payload writer — 5/5 frames loaded
  through the contract, both feet correctly planted the whole clip, slide
  0.0, conditioning reduced 5 → 2 frames (near-static clip).

### IK foot lock (P2-5)

- Core lock (`contacts.lock_feet`): per contact interval the ankle + toe are
  pinned to the interval's FIRST OBSERVED plant pose (a real detection, never
  fabricated) and the knee is re-solved by a deterministic 2-bone IK; the
  result is walk-in-place — the honest alternative to fabricating root motion
  (D-008/D-013). Already-clean actions are bit-for-bit untouched (snap
  tolerance). 10 CI tests (slide zeroed, leg lengths preserved, no-op on
  planted data, unreachable clamp, gap handling, to_ground projection, input
  immutability, determinism).
- Synthetic instrument gate (table below): slide 0.768 u → 0.000 (drift
  walk), 0.793 u → 0.000 (with wobble); cost = knee corrections ≤ 0.035 u.
- **Blender bake gate** (`RM_FOOT_LOCK` probe in `xtask/verify_pose_apply.sh`,
  real Blender 5.1 metarig): the add-on bake pins the planted leg's world
  pose during contact (2-bone ankle correction + held foot transform;
  deviation reported as `lock_dev_deg`). Synthetic planted-foot action:
  unlocked ankle drift **0.0371 m** across the 9 contact frames; locked
  **0.0000 m** (bar 0.010 m), lock_dev 5.10°, FK fidelity unchanged
  (RM_BAKE 0.0242°). CI runs the same probe on the 4.0.2 pin (D-014).

### Hip stabilization (P2-6)

- The pass (`action.stabilize_hips`): the solve anchors the hips at the
  origin every frame, so no absolute hip translation survives into an
  action — what survives is the hip FRAME wobbling around the body: the
  per-frame pixels-per-unit scale (bob + detector noise modulate the torso
  span, rescaling every coordinate — the "breathing" artifact) and, on
  neck-anchored frames, the anchor translation itself. `stabilize_hips`
  low-passes both tracks (centered moving average, window=9 observed frames
  ≈ 0.3 s at 30 fps) and damps their high-frequency residual by strength=0.7
  (order-of-magnitude defaults, documented in the module, NOT fixture-fitted
  — D-008), applying each frame's correction as a RIGID transform of the
  whole pose. Rigid per-frame transforms are FK-identical within the frame,
  so this re-anchoring changes no pose geometry — its effect is exactly on
  the inter-frame tracks the pipeline reads: contact detection, the
  foot-lock cost, and the slide metric. No translation is fabricated (D-008);
  the result stays walk-in-place. Frames missing the anchor role or a usable
  scale are left untouched and counted; failed frames are never interpolated.
- Composition: `condition_action(hip_stabilize=...)` runs stabilize →
  smooth → reduce in that order; 14 CI tests (damping, per-frame rigidity,
  zero-strength bit-for-bit no-op, input immutability, determinism, honest
  gap/missing-data notes, and the condition → detect → lock composition
  gate with the foot-lock guarantee intact).
- Synthetic instrument gate (HIPSTAB block below): stabilization alone
  halves the breathing-induced stance slide and cuts the scale-sway RMS by
  ~59%; contact structure is unchanged; the composed lock still zeroes the
  slide.

<!-- BENCHMARK:FOOTLOCK:BEGIN -->
### IK foot lock gate (P2-5, generated by `xtask/foot_lock_gate.py`) — SYNTHETIC

**Synthetic instrument, not a real-clip benchmark.** Walk actions are
constructed (full leg chain, canonical units); stance ankles drift
0.012 u/frame to reproduce the hip-anchoring artifact the lock
removes. Real-clip numbers land with P2-8. Contact thresholds are NOT
tuned against this fixture (D-008). Deterministic: rerun prints the
same numbers.

| scenario | contact frames | slide before (u) | slide after (u) | after <= before/5 | max knee correction (u) | max ankle shift (u) | clamped |
|---|---|---|---|---|---|---|---|
| drift walk | 69 | 0.7680 | 0.0000 | PASS | 0.0179 | 0.1680 | 0 |
| drift + wobble | 69 | 0.7926 | 0.0000 | PASS | 0.0348 | 0.1680 | 0 |

Slide = ankle path length while in contact (`contacts.foot_slide`).
After = 0.0 by construction (position pinning); the cost columns are
the honest price: how far knees and pinned ankles moved away from the
source observation to get there. A real (near-static) person clip
reads slide 0.0 before the lock — no slide to fix — which is why the
gate number comes from this labeled synthetic walk until P2-8.

Reproduce: `python3 xtask/foot_lock_gate.py`.
<!-- BENCHMARK:FOOTLOCK:END -->

## Planned (from the mission gates)

- **Phase 2 (closed, honest):** the foot-slide metric is published
  (instruments above; ≥5× improvement gate met on the labeled synthetic
  walks, now also per-rig in the WALKRIGS block). The real-clip gate —
  "dance + fight clips playable on 3 rigs" — is **NOT met with real clips**:
  the licensed-clip search is exhausted (NEEDS-HUMAN,
  out/video_smoke/SOURCES.md) and the Phase-2 media ships as the labeled
  synthetic walk × 3 rigs (WALKRIGS block above), decomposed exactly like the
  Phase-1 close. It is never relabeled as met.
- **Phase 5:** live-mode latency budget (<100 ms, mid laptop).
- **Always:** network-audit test (zero outbound connections in default use).

<!-- BENCHMARK:POSES:BEGIN -->
### Phase 1 pose benchmark (P1-9, generated by xtask/benchmark_poses.py)

`usable-straight-away` = solver-reliable AND every distal flip verified (>= 0.55; straight limbs are immaterial and auto-pass, unobserved distal joints read 0.0 = review, D-010) AND no deep-foreshortening flag (heuristic proxy for the two documented D-008 miss classes: deep kicks, wrists behind the back). Flags: `flip` = distal joint unseen, bend unverifiable; `fore-<segment>` = proximal segment 2D length < 0.6x canonical (single-view depth limitation).

#### anime set — 0/10 usable (0%), confidence min 0.00 / median 0.50 / max 0.73; detector found no person: 3/10

| image | figures | figure used | det score | pose conf | reliable | min flip margin | flags | usable |
|---|---|---|---|---|---|---|---|---|
| anime1_lineart.png | 0 | - | 0.00 | 0.00 | NO | 0.00 | flip;fore-no-person | no |
| anime2_lineart_hat.png | 0 | - | 0.00 | 0.00 | NO | 0.00 | flip;fore-no-person | no |
| anime3_lineart_sketch.jpg | 1 | figure 1 | 0.87 | 0.69 | yes | 0.35 | flip;fore-lower_leg.L:upper_leg.L,lower_leg.R:upper_leg.R | no |
| anime4_lineart_bag.jpg | 1 | figure 1 | 0.44 | 0.52 | NO | 0.34 | flip;fore-forearm.R:upper_arm.R,lower_leg.L:upper_leg.L,lower_leg.R:upper_leg.R | no |
| anime4_saber_night_crop.png | 1 | figure 1 | 0.89 | 0.49 | NO | 0.39 | flip;fore-forearm.L:upper_arm.L,forearm.R:upper_arm.R,lower_leg.L:upper_leg.L | no |
| anime6_gothic_dress_crop.png | 1 | figure 1 | 0.92 | 0.73 | yes | 0.82 | fore-lower_leg.L:upper_leg.L,lower_leg.R:upper_leg.R | no |
| commons_niabot_upright.jpg | 0 | - | 0.00 | 0.00 | NO | 0.00 | flip;fore-no-person | no |
| controlnet_anime3_crop.png | 1 | figure 1 | 0.88 | 0.64 | yes | 0.34 | flip;fore-lower_leg.L:upper_leg.L,lower_leg.R:upper_leg.R | no |
| onegirl_portrait.png | 1 | figure 1 | 0.96 | 0.45 | NO | 0.06 | flip | no |
| violet_ai_render.jpg | 1 | figure 1 | 0.85 | 0.71 | yes | 0.51 | flip;fore-lower_leg.L:upper_leg.L,lower_leg.R:upper_leg.R | no |

#### photo set — 0/10 usable (0%), confidence min 0.40 / median 0.66 / max 0.77

| image | figures | figure used | det score | pose conf | reliable | min flip margin | flags | usable |
|---|---|---|---|---|---|---|---|---|
| boy_hoodie.png | 1 | figure 1 | 0.96 | 0.61 | yes | 0.34 | flip;fore-lower_leg.L:upper_leg.L | no |
| girls_still_multi.png | 12 | figure 2 | 0.93 | 0.60 | yes | 0.12 | flip;fore-forearm.R:upper_arm.R,lower_leg.R:upper_leg.R | no |
| human_hand_behind_head.png | 1 | figure 1 | 0.95 | 0.59 | yes | 0.25 | flip;fore-forearm.L:upper_arm.L,forearm.R:upper_arm.R,lower_leg.L:upper_leg.L,lower_leg.R:upper_leg.R | no |
| m2_patterned_shirt.jpg | 1 | figure 1 | 0.96 | 0.72 | yes | 0.25 | flip | no |
| man2_thinking.jpg | 1 | figure 1 | 0.97 | 0.71 | yes | 0.93 | fore-lower_leg.L:upper_leg.L,lower_leg.R:upper_leg.R | no |
| pose1_white_shirt.png | 1 | figure 1 | 0.96 | 0.64 | yes | 0.36 | flip;fore-lower_leg.L:upper_leg.L,lower_leg.R:upper_leg.R | no |
| pose2_coat_man.png | 1 | figure 1 | 0.96 | 0.77 | yes | 0.34 | flip | no |
| rtmpose_human_pose.jpg | 1 | figure 1 | 0.96 | 0.70 | yes | 0.35 | flip;fore-lower_leg.R:upper_leg.R | no |
| ski_carving.jpg | 1 | figure 1 | 0.91 | 0.67 | yes | 0.12 | flip;fore-lower_leg.L:upper_leg.L | no |
| woman_lying.jpg | 1 | figure 1 | 0.90 | 0.40 | NO | 0.14 | flip;fore-forearm.R:upper_arm.R,lower_leg.L:upper_leg.L | no |

<!-- BENCHMARK:POSES:END -->

<!-- BENCHMARK:HIPSTAB:BEGIN -->
### Hip stabilization gate (P2-6, generated by `xtask/hip_stab_gate.py`) — SYNTHETIC

**Synthetic instrument, not a real-clip benchmark.** The scale track
breathes +/-0.5% (period 4 frames) — the anchor-frame artifact
P2-6 targets — and the walk scenario adds the P2-5 stance drift
(0.012 u/frame). Pipeline: stabilize_hips(0.7) -> detect -> lock.
Slide = ankle path length while in contact. Real-clip numbers land
with P2-8; no thresholds or priors were tuned against this fixture,
and the published P2-5 gate numbers above are untouched (D-008,
D-010..013). Deterministic: rerun prints the same numbers.

| scenario | contact raw -> cond | slide raw (u) | after stabilize (u) | after lock (u) | lock gate | scale sway RMS before -> after | max knee corr (u) | clamped |
|---|---|---|---|---|---|---|---|---|
| breathing stance (no drift) | 138 -> 138 | 0.6841 | 0.3393 | 0.0000 | PASS | 0.00316 -> 0.00130 | 0.0123 | 0 |
| drift + breathing walk | 69 -> 69 | 0.8636 | 0.8153 | 0.0000 | PASS | 0.00316 -> 0.00130 | 0.0588 | 0 |

The stabilization column is the honest P2-6 headline: anchor-frame
noise removed BEFORE detection, so the lock absorbs less of it. A
steady per-frame drift is low-frequency to any smoother by
construction — it stays the foot lock's job (scenario 2), which is
why both halves exist. Stance scenario isolates the breathing
artifact (no drift, both feet planted throughout).

Reproduce: `python3 xtask/hip_stab_gate.py`.
<!-- BENCHMARK:HIPSTAB:END -->

<!-- BENCHMARK:WALKRIGS:BEGIN -->
### Walk across three rigs (P2-8, generated by `xtask/render_walk_gifs.sh`) — SYNTHETIC

**Synthetic instrument, not real-clip footage.** The clip is the
labeled drift + breathing walk from `xtask/hip_stab_gate.py` (the
HIPSTAB generator), retargeted to three real rigs through the
documented pipeline: `condition_action(hip_stabilize=0.7,
min_cutoff=None, tolerance=None)` — the CI-certified composition,
stabilization only —>
`detect_contacts` -> `lock_feet` -> `bake_action(contacts=...)` — the
add-on's real bake path. Smoothing and keyframe reduction are
disabled for the media pass (the GIFs show the generator's native
frame count). The real
walking clip stays NEEDS-HUMAN (out/video_smoke/SOURCES.md); the
Phase-2 real-clip gate is recorded NOT-met-with-real-clips
(DECISIONS D-015) and is never relabeled as met.

The third rig caught a real compatibility bug: glTF has no bone-tail
concept, and the Mixamo glb's synthesized tails are ~100x the true
joint spacing, which broke Blender's evaluated placement (children
ladder away from parents), the lock's 2-bone solve lengths (bake now
uses head-to-head rest distances), and the proxy visualizer. The
media pipeline repairs tails WHEN they disagree with the skeleton
(deterministic; Blender-native rigs are bit-for-bit untouched) and
add-on import normalization is a recorded follow-up (D-015).

Per-rig bake numbers (WORLD units, so rigs of different scales compare). Drift = max ankle world drift WITHIN one contact interval (a walk replants each foot per cycle — the lock pins the plant, not the stride), the RM_FOOT_LOCK measurement. The publish gate is the PUBLISHED P2-5 >=5x slide criterion (FOOTLOCK block, D-013) — scale-free, so it compares across rigs; the 0.010 m metarig-probe bar is shown for scale context only. FK worst is on the UNLOCKED application, bar 0.5 deg.

| rig | format | bones | mapping | unlocked drift (m) | locked drift (m) | lock ratio | >=5x gate | 0.010 m bar | FK worst (deg) | lock_dev (deg) | clamped | locked frames |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| metarig | blend | 159 | live map_rig | 0.1741 | 0.0080 | 21.7x | PASS | PASS | 0.0000 | 24.74 | 5 | 59 |
| seedsan | vrm | 132 | live map_rig | 0.1261 | 0.0105 | 12.0x | PASS | miss (clamp cost) | 0.0000 | 26.38 | 9 | 59 |
| xbot | glb | 67 | live map_rig | 0.1467 | 0.0070 | 21.1x | PASS | PASS | 0.0001 | 24.73 | 5 | 59 |

Media (pipeline-generated headlessly, bone-proxy visualizer, workbench; committed under docs/media/, media-guard allowlisted):

- `docs/media/walk_lock_metarig.gif` — Rigify metarig: raw | locked.
- `docs/media/walk_lock_seedsan.gif` — Seed-san (VRM): raw | locked.
- `docs/media/walk_lock_xbot.gif` — Xbot (Mixamo export): raw | locked.
- `docs/media/walk_3rigs.gif` — the locked walk on metarig | Seed-san | Xbot.

Canonical side of this exact pipeline (same generator and
conditioning as the renders): slide 0.8153u
conditioned -> 0.0000u locked over
70 frames (knee corrections <= 0.0588u,
0 clamps). The HIPSTAB block above publishes the
stabilize-only variant of the same generator; FOOTLOCK the
drift-only variant. Nothing here relabels those instruments.

Reproduce: `make walk-gifs` (needs local rigs + Blender — the rigs
are git-ignored; see docs/BENCHMARKS.md reproduce blocks).
<!-- BENCHMARK:WALKRIGS:END -->

<!-- BENCHMARK:LIVE:BEGIN -->
### Live side-process budget (P5-1, generated by `xtask/live_probe.py`) — STATIC REPLAY

**Instrument, not an end-to-end benchmark.** Frames are STATIC
replays (2 warmup + 6 timed per config) of three single-person
photos from the P1-9 set (Apache-2.0, git-ignored) at native and
640w sizes; the tracked regime re-detects every 5th frame. Machine:
i5-10400F @ 2.90 GHz (12 threads), onnxruntime 1.25.1 CPU provider
with fixed <=4 threads (the P1-2 deterministic configuration) — an
RTX 3060 is present but NO GPU ORT provider is installed, so CPU is
the measured path and the mid-laptop-relevant one. `kp>0.3` = mean
count of keypoints above 0.3 (out of 133); body conf = the miss-floor
signal (floor 0.3). The Phase-5 <100 ms mid-laptop gate is P5-2's
END-TO-END number (capture -> apply); this is the side-process half.
Aggregate = mean over the 6 per-image/size configs (raw JSON:
`out/live_probe/probe_measurements.json`, git-ignored).

| regime | configs | mean ms | p50 ms | worst p95 ms | det calls | kp>0.3 | body conf min |
|---|---|---|---|---|---|---|---|
| full | 6 | 552.5 | 545.4 | 679.3 | 8-8 | 128.2 | 0.627 |
| tracked | 6 | 170.2 | 88.2 | 700.1 | 2-2 | 127.5 | 0.622 |
| poseonly | 6 | 90.0 | 87.1 | 113.5 | 0-0 | 127.3 | 0.621 |

The decision this measured (docs/LIVE.md): reuse the pinned DWPose
models — the detector CADENCE is the realtime lever (input downscale
is a dead knob: the ONNX inputs are fixed-size). No new model, no new
download, licenses unchanged. A first-frame cold session load (~2 s)
is normal and visible in the stream envelope (`detect_ms` on seq 0).

Reproduce: `python3 xtask/live_probe.py` (needs models + the
benchmark photos; answers RM_LIVE PROBE SKIPPED honestly without).
<!-- BENCHMARK:LIVE:END -->
