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
(deliberate, documented in DECISIONS) — no row may end "unknown".

## Standing constraints on EVERY phase below

- **Frozen-API amendment rule**: the canonical role set is frozen public
  API (P0-02). Any extension lands as a namespaced ADDITIVE map with its
  own format version + a DECISIONS entry (D-021 covers the finger/face
  namespace); nothing renames, nothing reorders. Payload changes are
  ADDITIVE fields only (v3); unknown-field policy stays ignore-with-note;
  every payload version bump bumps the contract test in the same commit.
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
  desk; #3 fingers/facials are P8-3/P8-4. Animation from video EXISTS
  (Phases 2, gate-verified) — P8-8 extends it to scenes, it is not a
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
  < 2% torso span after solve (bar), unpinned roles unchanged <= 0.5 deg,
  twin-run byte-identical, conflict case (competing pins) documented +
  gated.

### P8-3 Fingers (DWPose already detects them — 21 kps/hand, unused)
- **Canonical additive namespace (D-021)**: per-hand 5 finger chains
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
- **Accept**: expression benchmark (neutral + 8 expressions): per-param
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
  direction; pin nudge; per-figure flip) — manual polish measured in
  seconds on the benchmark (time-to-fix published).
- P1-8a (D-011): the sketch/anime fallback estimator behind the dual-
  estimator interface, gated on the existing benchmark, no scraped data
  ever.

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
