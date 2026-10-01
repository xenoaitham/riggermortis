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

## D-021 The finger/hand namespace is an additive separate map (2026-09-25, S28 — WRITTEN AT THIS LANDING, per the round-3 strike S2 rule)

This entry was RESERVED since the roadmap was written; it is written now,
in the same commit where the namespace code (`core fingers.py`) lands.

- **The namespace**: finger roles are `hand.<SIDE>.finger.<name>.<joint>`
  (e.g. `hand.L.finger.index.pip`) — 2 sides × 5 fingers (thumb→pinky) ×
  4 joints (mcp/pip/dip/tip) = 40 roles. They live in a SEPARATE additive
  topology (`fingers.FINGER_PARENT` / `finger_roles()` / `is_finger_role()`).
  `ALL_ROLES`, `CANONICAL`, `PRIMARY_CHILD`, `CORE_ROLES` are untouched;
  the mapper never assigns finger roles; consumers that ignore fingers
  are byte-identical (pinned by contract test).
- **4 joints, not 3** (amendment A2, recorded in docs/FINGERS.md before
  code): the roadmap's `hand.L.finger.<name>[0..2]` counted the 3
  articulated SEGMENTS; the namespace stores the 4 observed joints per
  finger because the apply path orients a bone toward
  `child_joint − joint` — the tip must exist as data for the dip segment
  to have a target. The tip binds no bone (no segment of its own);
  preset validation refuses `.tip` keys.
- **Data ride**: `CanonicalPose.hands` (default EMPTY, keyed hand.L/hand.R)
  — the frozen 22-role `positions` map untouched; `to_dict` omits the key
  when empty so hands-free poses serialize byte-identically to pre-P8-3
  output (the pins-in-v3 precedent). Payload format stays 3 (additive
  per-figure field through the pose dict). Apply is opt-in via the
  preset's optional `hands` bindings (format 2 unchanged — additive
  field; fingerprint-gated by `resolve_hands`, the P6-1a contract).
- **Policy coverage (D-019)**: fingers carry no content by themselves —
  no new policy surface; the existing subject checks apply unchanged;
  MCP stays SFW with no new tool (the session bridge's `apply_pose`
  gains additive `preset_path`/`preset_force` params only).
- **Gate discipline**: per-finger confidence floor 0.55 (the CONVENTIONS
  ambiguity bar, reused — the coupling precedent, declared untuned);
  occluded fingers are skipped + ledgered, never guessed; depth sign is
  the declared forward-curl rule (the D-008 elbow-forward prior one
  level down; the probe showed a flatten-prior enumeration un-curls
  grips — docs/FINGERS.md § Probe answers).

## D-022 The facial parameter namespace is an additive separate map (2026-09-25, S29 — WRITTEN AT THIS LANDING, per the round-3 strike S2 rule)

This entry was RESERVED since the roadmap was written; it is written now,
in the same commit where the namespace code (`core face.py`) lands.

- **The namespace**: 10 expression params — `brow.raise.L/R`, `blink.L/R`,
  `jaw.open`, `smile.L/R`, `pout`, `cheek.L/R` — a FIXED set (docs/FACE.md
  § the published landmark→param table, the page D-022 cites). They live
  in `face.py` (`FACE_PARAMS` / `is_face_param` / `FACE_BONE_PLAN`);
  `ALL_ROLES`, `CANONICAL`, `PRIMARY_CHILD`, `CORE_ROLES`, and the D-021
  finger namespace are untouched; the mapper never assigns face params
  (they bind via preset `face_bones` mappings only); consumers that
  ignore faces are byte-identical (pinned by contract test).
- **Params, not geometry** (the structural insight, docs/FACE.md): every
  param is a dimensionless landmark ratio (IOD- or aspect-normalized) —
  the payload carries SOLVED PARAMS + ledgers (the D-009 pattern), never
  landmark geometry. `CanonicalPose.face` (default None) — `to_dict`
  omits the key when None so face-free poses serialize byte-identically
  to pre-P8-4 output; `from_dict` tolerates absence; `mirrored()` swaps
  `.L`/`.R` values (geometry-free).
- **Honesty rules** (the finger rules one level up): the face solves
  only when the IOD anchor's four corner kps clear `FACE_CONF_FLOOR`
  0.55 (the CONVENTIONS bar reused — an absent face reads as clean); a
  param whose consumed kps fall below the floor is SKIPPED + LEDGERED,
  never guessed; a solved value below `FACE_ACT_FLOOR` 0.08 is LEDGERED
  as below-threshold, never interpolated. **Gaze is NOT a param**: the
  pinned DWPose has no iris kps; gaze enters only if a detector variant
  supplies them (conditional-OUT — the roadmap's pre-declared condition).
- **The measured side map** (amendment A4, the D-008 loop): the design
  DECLARED band A = subject-left; the probe MEASURED band A at image-left
  = the subject's RIGHT on 18/18 real faces — the `.L` constants read
  band B. Three neutral-geometry priors were redeclared from pooled real
  measurements (`PRIOR_CORNER_DROP 0.40`, `PRIOR_MOUTH_W 0.83`,
  `PRIOR_CHEEK 0.72`); EAR/brow priors stood. Declared → measured →
  redeclared BEFORE the core build.
- **Apply, two loud classes** (docs/FACE.md § apply): (a) bones via the
  preset's optional `face_bones` bindings (format 2 unchanged — additive
  field; `resolve_face`, the fingerprint-gate contract; rotations are the
  DECLARED `FACE_BONE_PLAN` axis-angle, param × max angle); (b) shape
  keys by naming convention (key name == param name on meshes deformed
  by the armature; missing keys report loud). NEITHER present → the
  loud "no facial targets" line, never silent. Facial bones never
  double-bind a body/finger bone (the cross-binding class, refused).
- **Policy coverage (D-019)**: expressions carry no content by
  themselves — no new policy surface; the existing subject checks apply
  unchanged; MCP stays SFW with no new tool (the session bridge's
  `apply_pose` preset path gained the `face_bones` resolution only).
- **Gate discipline**: per-param monotonicity ≥ 9/10 (violations ≤ 1 of
  9 steps, states sorted by GT, MONO_TOL 0.05) + reach ≥ 0.5 at the
  max-GT state (an all-zero sequence is trivially monotone — the probe's
  A3 amendment) on the 10-expression benchmark; bone apply ≤ the 0.5°
  family; shape-key applied-vs-intended ≤ 0.1 normalized; refusal
  branch: a param below its bar after two redesign cycles → REFUSED per
  param (Annex A.2).

## D-023 The roll namespace is an additive separate map (2026-09-26, S31 — WRITTEN AT THIS LANDING, per the round-3 strike S2 rule)

P8-6's arm-roll correction cannot ride positions (twist is an APPLY-time
quantity), so it lands as the third additive namespace on CanonicalPose,
written in the same commit where the namespace code (`core spine.py`)
lands.

- **The namespace**: `CanonicalPose.roll: dict[str, RollEntry]` — keys
  `forearm.L`/`forearm.R` (v1 writes; `upper_arm.L/R` are RESERVED: no
  humeral-twist evidence exists in point landmarks, declared not hidden).
  Each `RollEntry` carries the signed `twist_rad` (about the bone's
  TARGET axis) + `confidence`. Design of record: docs/SPINE.md
  (the page D-023 cites). `ALL_ROLES`, `CANONICAL`, `PRIMARY_CHILD`,
  `CORE_ROLES`, and the D-021/D-022 namespaces are untouched.
- **Byte identity** (the hands/face contract, pinned by test): `to_dict`
  OMITS the key when empty; `from_dict` tolerates absence and validates
  keys loud (the D-021 pattern); poses without entries apply
  BYTE-IDENTICALLY through `apply_canonical_pose` (the straight-arm
  no-op is structural — a straight arm produces no entry). `mirrored()`
  swaps sides and NEGATES the twist (an x-mirror reverses handedness
  about the mirrored axis); solve-after-mirror == mirror-after-solve is
  pinned by test.
- **The honesty rules** (the finger/face rules one pass up): entries
  exist only when the elbow bend clears `ROLL_BEND_MIN` 15 deg AND the
  chain confidence (capped at the CONVENTIONS geometry cap 0.75) clears
  0.55 — below either, the side is SKIPPED + LEDGERED in the report,
  never guessed. A not-applied roll changes NO bytes (the ledger lives
  in the returned `RollReport`, not in pose.notes); an applied roll adds
  one honest note per side. `fk_apply` composes any present entry as a
  twist ABOUT the target axis — direction fidelity is exact
  (verify_application errors stay 0).
- **The arch does NOT need this namespace**: the spine arch rides the
  SOLVED POSITIONS (the coupling write-back class — docs/SPINE.md),
  which is why the arch alone carries no DECISIONS entry; only the
  apply-time roll data is a namespace.

## NEEDS-HUMAN queue (updated 2026-09-16 S8)

- RETIRED — anime sourcing: set complete at 10/10 (SOURCES.md; Commons CC BY-SA crop provenance).
- RETIRED — real Mixamo gate: closed via three.js Xbot.glb (0 corrections, D-012).
- RETIRED — full Mimosa audit: completed CLEAN (findingCount=0, seal sha256:7c594eb7..., static-only evidence boundary).
- DONE — GitHub repo: https://github.com/xenoaitham/riggermortis (public, main, CI green).
- REMAINS — PyPI upload: needs LO's PyPI account/token (docs/PUBLISHING.md, one command).
- REMAINS — Blender Extensions upload: needs LO's blender.org account (docs/PUBLISHING.md).
- NEW (S8) — P2-8 real walking clip: bounded search exhausted (mmpose demo.mp4 is 1 s @ 5 fps — too short; Commons yields POV city walks / news footage — wrong kind and provenance-hostile). Need: single person, full body, side-ish view, >= 3 s, steady fps, named license (or LO-owned with a provenance statement). Evidence sidecar: out/video_smoke/SOURCES.md. P2-8 proceeds on the synthetic-labeled instruments until then (do NOT relabel them real).

## D-024 P8-9 verdicts: L10 CLOSED at the time-to-fix bar; L9 REFUSED-with-evidence — the dual-estimator INTERFACE ships (2026-09-28, S34 — the second exercised Annex A.2 branch)

P8-9's two ledger rows, closed on measured evidence (docs/REVIEW_UX.md is
the design page; docs/BENCHMARKS.md REVIEW-UX holds the numbers):

- **L10 (review/fix is workable but slow per-fix) = CLOSED.** The declared
  scripted click-through instrument (interaction model CLICK 1.0 s /
  DRAG 3.0 s / SLIDER 2.0 s, D-008-untuned constants declared BEFORE any
  measurement, op wall-clock published alongside) measures the median
  time-to-fix at **2.00 s over 54 flagged defects** on the benchmark
  fixture classes (flip 39 / finger 1 / face 13 / pin 1; per-class medians
  2.00 / 4.00 / 3.00 / 4.00 s) — the Annex A.1 bar is <= 15 s. Every
  corrected apply actually clears its defect within its family bar
  (flip sign == GT; authored finger at the canonical segment lengths,
  direction verified core-side; face param == the authored value; pin
  residual < 2% torso span after re-coupling). The four affordances
  (`author_finger` / `trim_face` / `flip_figure` / `retarget_pin` +
  `confirm_pin`) are pure, confidence-1.0, provenance-noted, and ride the
  EXISTING namespaces (D-021/D-022/P8-1) — no new solve, no new namespace,
  no payload format change; the untouched path is byte-identical (gate
  RUX-GATE-UNTOUCHED, 159 bones at 9 dp).
- **L9 (anime detector gap, D-011/D-012) = REFUSED-with-evidence after one
  candidate — the A.2 branch exercised (the L7 precedent).** The third-
  model ritual ran and found NOTHING to ritualize: no published anime/
  sketch whole-body keypoint estimator with adoptable weights exists.
  Evidence (2026-09-28 scans): HF "anime pose" (3 hits) resolves to
  Stable-Diffusion LoRAs/segmentation heads — image GENERATORS, not
  keypoint estimators (wrong product class); HF "dwpose" (37 hits) are
  re-uploads/repackagings of the SAME photoreal family already pinned
  (worse provenance, identical failure mode); "openpose anime", "manga
  pose", "sketch pose estimation", "anime keypoint", "lineart pose" return
  zero estimator hits; the official ControlNet Annotators repo carries no
  anime OpenPose variant; the deepghs/imgutils ecosystem (74 repos swept,
  MIT toolbox) has NO pose module (the one web-search lead was wrong on
  inspection). D-011's alternative candidate (fine-tune DWPose on licensed
  line-art) is BANNED by the ritual itself (NO fine-tune in the repo;
  adopted weights only). The adoption bars (no-person <= 1/10, latency
  <= 2x DWPose CPU, flip-margin parity within D-010) are therefore
  unreachable for lack of any candidate — the refusal is the honest
  terminal, not a threshold excuse. The DEFAULT detector's baseline is
  re-published for the record: no-person 3/10 on the anime benchmark
  (matches D-012 exactly), full p50 ~550-614 ms, pose-only p50 ~89-107 ms
  (CPU, mid-laptop).
- **The dual-estimator INTERFACE ships regardless** (D-011 planned it; the
  refusal does not retire it): `inference/estimator.py` — the Estimator
  protocol (name + the standard 133-kp Detection), `select_estimator`
  (default first, keyed-order fallback exactly on the no-person probe,
  honest no-person terminal — nothing fabricated), and the additive
  per-figure `estimator` payload provenance field (written ONLY for
  non-default estimators; the default-only pipeline stays byte-identical,
  pinned by contract test). Any future candidate enters ONLY through the
  P1-1 manifest ritual: license verbatim, sha256 + bytes, CPU budget
  measured on the mid-laptop baseline, a DECISIONS entry at the landing.
- The manifest state is pinned as the ritual's guard: exactly the two
  DWPose models unless an adoption lands through the full ritual (probe
  row RUX-EST-RITUAL). D-018 stays RESERVED (the live-camera amendment
  not exercised).

## D-025 P9-2: the P6-6 never-list amends to THREE — `u2net.onnx` adopted as the segmentation pass (2026-09-30, S37 — the third-model ritual exercised to ADOPTION, the first full amendment)

P9-2 (volume from silhouette) needs a segmentation pass = a THIRD pinned
model, which amends the P6-6 never-list ("no weights beyond the two
pinned DWPose models"). The ritual order was honored: SCAN-FIRST, THE
DECISION written before any adoption code. The scan surveyed the
human-matting / portrait-segmentation / person-segmentation families;
every measured candidate carries license verbatim, bytes, sha256,
input/output contract, and a CPU budget measured on THIS box (the
mid-laptop baseline: Intel i5-10400F, 12 threads, onnxruntime 1.25.1
CPUExecutionProvider; DWPose full-detect reference p50 550–614 ms,
D-024's republication; declared budget bar = the D-024 shape, <= 2x
DWPose CPU). Scan artifacts live under out/p9_2_scan/ (models, contracts,
IoU sweep, scripts; nothing committed from there but the recorded
numbers).

- **THE DECISION: ADOPT `u2net.onnx`.** Sole candidate clearing all four
  adoption gates:
  - **License (verbatim)**: Apache-2.0 — verified at the upstream repo
    (xuebinqin/U-2-Net, GitHub API license field + LICENSE file). The
    ONNX artifact is published by rembg (danielgatis/rembg, MIT); the
    release assets carry no separate license file (rembg issue #837) —
    the converted weights inherit upstream Apache-2.0. Caveat recorded
    verbatim in the manifest notes.
  - **Artifact**: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
    — 175,997,641 bytes, sha256
    `8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a728a912b491`
    (measured on the downloaded artifact; the P1-1 manifest flow is the
    only download path — checksum-pinned, user-initiated, zero
    default-use outbound).
  - **Input/output contract**: input `input.1`, 1x3x320x320 NCHW
    float32 (RGB/255, the rembg convention); primary output `1959`,
    1x1x320x320 sigmoid mask (+6 side outputs, ignored).
  - **CPU budget (measured)**: p50 413.2 ms / p90 421.0 ms (3 warmups,
    10 timed runs) = **0.73x the DWPose full-detect p50** — inside the
    declared <= 2x bar with margin.
  - **Benchmark-class quality (measured)**: silhouette IoU **0.8699**
    vs the free alpha GT on an engine-rendered mannequin fixture
    (640x960 WORKBENCH, film-transparent; the A.3 class) — above the
    A.1 volume bar (0.85) BEFORE the solve's headroom is added, with
    the sweep's prediction coverage tight (0.0227 vs GT 0.0197).
- **The scan evidence (verbatim; the D-024 shape — a scan that finds
  things is still a RESULT)**:
  - `u2netp.onnx` — same Apache-2.0 chain; 4,574,861 bytes; sha256
    `309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8`;
    p50 222.8 ms; IoU **0.7968** on the benchmark class — NOT selected:
    no headroom under the 0.85 end-to-end bar.
  - `silueta.onnx` — 44,173,029 bytes; sha256
    `75da6c8d2f8096ec743d071951be73b4a8bc7b3e51d9a6625d63644f90ffeedb`;
    p50 620.9 ms; IoU **0.8909** — the qualified alternate; provenance
    caveat: a rembg-author-trained compression with no explicit
    upstream license declaration — not selected over the cleaner chain.
  - `u2net_human_seg.onnx` — 175,997,641 bytes; sha256
    `01eb6a29a5c4d8edb30b56adad9bb3a2a0535338e480724a213e0acfd2d1c73c`;
    p50 399.3 ms; IoU **0.0000 — BLIND to the engine mannequin class**
    (prediction coverage 0.0000; the DWPose tier-2 pattern, caught by
    the same diligence) — REFUSED on the benchmark-class measurement.
  - `isnet-general-use.onnx` — Apache-2.0 (xuebinqin/DIS verified);
    178,648,008 bytes; sha256
    `60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a`;
    p50 **1400.6 ms = ~2.4x DWPose** — REFUSED on the CPU budget bar
    (the best raw IoU, 0.9089, does not buy the budget miss).
  - `MODNet` (portrait matting) — weights CC BY-NC 4.0 (code open,
    weights non-commercial per the repo README) — NOT ADOPTABLE for an
    MIT project; not downloaded.
  - `RobustVideoMatting` — code GPL-3.0, weights CC BY-NC 4.0 — NOT
    ADOPTABLE; not downloaded.
  - `PP-HumanSeg` (PaddleSeg, Apache-2.0) — license fine; NO first-party
    ONNX artifact exists (official weights are Paddle-format on
    bcebos; every ONNX is a third-party conversion — the D-024
    provenance shape) — NOT ADOPTABLE as-is.
  - `MediaPipe selfie segmenter` (Apache-2.0) — official artifact is
    TFLite-only; ONNX exists only as third-party conversions — the
    same provenance shape.
  - `YOLOv8/YOLO11-seg` — AGPL-3.0 — NOT ADOPTABLE.
  - `BiRefNet` (MIT, code+weights) — ONNX class 224 MB–1 GB;
    UNMEASURED: larger than the adopted candidate on every axis (bytes,
    latency class); the scan stops at the first clean pass and records
    why. Reopens only if the adopted model misses a future bar.
  - SAM/MobileSAM — promptable matting (wrong product class: needs
    prompts the pipeline does not have); ViT-class CPU budget out of
    the declared envelope; not measured.
- **Scope of this adoption**: `u2net.onnx` is the SEGMENTATION pass
  (input-side, the D-019 lines apply unchanged — it segments whatever
  the user's reference contains, it generates nothing). The ADOPTION is
  not a volume CLAIM — volume claims ride P9-2's own bar (Annex A.1:
  silhouette IoU >= 0.85 on the benchmark, visible-view scoped) through
  the design-of-record docs/VOLUME.md and its probe/gate. The manifest
  gains the third entry in the same landing; the manifest-state pin
  (RUX-EST-RITUAL) amends with it. D-018 stays RESERVED.
