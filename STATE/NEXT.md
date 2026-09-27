# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", critic-passed
   9.8/10; Annex A pre-declared bars are LAW): S31 landed P8-6 spine arch
   + roll — L5 + L6 CLOSED: the arch benchmark monotone (0.0000 < 0.0076
   < 0.0084 canon, signs correct, declared-family recovery 0.00000,
   neutral flat no-op byte-identical), FK bars hold through the REAL apply
   (0.0000° worst), D-008's flip accept 18/20 unchanged, the roll fixture
   corrected to bar (uncorrected 53.64° published → corrected, directions
   exact), straight arms bit-identical; D-023 written at the landing.
   The session map says **S32 = P8-7 root motion**: the declared
   coordinated positional upgrade — hips positional track from
   subject-position/scale drift (labeled approximate); the contact model
   becomes root-motion-aware BY DESIGN (design-first, probe, then
   tune-by-measurement with published numbers — never threshold-fitting
   to force plants, the S24 finding stands as the motivation).
   NEVER cut (Annex A cut order): P8-2 coupling and P8-3 visible fingers.

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly). Silent 19 straight sessions so far; the box side is READY
     (the DroidCam client just was never running).
   - **Silent again (20th)** → the P8-7 work order below.

2. **Then read, in order**: STATE/ROADMAP.md P8-7 + Annex A.1/A.2 (the
   root-motion bar: the drift track must beat walk-in-place slide on the
   REAL fixture (Xbot row) by the >= 5x family, else L7 ends REFUSED —
   walk-in-place stays and the treadmill finding remains the published
   truth; the in-place path's prior gate numbers byte-identical),
   docs/SPINE.md + docs/CAMERA.md + docs/SCENES.md § Contact coupling
   (the design→probe→core→gate pattern S32 reuses; the coupling pass is
   what becomes root-motion-aware), docs/MOTION_LIBRARY.md (the treadmill
   finding), STATE/TASKS.md (P8-6 DONE with the full S31 entry),
   STATE/PROGRESS.md (S31 entries), STATE/DECISIONS.md (D-023 WRITTEN;
   D-018 stays reserved), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
   docs/BENCHMARKS.md (the SPINE block + the MOTION block — the Xbot REAL
   row S32 revisits), docs/POLICY.md (D-019 unchanged — root motion
   carries no content), and the claim-bearing surfaces docs/LAUNCH.md +
   docs/TUTORIALS.md (one grep sweep together IF a number changes).
   Register as **Session 32**, claim P8-7 with [S32]; PROGRESS stamps via
   `date -u` read IMMEDIATELY before every append, then verify the stamp
   (S31 caught + corrected a FUTURE-stamped S30 entry — the S25 hazard
   class is alive).

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**568 expected** — S31 added 19 spine contract tests)
   + `make lint PY=/home/potato/miniconda3/bin/python3`, and `gh run
   list --branch main` (the S31 push is the newest; if red: download the
   log, root-cause, fix the real substance FIRST).

## S32 work order — P8-7 Root motion (the treadmill fix)

Design → probe → build → gate, in that order (NON-NEGOTIABLE). The
pattern is proven six times over (coupling, fingers, face, camera,
spine-arch, roll): design page first, probe with REAL rows, core lift,
sibling gate file.

1. **DESIGN-FIRST**: open docs/ROOT_MOTION.md (the SPINE.md sibling
   pattern) — the hips POSITIONAL track from subject-position/scale drift
   (labeled approximate): how the per-frame subject drift (the P2-1 job's
   keypoint stream) converts to a canonical-space hips translation track
   WITHOUT fabricating root motion (D-008's honesty line — the track is
   MEASURED drift, never authored); how the contact model
   (`contacts.py`/`lock_feet`, the certified composition) becomes
   root-motion-aware BY DESIGN (plants detected ON the drifting track —
   the S24 Xbot finding: hips-anchored treadmill glide 0.022–0.19 u/f
   exceeded the D-008-untuned enter bar → 0 plants, lock a verified
   no-op); the regression framing (the >= 5x family vs the status quo);
   the in-place path byte-identity declaration (no drift signal → the
   track is zero → the prior path bit-identical); the REFUSE branch (no
   drift measurable → walk-in-place stays, LOUD).
2. **PROBE-FIRST xtask/root_motion_probe.py** (RM_ROOT lines, grep-tested
   both shapes before push): (a) the synthetic drift fixture — an
   engine-built walking fixture with KNOWN subject drift, the track
   recovers it within a declared bar; (b) the REAL Xbot row re-visited —
   plants detected on the new model, lock >= 5x holds, the translation
   track matches the source drift within measured bars; (c) the in-place
   path's prior gate numbers byte-identical (RM_FOOT_LOCK 0.0371→0.0000,
   RM_MOTION 44997x, RM_BAKE 0.0242° x2 untouched); (d) REFUSE classes —
   no-drift/no-person streams stay loud; (e) DETERM twins.
3. **Core**: the drift track + the root-motion-aware contact pass as
   additive pure-core modules (the spine.py pattern); consumers that
   ignore them stay byte-identical; NO payload format change.
4. **Gate**: xtask/root_motion_gate.py (the sibling file per the Mimosa
   workaround, RM_ROOT rows wired into verify_pose_apply.sh + the
   Makefile lint list): the bars above + twin byte-identity + all prior
   numbers byte-identical.
5. **Early-finish option**: the S31 declared-open CLI/addon invocation
   wiring for the arch/roll passes (measured work only — the passes
   exist and are gate-exercised; wiring them into `rigpose pose` /
   the addon apply flow is a user-facing change needing its own
   byte-identity argument), or the P8-2 pin-suggestion inference as desk
   DATA.

**S31's contract facts S32 builds on** (do not re-learn):

- The probe→core lift pattern works six times over (coupling_probe/
  finger_probe/face_probe/camera_probe/spine_probe are the recipes; the
  SPINE gate lives in verify_pose_apply.sh — grep-tested both shapes).
- The additive-field contract: omit-when-empty byte-identity pinned by
  test (hands/face/roll); readers tolerate absence. NO payload format
  change landed in S31 either — keep it that way for the drift track
  (it rides the ACTION, not the pose).
- The gate env trap (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  grab the broken apt 4.0.2).
- The two-pass fixture-builder rule; place-update-then-measure
  (view_layer.update() BEFORE any world-space read — it fired AGAIN in
  S31's gate); mathutils rich-compare through nested containers is FLAKY
  in 5.1 (a wrong False AND a segfault) — compare plain-float tuples;
  PROGRESS stamps are REAL UTC (S31 caught a future-stamped entry).
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  in-place edits to existing gate/probe files can trip path-traversal
  FPs — a NEW sibling file scans clean (couple_gate/finger_gate/
  face_gate/camera_gate/spine_gate precedent); expect the pagedoc.py
  import-struct FP at every commit; -F commit-message files for
  heredoc-sensitive text.
- STATE stamps are REAL UTC, read-then-write-then-verify.

## Blocked / deferred (parked — do not burn time)

- Live capture device — parked LAST by LO; P5-4 runs when the phone comes
  up (box side READY; the client just never ran).
- PyPI description + Blender Extensions upload — LO's site-side steps
  (deferred to his final session by LO).
- P6-3 public benchmark suite packaging — roadmap-slack work.
- P6-2a `retarget_clip` session action — the refactor half is DONE; the
  executor wiring is roadmap-slack work.
- P1-8a fallback estimator — parked (D-011/D-012) until P8-9.
- Windowed Blender GL stability — best-effort only, never staged.
- Detector-visible mannequin fixtures (the P8-5 tier-2 path) — NOT MET
  with evidence (the pinned DWPose is blind to the engine's mannequin
  class, 0/36 across three fixture generations); reopened only if a
  detector-visible engine-built fixture path exists (the A.3
  re-validation trigger).
