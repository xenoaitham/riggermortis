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
| Mixamo export | not run — needs an Adobe login (NEEDS-HUMAN, DECISIONS queue). The synthetic Mixamo-style fixture (incl. the `LeftLeg`-is-a-shin trap) covers the naming traps meanwhile | — | — | — | — | — |

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

## Planned (from the mission gates)

- **Phase 1:** 20-image benchmark (10 photo, 10 anime) — ≥90% usable-straight-away poses.
- **Phase 2:** dance + fight clips on 3 rigs; published foot-slide metric.
- **Phase 5:** live-mode latency budget (<100 ms, mid laptop).
- **Always:** network-audit test (zero outbound connections in default use).

<!-- BENCHMARK:POSES:BEGIN -->
### Phase 1 pose benchmark (P1-9, generated by xtask/benchmark_poses.py)

`usable-straight-away` = solver-reliable AND every flip margin >= 0.55 AND no deep-foreshortening flag (heuristic proxy for the two documented D-008 miss classes: deep kicks, wrists behind the back). Flags: `flip` = bend direction for human review; `fore-<segment>` = proximal segment 2D length < 0.6x canonical (single-view depth limitation).

#### anime set — 0/1 usable (0%), confidence min 0.81 / median 0.81 / max 0.81

| image | figures | figure used | det score | pose conf | reliable | min flip margin | flags | usable |
|---|---|---|---|---|---|---|---|---|
| controlnet_anime_3.png | 5 | figure 4 | 0.67 | 0.81 | yes | 0.00 | flip;fore-forearm.L:upper_arm.L,forearm.R:upper_arm.R,lower_leg.R:upper_leg.R | no |

#### photo set — 0/1 usable (0%), confidence min 0.85 / median 0.85 / max 0.85

| image | figures | figure used | det score | pose conf | reliable | min flip margin | flags | usable |
|---|---|---|---|---|---|---|---|---|
| rtmpose_human_pose.jpg | 1 | figure 1 | 0.96 | 0.85 | yes | 0.00 | flip;fore-forearm.L:upper_arm.L,forearm.R:upper_arm.R,lower_leg.R:upper_leg.R | no |

**NEEDS-HUMAN (anime sourcing):** only 1 licensing-clean anime image(s) available locally; the P1-8 fallback-estimator decision stays explicitly pending until a 10-image set exists.

<!-- BENCHMARK:POSES:END -->
