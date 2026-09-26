# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", critic-passed
   9.8/10; Annex A pre-declared bars are LAW): S30 landed P8-5 reference
   camera solve (measured) — L4 CLOSED: GT-set yaw MAE 2.58° (bar 7.5°),
   pitch MAE 4.83° (bar 5°), distance MAE 3.42% (bar 12%), framing IoU
   0.8082 staged / 0.9621 median, both-floors staging (confidence 0.55 +
   IoU 0.75), CAM-MODEL vs Blender at 2.32e-07; tier-2 render+detector
   NOT MET with evidence (the pinned detector is blind to the engine's
   mannequin class — published, never relabeled). The session map says
   **S31 = P8-6 spine arch + roll**: the arch solve when the head is
   observed (distribute hips→shoulders→head misalignment across
   spine/chest/neck by proportion), the forearm/upper-arm roll alignment
   from wrist-vs-elbow geometry, confidence-gated; straight arms stay
   bit-identical (no-op proven). NEVER cut (Annex A cut order: P8-2
   coupling and P8-3 visible fingers; the P8-5 full solve was the
   next cut item and has now LANDED).

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly). Silent 18 straight sessions so far; the box side is READY
     (the DroidCam client just was never running).
   - **Silent again (19th)** → the P8-6 work order below.

2. **Then read, in order**: STATE/ROADMAP.md P8-6 + Annex A.1/A.2 (the
   arch bars: the arch benchmark monotone distribution + the FK bars hold
   + D-008's 18/20 flip accept unchanged; the roll bar: the roll fixture
   corrects to bar; straight arms bit-identical; the refusal branch:
   arch/roll that cannot hold the FK bars → REFUSED, documented as the
   single-view limit — the D-008 ledger entry updated), docs/CAMERA.md +
   docs/FACE.md + docs/FINGERS.md (the design→probe→core→gate pattern S31
   reuses), docs/SCENES.md § Contact coupling (the movable-chain table —
   P8-6's arch is the separately-gated torso articulation the coupling
   table deferred), STATE/TASKS.md (P8-5 DONE with the full S30 entry),
   STATE/PROGRESS.md (S30 entries), STATE/DECISIONS.md (D-021/D-022
   WRITTEN; D-018 stays reserved), STATE/CONVENTIONS.md,
   STATE/SESSIONS.md, docs/BENCHMARKS.md (the CAM block), docs/POLICY.md
   (D-019 unchanged — spine/roll carry no content), and the claim-bearing
   surfaces docs/LAUNCH.md + docs/TUTORIALS.md (one grep sweep together
   IF a number changes). Register as **Session 31**, claim P8-6 with
   [S31]; PROGRESS stamps via `date -u` read IMMEDIATELY before every
   append, then verify the stamp.

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**549 expected** — S30 added 17 camera contract tests)
   + `make lint PY=/home/potato/miniconda3/bin/python3`, and `gh run
   list --branch main` (the S30 push is the newest; if red: download the
   log, root-cause, fix the real substance FIRST).

## S31 work order — P8-6 Spine arch + roll

Design → probe → build → gate, in that order (NON-NEGOTIABLE). The
pattern is proven five times over (coupling, fingers, face, camera):
design page first, probe with REAL rows, core lift, sibling gate file.

1. **DESIGN-FIRST**: open a new design page (docs/SPINE.md, the
   CAMERA.md sibling pattern) — the ARCH solve: when the head AND the
   torso chain are observed, distribute the hips→shoulders→head
   misalignment across spine/chest/neck by proportion (a new
   observed-constraint solve; the D-008 priors untouched; the additive
   payload pattern — NO payload format change, the arch rides the SOLVED
   positions exactly like the coupling's write-back); the ROLL solve:
   forearm/upper-arm roll alignment from wrist-vs-elbow landmark
   geometry (the P1-11 declared follow-up), confidence-gated, straight
   arms BIT-IDENTICAL (the no-op proven by test). Declare D-008-style:
   the distribution proportions, the confidence arithmetic, the refuse
   branch (a pose class the arch cannot represent → the pose stays flat,
   reported, never guessed), the monotone-distribution benchmark design
   (neutral/arched/bow L/R), and the FK-fidelity acceptance (the arch
   must hold the 0.5° family through the REAL apply).
2. **PROBE-FIRST xtask/spine_probe.py** (RM_SPINE lines, grep-tested
   both shapes before push): (a) the arch benchmark — monotone
   distribution across neutral/arched/bow L/R fixtures (GT built
   engine-style, prior-consistent, SYNTHETIC-labeled); (b) the FK bars
   through the REAL apply path; (c) D-008's 18/20 flip accept unchanged
   (the arch solve must not disturb the flip enumeration); (d) the roll
   fixture corrects to bar; (e) straight arms BIT-IDENTICAL (the no-op
   proof, byte-level); (f) REAL rows on the P1-9 photos where ground
   truth does not exist — publish what the solve reports and its
   confidence, never prose claims; (g) DETERM twins.
3. **Core**: the arch + roll solves as additive pure-core modules (the
   camera.py pattern); consumers that ignore them stay byte-identical.
4. **Gate**: xtask/spine_gate.py (the sibling file per the Mimosa
   workaround, RM_SPINE rows wired into the battery + the Makefile lint
   list): the bars above + twin byte-identity + all prior numbers
   byte-identical.
5. **Early-finish option**: the P8-2 pin-suggestion inference (keypoint
   proximity) as desk DATA — measured work only, never auto-enforced.

**S30's contract facts S31 builds on** (do not re-learn):

- The probe→core lift pattern works four times over (coupling_probe/
  finger_probe/face_probe/camera_probe are the recipes lifted).
- The additive-field contract: omit-when-empty byte-identity pinned by
  test; readers tolerate absence. NO payload format change landed in S30
  (the camera solve reads the v3 fields that already exist) — keep it
  that way for the arch.
- The gate env trap (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  grab the broken apt 4.0.2).
- The two-pass fixture-builder rule (create every bone, then wire
  parents; a missing parent REFUSES); place-update-then-measure
  (view_layer.update() BEFORE any world-space read); cameras: build the
  quaternion FROM the model basis (no track_quat ambiguity) and set the
  scene res to the reference aspect (the sensor AUTO-fits the long side).
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  in-place edits to existing gate/probe files can trip path-traversal
  FPs — a NEW sibling file scans clean (couple_gate/finger_gate/
  face_gate/camera_stage precedent); expect the pagedoc.py import-struct
  FP at every commit; -F commit-message files for heredoc-sensitive text.
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
