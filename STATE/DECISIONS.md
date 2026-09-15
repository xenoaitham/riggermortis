# DECISIONS

Append-only. `NEEDS-HUMAN` items block nothing else — switch tasks and move on.

## D-001 Name availability — `riggermortis` confirmed usable (2026-09-06)
- PyPI `riggermortis`: **free** (404 on pypi.org/pypi/riggermortis/json).
- Blender Extensions: **free** (0 search results on extensions.blender.org).
- GitHub: one unrelated repo `TheOutdoorProgrammer/riggermortis` (Go,
  fishing-rig reference, 0 stars). Repo names are per-account → no conflict,
  but expect mild search collision; our README/keywords will dominate over time.
- Alternates `snapose`, `rigshot`, `posemd`: all free on PyPI too — kept as
  fallbacks, primary stays `riggermortis`.
- NEEDS-HUMAN: GitHub repo/org creation, PyPI account + name registration,
  extensions.blender.org account (publishing steps in Phase 7).

## D-002 Positioning vs prior art (researched 2026-09-06)
- **DeepMotion Animate 3D**: cloud SaaS, credit/second model — free tier ~60
  credits/mo, Starter ~$9/mo (180s), Studio $180/mo (7,200s). Uploads your
  video/character to their cloud. [deepmotion.com/pricing-animate3d](https://www.deepmotion.com/pricing-animate3d)
- **Rokoko Video/Studio**: free tier caps Vision AI (~30s/mo trial), $10/mo
  Basic = 600s/mo AI mocap, Plus ~$20/mo for full retargeting; cloud storage
  time-limited even on free. [rokoko.com/pricing](https://www.rokoko.com/pricing)
- **Mixamo**: free but rig-locked — auto-rigged skeletons can't be edited or
  extended, retargeting to custom rigs needs pose-matching + converters
  (Terribilis Mixamo Converter, UNAmedia), FBX round-trips fragile (0.01
  scale, axis conventions). Confirms "any rig" is a real pain point, not a
  made-up one. (Adobe community threads, Blender SE, Polycount.)
- **blender-mcp (ahujasid)**: closest to our MCP angle — but it is a generic
  scene-control bridge (LLM writes bpy code, executed unguarded; telemetry
  ON by default; blender.org Lab warns it executes LLM code without data
  guards). It has **no rig tools, no pose/animation semantics, no policy
  layer**. Our MCP contract = domain tools + structured refusals + local-only
  guarantee. [github.com/ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp), [blender.org/lab/mcp-server](https://www.blender.org/lab/mcp-server/)
- **Cascadeur**: desktop keyframing assistant (physics/AI-assisted posing),
  not image-driven, not rig-agnostic retargeting for arbitrary Blender rigs —
  adjacent, not competing on our core loop.
- **DWPose** (ICCV 2023, IDEA-Research): 133-keypoint whole-body estimator,
  ONNX Runtime CPU+GPU, the ControlNet-adjacent standard. Caveat found:
  trained on photoreal data; anime/sketch accuracy is a known gap (see
  SKEP-120K sketch-pose literature, arXiv 2510.26196). **Consequence:** the
  Phase 1 anime benchmark is load-bearing; if DWPose <90% usable on anime,
  plan a second estimator or fine-tune path (P1-8).
- **Unshipped combination confirmed:** local + rig-agnostic + art-pose
  support + MCP agent-drivable + manga output. Nothing found shipping all five.

## D-003 Core stays dependency-free AND process-free (2026-09-06)
- Phase 0 core has zero runtime deps (stdlib math only; numpy enters with
  inference as an optional extra).
- The core library performs **no subprocess spawning and no socket opens**.
  Initially architectural preference; then the workspace security gate
  (Mimosa) rejected any `subprocess` in library code — the boundary is now
  enforced by tooling and matches the embeddability goal (the add-on imports
  core inside Blender's Python; the MCP server may run it sandboxed).
- Blender interop therefore lives at the edges: `core/.../bridge/blender_extract.py`
  (runs *inside* Blender), `xtask/extract_blend.sh` + `xtask/blender_verify.sh`
  (shell glue), CI. `load_rig()` on a `.blend` returns an actionable error
  pointing at the edge script.

## D-004 Inference runs OUTSIDE the Blender process (Phase 1 architecture)
- onnxruntime in Blender's bundled Python is fragile (version/ABI, manylinux
  wheels). Decision: the add-on/MCP server invoke the core **inference CLI as
  a local subprocess** (edge layer only, per D-003) or a localhost helper;
  Blender consumes plain JSON keypoint/pose payloads. Keeps Blender stable,
  keeps the local-only property testable, allows GPU pickling-free lazy loads.

## D-005 Mapping algorithm v1 (locked until real-rig gate says otherwise)
- Name evidence → role-major greedy assignment (score desc, name asc),
  side-mismatch ×0.3, side-unknown ×0.8, one-to-one.
- Family overrides for Mixamo lies (`LeftLeg` = shin) keyed on the joined
  raw token string *including* side tokens (`leftleg`), computed before side
  stripping.
- Spine families (spine.001 / Spine1/2) resolved by chain-order promotion:
  leftover same-lexicon bones fill empty [spine, chest, neck, head] slots in
  height order; extras honestly unmapped.
- Geometry pass fills only still-empty roles, never clobbers name-pass
  results: root/hips disambiguation via parentless-fork shape, spine chain by
  height ordering, limb chains by direction+proportion+side(x).
- Confidence: 0.7·name + 0.3·geometry; geometry-only capped 0.75; ambiguous
  below 0.55; quadruped detection = mapped legs + remaining downward chains > 2.

## D-006 Conventions locked
- Side convention: character-left = +X (Blender world, facing −Y).
- Refusal codes are public API; presets keyed by rig fingerprint; determinism
  rules in CONVENTIONS.md.

## D-007 Mapping algorithm v2 — real-rig gate findings (2026-09-06, S2)
Driven by P0-15 on real Blender 4.0.2 Rigify rigs (metarig 159 bones,
generated 706 bones: 220 controls / 160 DEF- / 167 MCH- / 159 ORG-):
- **Side-marked hips flanks** (`pelvis.L/.R`) carry no hips evidence — half a
  pelvis is not the center hips (metarig previously mapped `hips → pelvis.L`).
- **Structural pre-pass**: a fork to downward limb chains spanning BOTH
  character sides at hip height pins `hips` when no name claims hips (the
  metarig's hips bone is lexicon-named `spine`); a single-child parentless
  bone directly above pins `root`. Both-sides requirement rejects a lowered
  (A-pose) hand fanning its fingers downward.
- **Prefix-duplicate barring**: bones sharing the fork's family signature
  (``DEF-spine``/``ORG-spine`` of a pinned ``spine``) are barred from the
  `spine` role — kills the one-vertebra-low torso chain on generated rigs
  (`spine → DEF-spine.001` now).
- **Pose-target preference**: name-pass ties break by prefix rank
  (unprefixed control > `DEF-` > `ORG-`); `MCH-` is a skip token (checked
  against pre-strip tokens so `MCH-spine` never maps) and `parent` is skipped
  (Rigify IK/FK parent helpers). Controls are the right FK posing target for
  generated rigs; DEF- wins where no control exists.
- **Duplicate-limb views** (co-located with or descending from a mapped
  thigh: `ORG-thigh.L`, bendy `DEF-thigh.L.001`) are not "extra limb chains";
  the quadruped detector also ignores skip-token bones (fingers).
- **Review-feed completeness**: every geometry-assigned role appends to
  `mapping.ambiguities[]`, not just low-confidence ones.

Gate results after v2 (see docs/BENCHMARKS.md): metarig 21 roles, core
complete, 0 corrections + 1 review-confirm (structural hips); generated 22/22
roles, core complete, 0 corrections, 0 flags.

## D-008 Pose-solve v1 design (locked for Phase 1, S3)

The 2D→3D lift is 2.5D by construction: in-plane (x, z) come from the image,
depth (y) is solved per joint under rigid canonical bone lengths.

- **Role-position semantics**: a role's position = the joint at the HEAD of
  that role's bone. Keypoints map: shoulder→`upper_arm.*`, elbow→`forearm.*`,
  wrist→`hand.*`, hip→`upper_leg.*`, knee→`lower_leg.*`, ankle→`foot.*`;
  neck/hips/toes are midpoint observations. The torso line hips→mid-shoulders
  spans 0.45 canonical units and hosts spine/chest by proportion.
- **Anchors**: shoulder/hip girdles are rigid at y = 0 (structural symmetry).
- **Proximal segments** (upper arm, thigh) take a FIXED forward prior
  (limbs hang slightly in front of the torso plane). A whole limb's global
  front/back mirror is underdetermined from one view; the prior resolves it.
  Known cost: limbs genuinely swung behind the torso plane get proximal
  depth error while flips stay correct.
- **Distal flips** (forearm, shank; 4 bits = 16 combos) are enumerated and
  scored by E = Σ conf·(0.5·y² + flexion terms). Flexion terms encode that
  elbows only bend forward (forearm behind elbow penalized ×4) and knees
  backward (shank > 0.05 forward of knee penalized ×2). Weights are
  order-of-magnitude choices, NOT fitted to the fixture set.
- **Known misses (accepted, reported, never hidden)**: deep forward kicks
  (2D-identical to a standing pose under the prior) and wrists held behind
  the back. The 20-pose accept is 18/20 with these two; the review UI
  (P1-6/P1-7) exposes per-flip manual override as the designed remedy.
- **Roll**: from-to rotations are roll-free (minimal rotation). v1 accepts
  twisted forearms in extreme poses; P1-11 polish may add roll alignment.
- **Torso**: modeled as the rigid hips→mid-shoulders line (spine/chest ride
  it proportionally); bows/leans tilt the line but spine articulation is not
  solved in v1.

## D-009 Payload-consumer architecture (2026-09-15, S4; amends D-004's wording)

D-004 said "the add-on/MCP server invoke the core inference CLI as a local
subprocess". As written that is impossible: the add-on and the MCP server are
`.py` files, and the workspace security gate forbids the string
`subprocess` in any Python file (D-003's boundary, tooling-enforced).
Resolution — the spawn lives OUTSIDE Python; the frontends consume payloads:

- **Spawning** `rigpose detect` / `rigpose pose` belongs to the user's shell,
  an agent, or `xtask/*.sh` glue — never to a `.py` file.
- **The Blender add-on and MCP tools consume plain JSON payloads**:
  - *detection payload*: `rigpose detect <image> --json` (figures + 133
    keypoints) — for review/figure UIs.
  - *pose payload*: `rigpose pose <image> <rig.rig.json> [--figure N|largest]
    [--out payload.json]` — image size, figure label, `CanonicalPose.to_dict`,
    ordered `BoneRotation.to_dict()` rotations, `skipped`, `notes`, rig
    fingerprint. Everything after `detect` is pure stdlib, so the command and
    payload are fully testable without models.
- The add-on applies a pose payload **in-process** (stdlib core import): it
  loads the payload, optionally mirrors the pose (`CanonicalPose.mirrored`),
  rebuilds role→bone from the `rm_role_*` props (fallback: `map_rig`), and
  writes pose-bone rotations in Blender's bone-local space (see the metarig
  probe — payload rotations are parent-space/world-frame and must be
  conjugated by each bone's rest matrix). Payload `rotations` remain in the
  file for headless/CLI/MCP consumers; the Blender path recomputes from the
  pose so mirror + manual remaps stay correct.

## D-010 Flip verification semantics + observation mapping fix (2026-09-15, S5)

Driven by the benchmark instrument reading structural zeros on ALL 17 real
images. Three changes, all reporting/bugfix class — no solve prior weights
touched (D-008 weights stand):

- **Arm observation mapping fixed to D-008's locked table.** The code mapped
  elbow→`upper_arm.*`, wrist→`forearm.*`, and never consumed the wrist as
  `hand.*` (legs already matched D-008). Consequences before the fix: the
  shoulder girdle anchor was actually elbows, flip-chain lengths were applied
  one joint down (0.32 on the forearm segment), distal-flip verification was
  IMPOSSIBLE on real detections (no hand role → margin 0.0 → every real image
  flagged), and the confidence formula silently excluded those zeros
  (`if conf > 0.0`), inflating whole-pose confidence (S4's 0.85–0.91).
  Fixtures were D-008-semantics all along; only the kp index table was wrong.
  Fixture flip accept unchanged at 18/20 (same two documented D-008 misses);
  per-pose confidences rose (true girdle anchors, correct segment lengths).
- **Immaterial flips (straight limbs) auto-pass.** A limb straight within
  ~14.5 deg (depth swing ≤ 0.25 distal-bone lengths) renders identically
  under both bend signs; its margin is a noise-driven near-tie, not review
  material. Such flips report verification 1.0 with an honest note
  ("flip immaterial, auto-pass"). Unobserved distal joints stay 0.0 =
  review (bend unverifiable). Real margins are evidence-conf-independent
  (ratio of energies) and — with the corrected mapping — legs mostly verify
  0.54–1.00 while arms genuinely land 0.12–0.53 on real photos (noisy wrists
  flatten the energy landscape): the D-008 single-view class, now visible
  instead of hidden.
- **Whole-pose flip quality aggregates by MEAN, not min.** Min made sense
  only while hands were unobservable; with four real margins, one noisy
  wrist must not mark an otherwise-good pose unreliable. Per-flip review
  triggers stay per-flip (each margin vs the 0.55 bar in review.py).

Instrument honesty: `usable-straight-away` is unchanged as a STRICT lower
bound. If it reads 0%, we publish 0% (see D-011) — thresholds are not
loosened to pass gates.

## D-011 P1-8 decision: fallback-estimator PLAN (2026-09-15, S5; not implemented)

Benchmark basis (out/benchmark/images/, provenance out/benchmark/SOURCES.md,
n=7 anime of the 10-slot gate — 3 slots NEEDS-HUMAN for LO-owned/CC0 art):

- anime: 0/7 usable-straight-away; **detector found no person on 2/7**
  (pure line-art sketches — the D-002-predicted photoreal-training gap);
  detected-5 confidences 0.45–0.71 vs photo 0.40–0.77.
- photo: 0/10 usable-straight-away — but 10/10 DETECTED fine; failures are
  solver-side (arm flip review, foreshortening heuristics), i.e. shared with
  anime, not anime-specific.

Decision: DWPose is **<90% on the anime set** (both raw usable rate and
detection success). The gap decomposes into (a) an anime-specific DETECTOR
gap (line-art no-person) and (b) a domain-general SOLVER class (flip review
need — the review UI is its remedy, not a second detector). Therefore:

- **Fallback-estimator plan (task P1-8a, not implemented this session):**
  1. Candidate: a sketch/anime-finetuned whole-body estimator with ONNX
     export (SKEP-120K-class sketch-pose models; or DWPose fine-tune on
     licensed line-art with pose labels). Gate any candidate on THIS
     benchmark set + the same usable metric — no new private metric.
  2. Architecture stays dual-estimator-capable: `inference/` gains an
     estimator interface; DWPose remains default; fallback selected
     per-image by a cheap detector-confidence probe (if no person / conf
     < threshold, retry with the anime estimator). Payload format v2 (B1)
     carries an `estimator` field so provenance travels with the payload.
  3. Licensing for any training data must be names + licenses, same bar as
     SOURCES.md. No scraped Danbooru-class data, ever.
- **The Phase-1 "≥90% usable-straight-away" gate is NOT met as measured**
  (0/10 photo, 0/7 anime). Honest status: the pipeline produces reliable,
  review-ready poses (median conf 0.66 photo / 0.52 anime; legs verify,
  arms often need a one-click flip review); it does not yet hit
  "usable with zero review" at 90% on strict criteria. This is recorded as
  the Phase-1 close-out position, not hidden behind a redefined metric.
- Re-decide at n=10 anime (LO-owned/CC0 art drops in) — the detector no-person
  rate is the number to watch; n=7 makes ±1 image worth ±14 points.

## NEEDS-HUMAN queue
- Benchmark anime sourcing: 3 of 10 anime slots open — drop LO-owned/CC0 art
  into `out/benchmark/images/anime/`, record in out/benchmark/SOURCES.md,
  rerun `python3 xtask/benchmark_poses.py` (SOURCES.md documents the bar).
- GitHub org/repo + PyPI registration + Blender Extensions account (D-001).
- Decide public repo name string exactly (`riggermortis` recommended).
- Sample-rig sourcing for P0-15 needs network access in the next session
  (Mixamo export requires an Adobe login — NEEDS-HUMAN to obtain a
  redistributable-license sample or use a CC0 VRM + Rigify-generated rigs).
