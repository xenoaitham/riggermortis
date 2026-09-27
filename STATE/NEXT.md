# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", critic-passed
   9.8/10; Annex A pre-declared bars are LAW): S32 landed P8-7 root motion
   — **L7 = REFUSED-with-evidence** (the Annex A.2 branch, exercised for
   the first time): the drift track + the root-motion-aware contact model
   LANDED as gated additive core (probe 7/7 + gate 8/8 RM_ROOT; the >= 5x
   family demonstrated at 46351.9x on the drift GT class), but the
   pre-declared bar's REAL fixture (the Xbot walk row) measurably carries
   NO root motion on any of the glb's seven clips — the S24 "Mixamo ROOT
   MOTION" attribution was CORRECTED (the glide is the in-place cycle's
   own leg kinematics), so the bar is unmeetable BY THE FILE'S CONTENT
   and walk-in-place ships. The session map says **S33 = P8-8
   multi-character video → scene animation** (no park/reorder happened —
   the refusal branch is the phase's own pre-declared terminal, not a
   reorder). NEVER cut (Annex A cut order): P8-2 coupling and P8-3
   visible fingers.

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly). Silent 20 straight sessions so far; the box side is READY
     (the DroidCam client just was never running).
   - **Silent again (21st)** → the P8-8 work order below.

2. **Then read, in order**: STATE/ROADMAP.md P8-8 + Annex A.1/A.2 (the
   P8-8 bars: identity swap rate <= 2% of frames on the synthetic
   fixture, swap alarm catching >= 90% of actual swaps, per-frame scene
   bake cost MEASURED on the mid-laptop baseline and PUBLISHED before
   any claim; the A.2 branch: swap rate > 10% after the repair work →
   auto-identity REFUSED, manual-assignment mode ships labeled),
   docs/SCENES.md (the CanonicalScene + the coupling pass S33 extends),
   docs/ROOT_MOTION.md (S32's as-built — the per-frame scene path may
   carry the drift track per figure), docs/MOTION_LIBRARY.md (the
   corrected S24 note), STATE/TASKS.md (P8-7 DONE with the full S32
   entry), STATE/PROGRESS.md (S32 entries), STATE/DECISIONS.md (D-023
   written; D-018 stays reserved), STATE/CONVENTIONS.md,
   STATE/SESSIONS.md, docs/BENCHMARKS.md (the ROOT block + the SCENE
   block S33 builds on), docs/POLICY.md (D-019 — scene animation is a
   content-carrying surface: check the subjects, MCP stays SFW), and
   the claim-bearing surfaces docs/LAUNCH.md + docs/TUTORIALS.md (one
   grep sweep together IF a number changes). Register as **Session 33**,
   claim P8-8 with [S33]; PROGRESS stamps via `date -u` read IMMEDIATELY
   before every append, then verify the stamp.

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**585 expected** — S32 added 17 root-motion contract
   tests) + `make lint PY=/home/potato/miniconda3/bin/python3`, and `gh
   run list --branch main` (the S32 push is the newest; if red: download
   the log, root-cause, fix the real substance FIRST).

## S33 work order — P8-8 Multi-character video → scene animation

Design → probe → build → gate, in that order (NON-NEGOTIABLE). The
pattern is proven seven times over (coupling, fingers, face, camera,
spine, root-motion instruments): design page first, probe with REAL
rows, core lift, sibling gate file.

1. **DESIGN-FIRST**: open docs/SCENE_ANIMATION.md (the ROOT_MOTION.md
   sibling): the P2-1 job container gains per-frame MULTI-FIGURE
   payloads + per-frame coupling (P8-2's `couple_scene` per frame with
   placements measured per frame) + fingers/facials riding per figure
   (P8-3/P8-4) -> scene actions -> bake BOTH rigs in one pass. The
   identity-stability algorithm is COMMITTED in the roadmap: per-frame
   figure→character assignment by pose-similarity cost matrix, solved
   with a deterministic assignment (Hungarian, keyed order), a cost
   jump raising a swap alarm, manual per-frame override winning over
   everything. The drift track (S32) rides per figure where the
   detector stream carries drift. NO payload format change beyond the
   existing v3 figures[] (declare whatever additive field the per-frame
   scene needs — the track rides the action, precedent S32).
2. **PROBE-FIRST xtask/scene_anim_probe.py** (RM_SANIM lines, grep-tested
   both shapes before push): (a) the synthetic two-person fixture — the
   engine-built deterministic renderer, two figures with KNOWN
   per-frame poses and one authored crossing (the swap-prone class);
   (b) identity assignment: swap rate measured on the fixture (<= 2%
   bar), the alarm catching >= 90% of the actual swaps (the authored
   crossing IS the alarm's GT); (c) per-frame coupling holds (residuals
   <= the 2% bar per frame); (d) the per-frame bake cost MEASURED and
   published (the mid-laptop baseline law — measure, never claim);
   (e) manual-override-wins row; (f) REFUSE classes loud; (g) DETERM.
3. **Core**: the deterministic assignment + swap alarm + the per-frame
   scene-action builder as additive pure-core modules (the spine.py
   pattern); consumers that ignore them byte-identical.
4. **Gate**: xtask/scene_anim_gate.py (the sibling file per the Mimosa
   workaround, RM_SANIM rows wired into verify_pose_apply.sh + the
   Makefile lint list): the bars above + twin byte-identity + all prior
   numbers byte-identical (incl. the S32 RM_ROOT rows).
5. **Early-finish option**: the S31 declared-open CLI/addon invocation
   wiring for the arch/roll passes, or the P8-2 pin-suggestion
   inference as desk DATA — measured work only.

**S32's contract facts S33 builds on** (do not re-learn):

- The REFUSED branch is a first-class terminal: L7's row ended
  REFUSED-with-evidence while the machinery ships gated — the scorecard
  (A.3) reads the ledger, not the calendar; S33's P8-8 rows must expect
  the same honesty bar (measure, publish, refuse on miss).
- The drift track rides the ACTION (`CanonicalAction.root_track`);
  per-figure scene actions can carry one track per figure — reuse
  `root_motion.py` verbatim, never fork it (D-016).
- The two-pass fixture-builder rule; place-update-then-measure
  (`view_layer.update()` BEFORE any world-space read — fired again in
  S32's first gate run); mathutils rich-compare through nested
  containers is FLAKY in 5.1 (plain-float tuples only); Blender masks
  script exceptions with exit 0 in some paths — grep the FINAL row
  (e.g. `RM_ROOT GATE: PASS`), never trust the exit code alone (S32's
  gate crashed twice before the greps caught it).
- The gate env trap (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  grab the broken apt 4.0.2).
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  a NEW sibling FILE scans clean where in-place edits trip path FPs
  (couple_gate/finger_gate/face_gate/camera_gate/spine_gate/
  root_motion_gate precedent); expect the pagedoc.py import-struct FP
  at every commit; heredoc/append FPs when text names source files.
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
- Root-motion BAKE (keying the drift track onto the rig's root) — the
  declared S32 follow-up; needs its own gate rows + byte-identity
  argument; revisit only if a real root-motion SOURCE exists (S32's A3
  finding: the local glb has none).
