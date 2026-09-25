# SESSION 30 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes landed (P8-1): one
payload poses N paired rigs in one action, pins carried as data, an
APPROXIMATE camera stages from the reference framing. Contact coupling
landed (P8-2): AUTHORED pins close deterministically, suggested/below-floor
pins stay loud data. Fingers landed (P8-3): the D-021 additive namespace
solves per-finger chains ONLY from observed hand keypoints — below the 0.55
floor a finger is skipped + LEDGERED, never guessed. Facials landed (P8-4):
the D-022 facial parameter namespace — 10 dimensionless expression params
solved ONLY from observed face landmarks through the PUBLISHED table, the
MEASURED side map (.L = band B — the probe flipped the declared convention
18/18 on real faces), per-param gates + ledgers (below the 0.55 floor
skipped, below the 0.08 activation floor ledgered, never interpolated),
gaze conditional-OUT (no iris kps from the pinned detector), the two-class
apply (preset `face_bones` bones + shape keys named == param on deformed
meshes, both loud, neither present → "no facial targets"). Toon renders,
manga pages. Live pose-stream puppeteering on the replay path. No cloud,
no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** V1 = Phase
8 complete + the Scene Test scorecard green (target S35; Annex A.3: the
scorecard overrides the calendar). S29 landed P8-4. **S30's rock is P8-5
reference camera solve (measured)** — the APPROXIMATE v0 stager (landed
P8-1, stages at IoU 0.8279 on the benchmark) gains the MEASURED solve:
fit yaw/pitch/distance/height from body kps + the canonical skeleton's
proportions as the known ruler; **bars: yaw MAE ≤ 7.5° / pitch MAE ≤ 5° /
distance MAE ≤ 12% on the GT set, framing IoU ≥ 0.75, low confidence
REFUSES to stage** (a wrong silent camera is the trust-killer); REFUSED
branch: GT yaw MAE > 15° ends the full solve, camera v0 remains as
CLOSED-v0. NEVER cut P8-3 visible fingers or P8-2 coupling (Annex A cut
order); gaze was P8-4's first cut and is already conditional-OUT.

## S29 contract facts (what S30 builds on)

- **P8-4 LANDED** (full entry in TASKS.md; numbers in BENCHMARKS FACE):
  core `face.py` — the 10-param namespace `FACE_PARAMS` + `solve_face`
  (pure, dimensionless ratios: the face solves iff the IOD anchor's four
  corner kps clear FACE_CONF_FLOOR 0.55 — below, NO entry, an absent
  face reads as clean; per-param consumed-kps gates with verbatim
  ledgers; below FACE_ACT_FLOOR 0.08 a solved value is LEDGERED, never
  interpolated) + `FACE_BONE_PLAN` (the DECLARED per-param axis-angle);
  named face constants + `face_kp_index` in poses.py (the MEASURED side
  map: DWPose band A = subject's RIGHT, `.L` reads band B — flipped by
  measurement, 18/18 faces, docs/FACE.md A4); three neutral-geometry
  priors REDECLARED from pooled real medians (corner drop 0.40, mouth
  width 0.83, cheek distance 0.72; EAR 0.28 + brow 0.30 stood; the
  declared values had smile/pout firing on every real neutral and cheek
  structurally dead — the D-008 loop: declared → measured → redeclared
  BEFORE the core build). The smile reference is the nose bottom (kp 33)
  — the corners' own line is degenerate under symmetric smiles (A1).
- **CanonicalPose.face**: additive `FacePose | None`, default None;
  `to_dict` OMITS the key when None (face-free poses serialize
  byte-identically — contract-pinned); `from_dict` tolerates absence;
  `mirrored()` swaps `.L`/`.R` values (geometry-free).
- **Apply**: two loud classes — (a) preset `face_bones` bindings
  (format 2 unchanged, `resolve_face` = the SAME fingerprint gate,
  cross-binding guards) feeding `apply_canonical_pose(...,
  face_bones=..., face_shape_keys=...)`: bound bones take the DECLARED
  axis-angle joining the SAME top-down parent-space pass; (b) shape
  keys by naming convention (key name == param name) on meshes deformed
  by the armature, resolved + driven addon-side, missing keys report
  loud; NEITHER present → the loud "no facial targets" line (verbatim:
  "face: N expression param(s) solved; no facial targets for this rig —
  face not applied"). CLI solves face by default; session `apply_pose`
  preset path resolves face_bones; KNOWN_ACTION_KINDS + MCP tool tables
  untouched.
- **Gate**: `xtask/face_gate.py` (finger_gate's SIBLING) wired into
  verify_pose_apply.sh: FACE-BENCH 0 violations / 9 steps (bar 1) +
  reach 1.00 (bar 0.5) over the 10-expression class [SYNTHETIC,
  prior-consistent GT]; FACE-GATE-OCCL zero guessed; FACE-BONE-APPLY
  0.0000° worst (bar 0.5) 5/5 bones; FACE-SHAPE-APPLY delta 0.0000
  (bar 0.1) 4/4 keys mesh-displaced; FACE-NOTARGET verbatim;
  FACE-TWIN byte-identical. Probe: `xtask/face_probe.py` 7/7 with REAL
  rows (band confs 0.97–1.00; priors published next to declared).
- **D-022 WRITTEN at the landing** (STATE/DECISIONS.md) — the second
  additive-namespace precedent (D-021 fingers); D-018 stays reserved.
- **532 → expect ~555+ tests** (S29 added 25 face contract tests); CI
  green through the S29 push; all gate numbers through S29 byte-
  identical (RM_BAKE 0.0242° ×2, RM_FOOT_LOCK 0.0371→0.0000, RM_TAILS,
  RM_MOTION, RM_SCENE 0.3388/0.8279, RM_COUPLE 0.00016/0.00035,
  RM_FINGER 0.0070°/0.00°/10.30°, RM_FACE 6 rows).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-5 work order below.
- Silent (18th): proceed with P8-5 directly.
- Then read, in order: STATE/ROADMAP.md (P8-5 + Annex A.1/A.2 — bars are
  law: yaw MAE ≤ 7.5°, pitch MAE ≤ 5°, distance MAE ≤ 12% on the GT set,
  framing IoU ≥ 0.75, low confidence refuses to stage; REFUSED branch:
  GT yaw MAE > 15° → full solve REFUSED, camera v0 remains as
  CLOSED-v0), docs/SCENES.md (the P8-1 camera v0 as-built S30 upgrades),
  docs/FACE.md + docs/FINGERS.md (the design→probe→core→gate pattern;
  the sibling design-page rule), docs/STYLE.md, STATE/NEXT.md,
  STATE/TASKS.md (claim P8-5 with [S30]), STATE/PROGRESS.md (S29
  entries), STATE/DECISIONS.md (D-022 now WRITTEN; D-018 stays
  reserved), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
  docs/BENCHMARKS.md (FACE block), docs/POLICY.md (D-019 unchanged —
  cameras carry no content), and the claim-bearing surfaces
  docs/LAUNCH.md + docs/TUTORIALS.md (one grep sweep together IF a
  number changes).
- Register as Session 30 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**532 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S29 discipline).

## S30 work order — P8-5 Reference camera solve (measured)

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST: open docs/CAMERA.md** (the FACE.md sibling pattern —
   never a fork): the camera model (yaw/pitch/distance/height fit from
   body kps with the canonical skeleton's proportions as the known
   ruler — the solve's depth assumptions declared D-008-style), what
   the APPROXIMATE v0 stager keeps doing (IoU floor + bbox stage, stays
   for the fallback path), the confidence arithmetic + the
   refuse-to-stage branch (loud, never a wrong silent camera), and the
   GT-set protocol (KNOWN camera -> render -> re-solve through the
   pipeline's OWN deterministic renderer, engine-built per Annex A.3;
   every claim SYNTHETIC-labeled with the optimism caveat verbatim; the
   re-validation trigger on real fixtures).
2. **PROBE-FIRST xtask/camera_probe.py** (RM_CAM lines, grep-tested
   both shapes before push): (a) GT-set solve error bars — yaw/pitch/
   distance MAE vs the bars over a deterministic camera sweep; (b)
   framing IoU distribution vs the 0.75 floor; (c) the refuse branch —
   degraded inputs (few figures, foreshortened, kp-starved) REFUSE to
   stage, loud + ledgered; (d) REAL rows on the P1-9 photos — where GT
   does not exist, publish the solve's outputs + confidences, never
   prose claims.
3. **Core**: the measured solve into the camera path (additive; the v0
   stager's confidence upgraded to the measured one; `scene_camera.py`
   consumers unchanged where the contract holds).
4. **Gate**: `xtask/camera_gate.py` (sibling file per the Mimosa
   workaround, RM_CAM rows wired into the battery): GT-set error bars
   vs the Annex bars, framing IoU, refuse-to-stage on degraded inputs,
   twin byte-identical, all prior numbers byte-identical.
5. **If early**: the P8-2 pin-suggestion inference (keypoint proximity)
   as desk DATA — measured work only, never auto-enforced.

Definition of S30 failure (name it, avoid it): a prose camera claim
without a GT number, a staged camera below the confidence floor, a
touched frozen-role set / D-021 / D-022 namespace, a face-free or
hands-free payload byte change, or ANY claim without a test/gate
citation. Anything 80% done is 0% shipped — park cleanly at a unit
boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored; every inferred thing carries confidence + residual; the
  camera is INFERRED — labeled approximate until measured, and
  measured with published error bars after); park criteria (two
  stalled probe/gate cycles → park with evidence, reorder); the cut
  order (P8-9 time-to-fix → P8-5 full solve → P8-6 roll; NEVER cut
  P8-3 visible fingers or P8-2 coupling); policy D-019 across new
  surfaces (MCP stays SFW, test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- STATE stamps: real UTC, read-then-write-then-verify.
- Mimosa: bash writes of source files blocked — Write/Edit; new sibling
  FILES scan clean where in-place edits trip path FPs (couple_gate.py /
  finger_gate.py / face_gate.py precedent); expect the pagedoc.py
  import-struct FP at every commit; heredoc/append FPs when text names
  source files — Edit tool + -F commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson (pb.matrix.to_translation()),
  joint-angle keying, factory-EMPTY FBX scenes, rotation modes before
  quaternion writes, place-update-then-measure (view_layer.update()
  BEFORE any world-space read), the two-pass fixture-builder rule, the
  wrist-is-body-kp-9 lesson — the S15..S29 facts in
  SESSION29_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S31 =
P8-6 spine arch + roll per the session map, UNLESS a park/reorder
happened (say which and why); write STATE/SESSION31_PROMPT.md in this
pattern (contract facts, STEP 0, the P8-6 work order with its Annex
bars: arch benchmark monotone distribution + FK bars hold + D-008's
18/20 flip accept unchanged; roll corrects to bar; straight arms
bit-identical); update STATE/SESSIONS.md row; commit + push (routine
commits authorized; keep CI green, fix inline like S12..S29); expect
and disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up). PyPI
description + Blender Extensions upload — LO's site-side steps (his final
session). P6-3 packaging + P6-2a wiring — roadmap slack. P1-8a — P8-9.
Windowed Blender GL stability — best-effort only, never staged.
