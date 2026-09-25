# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", critic-passed
   9.8/10; Annex A pre-declared bars are LAW): S29 landed P8-4 facials (the
   D-022 facial parameter namespace + the measured side map + per-param
   gated solve + the two-class apply; L3 CLOSED — BENCH 0 violations/9 +
   reach 1.00, bone apply 0.0000°, shape-key delta 0.0000, loud no-target;
   all prior numbers byte-identical). The session map says **S30 = P8-5
   reference camera solve (measured)** — GT-set yaw MAE ≤ 7.5° / pitch
   MAE ≤ 5° / distance MAE ≤ 12%, framing IoU ≥ 0.75, low confidence
   REFUSES to stage. NEVER cut (Annex A cut order: P8-2 coupling and
   P8-3 visible fingers; gaze was P8-4's declared first cut and is
   already conditional-OUT).

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly). Silent 17 straight sessions so far; the box side is READY
     (the DroidCam client just was never running).
   - **Silent again (18th)** → the P8-5 work order below.

2. **Then read, in order**: STATE/ROADMAP.md P8-5 + Annex A.1/A.2 (bars
   are law: yaw MAE ≤ 7.5°, pitch MAE ≤ 5°, distance MAE ≤ 12% on the GT
   set; framing IoU ≥ 0.75; low confidence refuses to stage — a wrong
   silent camera is the trust-killer; REFUSED branch: GT yaw MAE > 15°
   ends the full solve, camera v0 remains as CLOSED-v0), docs/SCENES.md
   (P8-1 camera v0's as-built — the APPROXIMATE stager S30 replaces with
   the measured solve), docs/FACE.md + docs/FINGERS.md (the
   design→probe→core→gate pattern S30 reuses), STATE/TASKS.md (P8-4 DONE
   with the full S29 entry), STATE/PROGRESS.md (S29 entries),
   STATE/DECISIONS.md (D-022 now WRITTEN — the second additive-namespace
   precedent; D-018 stays reserved), STATE/CONVENTIONS.md,
   STATE/SESSIONS.md, docs/BENCHMARKS.md (FACE block), docs/POLICY.md
   (D-019 unchanged across the camera surface), and the claim-bearing
   surfaces docs/LAUNCH.md + docs/TUTORIALS.md (one grep sweep together
   IF a number changes). Register as **Session 30**, claim P8-5 with
   [S30]; PROGRESS stamps via `date -u` read IMMEDIATELY before every
   append, then verify the stamp.

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**532 expected** — S29 added 25 face contract tests)
   + `make lint PY=/home/potato/miniconda3/bin/python3`, and `gh run
   list --branch main` (the S29 push is the newest; if red: download the
   log, root-cause, fix the real substance FIRST).

## S30 work order — P8-5 Reference camera solve (measured)

Design → probe → build → gate, in that order (NON-NEGOTIABLE). The
pattern is proven three times over (coupling, fingers, face): design
page first, probe with REAL rows, core lift, sibling gate file.

1. **DESIGN-FIRST: open docs/CAMERA.md** (the FACE.md sibling pattern):
   the camera model (yaw/pitch/distance/height from body kps + the
   solve's depth assumptions — the canonical skeleton's proportions are
   the known ruler), what the APPROXIMATE v0 stager keeps doing (it
   stages on the benchmark at IoU 0.8279 today), the confidence floor
   arithmetic with its refuse-to-stage branch, and the GT-set protocol
   (KNOWN camera -> render -> re-solve through the pipeline's own
   deterministic renderer, engine-built per Annex A.3; SYNTHETIC-labeled
   with the optimism caveat verbatim).
2. **PROBE-FIRST xtask/camera_probe.py** (RM_CAM lines, grep-tested both
   shapes before push): (a) GT-set solve error bars (yaw/pitch/distance
   MAE vs the bars); (b) framing IoU distribution vs the 0.75 floor;
   (c) the confidence floor — degraded inputs must REFUSE to stage
   (loud, never a wrong silent camera); (d) REAL rows on the P1-9
   photos where ground truth does not exist — publish what the solve
   reports and its confidence, never prose claims.
3. **Core**: the measured solve into the camera path (additive; the v0
   stager's refuse-to-stage floor upgraded to the measured confidence;
   `scene_camera.py` consumers unchanged where the contract holds).
4. **Gate**: `xtask/camera_gate.py` (sibling file, RM_CAM rows wired
   into the scene-verify half of the battery): GT-set error bars vs the
   Annex bars, framing IoU, refuse-to-stage on degraded inputs, twin
   byte-identical, all prior numbers byte-identical.
5. **Early-finish option**: the P8-2 pin-suggestion inference (keypoint
   proximity) as desk DATA — measured work only, never auto-enforced.

**S29's contract facts S30 builds on** (do not re-learn):

- The probe→core lift pattern works three times over (coupling_probe/
  finger_probe/face_probe are the recipes lifted).
- The additive-field contract: omit-when-empty byte-identity pinned by
  test; readers tolerate absence.
- The gate env trap (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  grab the broken apt 4.0.2).
- The two-pass fixture-builder rule (create every bone, then wire
  parents; a missing parent REFUSES); place-update-then-measure
  (view_layer.update() BEFORE any world-space read).
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  in-place edits to existing gate/probe files can trip path-traversal
  FPs — a NEW sibling file scans clean (couple_gate/finger_gate/
  face_gate precedent); expect the pagedoc.py import-struct FP at every
  commit; -F commit-message files for heredoc-sensitive text.
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
