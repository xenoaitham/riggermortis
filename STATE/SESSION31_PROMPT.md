# SESSION 31 PROMPT — riggermortis

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
MEASURED side map (.L = band B — the probe flipped the declared convention
18/18 on real faces), per-param gates + ledgers, gaze conditional-OUT
(no iris kps from the pinned detector), the two-class apply. The MEASURED
camera landed (P8-5): yaw/pitch/distance/height fitted from the body
keypoints with the canonical skeleton's proportions as the ruler —
GT-set yaw MAE 2.58° (bar 7.5°), pitch MAE 4.83° (bar 5°), distance MAE
3.42% (bar 12%), framing IoU 0.8082 staged / 0.9621 median, BOTH floors
(solve confidence 0.55 AND framing IoU 0.75) gate the staging, CAM-MODEL
matches Blender at 2.32e-07; tier-2 render+detector NOT MET with evidence
(the pinned detector is blind to the engine's mannequin class — published,
never relabeled). Toon renders, manga pages. Live pose-stream puppeteering
on the replay path. No cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** V1 = Phase
8 complete + the Scene Test scorecard green (target S35; Annex A.3: the
scorecard overrides the calendar). S30 landed P8-5 (L4 CLOSED). **S31's
rock is P8-6 spine arch + roll**: the ARCH solve when the head is observed
— distribute hips→shoulders→head misalignment across spine/chest/neck by
proportion (new observed-constraint solve; the D-008 priors untouched);
the ROLL solve — forearm/upper-arm roll alignment from wrist-vs-elbow
landmark geometry (the P1-11 declared follow-up), confidence-gated;
**bars: the arch benchmark monotone distribution (neutral/arched/bow L/R)
+ the FK bars hold (0.5° family through the REAL apply) + D-008's 18/20
flip accept unchanged; the roll fixture corrects to bar; straight arms
BIT-IDENTICAL (the no-op proven)**; refusal branch (Annex A.2): arch/roll
that cannot hold the FK bars → REFUSED, documented as the single-view
limit (the D-008 ledger entry updated). NEVER cut P8-3 visible fingers or
P8-2 coupling (Annex A cut order); the P8-5 full solve was the next cut
item and has LANDED.

## S30 contract facts (what S31 builds on)

- **P8-5 LANDED** (full entry in TASKS.md; numbers in BENCHMARKS CAM):
  design-first docs/CAMERA.md (the FACE.md sibling; amendments A1–A11
  probe-earned and recorded — read them, they are the map of every trap:
  the scale carrier is the payload's scale field A1; closed-form yaw from
  the head-placement direction ratio A3; R_SHOULDER 0.26 at the upper-arm
  heads A4; the depth-gradient system g = (hp/H − sh/S)/(0.45·hp/H) =
  sinθcosθ/D whose sign IS the pitch sign A5; the nose-to-ankle vertical
  ruler + dual-regime pitch with the regime bound A6/A7; the fixture law
  — girdle kps are rulers A8; the projection sign convention + general
  sensor AUTO-fit A10/A11).
- **Core `camera.py`**: `solve_camera_figure` (pure, per-figure, loud
  refusals: kp-starved / torso-degenerate / pose-class breach / envelope
  breach / head-placement degenerate) + `consensus_camera` (the
  confidence-weighted CIRCULAR mean for multi-figure yaw) + `sensor_fit`.
  NO payload format change — the camera solve reads the v3 fields that
  already exist; the hands-free face-free byte-identity contracts hold
  (pinned). **17 tests in test_camera.py = 549 total.**
- **Addon `camera_stage.py`**: `stage_scene_camera_measured` — the BOTH-
  floors staging (solve confidence ≥ 0.55 AND framing IoU ≥ 0.75, the IoU
  measured by projecting the posed subject through the staged camera, the
  v0 machinery); `rm_camera_solve="MEASURED"` + conf + IoU + params
  stamped on `rm_scene_camera`; the scene res set to the reference dims
  for the measurement (restored on refuse). The v0 `scene_camera.py` is
  BYTE-UNTOUCHED as the declared fallback; the RM_SCENE CAMERA-* rows
  keep exercising it (0.3388 refuse / 0.8279 stage). The Casting Desk
  button calls the measured path; refusals stay loud WARNINGs.
- **Gate `xtask/camera_gate.py`** (6 RM_CAM rows, wired into
  verify_pose_apply.sh + the Makefile lint list): CAM-MODEL 2.32e-07,
  CAM-GT 2.58/4.73/3.42 (n=75), CAM-STAGE yaw 19.86 vs GT 20 / IoU 0.8082,
  CAM-REFUSE loud no-camera, CAM-TWIN byte-identical.
- **Gate env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- **Camera facts** (if S31 touches cameras): build the quaternion FROM
  the model basis (right = fw×world-up IS screen-right → plus-sign u;
  up = right×fw; the camera's local axes = (right, up, −fw)); the sensor
  AUTO-fit is general (the LONG edge gets 36 mm); `view_layer.update()`
  before any world-space read.
- **532 → expect ~549+ tests** (S30 added 17 camera contract tests); CI
  green through the S30 push; all gate numbers through S30 byte-
  identical (RM_BAKE 0.0242° ×2, RM_FOOT_LOCK 0.0371→0.0000, RM_TAILS,
  RM_MOTION, RM_SCENE 0.3388/0.8279, RM_COUPLE 0.00016/0.00035,
  RM_FINGER 0.0070°/0.00°/10.30°, RM_FACE 6 rows, RM_CAM 6 rows).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-6 work order below.
- Silent (19th): proceed with P8-6 directly.
- Then read, in order: STATE/ROADMAP.md (P8-6 + Annex A.1/A.2 — the bars
  are law: the arch benchmark monotone distribution + the FK bars hold +
  D-008's 18/20 flip accept unchanged; the roll fixture corrects to bar;
  straight arms bit-identical; the refusal branch: arch/roll that cannot
  hold the FK bars → REFUSED, documented as the single-view limit — the
  D-008 ledger entry updated), docs/CAMERA.md + docs/FACE.md +
  docs/FINGERS.md (the design→probe→core→gate pattern; the sibling
  design-page rule), docs/SCENES.md § Contact coupling (the
  movable-chain table — the arch is the separately-gated torso
  articulation the coupling table deferred), docs/STYLE.md, STATE/NEXT.md,
  STATE/TASKS.md (claim P8-6 with [S31]), STATE/PROGRESS.md (S30
  entries), STATE/DECISIONS.md (D-021/D-022 WRITTEN; D-018 stays
  reserved), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
  docs/BENCHMARKS.md (the CAM block), docs/POLICY.md (D-019 unchanged —
  spine/roll carry no content), and the claim-bearing surfaces
  docs/LAUNCH.md + docs/TUTORIALS.md (one grep sweep together IF a
  number changes).
- Register as Session 31 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**549 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S30 discipline).

## S31 work order — P8-6 Spine arch + roll

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST**: open docs/SPINE.md (the CAMERA.md sibling pattern —
   never a fork): the ARCH model (when head + torso chain are observed,
   distribute the hips→shoulders→head misalignment across spine/chest/
   neck by declared proportion — the additive pattern rides the SOLVED
   positions like the coupling's write-back; NO payload format change),
   the ROLL model (forearm/upper-arm roll from wrist-vs-elbow landmark
   geometry, confidence-gated, straight arms bit-identical), the
   confidence arithmetic + the refuse branch (a pose class the arch
   cannot represent → the pose stays flat, REPORTED, never guessed), the
   monotone-distribution benchmark design (neutral/arched/bow L/R),
   and the GT-set protocol (engine-built prior-consistent fixtures,
   SYNTHETIC-labeled with the optimism caveat verbatim; the re-validation
   trigger on real fixtures).
2. **PROBE-FIRST xtask/spine_probe.py** (RM_SPINE lines, grep-tested
   both shapes before push): (a) the arch benchmark — the monotone
   distribution across neutral/arched/bow L/R; (b) the FK bars through
   the REAL apply path; (c) D-008's 18/20 flip accept unchanged (the
   arch must not disturb the flip enumeration); (d) the roll fixture
   corrects to bar; (e) straight arms BIT-IDENTICAL (byte-level no-op);
   (f) REAL rows on the P1-9 photos — outputs + confidences, never
   prose claims; (g) DETERM twins.
3. **Core**: the arch + roll solves as additive pure-core modules (the
   camera.py pattern); consumers that ignore them stay byte-identical.
4. **Gate**: `xtask/spine_gate.py` (the sibling file per the Mimosa
   workaround, RM_SPINE rows wired into the battery + the Makefile lint
   list): the bars above + twin byte-identity + all prior numbers
   byte-identical.
5. **If early**: the P8-2 pin-suggestion inference (keypoint proximity)
   as desk DATA — measured work only, never auto-enforced.

Definition of S31 failure (name it, avoid it): a prose spine/roll claim
without a benchmark number, an arch applied below its confidence floor,
a straight-arm pose that moves a single byte, a touched frozen-role set /
D-021 / D-022 namespace, a face-free or hands-free payload byte change,
or ANY claim without a test/gate citation. Anything 80% done is 0%
shipped — park cleanly at a unit boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored; every inferred thing carries confidence + residual); park
  criteria (two stalled probe/gate cycles → park with evidence,
  reorder); the cut order (P8-9 time-to-fix → P8-6 roll → NEVER P8-2/
  P8-3); policy D-019 across new surfaces (MCP stays SFW, test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- STATE stamps: real UTC, read-then-write-then-verify.
- Mimosa: bash writes of source files blocked — Write/Edit; new sibling
  FILES scan clean where in-place edits trip path FPs (couple_gate.py /
  finger_gate.py / face_gate.py / camera_stage.py precedent); expect the
  pagedoc.py import-struct FP at every commit; heredoc/append FPs when
  text names source files — Edit tool + -F commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson (pb.matrix.to_translation()),
  joint-angle keying, factory-EMPTY FBX scenes, rotation modes before
  quaternion writes (rotation_mode BEFORE rotation_quaternion!), the
  two-pass fixture-builder rule, place-update-then-measure (view_layer
  .update() BEFORE any world-space read), the wrist-is-body-kp-9 lesson,
  the girdle-kps-are-rulers fixture law — the S15..S30 facts in
  SESSION30_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S32 =
P8-7 root motion per the session map, UNLESS a park/reorder happened
(say which and why); write STATE/SESSION32_PROMPT.md in this pattern
(contract facts, STEP 0, the P8-7 work order with its Annex bars: the
drift track must beat walk-in-place slide on the REAL fixture (Xbot row)
by the >= 5x family, else L7 ends REFUSED; the in-place path's prior
gate numbers byte-identical); update STATE/SESSIONS.md row; commit +
push (routine commits authorized; keep CI green, fix inline like
S12..S30); expect and disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up). PyPI
description + Blender Extensions upload — LO's site-side steps (his final
session). P6-3 packaging + P6-2a wiring — roadmap slack. P1-8a — P8-9.
Windowed Blender GL stability — best-effort only, never staged.
Detector-visible mannequin fixtures (the P8-5 tier-2 path) — NOT MET with
evidence; reopened only if a detector-visible engine-built fixture path
exists (the A.3 re-validation trigger).
