# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", critic-passed
   9.8/10; Annex A pre-declared bars are LAW): S28 landed P8-3 fingers (the
   D-021 additive namespace + gated per-finger solve + preset-mapped apply;
   L2 CLOSED — bench median 0.00°/p90 10.30° vs bars 20°/35°, occlusion
   100% gated-skip, apply 0.0070°, all prior numbers byte-identical). The
   session map says **S29 = P8-4 facials** — the published landmark→param
   table (gaze ONLY with iris kps), bone/shape-key binding classes, loud
   no-target reporting. NEVER cut (Annex A cut order).

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly). Silent 16 straight sessions so far; the box side is READY
     (the DroidCam client just was never running).
   - **Silent again (17th)** → the P8-4 work order below.

2. **Then read, in order**: STATE/ROADMAP.md P8-4 + Annex A.1/A.2 (bars are
   law: per-param monotonicity ≥ 9/10 on the 10-expression benchmark, bone
   apply ≤ 0.5° family, shape-key delta ≤ 0.1 normalized; per-param
   refusal branch after two cycles; gaze conditional on iris kps — the
   pinned DWPose has NO iris kps, so gaze stays out unless a detector
   variant supplies them), docs/FINGERS.md (P8-3 as-built — the
   design→probe→core→gate pattern S29 reuses), docs/STYLE.md (shape-key
   and binding surfaces P8-4 may touch), STATE/TASKS.md (P8-3 DONE with
   the full S28 entry), STATE/PROGRESS.md (S28 entries),
   STATE/DECISIONS.md (D-021 now WRITTEN — the additive-namespace
   precedent; D-018 stays reserved; D-022 is RESERVED for the facial
   namespace, WRITTEN only when that code lands), STATE/CONVENTIONS.md,
   STATE/SESSIONS.md, docs/BENCHMARKS.md (FINGERS block), docs/POLICY.md
   (D-019 across the new facial surface), and the claim-bearing surfaces
   docs/LAUNCH.md + docs/TUTORIALS.md (one grep sweep together IF a
   number changes). Register as **Session 29**, claim P8-4 with [S29];
   PROGRESS stamps via `date -u` read IMMEDIATELY before every append,
   then verify the stamp.

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**507 expected** — S28 added 25 finger contract tests)
   + `make lint PY=/home/potato/miniconda3/bin/python3`, and `gh run
   list --branch main` (the S28 push is the newest; if red: download the
   log, root-cause, fix the real substance FIRST).

## S29 work order — P8-4 Facials

Design → probe → build → gate, in that order (NON-NEGOTIABLE). The data
audit precedent is DONE (docs/FINGERS.md): all 68 face kps + confidences
already reach the detection payload (face conf mean 0.958 on the P1-9
photo, 0/68 dropouts) — the drop is at the canonical-solve boundary, so
P8-4 is a SOLVE+PAYLOAD+APPLY extension exactly like P8-3: no new model,
no wrapper change, the P6-6 never-list untouched.

1. **DESIGN-FIRST: open docs/FACE.md** (the FINGERS.md pattern — a
   sibling design page, never a fork): the additive per-figure `face`
   payload field (format 3 unchanged, omit-when-empty byte-identity
   pinned — the `hands` contract), the PUBLISHED landmark→param table
   (brow raise = brow-kp row height delta; blink = eye aspect ratio vs
   the subject's open-eye prior; jaw open = lower-lip drop vs face
   height; smile/pout = mouth-corner elevation + width ratio; cheeks),
   neutral declared a POPULATION prior (D-008-untuned — single images
   carry no personal neutral); **D-022 is RESERVED for the facial
   namespace, WRITTEN at that landing** (never cited before — the
   strike-S2 rule; fingers took D-021).
2. **PROBE-FIRST xtask/face_probe.py** (RM_FACE lines, grep-tested both
   shapes before push): (a) landmark stability on real detections (the
   audit's 0.958 face-conf band); (b) per-param monotonicity on
   synthetic GT faces; (c) the no-observation gate (partial faces =
   skipped + ledgered, never guessed).
3. **Core**: the param table into the solve path (additive namespace +
   loud validation + round-trips; the pose payload carries face per
   figure; skip ledgers per param).
4. **Apply + gate**: the two binding classes (bones via preset mapping,
   shape keys by documented naming convention) — NEITHER present → loud
   "no facial targets" line; RM_FACE gate section (new sibling file per
   the Mimosa workaround): the 10-expression benchmark (neutral + 9),
   per-param monotonicity ≥ 9/10, bone apply ≤ 0.5° family, shape-key
   delta ≤ 0.1 normalized, loud no-target rig.
5. **Early-finish option**: the P8-2 pin-suggestion inference (keypoint
   proximity) as desk DATA — measured work only, never auto-enforced.

**S28's contract facts S29 builds on** (do not re-learn):

- The probe→core lift pattern works twice over (coupling_probe.py and
  finger_probe.py are the recipes coupling.py/fingers.py lifted).
- The additive-field contract: omit-when-empty byte-identity pinned by
  test; readers tolerate absence (copy the `hands` precedent for
  `face`).
- The gate env trap (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  grab the broken apt 4.0.2).
- The two-pass fixture-builder rule (create every bone, then wire
  parents; a missing parent REFUSES) + the S28 lesson that the wrist is
  a BODY keypoint (index 9) — block ranges do not include the anchor.
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  in-place edits to existing gate/probe files can trip path-traversal
  FPs — a NEW sibling file scans clean (couple_gate.py/finger_gate.py
  precedent); expect the pagedoc.py import-struct FP at every commit;
  -F commit-message files for heredoc-sensitive text.
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
