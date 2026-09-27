# SESSION 32 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes landed (P8-1): one
payload poses N paired rigs in one action, pins carried as data, a camera
stages from the reference framing. Contact coupling landed (P8-2): AUTHORED
pins close deterministically, suggested/below-floor pins stay loud data.
Fingers landed (P8-3): the D-021 additive namespace solves per-finger
chains ONLY from observed hand keypoints — below the 0.55 floor a finger
is skipped + LEDGERED, never guessed. Facials landed (P8-4): the D-022
facial parameter namespace — 10 dimensionless expression params solved
ONLY from observed face landmarks through the PUBLISHED table, the
MEASURED side map, per-param gates + ledgers, gaze conditional-OUT, the
two-class apply. The MEASURED camera landed (P8-5): yaw/pitch/distance/
height fitted from the body keypoints, GT bars met with margin, BOTH
floors gate the staging, CAM-MODEL matches Blender at 2.32e-07; tier-2
render+detector NOT MET with evidence (published, never relabeled). Spine
arch + roll landed (P8-6): the ARCH distributes the observed hips→
shoulders→head misalignment across the spine chain (the A1 Hermite, gain-2
tangents, the head-axis half-angle recovery) — monotone benchmark, FK bars
hold through the REAL apply, D-008's 18/20 flip accept unchanged, the
neutral flat no-op byte-identical; the ROLL solve corrects the forearm's
frame split via the D-023 additive namespace — the fixture corrected to
bar (uncorrected 53.64° published), straight arms BIT-IDENTICAL. Toon
renders, manga pages. Live pose-stream puppeteering on the replay path.
No cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** V1 = Phase
8 complete + the Scene Test scorecard green (target S35; Annex A.3: the
scorecard overrides the calendar). S31 landed P8-6 (L5 + L6 CLOSED).
**S32's rock is P8-7 root motion (the treadmill fix)**: the declared
coordinated positional upgrade — hips positional track from subject-
position/scale drift (labeled approximate); the contact model becomes
root-motion-aware BY DESIGN (design-first, probe, then tune-by-
measurement with published numbers — never threshold-fitting to force
plants, the S24 finding stands as the motivation); **bars: the drift
track must beat walk-in-place slide on the REAL fixture (Xbot row) by
the >= 5x family, else L7 ends REFUSED (walk-in-place stays, the
treadmill finding remains the published truth); the in-place path's
prior gate numbers byte-identical**; refusal branch (Annex A.2): see the
regression bar above — REFUSED means the walk-in-place status quo ships
and the ledger row says so with evidence. NEVER cut P8-3 visible fingers
or P8-2 coupling (Annex A cut order).

## S31 contract facts (what S32 builds on)

- **P8-6 LANDED** (full entry in TASKS.md; numbers in BENCHMARKS SPINE
  block): design-first docs/SPINE.md (the CAMERA.md sibling; ONE
  probe-earned amendment A1 — the Hermite tangent record: T0 = the chord
  counter-bowed, the -phi/+phi splay bows AWAY from the head tip
  (h11 <= 0; h10+h11 = t(1-t)(2t-1)), and the DECLARED form is T0 = the
  chord rotated by gain 2*phi toward the head side, T1 = the head axis —
  the physical C-bow; a constant-curvature arc is FORCED into the splay
  family and is documented as the rejected alternative). The ARCH rides
  the SOLVED POSITIONS (the coupling write-back class — no payload
  format change); the head axis is recovered EXACTLY from the stored
  derived head placement via the half-angle inverse theta = 2*atan2(v_x,
  v_z) (the CAMERA.md A3 identity reused). The ROLL rides the D-023
  additive namespace (CanonicalPose.roll, omit-when-empty byte identity,
  mirrored swaps sides + negates the twist) consumed by fk_apply as a
  twist ABOUT the target axis.
- **Core `spine.py`**: solve_spine_arch + solve_arm_roll + roll_correction
  + head_axis_in_plane; a not-applied pass returns the INPUT pose
  UNCHANGED (the ledger lives in the returned report, never in
  pose.notes — skipped/refused = byte-identical); **19 tests in
  test_spine.py = 568 total.**
- **Gate `xtask/spine_gate.py`** (5 RM_SPINE rows through the REAL addon
  apply via pose_apply.apply_payload, wired into verify_pose_apply.sh +
  the Makefile lint list): SPINE-ARCH monotone + signs + recovery +
  flat-no-op + apply worst 0.0000 deg; SPINE-FLIPS 18/20 byte-equal;
  SPINE-ROLL uncorrected 53.64 deg published / Blender-measured applied
  twist 53.64 deg IN MAGNITUDE (the sign is a Blender bone-frame
  convention; the signed twist lives core-side) / direction fidelity
  0.0000 deg both paths; SPINE-STRAIGHT no entries + apply rotations
  byte-identical; SPINE-TWIN byte-identical (19 bone matrices).
- **NOT landed (declared)**: the CLI/addon invocation wiring for the
  arch/roll passes (the S31 work order's unit boundary was the pure core
  + the REAL-apply gate; the payload-carrying-roll apply needs no addon
  change since poses build through CanonicalPose.from_dict). This is
  S32's early-finish option or a Scene-Test integration decision.
- **Gate env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- **Instrument lessons (S31, do not re-learn)**: the Blender stale-matrix
  lesson fired AGAIN (view_layer.update() BEFORE any pb.matrix read —
  stale zero columns divide by zero); mathutils rich-compare through
  nested containers is FLAKY in 5.1 (a wrong False AND a segfault in
  PyObject_RichCompare — compare plain-float tuples only); a
  FUTURE-STAMPED S30 PROGRESS entry was caught + corrected (the S25
  hazard class — stamp with `date -u` read immediately before append).
- **549 → expect ~568+ tests** (S31 added 19 spine contract tests); CI
  GREEN through the S31 pushes (checked at close; appended in PROGRESS).
  All gate numbers through S31 byte-identical (RM_BAKE 0.0242° ×2,
  RM_FOOT_LOCK 0.0371→0.0000, RM_TAILS, RM_MOTION, RM_SCENE
  0.3388/0.8279, RM_COUPLE 0.00016/0.00035, RM_FINGER
  0.0070°/0.00°/10.30°, RM_FACE 6 rows, RM_CAM 6 rows, RM_SPINE 5 rows).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-7 work order below.
- Silent (20th): proceed with P8-7 directly.
- Then read, in order: STATE/ROADMAP.md (P8-7 + Annex A.1/A.2 — the bars
  are law: the drift track must beat walk-in-place slide on the REAL
  fixture (Xbot row) by the >= 5x family, else L7 ends REFUSED; the
  in-place path's prior gate numbers byte-identical), docs/SPINE.md +
  docs/CAMERA.md + docs/SCENES.md § Contact coupling (the design→probe→
  core→gate pattern; the coupling pass is what becomes root-motion-
  aware), docs/MOTION_LIBRARY.md (the treadmill finding), STATE/NEXT.md,
  STATE/TASKS.md (claim P8-7 with [S32]), STATE/PROGRESS.md (S31
  entries), STATE/DECISIONS.md (D-023 WRITTEN; D-018 stays reserved),
  STATE/CONVENTIONS.md, STATE/SESSIONS.md, docs/BENCHMARKS.md (the
  SPINE block + the MOTION block — the Xbot REAL row S32 revisits),
  docs/POLICY.md (D-019 unchanged — root motion carries no content), and
  the claim-bearing surfaces docs/LAUNCH.md + docs/TUTORIALS.md (one
  grep sweep together IF a number changes).
- Register as Session 32 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**568 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S31 discipline).

## S32 work order — P8-7 Root motion

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST**: open docs/ROOT_MOTION.md (the SPINE.md sibling
   pattern — never a fork): the hips POSITIONAL track from subject-
   position/scale drift (labeled approximate; MEASURED drift, never
   authored root motion — D-008's honesty line); the root-motion-aware
   contact model (plants detected ON the drifting track — the S24 Xbot
   finding: hips-anchored treadmill glide 0.022–0.19 u/f exceeded the
   D-008-untuned enter bar → 0 plants, lock a verified no-op); the
   regression framing (the >= 5x family vs the walk-in-place status
   quo); the in-place path byte-identity declaration (no drift signal →
   the track is zero → the prior path bit-identical); the REFUSE branch
   (no drift measurable → walk-in-place stays, LOUD).
2. **PROBE-FIRST xtask/root_motion_probe.py** (RM_ROOT lines, grep-tested
   both shapes before push): (a) the synthetic drift fixture — an
   engine-built walking fixture with KNOWN subject drift, the track
   recovers it within a declared bar; (b) the REAL Xbot row re-visited —
   plants detected on the new model, lock >= 5x holds, the translation
   track matches the source drift within measured bars; (c) the in-place
   path's prior gate numbers byte-identical (RM_FOOT_LOCK
   0.0371→0.0000, RM_MOTION 44997x, RM_BAKE 0.0242° x2 untouched);
   (d) REFUSE classes — no-drift/no-person streams stay loud; (e) DETERM
   twins.
3. **Core**: the drift track + the root-motion-aware contact pass as
   additive pure-core modules (the spine.py pattern); consumers that
   ignore them stay byte-identical; NO payload format change (the track
   rides the ACTION, not the pose).
4. **Gate**: `xtask/root_motion_gate.py` (the sibling file per the
   Mimosa workaround, RM_ROOT rows wired into verify_pose_apply.sh + the
   Makefile lint list): the bars above + twin byte-identity + all prior
   numbers byte-identical.
5. **If early**: the S31 declared-open CLI/addon invocation wiring for
   the arch/roll passes (measured work only — a user-facing change
   needing its own byte-identity argument), or the P8-2 pin-suggestion
   inference (keypoint proximity) as desk DATA — measured work only,
   never auto-enforced.

Definition of S32 failure (name it, avoid it): a prose root-motion claim
without a benchmark number, a drift track that fabricates motion the
keypoints never showed, an in-place pose/action that moves a single byte,
a touched frozen-role set / D-021 / D-022 / D-023 namespace, a face-free
or hands-free payload byte change, or ANY claim without a test/gate
citation. Anything 80% done is 0% shipped — park cleanly at a unit
boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored; every inferred thing carries confidence + residual); park
  criteria (two stalled probe/gate cycles → park with evidence,
  reorder); the cut order (P8-9 time-to-fix → P8-6 roll (LANDED) →
  NEVER P8-2/P8-3); policy D-019 across new surfaces (MCP stays SFW,
  test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- STATE stamps: real UTC, read-then-write-then-verify (S31 caught a
  future-stamped entry — the S25 hazard class is alive).
- Mimosa: bash writes of source files blocked — Write/Edit; new sibling
  FILES scan clean where in-place edits trip path FPs (couple_gate.py /
  finger_gate.py / face_gate.py / camera_gate.py / spine_gate.py
  precedent); expect the pagedoc.py import-struct FP at every commit;
  heredoc/append FPs when text names source files — Edit tool + -F
  commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson (pb.matrix.to_translation()),
  joint-angle keying, factory-EMPTY FBX scenes, rotation modes before
  quaternion writes (rotation_mode BEFORE rotation_quaternion!), the
  two-pass fixture-builder rule, place-update-then-measure (view_layer
  .update() BEFORE any world-space read — fired AGAIN in S31), the
  wrist-is-body-kp-9 lesson, the girdle-kps-are-rulers fixture law,
  mathutils nested rich-compare FLAKY in 5.1 (plain-float tuples only) —
  the S15..S31 facts in SESSION31_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S33 =
P8-8 multi-character video → scene animation per the session map, UNLESS
a park/reorder happened (say which and why); write STATE/SESSION33_PROMPT.md
in this pattern (contract facts, STEP 0, the P8-8 work order with its
Annex bars: identity swap rate <= 2% of frames on the synthetic fixture,
swap alarm catching >= 90% of actual swaps, per-frame scene bake cost
measured on the mid-laptop baseline and PUBLISHED before any claim);
update STATE/SESSIONS.md row; commit + push (routine commits authorized;
keep CI green, fix inline like S12..S31); expect and disclose the Mimosa
pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up). PyPI
description + Blender Extensions upload — LO's site-side steps (his final
session). P6-3 packaging + P6-2a wiring — roadmap slack. P1-8a — P8-9.
Windowed Blender GL stability — best-effort only, never staged.
Detector-visible mannequin fixtures (the P8-5 tier-2 path) — NOT MET with
evidence; reopened only if a detector-visible engine-built fixture path
exists (the A.3 re-validation trigger).
