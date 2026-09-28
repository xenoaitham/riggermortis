# SESSION 36 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes (P8-1), contact
coupling (P8-2), fingers (P8-3), facials (P8-4), the MEASURED camera
(P8-5), spine arch + roll (P8-6), root motion as gated additive core with
L7 REFUSED-with-evidence (P8-7), scene animation (P8-8: swap 0.0000),
review fix affordances (P8-9: L10 CLOSED, L9 REFUSED-with-evidence), and
**THE SCENE TEST (P8-10) GREEN — the composite scorecard measured every
stage independently against its pre-declared Annex A.1 bar (pin residual
frac 0.000174, fingers 0.00°/10.30°, face 0 violations/reach 1.00,
framing IoU 0.8630, swap 0.0000 + alarm 2/2, FK 0.0000° — 11/11 RST rows,
twins byte-identical) → V1's launch gate is MET and the honest-limits
ledger is fully CLOSED/REFUSED**. V1's launch announcement itself is a
session-sized event LO owns; the repo ships the scored surfaces.
**Phase 9 opens (post-V1, pre-text): auto-sculpt — the body matches the
reference.** Toon renders, manga pages. Live pose-stream puppeteering on
the replay path. No cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** Phase 9 =
auto-sculpt, and it lives or dies on the honest physics: body keypoints
give SKELETON positions, not VOLUME. **S36's rock is P9-1 proportion
auto-sculpt — the MECHANISM PROBE FIRST**: candidates are (a) a rig-bound
lattice driven by proportion deltas, (b) shape-key binding by convention
(the P8-4 facial pattern generalized to body regions), (c) armature
scale-correctives. The probe measures deformation quality on the metarig
AND a Mixamo-class rig; SELECTION BAR (Annex A.1): the mechanism holding
the 5% bar on BOTH rigs with the fewest required rig-side artifacts
(tie-break: candidate name ascending — the keyed-sort law); ALL
candidates missing the bar on either rig ends Phase 9
REFUSED-with-evidence — the reference-proportion REPORT still ships as
data, the auto-sculpt claim is never made. NEVER cut P8-2 coupling or
P8-3 visible fingers (Annex A cut order).

## S35 contract facts (what S36 builds on)

- **P8-10 LANDED, the scorecard GREEN, V1's gate MET** (full entry in
  TASKS.md; numbers + the labeled choices in BENCHMARKS.md SCENE TEST;
  design + amendments A1–A3 in docs/SCENE_TEST.md): the scenario is the
  compact arm-in-arm couple (two canonical-class fixtures 0.78 u apart,
  ONE authored elbow pin, hands from observed kps, the LEVEL FRONTAL
  camera class at D = 6). The scorecard gate runs inside `make
  pose-verify` (the RST grep rows after the RM_RUX block, both shapes
  tested) and standalone via `make scene-test`.
- **Gate-earned fixture lessons (S35, do not re-learn)**: the staging
  instrument's subject cloud is ALL pose-bone heads — the canonical-class
  fixture is the honest kp-set match, and the scale pairing
  (`dist = consensus_distance × rig_torso/0.45`) is LOAD-BEARING (the
  1/0.55-class fixture staged ~25% close); wide two-figure spreads put
  figures off-axis where the perspective KEYSTONE fakes a depth gradient
  past the solve's vertical-regime switch (the consensus pitch clamped at
  +4.31° = asin(0.15)/2 on a level fixture — the A8 fixture law: the
  fixture was wrong); at yaw ≠ 0 the two-figure parallax puts the
  per-figure solo pitch solves on OPPOSITE sides (each within its
  published MAE; the consensus mean misses); the STATIC scene path
  carries the arrangement in the ARTIST'S rig placement — never from
  bboxes (the bbox-staged placement is the P8-8 stream path); rigs built
  at the same origin superimpose (subject span 0.25 u, IoU 0.23).
- **The scorecard composes, it does not re-derive**: class instruments
  are imported (ONE fixture copy — the motion_fixture rule): finger_gate's
  benchmark machinery, face_gate's, scene_anim_probe's stream. Reusing a
  class instrument must REPRODUCE its published numbers byte-identically
  (they did). A canonical-vs-world raw-direction comparison is INVALID
  (the solve's canonical frame is yawed/scaled by design) — dropped from
  the scorecard for that reason.
- **NOT landed (declared)**: scene-animation session/MCP wiring (S33
  follow-up); the S31 CLI/addon invocation wiring; the root-motion BAKE;
  real-detector-stream validation (the A.1 re-validation trigger);
  viewport drag-gizmo polish (the operators ARE the interactive surface).
- **Gate env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- **Instrument lessons (standing)**: Blender masks crashed scripts with
  exit 0 — grep the FINAL row (`RST GATE: PASS` for the Scene Test);
  place-update-then-measure; mathutils nested rich-compare FLAKY in 5.1
  (plain-float tuples only); the session DATE is the UTC date (`date -u`).
- **634 → expect 650+ tests** (S36 adds its own); CI GREEN through the
  S35 pushes (checked at close; appended in PROGRESS). All gate numbers
  through S35 byte-identical (RM_BAKE 0.0242° ×2, RM_FOOT_LOCK
  0.0371→0.0000, RM_MOTION 44997x, RM_SCENE 0.3388/0.8279, RM_COUPLE
  0.00016/0.00035, RM_FINGER 0.0070°/0.00°/10.30°, RM_FACE 6 rows,
  RM_CAM 6 rows, RM_SPINE 5 rows, RM_ROOT 11 grep rows, RM_SANIM 10
  grep rows, RM_RUX 10 rows, RST 12 rows incl. GATE).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P9-1 work order below.
- Silent (24th): proceed with P9-1 directly.
- Then read, in order: STATE/ROADMAP.md (Phase 9 — the honest physics,
  the P9-1 selection bar, P9-2's third-model decision, Annex A), 
  docs/SCENE_TEST.md (the V1 gate's design of record — the newest
  sibling pattern), docs/FACE.md (the shape-key binding precedent P9-1's
  candidate (b) generalizes), docs/SPINE.md + core/spine.py (the
  positions-surgery class candidate (c) rides), STATE/NEXT.md,
  STATE/TASKS.md (claim P9-1 with [S36]), STATE/PROGRESS.md (S35
  entries), STATE/DECISIONS.md (the ledger state; D-018 stays reserved),
  STATE/CONVENTIONS.md, STATE/SESSIONS.md, docs/BENCHMARKS.md (the SCENE
  TEST block — the scorecard that must stay green), docs/POLICY.md
  (D-019), and the claim-bearing surfaces README + docs/LAUNCH.md +
  docs/TUTORIALS.md (one grep sweep together IF a number changes).
- Register as Session 36 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**634 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S35 discipline).

## S36 work order — P9-1 proportion auto-sculpt (the mechanism probe)

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST**: open docs/AUTO_SCULPT.md (the SCENE_TEST.md
   sibling): the honest physics verbatim (keypoints give SKELETON, not
   VOLUME — v1 matches SKELETON proportions, volume is
   unobservable-from-keypoints and is P9-2's separate third-model
   decision); the three candidate mechanisms with their declared
   deformation-quality instruments; the SELECTION BAR verbatim (5% on
   metarig + Mixamo-class, fewest rig-side artifacts, name-ascending
   tie-break); the REFUSED branch (all fail → the proportion REPORT
   ships as data, the auto-sculpt claim is never made); NO payload
   format change; any new pose field is additive with its DECISIONS
   entry WRITTEN at the landing (D-025 is the next free number).
2. **PROBE-FIRST xtask/auto_sculpt_probe.py** (RM_ASCULPT rows,
   grep-tested both shapes before push): implement all THREE candidate
   mechanisms as probe-local pure functions first; author the proportions
   benchmark fixture set (heavy/slender/tall reference-class skeletons
   vs one base rig, prior-consistent GT, SYNTHETIC-labeled); MEASURE
   post-sculpt joint positions vs intent per mechanism per rig; the
   fewest-artifact count; the tie-break; DETERM twins.
3. **Core + apply**: ONLY the selected mechanism lands as core (the
   probe's winning function, productionized); rigs without a viable
   target report loudly (the P8-4 capability pattern); the proportion
   REPORT (the measured deltas) ships as data regardless.
4. **Gate**: xtask/auto_sculpt_gate.py (the sibling file per the Mimosa
   workaround) wired into verify_pose_apply.sh + the Makefile lint list:
   the 5% bar on BOTH rig classes + all prior numbers byte-identical
   (incl. the S35 RST rows — the Scene Test must stay green).
5. **If early**: the declared wiring items (scene-animation session/MCP
   wiring; the S31 CLI/addon invocation wiring) — measured work only,
   each needs its own gate rows.

Definition of S36 failure (name it, avoid it): a mechanism claim without
a measured deformation number on BOTH rig classes, a selection made on
vibes instead of the fewest-artifact rule, a volume claim (P9-2's
decision, not P9-1's), an auto-sculpt claim after a REFUSED branch, a
touched frozen-role set / D-021 / D-022 / D-023 namespace, or ANY claim
without a test/gate citation. Anything 80% done is 0% shipped — park
cleanly at a unit boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored; every inferred thing carries confidence + residual); park
  criteria (two stalled probe/gate cycles → park with evidence,
  reorder); the cut order (NEVER P8-2/P8-3); policy D-019 across new
  surfaces (MCP stays SFW, test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap (above).
- STATE stamps: real UTC, read-then-write-then-verify; the session date
  is the UTC date.
- Mimosa: bash writes of source files blocked — Write/Edit; the scanner
  blocks env-sourced path-write shapes in gate scripts (zero-IO gates
  are the proven shape); new sibling FILES scan clean where in-place
  edits trip path FPs (couple_gate.py / finger_gate.py / face_gate.py /
  camera_gate.py / spine_gate.py / root_motion_gate.py / scene_anim_gate.py
  / review_ux_gate.py precedent); expect the pagedoc.py import-struct FP
  at every commit; heredoc/append FPs when text names source files —
  Edit tool + -F commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson (pb.matrix.to_translation()),
  joint-angle keying, factory-EMPTY FBX scenes, rotation modes before
  quaternion writes, the two-pass fixture-builder rule,
  place-update-then-measure, the wrist-is-body-kp-9 lesson, the
  girdle-kps-are-rulers fixture law, mathutils nested rich-compare FLAKY
  in 5.1 (plain-float tuples only), the operator return/poll/ERROR-report
  classes, the S35 fixture lessons (the subject cloud, the scale pairing,
  the keystone clamp, the placement law) — the S15..S35 facts in
  SESSION35_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S37 =
P9-2 the volume decision (the third-model ritual: license, checksum, CPU
budget on the mid-laptop baseline BEFORE adoption, the DECISIONS entry;
REFUSED path ships P9-1 + the documented refusal) per the session map,
UNLESS P9-1 ended REFUSED-with-evidence (then S37 = P10-1 the PoseSpec +
plausibility validator — Phase 9's remainder is the documented refusal,
Phase 10 does not wait for it) or a park/reorder happened (say which and
why); write STATE/SESSION37_PROMPT.md in this pattern (contract facts,
STEP 0, the next work order); update STATE/SESSIONS.md row; commit +
push (routine commits authorized; keep CI green, fix inline like
S12..S35); expect and disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up; silent 23
straight sessions through S35). PyPI description + Blender Extensions
upload — LO's site-side steps (his final session). P6-3 packaging +
P6-2a wiring — roadmap slack. Windowed Blender GL stability —
best-effort only, never staged. Detector-visible mannequin fixtures (the
P8-5 tier-2 path) — NOT MET with evidence; reopened only if a
detector-visible engine-built fixture path exists. Root-motion BAKE —
revisit only when a real root-motion source exists. Scene-animation
session/MCP wiring — declared S33 follow-up (needs its own gate rows).
The anime fallback estimator — REFUSED-with-evidence (D-024); reopened
only through the full P1-1 third-model ritual with a real candidate.
