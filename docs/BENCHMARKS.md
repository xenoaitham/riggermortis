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
(deterministic; Blender-native rigs are bit-for-bit untouched);
the ADD-ON runs the same conditional repair on Inspect & Map and
agent applies — the D-016 absurd-ratio rule, count always
reported, sane rigs untouched.

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

### Live consumer, emit -> apply (P5-2, `make live-verify`) — REPLAY

The consumer half's number, distinct from the side-process half above:
apply fidelity 9/9 lines at 0.0000 deg worst (bar 0.5), Blender-side
apply cost p95 ≈ 3.8 ms, stream emit -> applied p50 ≈ 157 ms with the
stalls landing on the producer's detector frames — measured by the gate
(`xtask/live_verify.sh`: REAL side process + REAL headless Blender) and
labeled REPLAY (files, not a camera). The S19 gate re-run of the same
instrument read apply p95 ≈ 2.7 ms / emit -> apply p50 ≈ 124 ms — same
gate, same configuration; run-to-run jitter is normal (stalls land on
the producer's DETECTOR frames, the first line sits in the ~2 s cold
window) and is never tuned away (D-008). Full per-line rows, the
staleness and miss-keeps-pose gate halves, and the honest
unclaimed-live-number statement: docs/LIVE.md, P5-2 budget section.

### Smoothing sweep + failsafe (P5-3, `make live-verify`) — REPLAY/SYNTHETIC

The conditioning half's numbers, same gate, same run A control (9/9 at
0.0000 deg, smoothing OFF — the P5-2 path byte-identical). The **smoothing
sweep** is a SYNTHETIC stream built from run A's first REAL payload line
with deterministic two-tone jitter (amplitude 0.01 canonical units,
envelopes at the P2-2 sampling class of 30 Hz): smoothing ON cut the
applied-curve variance **≈ 8.5x** per jittered axis (bar: the published
P2-2 >= 4x, reused verbatim), the smoothed mean tracked the raw mean
within ~9e-4 units (bar: the jitter amplitude), every applied line held
the 0.5-deg FK bar, and constant channels did not move. The **failsafe**
run: silence past the configured threshold fires the edge once, the rig
lands byte-at-rest, the readout says FAILSAFE, a continuation line
applies automatically and passes the reset smoother through EXACTLY.
Defaults (min_cutoff 1.0 Hz, beta 0.05, failsafe 10 s) are documented
order-of-magnitude starting points — **NOT tuned** (D-008); there is
still no real-motion stream, so these claims stay replay/synthetic-labeled
and the live <100 ms gate stays unclaimed. Gate lines: `RM_LIVE SMOOTH`,
`RM_LIVE SMOOTH-SUMMARY`, `RM_LIVE FAILSAFE`, `RM_LIVE FAILSAFE-RECOVERY`.

### 18+ module enforcement (P6-4/P6-5, session 21) — test/gate-pinned

Not a timing benchmark — the Phase-6 gate is PROOF, and this block cites
where each half lives:

- **Fresh-install default OFF, both frontends.** Core: `PolicyEngine()`
  status OFF, construction with the module enabled raises (core tests).
  Add-on: the bpy-free binding syncs OFF from fresh defaults, and a REAL
  Blender enables the add-on the way the user's checkbox does
  (`addon_utils.enable`) — real `AddonPreferences` defaults (False/False),
  engine OFF, `fictional_adult` refused retryably. MCP: `policy_status`
  answers OFF on a fresh server, twice, with no drift.
- **The enable needs BOTH toggles** ("Enable 18+ module" + "I understand
  the policy"): one-toggle syncs stay OFF in unit tests AND in the real
  Blender flow; both toggles go through the documented
  `enable_adult_module(confirm=True)` — the constructor shortcut is
  forbidden by the core itself. Toggling back off re-closes the gate.
- **Hard lines hold while enabled**: `minor` and `real_person` refuse with
  `minor_content_prohibited` / `real_person_explicit_prohibited`, NOT
  retryable, codes verbatim in the add-on report line (`refused [<code>] …`).
- **No agent-facing enable path**: the MCP tool table carries no
  enable/adult/confirm tool (golden-schema-pinned) — only the human's
  Blender preferences can enable the module.
- **Zero outbound preserved**: the network-audit sweep now covers the
  binding (both toggle states, full check sweep) — no socket events.

Where: 9 new core tests (`test_policy_enforcement.py` + the MCP
no-enable-path test; 358 total), the Blender gate step 5/5
(`xtask/blender_verify.sh`; lines `RM_POLICY ENABLE-ADDON / FRESH-OFF /
ONE-TOGGLE-STILL-OFF / ENABLE-BOTH-TOGGLES / HARD-LINES-HOLD /
DISABLE-REOFF`, grep-tested, `PHASE 0 BLENDER GATE: PASS` on 5.1.0), and
`docs/POLICY.md` § Enforcement. Local battery at close: lint clean,
358 passed, media-guard clean, blender/export/session/pose/style/live
gates PASS.

### Secondary motion (P6-1, session 22) — test/gate-pinned

Spring-chain follow-through over canonical roles (design of record:
`docs/SECONDARY_MOTION.md`). Direction-only v1: each link is a damped
angular spring pulled toward a rest direction authored in its parent frame;
constants (3.0 Hz / ζ 0.5 / 240 Hz integration target) are order-of-magnitude
defaults declared UNTUNED per D-008 — every assertion below is behavior or
composition, never a trajectory value.

- **Spec validation (CI, `test_secondary.py`)**: unknown fields, unknown /
  parentless anchor roles, links and freq/ζ bands, zero-length rest
  directions — all refuse with actionable hints; `to_dict`/`from_dict`
  round-trips exact; the shipped DATA file
  (`presets/secondary/demo_tail.json`) validates through the same
  `ChainSpec.from_dict`.
- **Determinism (CI)**: two simulations of the same action are exactly
  equal, tracks keyed in sorted-name order, fixed 8 substeps/frame at
  30 fps; the input action is never mutated.
- **Translation inertness (CI, pinned contract)**: a pure translation of
  the pose moves the chain ZERO — direction-only v1 feels anchor rotation,
  not translation (walk-in-place is rotation-dominant; positional state is
  the declared upgrade).
- **Follow + settle (CI + probe)**: a 30° head step makes the chain lag
  visibly (probe: max deviation 24.84° during response, bar ≥5°) and the
  untuned damping settles it to rest within a 1 s hold (probe residual
  0.00°, CI bar ≤2°).
- **Blender composition (probe, `xtask/secondary_probe.py`, 5.1.0
  headless)**: the pose-basis relation `pb = C @ rest @ basis` proven by a
  non-commuting test (rest@basis delta 0.000000 vs basis@rest 1.000000);
  keyed chain directions reproduce the simulated track at 0.0000° (bar
  0.05°) through a POSED parent chain, survive a 30°-rotated armature
  object at 0.0000°, and re-evaluate byte-identically from the fcurves.
- **Real-bake integration (gate, `make pose-verify` → `RM_SECONDARY`
  lines)**: `demo_tail.json` + the SYNTHETIC walk fixture
  (`xtask/walk_job.py`, labeled synthetic) through `core.simulate_secondary`
  and `bake_action(secondary=…)`: chain deviation 1.81° on the walk's hip
  motion (≥0.5° respond rail; determ=True), 4 appendage bones / 280 chain
  keys / 1120 FK keys over 70 frames, chain directions re-evaluate at
  0.0000° (bar 0.05°), and FK role world directions are UNCHANGED with vs
  without the binding at 0.00000° (bar 0.001°) — the certified composition
  (stabilize → smooth → reduce → detect → lock) is untouched; secondary
  rides strictly after it and keys appendage bones only.
- **Chain-binding preset equivalence (P6-1a, S25; gate `RM_SECONDARY
  PRESET` + `RM_SECONDARY PRESET_GATE` lines)**: the same chain through the
  full preset path — author (`preset_from_mapping` with bindings) → save →
  load (format 2) → fingerprint-gate (`resolve_secondary`) → simulate →
  bake — keys EXACTLY what the direct binding keyed (280 = 280 chain keys,
  4 bones, 70 frames); a mismatched fingerprint refuses (`mismatch_refused=
  True`) and `force=True` proceeds (1 binding). Schema: 426-test suite
  (17 `core/tests/test_preset_secondary.py` + 3 CLI round-trips) pins the
  format-2 write / format-1 back-compat read, loud per-field validation,
  sorted storage, byte-stable re-save, and the one-bone-one-chain guard on
  both the preset and the bake.

No timing claims: the simulation is per-frame pure math on the frames the
bake already walks (no process, no socket, no I/O — D-003/D-009 untouched).
Reproduce: probe
`blender -b --python xtask/secondary_probe.py`; gate
`BLENDER=… RIGPOSE=… PY=… make pose-verify`; unit contract
`pytest core/tests/test_secondary.py`.

### Motion library retarget (P6-2, session 24) — test/gate-pinned

Imported clips (Mixamo glTF / BVH / FBX) as a SECOND animation source for
the same canonical actions (design of record: `docs/MOTION_LIBRARY.md`;
the S23 probe proved the Blender-side recipe, S24 productionized it). The
converter MEASURES instead of solves: hips-anchored positions scaled by the
source rest torso span (`scale_ref`), flips measured not guessed, confidence
1.0 with provenance, root translation dropped (walk-in-place, D-008). The
certified downstream (condition → detect → lock → bake) runs UNCHANGED —
the composition never learns the action came from a clip.

- **The bridge (`xtask/sample_clip.py`, shell-glue spawned, D-009)** —
  builtin importers only (BVH pins the measured `axis_forward='Y',
  axis_up='Z'` contract), the REAL core mapper (no name hardcoding), per
  frame `frame_set` → `view_layer.update()` → mapped-role
  `pb.matrix.to_translation()` heads, format-1 clip JSON. Two independent
  sample passes per file must agree byte-for-byte (the probe's DETERM,
  now per-file, grep-tested in the gate).
- **Fixture row (SYNTHETIC, generated at gate time — nothing binary
  committed; `xtask/motion_fixture.py`)**: a 49-frame sliding walk whose
  stance legs are RIGID and sweep ±5° about the hip on the 0.84 m radius —
  0.0143 canonical u/frame of deliberate ankle drift (below the detector's
  documented 0.02 enter bar, so plants classify while visibly sliding;
  thresholds NOT fitted, D-008), swing knee flexion 50°. Through the full
  bridge: sampler maps 19/19 bones (0 unmapped), `scale_ref` 0.420000 m,
  DETERM PASS; converter produces 49 canonical frames, 22-role ledger
  honest (root + shoulders absent → ledgered, never guessed); detector
  finds exactly the authored phase structure — foot.L (2–12)(25–36)(49),
  foot.R (13–24)(37–48); the lock zeroes the slide **0.6140 u → 0.000014 u
  (44997×; the published bar is ≥5×)**; `bake_action` on the real metarig
  keys 49 frames / 686 keys, re-evaluates from the fcurves at **0.0000°**
  (bar 0.5°, 14 roles × 6 spread frames, 84 checks), `lock_dev` 0.00°,
  48 frames pinned.
- **FBX vs BVH (the same authored walk, both formats)**: canonical
  positions agree to **0.000005 u** (bar 0.005 u, the probe's round-trip
  family) — the bridge is format-honest by positions.
- **REAL-Motion row (Xbot.glb `walk`, the gated real Mixamo export — no
  Adobe login)**: sampler maps 21 canonical roles (46 bones honestly
  unmapped — Mixamo fingers etc.), `scale_ref` **40.4154** (the source is
  cm-scale — exactly the case `scale_ref` exists for), DETERM PASS;
  converter emits 24 frames; `bake_action` on the metarig re-evaluates at
  **0.0000°** (bar 0.5°, 16 roles × 6 frames, 96 checks). **The honest
  contact finding, published not tuned**: the detector reports 0 contact
  intervals on this clip — it carries Mixamo ROOT MOTION, so hips-anchoring
  (walk-in-place per D-008) turns it into a treadmill whose stance feet
  glide 0.022–0.19 u/frame, above the D-008-UNTUNED enter_speed 0.02; the
  lock is a bit-for-bit no-op on it (the no-op-on-clean-data contract,
  verified). Nothing was re-tuned to force plants — the remedy is the
  already-declared coordinated positional/root-motion upgrade
  (`docs/MOTION_LIBRARY.md` § out of scope), the same contract change the
  secondary-motion positional upgrade would make. In-place clips and slow
  walks plant normally (the fixture row above IS that shape).
- **Where**: gate `make pose-verify` → `RM_MOTION` lines (CONVERT /
  CONTACTS / LOCK / FIXTURE BAKE / FIXTURE REEVAL / FBX / XBOT — the XBOT
  row PASSes on the local box, SKIPPED honestly without the sample; both
  grep shapes verified), unit contract `pytest
  core/tests/test_motion_library.py` (27 tests incl. the certified
  composition pin), design + recipe `docs/MOTION_LIBRARY.md`.

### Scenes + camera v0 (P8-1, session 26) — test/gate-pinned

The CanonicalScene (N named figures + ContactPin data), the Casting Desk,
and the approximate scene camera (design of record: `docs/SCENES.md`).
Pins are CARRIED AND REPORTED, never enforced (P8-2 owns enforcement); the
camera is labeled APPROXIMATE and refuses to stage below the confidence
floor instead of staging a wrong silent camera.

- **Camera v0 floor derivation (Annex A.1, strike S12) — SYNTHETIC
  benchmark, labeled**: measured by `xtask/scene_probe.py` on its
  self-contained two-figure benchmark (Blender 5.1.0, headless). The
  v0-solved camera (front prior, 50 mm, closed-form width/center match)
  measures **IoU 0.9657** against a deliberately off-prior reference (35 mm,
  yawed 12°, low) — the intended-framing class. Degraded cameras: distance
  ×1.5 → **0.4684**; single-figure framing of a two-figure reference →
  **0.1324** — the visibly-wrong-shot class. **The floor 0.75 sits inside
  the gap with margin on both sides.** Scope: synthetic derivation; the
  P8-5 GT set re-derives it on real references (Annex A.1 re-validation
  trigger). Projection model pinned by the probe (err 1.09e-07):
  `u = 0.5 − Δx/d·f/sensor_w`, `v = 0.5 + Δz/d·f/sensor_h` for the level
  90°/0°/180° camera; `world_to_camera_view` is v-up, unclamped — the
  reference normalization flips v and clamps to the frame.
- **Scene gate rows (real assets, real models)** — `xtask/scene_gate.py`
  via `make pose-verify`, RM_SCENE lines, all PASS: CASTING refusals 3/3
  (unknown figure / double-cast armature / unknown armature) with
  subset-casting valid; **APPLY2** — the session executor's `apply_scene`
  drove ONE 12-figure real detector payload into TWO rigs in one action,
  re-evaluated worst **0.0198°** (figure 1) / **0.0063°** (figure 2), bar
  0.5°; **V2-BACKCOMPAT** — the same content as a format-2 payload applies
  byte-identically through the v3 code (38 bones, exact quaternion
  equality); **CAMERA-REFUSE** — a reference framing that does not match
  the scene measures IoU **0.3388** < 0.75 and stages NOTHING (no camera
  object left, previous scene camera restored); **CAMERA-STAGE** — the
  matched-layout reference clears the floor at **IoU 0.8279**, the staged
  `rm_scene_camera` carries `rm_camera_v0="APPROXIMATE"` + the measured
  IoU and is the scene camera.
- **Order/cleanup facts (probe-pinned)**: apply order A-then-B vs B-then-A
  is byte-identical (exact quaternion equality, 38 bones); a second full
  apply is idempotent; `clear_pose` on one rig leaves the other
  byte-unchanged.
- **Where**: probe `blender -b --python xtask/scene_probe.py` (9 RM_SCENE
  rows, self-contained); gate `make pose-verify` (RM_SCENE CASTING /
  APPLY2 / V2-BACKCOMPAT / CAMERA-REFUSE / CAMERA-STAGE / GATE, grep-pinned
  both shapes); unit contract `pytest core/tests/test_scene.py` (28 tests:
  schema refusals, determinism, payload v3 + the back-compat pin, casting);
  design of record `docs/SCENES.md`.

### Contact coupling (P8-2, session 27) — test/gate-pinned

The deterministic pass enforcing AUTHORED pins over the scene (design of
record: `docs/SCENES.md` § Contact coupling). Suggested / below-floor /
unplaced pins are REPORTED LOUD and move nothing; the solve is pure
position-space surgery (rotations derive at apply time), so the certified
apply path consumes coupled poses unchanged.

- **Annex A.1 bar met, with three orders of margin**: on the engine-built
  hold-from-behind-class fixture (canonical-exact rigs, Annex A.3), both
  authored pins close at rig-space residuals **0.00007 / 0.00016 m** —
  fracs **0.00016 / 0.00035** of torso span (bar 0.02) through the REAL
  scene-apply path with placements MEASURED from the posed rigs; the
  coupled apply re-evaluates at **0.0000°** worst (bar 0.5° family).
- **Probe numbers** (`xtask/coupling_probe.py`, 7/7 RM_COUPLE rows, pure
  core + the REAL `apply_canonical_pose`): convergence fracs
  0.000158/0.000189 in 27 iterations; non-chain positions byte-identical
  and their derived rotations byte-identical through the real apply while
  the pinned chains move; competing pins converge to the
  confidence-weighted compromise (residuals 0.111/0.059 reported, both
  flagged unclosable, twin byte-identical); suggested + below-floor pins
  move nothing and say why; unreachable targets straighten the chain and
  stay loud. SYNTHETIC-labeled (engine-built fixtures; real references
  re-run the bar per the Annex A.1 re-validation trigger).
- **Gate rows** (`xtask/couple_gate.py` via `make pose-verify`, RM_COUPLE
  lines, Blender 5.1.0): COUPLE-RESIDUAL (fracs 0.00016/0.00035 + report
  rows closed + worst_fk 0.0000°), COUPLE-NONCHAIN (non-subtree positions
  byte-equal; live apply fidelity worst 0.014° vs the coupled targets —
  riding subtrees swing rigidly with a moved ancestor, which is the
  coupled pose's own physics; the "unchanged" guarantee is byte-exact
  non-subtree positions core-side + the 0.5° apply family, unit-pinned),
  COUPLE-TWIN (42 bones byte-identical), COUPLE-CONFLICT (compromise
  reported, fracs 0.2486/0.1292, both unclosable loud, apply succeeds),
  COUPLE-NOENFORCE (a suggested pin moves nothing, byte-equal, reason
  reported).
- **Declared constants (untuned, D-008)**: `MAX_ITERS 32`,
  `EARLY_EXIT_FRAC 2e-4`, enforcement floor `0.55` (the CONVENTIONS
  ambiguity bar, reused), bar `0.02` (Annex A.1). Enforcement gates on
  the PIN's confidence; the endpoints' joint confidence feeds the split
  weights (`w ∝ 1 − c`).
- **Gate-earned lessons**: the placement origin must map the canonical
  ORIGIN (`t = world(anchor) − s·R·canonical(anchor)` — identity for
  detector-solved poses); the coupled write-back is FULL precision (riding
  roles keep byte-exact segment directions); and the fixture-builder
  lesson (parents must exist before children — an alphabetical creation
  order silently disconnected limbs and only the real-Blender gate caught
  it; the builder is two-pass and a missing parent refuses).
- **Where**: probe `/home/potato/miniconda3/bin/python3
  xtask/coupling_probe.py` (self-contained, no Blender); gate `make
  pose-verify` (RM_COUPLE RESIDUAL / NONCHAIN / TWIN / CONFLICT /
  NOENFORCE / GATE, grep-pinned); unit contract `pytest
  core/tests/test_coupling.py` (23 tests: the movable-chain table,
  placements, enforcement gate, weights, conflict, reach, scale
  invariance, purity, determinism, report shape); design of record
  `docs/SCENES.md` § Contact coupling.

### Fingers (P8-3, session 28) — test/gate-pinned

The additive finger namespace (D-021, written at that landing) + the
per-hand solve: finger chains solve ONLY from observed keypoints — every
chain's four kps must clear the 0.55 confidence floor (the CONVENTIONS
ambiguity bar, reused, untuned), below it the finger is SKIPPED and
LEDGERED, never guessed. Depth magnitude from declared canonical segment
lengths (D-008 priors); depth SIGN is the declared forward-curl rule
(the elbow-forward prior one level down — the probe showed a
flatten-prior sign enumeration un-curls grips). Design of record:
`docs/FINGERS.md` § As-built design.

- **Annex A.1 bars met**: the 20-pose hand benchmark class
  (flat/spread/grip/curl/point/…, SYNTHETIC parametric GT,
  prior-consistent) measures per-SEGMENT direction error at **median
  0.00° (bar 20) / p90 10.30° (bar 35)** over 300 segments; the
  occlusion fixtures gate-skip **100%** (wrist below floor → no hand
  entry — an absent hand reads as clean; finger kps below floor → 0
  solved, 5/5 ledgered with verbatim reasons — zero guessed fingers);
  apply through the REAL add-on path on engine-built metarig-class AND
  Mixamo-class fixtures (mixamorig naming, 0.01 object scale) re-evals
  finger bones at **0.0070° worst** (bar: the 0.5° FK family), 15/15
  bones keyed, twin byte-identical.
- **Real-photo honesty** (`xtask/finger_probe.py`, 8/8 RM_FINGER rows,
  pinned DWPose models on the P1-9 set): the canonical wrist→forearm
  span median is **0.280 u** across 11 poseable hands (0 degenerate —
  the hand frame's stability surface is solid); **25 fingers solved /
  30 gated-skipped** at the floor, and the occlusion-class photo
  (hand behind head) gated all 5 fingers of its hand. Real photos skip
  loudly roughly half the time — that is the design working (an absent
  finger reads as clean), not a defect.
- **Where**: probe `/home/potato/miniconda3/bin/python3
  xtask/finger_probe.py` (models + photos, RM_FINGER PROBE); gate `make
  pose-verify` (RM_FINGER BENCH / GATE-OCCL / APPLY / MIXAMO / NOTARGET
  / TWIN / GATE, grep-pinned); unit contract `pytest
  core/tests/test_fingers.py` (25 tests); design of record
  `docs/FINGERS.md` + `STATE/DECISIONS.md` D-021. SYNTHETIC-labeled:
  the direction bars are measured on engine-built GT; the Annex A.1
  re-validation trigger applies when real hand-labeled fixtures enter
  the workflow.

### Face (P8-4, session 29) — test/gate-pinned

The additive facial parameter namespace (D-022, written at that landing)
+ the expression solve: 10 dimensionless params (brow.raise.L/R,
blink.L/R, jaw.open, smile.L/R, pout, cheek.L/R) read ONLY from observed
face landmarks through the published table (docs/FACE.md) — the face
solves only when the IOD anchor's four corner kps clear the 0.55 floor
(CONVENTIONS bar reused); a param whose kps fall below the floor is
SKIPPED + LEDGERED, and a solved value below the 0.08 activation floor
is LEDGERED as below-threshold, never interpolated. Gaze is
conditional-OUT (the pinned DWPose has no iris kps). Design of record:
`docs/FACE.md` § As-built.

- **Annex A.1 bars met**: the 10-expression benchmark (neutral + 9,
  SYNTHETIC prior-consistent GT) measures per-param monotonicity at
  **0 violations / 9 steps (bar 1)** with **reach 1.00** (bar 0.5)
  across all 10 params; apply through the REAL add-on path on
  engine-built fixtures re-evals facial bones at **0.0000° worst**
  (bar: the 0.5° FK family, 5/5 bones keyed via the preset
  `face_bones` contract) and convention shape keys at **0.0000**
  applied-vs-intended (bar 0.1 normalized, 4/4 keys, mesh displaced);
  a no-target rig reports the loud capability line verbatim; twin
  applies byte-identical.
- **Real-face honesty** (`xtask/face_probe.py`, 7/7 RM_FACE rows,
  pinned DWPose models on the P1-9 set, n=18 faces / 36 eyes, pooled
  over both face bands): the MEASURED side map flipped the declared
  convention — DWPose's band A sits image-left = the subject's RIGHT
  (18/18 faces, median −51.5 px), so `.L` constants read band B; three
  neutral-geometry priors were REDECLARED from measurement
  (corner drop 0.403, mouth width 0.832, cheek distance 0.731) — the
  declared values had smile/pout firing on every real neutral and
  cheek structurally unable to fire; EAR (0.283 vs 0.28) and brow gap
  (0.296 vs 0.30) stood. Band confidences run 0.97–1.00 medians (the
  audit's 0.958 face band, per-region).
- **Where**: probe `/home/potato/miniconda3/bin/python3
  xtask/face_probe.py` (models + photos, RM_FACE PROBE); gate `make
  pose-verify` (RM_FACE BENCH / GATE-OCCL / BONE-APPLY / SHAPE-APPLY /
  NOTARGET / TWIN / GATE, grep-pinned); unit contract
  `core/tests/test_face.py` (25 tests); design of record `docs/FACE.md`
  + `STATE/DECISIONS.md` D-022. SYNTHETIC-labeled: the monotonicity
  bars are measured on engine-built GT; the Annex A.1 re-validation
  trigger applies when real expression-labeled fixtures enter the
  workflow. The neutral is a POPULATION prior (D-008-untuned): a
  single image carries no personal neutral, and a resting-low brow
  reads slightly raised — published, never hidden.

### Measured reference camera (P8-5, session 30) — test/gate-pinned

The measured solve fitting yaw/pitch/distance/height from the body
keypoints with the canonical skeleton's proportions as the ruler (design
of record: `docs/CAMERA.md`; the APPROXIMATE v0 stager above stays as the
fallback path, byte-untouched).

- **Annex A.1 bars MET on the tier-1 deterministic GT set** (150 GT
  cameras = yaw {−40..40 step 20}° × D {2.6, 4, 6} × elevation
  {−1..+1} × 2 poses, noiseless projections through the REAL pipeline —
  observations → solve_pose → camera solve; SYNTHETIC, prior-consistent
  GT): **yaw MAE 2.58° (bar 7.5), pitch MAE 4.83° (bar 5), distance MAE
  3.42% (bar 12%), 0 refused, 150/150 solved.** Framing IoU of the
  solved cameras vs the GT cameras: median **0.9621**, 99% ≥ the 0.75
  floor (projection space, the declared staging placement). Optimism
  caveat verbatim: *measured on synthetic prior-consistent ground truth;
  real-detector noise is not in these numbers; the Annex A.1
  re-validation trigger applies when real labeled fixtures enter the
  workflow.*
- **Gate rows** (`xtask/camera_gate.py` via `make pose-verify`, RM_CAM
  lines, Blender 5.1.0): **CAM-MODEL** — the composed yaw+pitch
  projection matches Blender's `world_to_camera_view` at max err
  **2.32e-07** (bar 1e-4) over 9 yawed+pitched cameras, the camera
  quaternion built from the model basis (no track_quat ambiguity);
  **CAM-GT** — the sweep re-run inside Blender, yaw **2.58°** / pitch
  **4.73°** / distance **3.42%** (n=75, bars 7.5/5/12%); **CAM-STAGE** —
  the REAL addon path (camera_stage.stage_scene_camera_measured) staged a
  GT reference (yaw 20°, D 4, elev 0.5) at solved yaw **19.86°**, framing
  **IoU 0.8082** ≥ 0.75, solve confidence 1.00, `rm_camera_solve=
  "MEASURED"` + conf + IoU + params stamped, scene camera set;
  **CAM-REFUSE** — a kp-starved payload refuses LOUD ("no usable figure
  solves…") and leaves NO camera object; **CAM-TWIN** — twin staging
  byte-identical (IoU, params, camera location). All prior gate numbers
  byte-identical (RM_BAKE 0.0242° ×2, RM_FOOT_LOCK 0.0371→0.0000,
  RM_MOTION, RM_SCENE 0.3388/0.8279, RM_COUPLE 0.00016/0.00035,
  RM_FINGER 0.0070°/0.00°/10.30°, RM_FACE 6 rows).
- **Refuse-to-stage classes** (probe, 5/5 loud, zero guessed):
  kp-starved girdles, torso-degenerate (the sitting/slumped class),
  crouch fixture (pose-class breach), cropped bbox, profile view
  (envelope breach). On the P1-9 real photos (tier 3, no GT exists):
  10 figures, 9 refused with verbatim reasons (honest — cropped/
  crouched/starved classes), 1 solved and published with its confidence.
- **Tier-2 (render + REAL detector) NOT MET with evidence** — the D-015
  decomposition, measured: the pinned DWPose person detector is BLIND to
  the engine's mannequin fixture class (0 detections / 36 renders across
  three fixture generations: workbench stick, workbench thick, EEVEE
  sun-lit). The Annex bars bind on the tier-1 deterministic GT set + the
  tier-3 real rows; the A.3 re-validation trigger applies to any future
  detector-visible fixture path. Never relabeled as real.
- **Where**: probe `/home/potato/miniconda3/bin/python3
  xtask/camera_probe.py` (8 RM_CAM rows; models + Blender for the render
  tier), gate `make pose-verify` (RM_CAM MODEL / GT / STAGE / REFUSE /
  TWIN / GATE, grep-pinned); unit contract `core/tests/test_camera.py`
  (17 tests); design of record `docs/CAMERA.md` (amendments A1–A11).
  The solve is pure core (`core camera.py`) — no payload format change
  (the hands-free face-free byte-identity contracts hold, pinned).

### Spine arch + arm roll (P8-6, session 31) — test/gate-pinned

The post-solve articulation passes closing L5 (rigid torso line) and L6
(roll-free rotations): the arch distributes the observed hips→shoulders→
head misalignment across the spine chain (design of record: `docs/SPINE.md`
— a cubic Hermite through the pinned endpoints with the probe-earned A1
tangents); the roll corrects the forearm's frame split to the declared
frame-continuation convention via the D-023 additive namespace
(`CanonicalPose.roll`, written at the landing). No payload format change
(the hands-free face-free byte-identity contracts hold, pinned).

- **Annex bars MET on the declared-family benchmark** (four classes
  neutral / bow_L +18° / bow_R −18° / arched +30°, engine-built
  prior-consistent GT torsos at the D-008 fractions; SYNTHETIC):
  chest deviation from the chord strictly monotone **0.0000 < 0.0076 <
  0.0084** canon (neutral not applied, byte-identical flat no-op),
  signs bow_L > 0 > bow_R, declared-family recovery max **0.00000**
  canon (bar 0.002). Optimism caveat verbatim: *measured on synthetic
  prior-consistent ground truth; real-detector noise is not in these
  numbers; the Annex A.1 re-validation trigger applies when real labeled
  fixtures enter the workflow.*
- **FK bars hold**: worst per-role direction error **0.0000°** (bar
  0.5°) through the REAL apply on every benchmark class, both roll paths.
- **D-008's flip accept unchanged**: **18/20** (bar ≥ 18) through
  solve → arch → roll; every `flips` dict byte-equal to the plain solve
  (the passes touch no distal segment).
- **Roll corrects to bar**: the frame-continuity fixture (left arm bent
  in a non-trivial orientation, right straight) — uncorrected forearm
  twist **53.64°** (the D-008 artifact, published), corrected **6.9e-15°**
  core-side / Blender-measured applied twist **53.64° in magnitude**
  (the solved correction; the sign is a Blender bone-frame convention,
  the signed twist lives core-side); direction fidelity exact in both
  paths.
- **Straight arms BIT-IDENTICAL**: no roll entries on any sub-15° bend
  across the 20-pose set; the addon apply rotations byte-identical with
  and without the roll pass (the structural no-op, pinned by test).
- **REAL rows** (tier 3, the P1-9 photos, no GT exists; the outputs ARE
  the data): 10 figures, the arch applied on 5 with published
  misalignments (+27.6° to −15.8°, confidences 0.71–0.75), flat on the
  rest with verbatim reasons, 2 roll entries.
- **Where**: probe `/home/potato/miniconda3/bin/python3
  xtask/spine_probe.py` (7 RM_SPINE rows; models for the REAL tier),
  gate `make pose-verify` (RM_SPINE SPINE-ARCH / FLIPS / ROLL / STRAIGHT
  / TWIN / GATE, grep-pinned); unit contract `core/tests/test_spine.py`
  (19 tests); design of record `docs/SPINE.md` (amendment A1, the
  probe-earned tangent record). The arch is pure positions-surgery
  (`core spine.py`, the coupling write-back class); the roll rides the
  D-023 additive namespace consumed by `fk_apply` — poses without
  entries apply byte-identically. The CLI/addon invocation wiring is
  deliberately open (the work order's unit boundary is the pure core +
  the REAL-apply gate); the payload-carrying-roll apply needs no addon
  change (poses build through `CanonicalPose.from_dict`).

### Root motion (P8-7, session 32) — test/gate-pinned — L7 = REFUSED-with-evidence

The measured hips drift track + the root-motion-aware contact model
(design of record: `docs/ROOT_MOTION.md`, written BEFORE the build with
the pre-declared Annex A.1 bar; the sibling design-page pattern). The
machinery lands as gated additive core; the ledger row ends REFUSED per
Annex A.2 because the motivating REAL fixture measurably carries no
drift — the evidence below is the refusal's substance, not a shrink of
the claim.

- **The corrected finding (the session's decisive measurement)**: the
  Xbot.glb carries NO root motion on ANY of its seven clips — the walk
  clip's hips bone y is constant to the sampler's 1e-6 m, the run clip's
  track span measures **0.0000u**, the armature object never moves. The
  S24 "carries Mixamo ROOT MOTION" attribution is corrected
  (docs/MOTION_LIBRARY.md): the published 0.022–0.19 u/f stored glide is
  the in-place walk cycle's own leg kinematics, which hips-anchoring
  cannot and should not remove. The >= 5x-on-the-Xbot-row bar is
  unmeetable BY THE FILE'S CONTENT; walk-in-place ships (the Annex A.2
  REFUSED branch, verbatim).
- **Track recovery (SYNTHETIC GT)**: the engine-built drift fixture
  (authored world-planted walk, 0.03 m/frame hips translation, the A2
  counter-sweep keeping the stance ankles world-stationary) recovers the
  authored curve at max_err **0.000000 canon** (bar 0.005) through BVH
  export → import → sampler → format-2 clip → conversion; the
  compensated detection lands exactly on the observable stance
  structure (landing frames excluded by the enter contract). Optimism
  caveat verbatim: *measured on synthetic prior-consistent ground
  truth; real-detector noise is not in these numbers; the Annex A.1
  re-validation trigger applies when real labeled fixtures enter the
  workflow.*
- **The >= 5x family demonstrated on the drift class**: the root-aware
  lock zeroes the stored glide **0.6479u → 0.0000u = 46351.9x** (bar
  >= 5x) on the same fixture; the in-place reading of the same action
  finds 5 spurious intervals (the treadmill confusion, reproduced).
- **The certified path byte-identical**: a zero track reduces detect +
  lock to the in-place path (structure AND locked positions equal,
  pinned by test and gate row); the REAL bake of a root-motion-locked
  action re-evaluates at **0.0000°** (bar 0.5°, 98 checks) — the
  certified bake is untouched; the certified composition, the sampler
  default path (format-1 bytes, the 57111-byte fixture sample), and all
  prior gate numbers re-print byte-identical.
- **The clip-sample format 2 carrier**: `--root-track` (default OFF)
  adds the `hips_track` field (the sampler's world hips heads; write 2 /
  read 1+2, the preset-schema pattern); NO payload format change — the
  track rides the ACTION (additive `CanonicalAction.root_track`,
  conditioning carries it).
- **Where**: probe `blender -b --python xtask/root_motion_probe.py` (7
  RM_ROOT rows, 7/7 PASS), gate `make pose-verify` (11 RM_ROOT grep
  rows via `xtask/root_motion_gate.py`), unit contract
  `core/tests/test_root_motion.py` (17 tests, 585 total); design of
  record `docs/ROOT_MOTION.md` (amendments A1–A3, the A3 corrected
  finding included). The S24 MOTION block's finding text above is
  corrected in place by the dated note — history not rewritten.

### Scene animation (P8-8, session 33) — test/gate-pinned — L8 CLOSED

Identity-stable multi-character video → scene animation (design of
record: `docs/SCENE_ANIMATION.md`, written BEFORE the build with the
pre-declared Annex A.1 bars; the ROOT_MOTION.md sibling pattern). The
identity assignment is the roadmap-committed algorithm made concrete:
per-frame figure→character cost = mean position distance over common
roles + `|log(scale ratio)|` (SCALE_WEIGHT 1.0, declared untuned), solved
by a deterministic Kuhn-Munkres assignment over SORTED keys, an evidence
swap alarm (no ground truth needed), manual overrides winning over
everything.

- **Identity swap rate (the Annex bar <= 2%)**: **0.0000** (0/49 solved
  frames) on the synthetic two-person fixture through BOTH authored
  label-swap events — the assignment follows pose+scale identity through
  the detector-class glitches, so walk-through-crossing identity HOLDS.
  [SYNTHETIC, prior-consistent GT; the optimism caveat verbatim:
  *measured on synthetic prior-consistent ground truth; real-detector
  noise is not in these numbers; the Annex A.1 re-validation trigger
  applies when real labeled fixtures enter the workflow.*]
- **The declared single-view limit, published separately**: the
  AMBIGUITY class (identical pose shapes AND identical scales through
  the window — the duplicated-person class) measures **0.1224** (6/49
  frames) — unresolvable from single-view keypoints BY CONSTRUCTION,
  reported separately, never averaged into the primary rate; the manual
  override is the designed answer (gate row SANIM-OVERRIDE: the authored
  word moves the character, marks the frame, records the solve-vs-
  authored disagreement verbatim, and is EXCLUDED from the automatic
  rate). The A.2 refusal branch (swap > 10% after repair) was not
  reached — the primary class never left 0.
- **The swap alarm (the Annex bar >= 90%)**: **caught 2/2 authored
  events within the 2-frame halo (1.00)**; the cost-jump distributions
  published: event frames min_abs **0.4463** vs non-event max_abs
  **0.0000** — ALARM_ABS 0.02 sits in the gap with margin (the
  strike-S12 derivation pattern; ALARM_REL 0.25 guards the
  near-zero-cost class). Both constants declared untuned, published
  here.
- **Per-frame coupling (the P8-2 bar, per frame)**: the authored
  hand-holding pin closes on **13/13** contact-window frames at worst
  **residual_frac 0.000190** (bar 0.02) through the UNTOUCHED
  `couple_scene` with placements MEASURED per frame from the stream's
  detector bboxes (in-plane only, depth exactly zero, APPROXIMATE-
  labeled, apparent-size staging `s = figure_scale / U`); the 25
  beyond-reach frames report unclosable LOUD (the P8-2 REACH honesty,
  per frame).
- **Per-frame scene bake cost (the Annex publication bar — MEASURED,
  PUBLISHED, mid-laptop baseline)**: the REAL `bake_action` over BOTH
  characters (two metarig armatures, one scene) measures **0.8–1.0
  ms/frame-bake = 1.7–1.9 ms per scene-frame across the 2 rigs**
  (98 frame-bakes in ~0.09 s; worst FK 0.0000°, bar 0.5°) — the
  certified bake is composed, never forked.
- **Per-character drift tracks**: S32's `track_from_payload_stream`
  reused VERBATIM per character — the side swap is IN the track (span
  1.0000u), depth exactly zero, the APPROXIMATE label travels.
- **Where**: probe `blender -b --python xtask/scene_anim_probe.py` (10
  RM_SANIM rows, 10/10 PASS), gate `make pose-verify` (10 RM_SANIM grep
  rows via `xtask/scene_anim_gate.py`), unit contract
  `core/tests/test_scene_anim.py` (30 tests, **615 total**); design of
  record `docs/SCENE_ANIMATION.md`. Fixture law: the two-person stream
  is engine-built (contract-valid v3 payloads + a real P2-1 job state,
  generated at gate time, never committed); the pose shapes are
  clothed-mannequin class (the A.3 SFW fallback).

## REVIEW-UX (P8-9, session 34) — time-to-fix + the estimator verdicts

Written by the discipline (design of record `docs/REVIEW_UX.md`), measured
by `xtask/review_ux_probe.py` (RM_RUX rows, 7/7 PASS; re-run against the
core — numbers reproduced) and gated by `xtask/review_ux_gate.py` inside
`make pose-verify` (10 RM_RUX grep rows through the REAL operators).

### The time-to-fix instrument (declared BEFORE measurement)

Interaction-cost model (the DECLARED instrument constants, D-008-untuned,
never claimed as human-timed wall-clock): CLICK 1.0 s (pick a flagged
item + invoke its operator), DRAG 3.0 s (aim + drag + release),
SLIDER 2.0 s (panel trim). time-to-fix = Σ interaction costs + the
measured op wall-clock (published alongside: ~0.0001-0.0002 s median
core-side, ~7-14 ms per Blender operator).

| defect class | fixture source | n | sequence | median t2f |
|---|---|---|---|---|
| flip | the 20-pose class, material flips, wrong-sign injection [INSTRUMENT] | 39 | CLICK+CLICK | 2.00 s |
| finger | the finger-gate occlusion ledger (the engine's own loud output) | 1 | CLICK+DRAG | 4.00 s |
| face | the 10-expression class under the declared occlusion rule | 13 | CLICK+SLIDER | 3.00 s |
| pin | a beyond-reach pin the coupling pass reports unclosable | 1 | CLICK+DRAG | 4.00 s |
| **ALL** | | **54** | | **2.00 s (bar <= 15 s — PASS)** |

Every corrected apply clears its defect within its family bar (flip sign
== GT; authored finger at the canonical segment lengths; face param ==
the authored value; pin residual < 2% torso span after re-coupling);
twins byte-identical; clean inputs stay byte-identical with the
affordances registered. Reproduce: `python3 xtask/review_ux_probe.py`.

### The estimator baseline + the ritual verdict (D-024)

| measure | value |
|---|---|
| default detector no-person, anime benchmark | **3/10** (matches D-012 exactly) |
| default detector latency, full p50 | ~550-614 ms (CPU, mid-laptop) |
| default detector latency, pose-only p50 | ~89-107 ms (CPU, mid-laptop) |
| candidate scan (one candidate class) | **no adoptable anime/sketch whole-body estimator exists** — HF "anime pose" hits are SD LoRAs (image generators, wrong class); HF "dwpose" hits are re-uploads of the pinned photoreal family; "openpose anime"/"manga pose"/"sketch pose estimation" return zero estimator hits; the official ControlNet annotators carry no anime variant; the imgutils ecosystem has no pose module; the fine-tune route is banned in-repo (D-011 verbatim) |
| **L9 verdict** | **REFUSED-with-evidence after one candidate** (the A.2 terminal); the adoption bars (no-person <= 1/10, latency <= 2x DWPose CPU, flip-margin parity within D-010) are unreachable for lack of any candidate |
| the INTERFACE | ships regardless: `inference/estimator.py` (protocol + keyed-order fallback on the no-person probe + the additive `estimator` payload field, never written for the default); any future candidate enters ONLY through the P1-1 manifest ritual (license, sha256, CPU budget, DECISIONS entry) |
| **L10 verdict** | **CLOSED** — median time-to-fix 2.00 s <= 15 s with every fix verified corrective |

## SCENE TEST (P8-10, session 35) — the composite scorecard — ALL MEASURES GREEN

V1's launch gate (design of record: `docs/SCENE_TEST.md`, written BEFORE
any measurement — the SCENE_ANIMATION.md sibling). ONE E2E scenario on
engine-rendered couple fixtures (the A.3 fixture law: engine-built
canonical-class rigs, the pipeline's own deterministic WORKBENCH render,
the clothed SFW class, generated at probe time, nothing committed),
INDEPENDENT measures per stage, each against its pre-declared Annex A.1
bar. The scenario: the arm-in-arm couple — two figures 0.78 u apart,
elbows pinned at the scene center by ONE AUTHORED pin, hands solved from
observed kps, seen by a level frontal reference camera (D = 6). The
detect stage rides the tier-1 deterministic GT instrument (the P8-5
pattern; the detector-blindness to engine mannequins is labeled choice
1 below, never relabeled). Gate: `make scene-test` (RST rows, 11 rows +
the final `RST GATE: PASS` row, grep-tested both shapes inside
pose-verify). Twin runs byte-identical (the wall-clock bake cost is the
only run-varying value and is not a bar).

| # | measure (the stage) | number | bar (Annex A.1 verbatim) | verdict | instrument |
|---|---|---|---|---|---|
| 1 | pin residuals (coupling) | **residual_frac 0.000174** (worst_fk 0.0000°) | < 2% torso span | **PASS** | the REAL `apply_scene_payload` (placements measured, coupling enforced, coupled re-apply) |
| 2 | per-finger accuracy (fingers) | **median 0.00° / p90 10.30°** over 300 visible segments; scenario hands: 10 chains solved from observed kps, byte-stable round-trip | median <= 20 deg / p90 <= 35 deg on VISIBLE fingers; occlusion 100% gated-skip | **PASS** | the P8-3 gate's own 20-pose class machinery, re-run verbatim (numbers reproduce byte-identically) |
| 3 | per-param expression monotonicity (face) | **0 violations / 9 steps, reach 1.00** across 10 params | >= 9/10 per param | **PASS** | the P8-4 gate's own 10-expression class machinery, re-run verbatim |
| 4 | camera framing IoU (camera) | **IoU 0.8630** (solved yaw −0.00° vs GT 0, dist 5.972 vs 6.0, solve conf 1.00) | >= 0.75 (MEASURED staging, both floors) | **PASS** | the REAL `stage_scene_camera_measured` (per-figure solves → consensus → both floors, MEASURED-stamped) |
| 5 | identity swap rate + alarm (video path) | **swap 0.0000** (0/49 solved frames); **alarm 2/2** (catch 1.00); AMBIGUITY class **0.1224** published separately | swap <= 2%; alarm >= 90% | **PASS** | `assign_stream` + the evidence alarm on the ONE stream fixture copy (reproduces the S33 numbers exactly) |
| 6 | FK fidelity (the composed bake) | **worst re-eval 0.0000°** over 98 frame-bakes on BOTH rigs | <= 0.5 deg family | **PASS** | the REAL `bake_action` over the composed two-character scene action |
| — | bake cost (information, not a bar) | **1.0–1.1 ms/frame-bake = 2.1–2.2 ms/scene-frame** across 2 rigs | published, never claimed | **PUBLISHED** | wall-clock on the mid-laptop baseline |
| — | the reference render (chain input) | deterministic WORKBENCH 640x960 PNG at probe time | the A.3 fixture law | **PRODUCED** | the pipeline's own renderer; never committed |
| — | loud refusals (the honesty half) | **3/3**: kp-starved figure refuses the camera (nothing staged); below-floor hand kps → 0 hands solved (zero guessed); beyond-reach pin stays loud | zero silent failures | **PASS** | the chain's refuse classes |
| — | determinism | twin runs byte-identical (payloads, solves, reports, actions) | keyed determinism law | **PASS** | ST-DETERM |

**VERDICT: every measure green → V1's scorecard gate is MET** (per A.3
the scorecard overrides the calendar). The ledger is fully CLOSED/REFUSED
(L1–L6, L8, L10 CLOSED; L7 and L9 REFUSED-with-evidence — see
STATE/TASKS.md for the row map).

### The labeled choices (every residual limitation — none averaged)

1. **DETECTOR-BLIND (tier-2)** — the pinned DWPose detects no engine
   mannequin; the detect stage rides the deterministic GT instrument.
   Real-photo honesty lives in the published P1-9/P8-3/P8-4/P8-5 REAL
   rows; the A.1 re-validation trigger applies when real labeled fixtures
   enter the workflow.
2. **WALK-IN-PLACE (L7 REFUSED-with-evidence)** — no real root-motion
   source exists; the drift track ships for streams WITH drift.
3. **ESTIMATOR (L9 REFUSED-with-evidence, D-024)** — no adoptable
   anime/sketch whole-body estimator; the interface ships; the P1-1
   ritual is the only door back.
4. **THE AMBIGUITY CLASS (0.1224 on the stream fixture)** — duplicated
   pose+scale frames are unresolvable from single views BY CONSTRUCTION;
   the manual override is the designed answer; published separately.
5. **CAMERA error bars are tier-1 numbers** (yaw 2.58° / pitch 4.83° /
   distance 3.42% MAE, synthetic GT); tier-2 render+detector NOT MET with
   evidence; framing IoU is projection-space through the CAM-MODEL-verified
   model (2.32e-07 vs Blender).
6. **GATED SKIPS, BY DESIGN** — fingers/face below the 0.55 floor skip +
   ledger; face params below the 0.08 activation floor ledger; gaze
   conditional-OUT (no iris kps).
7. **UNCLOSABLE / BEYOND-REACH PINS STAY LOUD** (the P8-2 REACH honesty,
   re-proven on the scenario).
8. **D-008 MISS CLASSES** — the two documented flip misses and the
   population-prior neutral face; carried with confidence + residual.
9. **IN-PLACE DEPTH** — placements in-plane (dy == 0 exactly,
   apparent-size staging); depth never guessed from single views.
10. **BAKE COST is information** — no real-time claim anywhere in V1.

Optimism caveat, verbatim, on every synthetic-derived claim above:
*measured on synthetic prior-consistent ground truth; real-detector
noise is not in these numbers; the Annex A.1 re-validation trigger
applies when real labeled fixtures enter the workflow.*

Gate-earned fixture lessons (details in docs/SCENE_TEST.md A1–A3): the
staging instrument's subject cloud is ALL pose-bone heads (the
canonical-class fixture is the honest kp-set match; the scale pairing
`dist = consensus × torso/0.45` is load-bearing); wide two-figure
spreads put figures off-axis where the perspective keystone fakes a depth
gradient past the vertical-regime switch (the A8 fixture law again — the
fixture was wrong); the static scene path carries the arrangement in the
ARTIST'S rig placement, never from bboxes.

Where: probe `blender -b --python xtask/scene_test_probe.py` (11 RST rows,
self-contained beyond the core/addon); gate `make pose-verify` (the RST
grep rows, both shapes) + `make scene-test`; design of record
`docs/SCENE_TEST.md` (amendments A1–A3, as-built).

## AUTO-SCULPT (P9-1, session 36) — the mechanism probe + the selected
### mechanism's gate — ALL MEASURES GREEN

Phase 9's opener (design of record `docs/AUTO_SCULPT.md`, written BEFORE
any measurement — the SCENE_TEST.md sibling). The honest physics: body
keypoints give SKELETON positions, not VOLUME — P9-1 matches SKELETON
proportions (ratios to the torso anchor); volume is P9-2's separate
third-model decision, never a P9-1 claim. Three candidate mechanisms
measured on engine-built metarig-class AND Mixamo-class skinned fixtures
(deterministic nearest-bone weights, nothing committed) against the
pre-declared Annex A.1 bar: **post-sculpt joint positions within 5% of
the segment's length vs intent**. Selection bar: 5% on BOTH rigs, fewest
required rig-side artifacts, name-ascending tie-break.

| # | measure | number | bar / rule | verdict | instrument |
|---|---|---|---|---|---|
| 1 | lattice capability (candidate a) | armature heads unmoved at 1e-6 under a 20% lattice stretch; parent_set LATTICE adds the modifier to the MESH only, the armature gets plain OBJECT parenting | the joint bar on BOTH rigs | **STRUCTURALLY OUT** (mesh-only deform class — measured, never assumed; the first "heads move" reading was float32 noise at a 1e-9 threshold, corrected) | `bpy.ops.object.parent_set` + evaluated depsgraph heads |
| 2 | shape-key binding (candidate b) | joints byte-unmoved on every class; worst fracs 0.1875 / 0.1125 / 0.3147 (the full deltas); surface verts move (156–828 per class) | the joint bar; 6 authored convention keys REQUIRED | **STRUCTURALLY OUT** — the skin–skeleton separation made numeric | convention keys authored on the fixture, evaluated mesh + rest heads |
| 3 | armature scale-correctives (candidate c) | worst frac **0.0000** on BOTH rigs × all 3 classes; the rest-edit delivery REFUTED (follow 0.0000 — skinning re-binds to the new rest, amendment A1); the pose-translation delivery follows 0.76/0.82 | the joint bar; 0 required rig-side artifacts | **SELECTED** (sole bar-holder, fewest artifacts; no tie-break needed) | pose-translation correctives, linear response solve (measured R per bone), absolute-target |
| 4 | the gate through the REAL addon apply | GATE-SCALE worst **0.0000** everywhere (incl. sequential re-sculpts = idempotence); GATE-COMPOSE FK **0.0000°** (bar 0.5°) + the sculpted girdle width survives the pose (drift 1.5e-06 m); GATE-NOTARGET the capability line verbatim; GATE-UNTOUCHED zero-delta = byte-identical; GATE-TWIN 19 bones byte-identical | the 8 RM_ASCULPT GATE rows in pose-verify | **PASS** | `xtask/auto_sculpt_gate.py` (wired into pose-verify, grep-tested both shapes) |
| — | the proportion REPORT | ships as data regardless (`ProportionReport`: reference/base/factors/adjusted/capability_lines) | the roadmap's refuse branch keeps its value | **SHIPPED** | core `proportion_report`, round-trip pinned |

**VERDICT: P9-1's mechanism selection is MEASURED and LANDED** —
`armature_scale_correctives` (pose-translation delivery) as core + add-on;
the REFUSED branch was never reached (a candidate holds the bar on both
rigs). The auto-sculpt CLAIM carries the gate's scope exactly: skeleton
proportions on the six declared rulers, torso anchored, pose applied
afterwards by the certified FK path. Volume is NOT claimed (P9-2's
decision). Optimism caveat, verbatim: *measured on synthetic
prior-consistent ground truth; real-detector noise is not in these
numbers; the Annex A.1 re-validation trigger applies when real labeled
fixtures enter the workflow.*

Where: probe `blender -b --python xtask/auto_sculpt_probe.py` (9 RM_ASCULPT
rows, the selection evidence); gate `make pose-verify` (the 8 RM_ASCULPT
GATE grep rows); design of record `docs/AUTO_SCULPT.md` (amendments A1/A2,
as-built).

## VOLUME (P9-2, session 37) — the third-model decision + the selected
### mechanism's gate — ALL MEASURES GREEN

Phase 9's second rock (design of record `docs/VOLUME.md`, written BEFORE
any measurement — the AUTO_SCULPT.md sibling). THE DECISION (D-025, written
before any adoption code): **`u2net.onnx` ADOPTED as the segmentation pass**
— the P6-6 never-list amends to three. Sole scan candidate clearing all
four gates: license Apache-2.0 verbatim (upstream xuebinqin/U-2-Net,
API-verified; the ONNX artifact published by rembg, MIT, release assets
carry no separate license, rembg issue #837); 175,997,641 bytes, sha256
`8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491` (the P1-1
manifest flow is the only download path); contract in `input.1`
1x3x320x320 NCHW f32, out 1x1x320x320 sigmoid; CPU p50 413.2 ms = 0.73x
the DWPose full-detect reference (inside the declared <= 2x bar). The scan
evidence (verbatim, the D-024 shape): u2netp 0.7968 IoU (no headroom),
silueta 0.8909 (provenance caveat), **u2net_human_seg 0.0000 — BLIND to the
engine mannequin class** (the DWPose tier-2 pattern, caught by the same
diligence), isnet 1400.6 ms = 2.4x DWPose (budget miss, best raw IoU
0.9089), MODNet/RVM CC BY-NC weights, PP-HumanSeg/MediaPipe no first-party
ONNX, YOLO-seg AGPL, BiRefNet unmeasured (dominated on every axis).

| # | measure | number | bar / rule | verdict | instrument |
|---|---|---|---|---|---|
| 1 | the blind-guard (the adopted artifact) | min 0.7738 over the reference renders (heavy 0.8639 / slender 0.7738 / thick_thigh 0.7983 / wide_hip 0.9157) | >= 0.75 (the GUARD, NOT the product bar) | **PASS** | u2net vs free alpha GT, engine renders |
| 2 | the solve | factors track the authored deltas within ~3% (heavy 1.147/1.15, slender 0.882/0.88, wide_hip 1.176/1.20, thick_thigh 1.176/1.20); authored recovery + determinism exact | FP-true recovery, loud clamps | **PASS** | region widths through the adopted model, both sides |
| 3 | THE A.1 BAR (region-scoped, amendment A5) | worst region IoU **0.9499** over 8 cases; NO-SOLVE counterfactual 0.8907 published; every case improves | >= 0.85 AND > counterfactual, visible-view scoped | **PASS** | sculpt vs reference silhouettes, model-free (the A3 amendment: the model-mediated form is published information, worst 0.8592 — the u2net shape prior compresses silhouette differences: the unsolved base scores 0.8838-0.9744 frame-wide) |
| 4 | skeleton invariance | all 8 applies: every pose bone byte-identical pre/post | the joints never move (the S36 flip: surface-without-joints is the FEATURE) | **PASS** | joint-bytes through the REAL addon apply, both rig classes |
| 5 | width delivery | all 16 mid-band ratios exact to 4 decimals (heavy 1.1500/1.15, slender 0.8800/0.88 metarig and mixamo) | within 10% of the factor | **PASS** | owned-group mid-band extents, per-case clean scenes |
| 6 | the artist exit | zero-value restore drift 1.19e-07 m | <= 1e-04 m (an order above the f32 noise band) | **PASS** | addon `measure_zero_restore` |
| 7 | the loud refusals | no-mesh: the capability line verbatim, nothing created | zero silent failures | **PASS** | the no-target class |
| 8 | determinism | 4 keys byte-identical (values + unit-warp data) | keyed determinism law | **PASS** | twin applies |
| — | the rejected classes | lattice: region IoU 0.0000 (the draft's radial cage shrinks the figure out of the region); armature girdle-widen: joints moved (out by invariance; its record case region IoU 0.9016) | the selection bar | **RECORDED** | the probe's drafts, measured |

The five probe-earned lessons (A1-A5 + the product lessons, full detail in
docs/VOLUME.md as-built): the fixture class repair (arm bridging + crotch
fill), the mid-band anchor, the model-mediated bar's compression (the A3
amendment — the binding form is model-free), the per-box skin ownership
(nearest-bone starves the hip band), and the region-scoped bar with the
no-solve counterfactual (whole-frame IoU cannot discriminate). The 5.1
product lessons: shape-key `slider_min` defaults to 0.0 (negative values —
the slender direction — silently dead until widened), one unit system or
the apply is a silent no-op on Mixamo-class rigs, `from_mix=False` at key
creation, clean scenes per render AND per width case, measurement windows
over owned groups covering the clamp ceiling.

Where: probe pipeline `xtask/volume_probe.py` (RM_VOL stages) +
`xtask/volume_measure.py` + `xtask/volume_rows.py` (the model rows print
SKIPPED honestly when the artifact is absent — `rigpose models download
u2net`); gate `xtask/volume_gate.py` (7 RM_VOL GATE rows, model-free,
wired into pose-verify); design of record `docs/VOLUME.md` (amendments
A1-A5, as-built); the decision STATE/DECISIONS.md D-025.

Optimism caveat, verbatim: *measured on synthetic prior-consistent ground
truth; real-detector noise is not in these numbers; the Annex A.1
re-validation trigger applies when real labeled fixtures enter the
workflow.*
