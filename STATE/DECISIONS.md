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

## D-012 P1-8 re-decision at n=10 + real-Mixamo gate (2026-09-15, S5 NEEDS-HUMAN-clearing run)

- **P1-8 at full n=10** (D-011 amendment): anime set completed with two
  recorded crops of Apache-2.0 ControlNet screenshots (anime_4/anime_6) and
  one Wikimedia Commons hand-drawn illustration (CC BY-SA 3.0, User:Niabot —
  provenance in SOURCES.md). Result: **3/10 outright detector failures** and
  0/10 usable-straight-away; median anime conf 0.50 vs photo 0.66. Key new
  fact: the Commons soft-shaded HAND-DRAWN illustration also gets zero
  detections — the gap is NOT line-art-only. D-011's fallback-estimator plan
  (P1-8a) is CONFIRMED necessary at full statistical weight.
- **Real Mixamo gate closed without Adobe**: Xbot.glb is a genuine Mixamo
  export distributed in mrdoob/three.js (MIT). Mapper: 21/22 roles, core
  complete, 0 corrections, 2 review flags (upper_arm conf 0.50) — within the
  ≤2-corrections gate. The NEEDS-HUMAN (Adobe login) item is RETIRED.
- NEEDS-HUMAN cleared by tooling: gh CLI authenticated → GitHub repo
  creation + push unblocked (CI's first run). PyPI upload still requires
  LO's account credentials (prep-only: build + twine check + runbook).

## D-013 P2-5 IK foot lock v1 scope (2026-09-16, S7)

The contact report (P2-4) becomes a lock in two coordinated halves:

- **Core — canonical position pin** (`contacts.lock_feet`): per contact
  interval the ankle AND toe are pinned to the interval's FIRST OBSERVED
  positions (a real detected plant pose, never fabricated), and the knee is
  re-solved by a deterministic 2-bone IK (closest-to-original pole; fixed
  fallback ladder for straight-leg degeneracy; unreachable targets clamped
  along hip->ankle and counted). The locked action is walk-in-place — the
  honest alternative to fabricating root motion (D-008). Frames already at
  their pinned position (within 1e-12) keep their original values, so
  locking clean data is a bit-for-bit no-op. `to_ground` optionally projects
  pinned ankles onto the report's ground estimate. Returns a LockReport with
  slide before/after (the >=5x gate) plus cost columns (knee corrections,
  ankle shifts, clamps).
- **Add-on bake — rig-space world pin** (`bake_action(contacts=...)`): per
  locked frame the thigh+shin are re-solved by a small 2-bone correction so
  the ankle's WORLD position stays at the captured plant, and the foot
  bone's world transform is held (no pivot, no drift). Deviation from the
  source pose is reported as `lock_dev_deg`, separate from FK fidelity
  (`worst_deg`, always measured on the UNLOCKED application); unreachable
  targets count in `lock_clamped`. Requires all three leg roles mapped;
  missing roles degrade that frame to computed keys.
- **Implementation facts worth keeping** (both bit us): bone rest LENGTHS
  are `Bone.length`, NOT recoverable from `matrix_local`'s 3x3 (pure
  rotation -> unit Y); and `pb.matrix` reads are STALE once an action is
  assigned — mid-bake world matrices are composed locally via
  `W = P @ (Mp⁻¹ Mb) @ B` (identity verified to 0.000000 on the real
  metarig) and carried across frames (previous key = constant interpolation,
  matching Blender).
- **Gate numbers** (published in docs/BENCHMARKS.md): synthetic labeled
  instrument slide 0.768 u -> 0.000 / 0.793 u -> 0.000 (cost: knee
  corrections <= 0.035 u); real-Blender bake probe 0.0371 m unlocked ankle
  drift -> 0.0000 m locked (bar 0.010 m) at lock_dev 5.10 deg, FK fidelity
  unchanged (0.0242 deg). Real-clip numbers land with P2-8; thresholds NOT
  tuned against fixtures (D-008).

## D-014 CI Blender pin: keep apt 4.0.2, document the dev-box skew (2026-09-16, S7)

- CI keeps ubuntu-24.04's apt Blender 4.0.2: it is the oldest supported
  path, installs fast without a 300 MB download per run, and the suite has
  been green on it since the first CI run. The dev box runs the real
  install, Blender 5.1.0 — BOTH gates were re-verified there (S6b, identical
  numbers) and S7's RM_FOOT_LOCK probe was written and PASSes on 5.1.0.
- The skew is now DOCUMENTED in ci.yml (step name) rather than silent.
- Revisit trigger: any gate needing a Blender >= 4.2-only feature (add-on
  extensions manifest work, new API) should bump CI to an official 5.x
  tarball with actions/cache in one deliberate commit.

## D-015 Phase-2 close: NOT-met-with-real-clips + the glTF tail finding (2026-09-17, S9)

**The real-clip gate is NOT met, recorded like the Phase-1 close (D-011
style).** "Dance + fight clips playable on 3 rigs" decomposes into: the
PIPELINE is complete and verified end-to-end on real rigs (bake, contacts,
lock, stabilization, export — every stage gate-published), the MEDIA ships as
the labeled SYNTHETIC walk retargeted to 3 rigs (WALKRIGS block + 4 GIFs,
generator-cited), and the REAL-CLIP half stays NEEDS-HUMAN (bounded search
exhausted, out/video_smoke/SOURCES.md). Nothing is relabeled: the synthetic
blocks (FOOTLOCK/HIPSTAB/WALKRIGS) stay labeled synthetic; a real clip
re-runs the SAME instruments and re-opens the gate honestly.

**Third-rig compatibility finding (the gate earned its keep again):** the
Mixamo Xbot.glb's glTF-synthesized bone tails are ~100x the true joint
spacing. Garbage tails broke three consumers: (1) the P2-5 2-bone lock solve
(Bone.length as l1/l2 is WRONG on such rigs — bake.py now derives lengths
from head-to-head rest distances of the chain bones; identical numbers on
sane rigs, proven by the unchanged RM_FOOT_LOCK/RM_BAKE gates); (2) Blender's
EVALUATED bone placement (posed children ladder away from their parents —
the core-side FK verified 0.0000 deg while the evaluated rig was broken, so
only a real-Blender per-rig gate catches this class); (3) the bone-proxy
visualizer (built in armature space — now composed through the armature's
world matrix). The walk media pipeline repairs tails WHEN they disagree with
the skeleton (deterministic, conditional: sane rigs are bit-for-bit
untouched). FOLLOW-UP (task P2-8a): the ADD-ON needs the same conditional
tail normalization on VRM/glTF import — users posing imported rigs hit the
same evaluated-placement breakage; not silently bundled into S9.

**Cross-rig drift gate:** per-rig table gates on the PUBLISHED P2-5 >=5x
slide-reduction criterion (scale-free; metarig 21x, seedsan 12x, xbot 21x).
The RM_FOOT_LOCK 0.010 m absolute bar is shown as a context column, NOT the
gate — it bakes in one rig's scale (seedsan misses it by ~5% on its 9
clamp-cost frames while locking 12x). Published ratios and absolute numbers
together; nothing hidden.

## D-016 P2-8a tail-normalization rule: absurd-ratio threshold + co-located skip (2026-09-17, S10)

The add-on tail repair (P2-8a) exposed that D-015's "sane rigs are
bit-for-bit untouched" claim was true only for the rigs the rule had been
certified on — the pose gate's new noop assertion FAILED on the
Blender-native metarig (the 1%-disagreement trigger wanted to repair ~20
artist-intended tails: palm/forehead/hand chain bones at 1.7–2.7x, pelvis/
breast leaf flanks at 3.4–5.1x). The rule is re-keyed on measured data:

- **Absurd-ratio threshold (10x).** A chain tail is repaired only when its
  length exceeds 10x the distance to the nearest child's head; a childless
  leaf only above 10x the rig's median joint span. Measured separation:
  sane max ~5.1x (metarig pelvis flanks), importer garbage starts at ~76x
  and sits at ~100x (Xbot) — an order of magnitude of clean margin on both
  sides. The 2-bone lock solve is unaffected either way (bake derives
  lengths from head-to-head distances since D-015).
- **Co-located-child skip.** A child whose head sits within 5% of the
  median joint span of the bone's head gives no tail evidence and is
  skipped (the metarig's spine/spine.006 have such children; treating
  span~0 as an infinite ratio would snap artist tails to zero length).
- **Lockstep.** The rule lives in `addon/riggermortis_addon/tails.py` AND
  `xtask/walk_media.py::_repair_imported_tails`, textually identical.
- **Add-on wiring.** Inspect & Map runs the repair BEFORE mapping; the
  session bridge's `apply_pose` runs it before applying (P2-8a's whole
  point: an agent posing an imported garbage-tail rig must not hit the
  evaluated-placement breakage). The count is always REPORTED, never
  silently applied.
- **Gate (pose-apply, local).** `RM_TAILS XBOT`: raw lift 1.5177 m ->
  repaired 0.2817 m, inside the MEASURED sane-rig band (the same canonical
  pose lifts seedsan 0.2464 m and metarig 0.3214 m); bars: fixed in
  [0.15, 0.40] m, raw > 1.0 m and > 3x fixed. `RM_TAILS METARIG_NOOP`:
  0 bones repaired. All pre-existing gate numbers byte-identical
  (0.0242 deg x 3). Instrument lessons (do not reintroduce):
  `pose_bone.matrix` is ARMATURE-space (world needs `matrix_world`), and a
  glTF import bakes a skin pose into `matrix_basis` (66/67 bones
  non-identity on Xbot) — so evaluated-vs-rest is only meaningful as a
  grounded-lift comparison against calibrated sane rigs, never as an
  absolute.
- **WALKRIGS regeneration (rule lockstep).** seedsan + xbot rows
  byte-identical; the metarig row moved 0.1732 -> 0.1741 m unlocked drift,
  ratio 21.3x -> 21.7x (the walk pipeline had been silently repairing ~20
  artist tails on the native metarig; corrected rule repairs 0). All rows
  still PASS the >=5x gate; the 4 GIFs regenerated in place by
  `make walk-gifs` (same allowlisted filenames).

## D-017 Phase-4 close: honest decomposition (2026-09-21, S16)

**Phase 4 is CLOSED.** The gate — "6-page wordless manga in docs/manga/,
readable + charming; same scene in 3 styles side-by-side" — is met:
`docs/manga/page_01..06.png` (Paper Dart: find → take → throw → crash →
repair → soar; wordless, one deliberately EMPTY bubble — verified to skip
the text object entirely), `docs/manga/hero_3styles.png` (one camera, one
beat, manga/anime/western), `docs/manga/paper_dart.pdf` (write_pdf +
in-process parse-back). All GENERATED by `bash xtask/manga_build.sh`
(Blender spawn + artifact moves in shell glue, D-009); the media-guard
pins the 8 files in the same commit.

What is VERIFIED (each cites its gate):
- toon materials, line art, screentones, persistent per-panel styles,
  bubbles, byte-faithful page assembly, deterministic PDF/EPUB, animatic
  timing (STYLE GATE P4-1..P4-7, real pixels, dev box AND CI);
- the per-panel `frame` field (P4-8, the one engine extension): CI
  contract tests + `RM_STYLE FRAMES: PASS` (frames 1 vs 3 render distinct
  pixels, re-render identity, preset-sized assembly);
- the full manga pipeline runs end-to-end on 5.1 headless with its own
  parse-back (8 PASS lines in the driver log);
- lineart radii re-tuned on real character framing as the P4-2 note
  promised (manga 0.008 / anime 0.006 / western 0.0055 — data edit,
  visually checked, gate thresholds untouched).

What stays OPEN (recorded future scope, never silently dropped):
- tone grids live in Generated space — per-object density mismatch and a
  screen-space unified grid (P4-3 scope note);
- camera animation within a shot / per-shot transitions / audio (P4-7
  scope; static cameras are the P4-4 data rule);
- bubbles on animatic frames (bubbles are PAGE data);
- panel crop-into-camera-frame semantics (P4-4 v1 renders the full frame);
- the full manga is deliberately NOT re-rendered in CI (llvmpipe cost vs
  zero new mechanism coverage) — media is a local guarded pipeline like
  the walk GIFs;
- the mannequin is rigid-part geometry (no skinning); production skinned
  characters are the untested-but-designed path (the style builders are
  mesh-agnostic).

## D-019 The 18+ enable path is the add-on preferences ONLY; the MCP server can never enable (2026-09-22, S21)

Closing P6-4 forced one architectural stance the policy page implied but
nothing had pinned:

- **The Blender add-on preferences are the ONLY enable path.** The two
  toggles ("Enable 18+ module" + "I understand the policy") sync the
  add-on's single core `PolicyEngine` through the documented calls only
  (`enable_adult_module(confirm=True)` / `disable_adult_module()`); the
  binding (`addon/riggermortis_addon/policy.py`) is bpy-free at import so
  the flow is unit-testable headlessly, and the REAL flow (the checkbox,
  real `AddonPreferences` defaults) is gated in `xtask/blender_verify.sh`
  (`RM_POLICY` lines). NOTE: `bpy.context.preferences.addons.new()` takes
  NO arguments on Blender 5.1 — the addon_utils.enable route is the real
  user path and what the gate exercises.
- **The MCP server builds a fresh default (SFW) engine per call and its
  tool table carries NO enable/confirmation tool — test-pinned.** An
  agent therefore cannot turn the module on anywhere; the MCP refusal for
  `fictional_adult` stays `adult_module_disabled` (retryable = the human
  can enable it, in Blender, locally). If a future content-carrying tool
  needs the add-on's engine state, that is a NEW deliberate decision —
  not silent pass-through over the session bridge.
- **D-018 stays RESERVED** for the S18 duplicate-contract amendment (the
  LIVE.md producer-restart revisit trigger); this entry deliberately
  skips the number to keep that reservation intact.
- Scope honesty: the engine poses rigs — no content-carrying tool exists
  yet, so the add-on's enforcement surface is the policy check operator
  (`rm.policy_check`, panel "Content policy" section) + the preferences
  flow. The refusal shape every future content tool must return is
  already pinned (P3-3 `Refusal.to_dict()` mirroring).

## D-020 P6-3 licensing/packaging answers — the benchmark suite is UNBLOCKED (2026-09-23, post-S25 blocker triage)

The 7 questions parked in NEXT.md since S21/S22/S23, answered by LO
(CC0 confirmed directly; the rest delegated to the session with "you
choose the best, I trust you" — recorded here so the delegation is
explicit and revisitable):

1. **Suite media license: CC0** (code stays MIT). Everything the project
   generates or crops is dedicated CC0; third-party items that cannot be
   CC0-compatible are REPLACED, not licensed around (answers 2+3).
2. **ControlNet screenshot crops (anime_4/anime_6): REPLACE.** The two
   slots go to LO-owned or CC0-licensed art (keeping n=10); the
   third-party-UI-screenshot rights question is killed by not shipping
   them. The benchmark swap needs an honest re-run note for the 2 slots.
3. **The CC BY-SA Commons illustration: REPLACE** (same treatment). One
   BY-SA file means one special case documented forever; uniform CC0
   across the suite wins over dataset variety.
4. **Identifiable people: LO reviews the 10 photo-set images** at
   packaging time (the files surfaced to him); any slot showing an
   identifiable real person gets replaced. The policy page's real-person
   line applies to inputs.
5. **Distribution: IN-REPO, `docs/`-tracked.** CI can run it, one source
   of truth, ~20 images is a few MB of clone growth; the media-guard
   allowlist is extended in the same commits as the media (standing rule).
6. **The PUBLIC suite becomes the CI gate fixture.** Determinism is the
   project's brand; ~20 CPU detections per push (~17 s at the measured
   0.85 s/image) is acceptable cost, and published benchmark numbers
   become reproducible by anyone cloning the repo.
7. **P2-8: RETIRED as satisfied-by-Xbot** for pipeline-verification
   purposes — the Xbot.glb `walk` REAL row exercises the whole
   import→sample→convert→composition→bake path and is already
   published with its honest label (Mixamo-rooted synthetic-real hybrid
   data, NOT human video). A real human clip remains welcome if it ever
   appears, but it is no longer gating anything.

Consequence: P6-3 packaging is buildable work (slots to replace, SOURCES
manifest, media-guard allowlist, the CI detection job) — work order
material for S26+, no longer a NEEDS-HUMAN blocker.

## NEEDS-HUMAN queue (updated 2026-09-16 S8)

- RETIRED — anime sourcing: set complete at 10/10 (SOURCES.md; Commons CC BY-SA crop provenance).
- RETIRED — real Mixamo gate: closed via three.js Xbot.glb (0 corrections, D-012).
- RETIRED — full Mimosa audit: completed CLEAN (findingCount=0, seal sha256:7c594eb7..., static-only evidence boundary).
- DONE — GitHub repo: https://github.com/xenoaitham/riggermortis (public, main, CI green).
- REMAINS — PyPI upload: needs LO's PyPI account/token (docs/PUBLISHING.md, one command).
- REMAINS — Blender Extensions upload: needs LO's blender.org account (docs/PUBLISHING.md).
- NEW (S8) — P2-8 real walking clip: bounded search exhausted (mmpose demo.mp4 is 1 s @ 5 fps — too short; Commons yields POV city walks / news footage — wrong kind and provenance-hostile). Need: single person, full body, side-ish view, >= 3 s, steady fps, named license (or LO-owned with a provenance statement). Evidence sidecar: out/video_smoke/SOURCES.md. P2-8 proceeds on the synthetic-labeled instruments until then (do NOT relabel them real).
