# ROADMAP — "the Producer" (Phase 8+): from poser to scene engine

Written 2026-09-23 (post-S25 blocker triage, LO-directed), revised after a
two-round adversarial critic pass (round 1: 5.1/10 FAIL — ten strikes
recorded in PROGRESS; this revision answers every strike). The mission
shift: LO poses NSFW multi-character scenes from references — the engine
must COUPLE characters, articulate fingers and faces, solve the reference
camera, and animate SCENES (multiple rigs from one video), not just pose
single humanoids. This roadmap closes every item on the honest-limits
ledger either by building it or by a deliberate, documented refusal.

Discipline unchanged (CONVENTIONS + DECISIONS): probe-first, design-first,
D-008 (measure/publish, never fit), D-003/D-009 boundaries, honest claims
cite a test/gate, synthetic stays labeled, STATE append-only, ruff+pytest
green, media rule, determinism everywhere, errors actionable, park
cleanly where a session runs out.

NOTE ON CRITIQUE PROVENANCE: this roadmap has been through FOUR
adversarial rounds (round 4 by a second independent fresh-subagent critic,
cold, post-annex) — round 1 (in-session author-critic, 5.1 FAIL, ten
strikes), round 2 (the revision, 9.8 self-scored), round 3 (an
INDEPENDENT fresh-subagent critic, 6.8 FAIL, thirteen strikes S1–S13
recorded in PROGRESS). Annex A below is the round-3 resolution set:
pre-declared numeric bars, refuse branches, precedence rules. A fresh
critic re-scores after annex A; the score lives in PROGRESS, not here.

## The ledger this roadmap closes (things the engine will NOT do today)

| # | today's honest limit | closes in |
|---|---|---|
| L1 | multi-figure = independent pasted poses; no contact | P8-2 |
| L2 | no fingers (DWPose hand kps detected, unused) | P8-3 |
| L3 | no face/expressions (68 face kps detected, unused) | P8-4 |
| L4 | reference camera/framing not solved; static scene cameras | P8-1 (v0) + P8-5 |
| L5 | torso = rigid hips->shoulders line (no arch) | P8-6 |
| L6 | roll-free rotations (twisted forearms accepted) | P8-6 |
| L7 | walk-in-place only; no root motion (treadmill finding) | P8-7 |
| L8 | single-character video only (multi-figure labels unstable) | P8-8 |
| L9 | anime detector gap (D-011: P1-8a plan, not built) | P8-9 |
| L10 | review/fix is workable but slow per-fix (perceived quality) | P8-9 |

Every row ends the roadmap CLOSED (built, gate-cited) or REFUSED
(deliberate, documented in DECISIONS; CLOSED may carry the Annex A.2
subtypes CLOSED-LIMITED / CLOSED-v0) — no row may end "unknown".

## Standing constraints on EVERY phase below

- **Frozen-API amendment rule**: the canonical role set is frozen public
  API (P0-02). Any extension lands as a namespaced ADDITIVE map with its
  own format version + a DECISIONS entry **written when the namespace
  code lands — D-021 is RESERVED for the finger/face namespace and is
  not cited as existing until that commit** (round-3 strike S2: a
  decision entry may never be referenced before it is appended).
  Nothing renames, nothing reorders. Payload changes are ADDITIVE fields
  only (v3); unknown-field policy stays ignore-with-note; every payload
  version bump bumps the contract test in the same commit.
- **Honesty law for coupling and cameras**: the engine may ENFORCE what
  the artist AUTHORED (pins) and SUGGEST what it inferred; it never
  presents inferred contact/camera as ground truth. Every inferred thing
  carries confidence + residual; every gate publishes its error bars.
- **Park criteria**: two stalled probe/gate cycles on one unknown → park
  the phase with a NEEDS-HUMAN/NEEDS-DATA note in NEXT.md, reorder the
  queue, never burn the slack on one rock.
- **Policy (D-019) across the whole scene pipeline**: every new
  content-carrying surface (coupled scenes, facials, scene animation)
  checks the existing policy subjects; anything adult-gated rides the
  add-on-preferences enable path; MCP stays SFW permanently (test-pinned).
- **Priority rationale (LO's pain order)**: #1 was "it must do cameras" —
  answered EARLY as P8-1's v0 approximate stage-camera (explicit error
  bars) so camera value ships in session one, with the measured solve in
  P8-5; #2 "not touching = bad" is P8-2, immediately after the casting
  desk; #3 fingers/facials are P8-3/P8-4. Animation from video EXISTS on
  the SYNTHETIC-LABELED path (Phases 2, gate-verified; the real-clip gate
  honestly decomposed per D-015) — P8-8 extends it to scenes; it is not a
  rebuild.

## The phases

### P8-1 CanonicalScene + the casting desk + camera v0 (S26 rock)
- **Core**: `scene.py` — `ScenePose` (N named figures, each a CanonicalPose)
  + `ContactPin` links (figure A role/bone ↔ figure B role/bone, authored
  or suggested), deterministic. Payload v3 ADDITIVE (`figures[]`,
  `pins[]`); v2 readers keep working (back-compat pinned byte-identical).
- **Add-on**: the Casting Desk — one panel listing detected figures ×
  armatures; the artist pairs them (who is who) and applies all in one
  action. Session/MCP: `apply_scene` (v1 additive).
- **Camera v0**: stage a scene camera from the reference's framing via the
  subject bounding box + solve priors — APPROXIMATE, labeled, one button,
  manual keyframing supported from day one (the measured solve is P8-5).
- **Accept**: 2-rig .blend + 2-figure reference -> both posed in one
  operation (per-figure fidelity <= the 0.5 deg family); v2 payloads apply
  byte-identically; camera v0 stages on the benchmark set with published
  framing-error bars (subject bbox IoU) and refuses to stage below the
  confidence floor (loud, never a wrong silent camera).

### P8-2 Contact coupling (the "not touching = bad" fix)
- **Core**: after independent per-figure solves, a COUPLING PASS enforces
  AUTHORED pins: deterministic iterative redistribution over the canonical
  figures. **Conflict rule (fixed in critique)**: pins resolve in authored
  order, weighted by per-role confidence; an over-determined set solves
  least-squares with a keyed iteration order (deterministic); each pin
  reports its residual; unclosable pins stay loud, the solve never moves a
  role to satisfy a pin below its confidence floor.
- **Suggestions vs enforcement**: pins inferred from keypoint proximity are
  SUGGESTIONS the artist confirms in the Casting Desk. Enforcement of
  unsupported contact would be fabrication (D-008) — the line is the
  feature.
- **Accept**: coupled pair (hold-from-behind) reference: pin distance
  < 2% torso span after solve (bar), roles NOT on any pin's dependency
  chain unchanged <= 0.5 deg (chain roles report deviation as pin cost —
  Annex A.1),
  twin-run byte-identical, conflict case (competing pins) documented +
  gated.

### P8-3 Fingers (DWPose already detects them — 21 kps/hand, unused)
- **Canonical additive namespace** (the DECISIONS entry — D-021 — is
  WRITTEN when this code lands, never cited before): per-hand 5 finger chains
  (3 joints each) as `hand.L.finger.<name>[0..2]` in a SEPARATE additive
  map — the frozen 22-role core is untouched; consumers that ignore
  fingers work unchanged.
- **Solve**: fingers solve ONLY from observed kps, per-finger confidence
  gates (occluded finger = skipped + flagged, never guessed — a wrong
  finger reads as broken, an absent one reads as clean).
- **Apply**: finger bones via the preset mapping (authored once per rig);
  a rig without finger targets reports a loud capability line, never a
  silent no-op.
- **Accept**: 20-pose hand benchmark (fist/spread/grip/pinch...):
  per-finger direction correct on observed kps (bar per finger class),
  occlusion gating proven, metarig + Mixamo-class apply <= FK family bar.

### P8-4 Facials (expressions, not identity)
- **Core**: 68 face kps -> a fixed param set with a PUBLISHED
  landmark->param table (critique fix): brow raise = brow-kp row height
  delta; blink = eye aspect ratio vs the subject's open-eye prior; jaw
  open = lower-lip drop vs face height; smile/pout = mouth-corner
  elevation + width ratio; cheeks; **gaze ONLY when the detector variant
  supplies iris kps** (capability probe at detection time — no
  corner-geometry guessing); neutral is a POPULATION prior declared
  D-008-untuned (single images carry no personal neutral).
- **Apply binding, two explicit target classes (loud per rig)**: (a) bones
  via preset mapping (jaw/eye/brow chains), (b) shape keys by documented
  naming convention. Neither present -> "no facial targets" line, never
  silent.
- **Accept**: expression benchmark (10 states: neutral + 9 expressions,
  matching Annex A.1's gate): per-param
  monotonicity bars vs landmarks, apply on a shape-key rig AND a bone-faced
  rig within tolerances, no-target rig honest, param table published in
  docs.
- Rides the D-019 module contract (see standing constraints).

### P8-5 Reference camera solve (measured)
- **Core**: fit an approximate camera (yaw/pitch/distance/height) from
  body kps + the solve's depth assumptions; per-frame for video ->
  a camera track. Underdetermined by nature: claims come from a
  synthetic ground-truth set (KNOWN camera -> render -> re-solve) with
  published error-bar distributions — never prose claims.
- **Low confidence = refuse to stage** (critique fix): below the confidence
  floor the operator reports and stages nothing; a wrong silent camera is
  the trust-killer this phase exists to avoid.
- **Accept**: GT-set yaw/pitch/distance error bars published; framing IoU
  bar on the benchmark; the P4 manga/animatic pipelines gain per-shot
  camera tracks (closes D-017's static-camera note for sourced shots).

### P8-6 Spine arch + roll
- **Spine arch**: when the head is observed, solve a torso arc
  distributing hips->shoulders->head misalignment across spine/chest/neck
  by proportion (new observed-constraint solve; D-008 priors untouched).
  Arched backs stop being flat.
- **Roll**: forearm/upper-arm roll alignment from wrist-vs-elbow landmark
  geometry (the P1-11 declared follow-up), confidence-gated; straight
  arms stay bit-identical (no-op proven).
- **Accept**: arch benchmark (neutral/arched/bow L/R) monotone
  distribution + FK bars hold + D-008's 18/20 flip accept unchanged; roll
  fixture corrects to bar; full battery re-run byte-identical on priors.

### P8-7 Root motion (the treadmill fix)
- **Core**: the declared coordinated positional upgrade — hips positional
  track from subject-position/scale drift (labeled approximate); the
  contact model becomes root-motion-aware BY DESIGN (design-first, probe,
  then tune-by-measurement with published numbers — never threshold-
  fitting to force plants, the S24 finding stands as the motivation).
- **Accept**: the Xbot walk REAL row re-visited: plants detected on the
  new model, lock >= 5x holds, translation track matches source drift
  within measured bars; the in-place path's prior gate numbers
  byte-identical (no regressions).

### P8-8 Multi-character video -> scene animation
- P2-1's job container gains per-frame multi-figure payloads + per-frame
  coupling (P8-2) + fingers/facials (P8-3/4) -> scene actions -> bake BOTH
  rigs in one pass -> the A-and-B animation.
- **Identity stability (critique fix — algorithmic direction committed)**:
  per-frame figure→character assignment by pose-similarity cost matrix,
  solved with a deterministic assignment (Hungarian, keyed order); a cost
  jump between consecutive frames raises a swap alarm; manual per-frame
  override map wins over everything; swap rate MEASURED and published on
  the fixture before any claim.
- **Accept**: two-person synthetic video fixture (deterministic
  renderer): both rigs animate, coupling holds per frame, identity swap
  rate published, honest synthetic labels (real clip only when a licensed
  one exists).

### P8-9 Review UX speedrun + fallback estimator
- Per-finger/per-face/per-pin fix affordances (click a finger, drag the
  direction; pin nudge; per-figure flip) — BAR (round-4 strike 4.1):
  median scripted time-to-fix <= 15 s per flagged defect on the benchmark
  fixture set (click-through measured, published); L10 closes CLOSED only
  at that bar, else REFUSED-with-evidence.
- P1-8a (D-011): the sketch/anime fallback estimator behind the dual-
  estimator interface, no scraped data ever. ADOPTION BAR (strike 4.1 —
  D-011 declared no number): no-person rate <= 1/10 on the anime
  benchmark (vs the measured 3/10, D-012) AND per-image latency <= 2x
  DWPose CPU AND flip-margin parity within the D-010 tolerance on the
  detected set; met -> L9 CLOSED; missed after one candidate -> L9
  REFUSED-with-evidence (the estimator documented as not viable at this
  benchmark n; the dual-estimator INTERFACE remains).

## The Scene Test (what "100% perfect" MEANS — non-circular)

One E2E scenario with a COMPOSITE SCORECARD (critique fix — not "its
stages pass"): a two-character NSFW reference in -> coupled, fingered,
faced, camera-matched two-rig scene out; a two-person reference video in
-> the same scene animated. The scorecard publishes INDEPENDENT
measures per stage — pin residuals (u), per-finger accuracy vs the
fixture's ground truth, per-param expression monotonicity, camera framing
IoU, identity swap rate, FK fidelity — each against its pre-declared bar,
assembled into one table shipped in docs/BENCHMARKS.md. Pass = every
measure green AND every residual limitation is a labeled choice in the
report (skips, unclosable pins, camera error bars), not a surprise.
Perfection = nothing breaks silently, everything measurable is measured,
everything not solved is loud and one click from fixed; the ledger ends
every row CLOSED or REFUSED.

## Session mapping (LO's ~15 estimate vs the honest count)

S26 P8-1 · S27 P8-2 · S28 P8-3 · S29 P8-4 · S30 P8-5 · S31 P8-6 ·
S32 P8-7 · S33 P8-8 · S34 P8-9 · S35 the Scene Test + close-out.
10 planned + up to 5 slack for the discipline's honest overruns (probe
surprises, gate-caught redesigns, real-data findings, parked phases
reordering the queue). LO's 15 is the right envelope. P5-4/the camera
unblocks the live demo whenever the phone comes up — parked last by LO,
structurally independent of this roadmap.

## V1 — the launch gate at S35 (LO-locked)

**V1 ships when the Scene Test scorecard is green** — target S35, and per
Annex A.3 the scorecard overrides the calendar (slack consumes sessions,
never bars): Phase 8 complete, the Scene Test
scorecard green, the ledger fully CLOSED/REFUSED, every gate byte-green,
launch surfaces (README/LAUNCH/TUTORIALS) claiming exactly the scored
reality. Everything below this line is POST-V1 — V1 does not wait for
sculpting or text, and neither delays V1.

## Phase 9 — auto-sculpt: the body matches the reference (post-V1, before text)

LO's feature: hand the engine an image (or video) and the character's
BODY auto-adjusts to match the reference's build — proportions AND
volume — for posing AND animation ("no manual sculpting" is the
user-facing behavior; the artist can still tweak afterward, which is the
perceived-perfection pattern, not a requirement).

**The honest physics first (the phase lives or dies on this)**: body
keypoints give SKELETON positions, not VOLUME. So the feature decomposes:

- **P9-1 Proportion matching (keypoints-only, no new models)**: the solve
  already measures the reference's limb/torso/width ratios — v1 matches
  SKELETON proportions and reports volume as unobservable-from-keypoints.
  Mechanism probe FIRST (the Blender unknown): candidate mechanisms are
  (a) a rig-bound lattice driven by proportion deltas, (b) shape-key
  binding by convention (the P8-4 facial pattern generalized to body
  regions), (c) armature scale-correctives. The probe picks ONE with
  measured deformation quality on the metarig + a Mixamo-class rig;
  rigs without any viable target report loudly (the P8-4 capability
  pattern). SELECTION BAR (round-4 strike 4.3): the mechanism holding the
  5% Annex A.1 bar on BOTH the metarig and a Mixamo-class rig with the
  fewest required rig-side artifacts (tie-break: deterministic
  application — the keyed-sort law of CONVENTIONS, i.e. the candidate name
  ascending breaks equal scores); ALL candidates missing the bar on either rig ends Phase 9
  REFUSED-with-evidence — the reference-proportion REPORT still ships as
  data, the auto-sculpt claim is never made.
- **P9-2 Volume from silhouette (the deliberate third-model decision)**:
  volume (hips/waist/bust/thighs — the NSFW-relevant shapes) is a
  SILHOUETTE property. Getting it needs a segmentation pass = a THIRD
  pinned model, which amends the P6-6 never-list ("no weights beyond the
  two pinned DWPose models"). That amendment is a written DECISIONS entry
  with the model's license, size, checksum pinning, and CPU budget
  measured BEFORE adoption (the mid-laptop law). If the decision is NO,
  the phase ships P9-1 + a documented REFUSED row — never a half-claimed
  volume feature.
- **P9-3 Sculpt + animation**: static sculpt applies once (frame one)
  before animation drives the rig; per-frame soft-tissue dynamics are
  explicitly OUT (that is simulation, a different product).
- **Accept**: a proportions benchmark (heavy/slender/tall references vs
  one base rig): measured ratio deltas after sculpt within bars; volume
  benchmark (if P9-2 adopted): silhouette IoU of sculpted render vs
  reference mask (bar published); every result lands on editable shape
  targets (artist-tweakable is the realism exit); D-008: the estimator's
  priors are declared, never fitted to fixtures.

## Phase 10 — text → pose / text → animation (post-V1, after sculpt)

LO's feature: describe the pose or the animation in words ("she bends
over and looks back at him") and the ENGINE produces it — SFW and NSFW —
and the result must read as **a real person's work, not AI output**.

**The architecture answer (on-brand, no diffusion)**: poses are DATA.
Text never generates pixels — it generates canonical-pose parameters
that the core VALIDATES against the anatomical model (joint limits,
ground contact, balance/center-of-mass, self-intersection approximations),
then the SAME realism stack everything else uses applies it: contact
coupling (P8-2), fingers (P8-3), facials (P8-4), spine arch (P8-6),
secondary motion (P6-1), foot lock (P2-5). "Not AI-looking" is enforced
by construction: diffusion artifacts cannot exist in joint-angle data;
what CAN look fake is implausible data, and the validator + physics
gates exist precisely to refuse it. The realism bar is measured, not
vibed (below).

- **P10-1 The pose parameter contract + the plausibility validator**
  (pure core, model-free): a versioned PoseSpec (per-role rotations +
  balance/contact constraints) and the validator that REFUSES
  anatomically impossible specs with actionable hints. This is the
  foundation everything else binds to — and it is useful even alone
  (hand-authored poses, imported poses).
- **P10-2 Agent-driven posing (zero new models)**: an MCP/session
  surface where the CONNECTED coding agent is the text model — the agent
  emits PoseSpec JSON from the user's description, the core validates,
  the add-on applies. The project's MCP heritage is the v1 text path;
  SFW-only over MCP (D-019 stands, test-pinned), NSFW in the add-on with
  the module enabled.
- **P10-3 The local LLM path (deliberate model decision)**: `rigpose
  text-pose "..."` with a pinned local text model (llama.cpp-class) as
  the no-agent path. Same third-model discipline as P9-2: license,
  checksum, CPU budget measured first (a small model drafting PoseSpec
  drafts is CPU-viable; the validator is the quality gate either way).
  Amendment to the P6-6 never-list or it does not ship.
- **P10-4 Text → animation**: the LLM/agent emits a PoseSpec SEQUENCE
  with timing ("slowly turns, then bends") -> a canonical action (the
  engine already consumes actions — `action_from_poses`) -> the
  certified pipeline (conditioning, contacts, lock, bake) -> the same
  animation artifact a video would have produced. Reuse is the feature.
- **P10-5 The realism pass + the measured bar**: a naturalness layer
  over generated sequences — weight shifts, breathing idle, asymmetry
  injection (LLMs draft symmetric mannequin poses; humans do not hold
  them), timing eases — all deterministic, all D-008-declared. The
  "looks real" metric: a plausibility scorecard (physics checks green +
  motion-variance/timing-distribution measures vs the REAL motion
  fixtures we already gate on) + LO's structured eyeball on a blind
  fixture set (his judgment is the product's north star; the physics
  numbers keep it honest).
- **Accept**: prompt benchmark (20 prompts SFW + 20 NSFW, fixed in-repo
  as text fixtures): validator refuses 100% of an impossible-spec
  red set; generated animations pass the plausibility scorecard bars;
  blind review verdicts recorded honestly (including misses).

## V2 — the second launch gate (target ~S45, LO's "+15" envelope)

Phase 9 + Phase 10 complete, their scorecards green, V1's gates still
byte-green (no regressions), the extended ledger CLOSED/REFUSED.
Session map: S36 P9-1 · S37 P9-2 · S38 P9-3 · S39 sculpt polish ·
S40 P10-1 · S41 P10-2 · S42 P10-3 · S43 P10-4 · S44 P10-5 ·
S45 V2 Scene Test extended (sculpt + text) + launch. 10 planned + 5
slack, same discipline. Between S35 and S36 the V1 launch itself is a
session-sized event (LO owns the announcements; the repo ships the
assets).

## Annex A — round-3 critic resolutions (the pre-declared bars)

A fresh independent critic (6.8/10 FAIL, strikes S1–S13) demanded the
numbers BEFORE execution, refuse branches per ledger row, and precedence
rules. Here they are; a phase that cannot meet its annex bar ends its
ledger row REFUSED, with the measured evidence — never "unknown".

**A.1 Numeric acceptance bars (derivation stated per bar):**

| measure | bar | derivation |
|---|---|---|
| camera v0 stage gate (P8-1) | stage iff subject bbox IoU >= 0.75 vs reference; below -> refuse-to-stage | product framing bar (a looser IoU reads as "wrong shot"); measured per-benchmark in S26 and published WITH the floor derivation in that session's benchmark block (strike S12) |
| camera solve (P8-5) | yaw MAE <= 7.5 deg, pitch MAE <= 5 deg, distance MAE <= 12% on the GT set; framing IoU >= 0.75 | composition-view tolerance: beyond these the framing visibly disagrees with the reference; product bar, not a physics claim |
| fingers (P8-3) | per-finger direction error: median <= 20 deg, p90 <= 35 deg on VISIBLE fingers of the 20-pose benchmark; occlusion fixtures named (hand-behind-back, clenched) must show 100% gated-skip (no guessed finger) | 2D keypoint jitter on re-detect pairs is the noise floor; a 3-joint chain amplifies it ~2x — the bars sit above that floor with margin |
| facials (P8-4) | per-param monotonicity on 10-expression benchmark >= 9/10 per param; bone apply <= 0.5 deg family; shape-key apply: applied-vs-intended param delta <= 0.1 normalized | monotonicity is the perception-relevant property for expressions; the delta bar is one Just-Noticeable-Difference class |
| coupling (P8-2) | pin residual < 2% torso span; roles NOT on any pin's dependency chain unchanged <= 0.5 deg (strike S9 carve-out — chain roles on resolved pins report deviation as pin cost, separately) | the torso-span bar is scale-free like the >= 5x lock family |
| multi-char video (P8-8) | identity swap rate <= 2% of frames on the synthetic fixture, swap alarm catching >= 90% of actual swaps; per-frame scene bake cost measured on the mid-laptop baseline and PUBLISHED before any claim (folded minor) | 2% keeps a 10 s clip under ~15 swapped frames, each alarmed; the cost bar is the P9/P10 model-law applied to compute |
| root motion (P8-7) | the drift track must beat walk-in-place slide on the REAL fixture (Xbot row) by the >= 5x family, else L7 ends REFUSED | regression-framed: the upgrade must beat the status quo it replaces |
| proportions (P9-1) | post-sculpt joint positions within 5% of the segment's length vs intent | one twentieth of a segment is beneath visual notice at posing distance |
| volume (P9-2, if adopted) | single-view silhouette IoU >= 0.85 on the benchmark, scoped to the VISIBLE view (strike S10: single-view volume is underdetermined — front silhouette constrains visible extent; depth comes from width priors, declared D-008) | 0.85 IoU reads as "the same body" at posing distance |
| text poses (P10-1/5) | impossible-spec red set: validator refuses 100%; generated sequences pass the plausibility scorecard on ALL physics checks; <= 4/20 benchmark prompts may need manual touch to pass, else the phase iterates (strike S11: the miss budget is pre-declared);
  two failed iteration cycles end the over-budget classes REFUSED-with-evidence
  (simple-motion prompts ship, the remainder is documented); asymmetry-injection constants are FIXED in the PoseSpec contract before any measurement (no tune-until-passes) | red-set refusal is a hard contract; the miss budget makes "iterate" bounded |

**A.2 Refuse branches (pre-declared, per ledger row):**

Precedence (round-4 strike 4.2): ROW-LOCAL triggers below are SPECIFIC-OVER-
GENERAL — they override the general preamble above. Between a bar and its
refusal trigger lies a bounded repair cycle — DEFAULT one, with row-local
counts overriding where their branches declare more (L1/L3: two redesign
cycles; P10: two iteration cycles — the row-local number always governs);
a final miss of the same bar takes the row-local refusal trigger. No dead
bands: the bar is the repair ENTRY, the branch trigger is the repair EXIT,
and both are numbers.
- L1/P8-2: solve cannot hold the pin bar after two redesign cycles ->
  coupling ships as rigid pin-SNAP only (reported as such), L1 = CLOSED-
  LIMITED, documented in DECISIONS.
- L2/P8-3: a finger class that cannot meet its bar (e.g. permanently
  occluded) -> REFUSED per class, visible-fingers-only ships.
- L3/P8-4: a param below monotonicity bar after two cycles -> REFUSED
  per param (gaze is already conditional on iris kps).
- L4/P8-5: GT-set yaw MAE > 15 deg -> full solve REFUSED; camera v0
  remains, L4 = CLOSED-v0.
- L5/L6/P8-6: arch/roll that cannot hold FK bars -> REFUSED, documented
  as the single-view limit (the D-008 ledger entry updated).
- L7/P8-7: see the regression bar above — REFUSED means walk-in-place
  stays and the treadmill finding remains the published truth.
- L8/P8-8: swap rate > 10% after the repair work -> auto-identity
  REFUSED; manual-assignment mode ships, labeled.
- L9/L10/P8-9: estimator adoption follows the third-model law (strike
  S4: P1-8a IS a third pinned model — it gets the FULL amendment ritual:
  license, checksum, CPU budget, DECISIONS entry; and the training
  boundary is explicit: NO fine-tune in the repo; adopted weights only,
  per the P9-2/P10-3 ritual).
- **Park vs ledger (strike S3): a parked phase produces its evidence and
  its ledger row ends REFUSED-with-evidence — "unknown" is the one
  illegal terminal state. V1's gate reads the ledger, not the calendar.**

**A.3 Precedence + scope rules:**
- **S35/scorecard precedence (strike S8): the scorecard being green
  overrides the session number. S35 is the estimate, not the trigger;
  slack consumes calendar, never bars.**
- **Cut order when slack runs low (strike S7), first cut first:**
  P8-4 gaze (already conditional) -> P8-9 time-to-fix -> P8-5 full solve
  (camera v0 satisfies V1) -> P8-6 roll. NEVER cut: P8-2 coupling and
  P8-3 visible fingers — they are the product's core promise.
- **Synthetic-bar caveat + re-validation trigger (strike S5): every
  synthetic-derived claim ships with the optimism caveat verbatim; the
  trigger: any real reference/video fixture entering the workflow
  re-runs the owning bar before dependent claims ship.**
- **Scene Test fixtures (strike S6): engine-rendered couple fixtures
  (the pipeline's own deterministic renderer, clothed and unclothed
  mannequins) — NO external NSFW sourcing exists or is needed; LO-authored
  explicit references stay LOCAL, never committed (policy law). The SFW
  fallback fixture is the same renderer, clothed.**
- **Text-feature path matrix (strike S13): NSFW text-to-pose paths =
  the add-on's connected agent OR the P10-3 local model, both with the
  18+ module enabled in the add-on; MCP stays SFW permanently (D-019,
  test-pinned). SFW exists on all three paths.**
- **P10-5 review integrity (strike S11): the blind fixture review adds
  one non-author reviewer per round (a fresh subagent critic, the same
  rule LO set for this roadmap); LO's verdicts are recorded with the
  reviewer's, misses included.**
