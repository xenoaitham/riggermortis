# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", critic-passed
   9.8/10; Annex A pre-declared bars are LAW): S27 landed P8-2 contact
   coupling (the "not touching = bad" fix — authored pins close at fracs
   0.00016/0.00035 vs the 0.02 bar; L1 CLOSED). The session map says
   **S28 = P8-3 fingers** — the additive finger namespace (D-021 is
   WRITTEN when that code lands, never cited before), per-finger
   confidence gates, preset-mapped apply. NEVER cut (Annex A cut order).

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly). Silent 15 straight sessions so far; the box side is READY
     (the DroidCam client just was never running).
   - **Silent again (16th)** → the P8-3 work order below.

2. **Then read, in order**: STATE/ROADMAP.md P8-3 + Annex A.1/A.2 (bars are
   law: median ≤ 20° / p90 ≤ 35° visible fingers, 100% gated-skip on
   occlusion fixtures; per-class refusal branch), docs/FINGERS.md (the S26
   audit + the S28 design skeleton — EXTEND it, never fork it),
   docs/SCENES.md (P8-2 as-built — the coupling pass is the pattern for
   probe-first/lift-into-core), STATE/TASKS.md (P8-2 DONE with the full
   S27 entry), STATE/PROGRESS.md (S27 entries), STATE/DECISIONS.md
   (D-019/D-020; D-021 stays RESERVED until the finger/face code lands —
   WRITE IT at that landing; D-018 stays reserved), STATE/CONVENTIONS.md,
   STATE/SESSIONS.md, docs/BENCHMARKS.md (SCENE + COUPLING blocks),
   docs/POLICY.md, and the claim-bearing surfaces docs/LAUNCH.md +
   docs/TUTORIALS.md (one grep sweep together IF a number changes).
   Register as **Session 28**, claim P8-3 with [S28]; PROGRESS stamps via
   `date -u` read IMMEDIATELY before every append, then verify the stamp.

3. **PUSH FIRST (see the blocker below), then baseline**: `cd core &&
   /home/potato/miniconda3/bin/python3 -m pytest tests` (**482 expected**
   — S27 added 23 coupling tests) + `make lint
   PY=/home/potato/miniconda3/bin/python3`, and `gh run list --branch
   main` (the S27 commit 3ca848d is the newest, pushed-pending). If red:
   download the log, root-cause, fix the real substance FIRST.

## S28 work order — P8-3 Fingers

Design → probe → build → gate, in that order (NON-NEGOTIABLE). The data
audit is DONE (docs/FINGERS.md): all 133 kps + confidences already reach
the detection payload — the drop is at `observations_from_keypoints` (it
reads only body/foot indices). P8-3 is a SOLVE+PAYLOAD+APPLY extension:
no new model, no wrapper change, the P6-6 never-list untouched.

1. **DESIGN-FIRST: extend docs/FINGERS.md** with the as-built design: the
   additive per-figure `hands` payload field (format 3 unchanged,
   optional; readers that ignore unknown fields keep working);
   `hand.L/R` COCO-WholeBody layout via NAMED constants (wrist + 5
   fingers × 4 mcp/pip/dip/tip, thumb→pinky) pinned in poses.py the same
   commit; per-finger 3-joint chains solved ONLY from observed kps,
   wrist-anchored, hand frame from the canonical wrist→forearm direction;
   per-finger confidence gates (occluded = skipped + FLAGGED, never
   guessed); apply via preset mapping (authored once per rig); a rig
   without finger targets reports a loud capability line, never silent.
   **D-021 (the additive-namespace DECISIONS entry) is WRITTEN in the
   commit where the namespace code lands** — the frozen 22-role core is
   untouched.
2. **PROBE-FIRST xtask/finger_probe.py** (RM_FINGER lines, grep-tested
   both shapes): the unknowns — (a) hand-frame stability from the
   canonical wrist→forearm direction on real detections (degenerate when
   the forearm is near-straight/short?); (b) per-finger chain solve
   accuracy vs the 2D kps on real models (the audit's 0.65/0.86 hand
   conf bands); (c) the occlusion gate on hand-behind-back / clenched
   fixtures (100% gated-skip, zero guessed fingers).
3. **Core**: finger chains into the solve path (additive namespace +
   from_dict/to_dict round-trips; pose payload carries them per figure);
   confidence gates with loud skip ledgers.
4. **Apply + gate**: preset mapping for finger bones; RM_FINGER gate
   section (pose-verify sibling shape): the 20-pose hand benchmark class
   (fist/spread/grip/pinch…) with per-finger direction bars (median
   ≤ 20° / p90 ≤ 35° visible), occlusion fixtures 100% gated-skip,
   metarig + Mixamo-class apply ≤ the FK family, loud no-target rig.
5. **Early-finish option**: the P8-2 pin-suggestion inference (keypoint
   proximity) as desk DATA — measured work only, never auto-enforced.

**S27's contract facts S28 builds on** (do not re-learn):

- Coupling landed: `couple_scene(scene, placements)` pure + gated
  (authored + conf ≥ 0.55); the addon couples between the first apply and
  the re-apply with MEASURED placements; report carries per-pin rows +
  unclosable loud. The gate lives at xtask/couple_gate.py wired into
  pose-verify (RM_COUPLE lines grep-pinned).
- The probe→core lift pattern works (coupling_probe.py is the recipe
  coupling.py lifted) — reuse it for fingers.
- The gate fixture-builder rule: TWO-PASS (create every bone, then wire
  parents; a missing parent REFUSES) — alphabetical creation silently
  disconnected limbs and only the real-Blender gate caught it.
- Payload additive-field policy: unknown-field ignore-with-note stands;
  a hands-free payload stays byte-identical (contract-test it).
- The gate env trap (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  grab the broken apt 4.0.2).
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  in-place edits to existing gate/probe files can trip path-traversal
  FPs — a NEW sibling file scans clean (couple_gate.py precedent);
  expect the pagedoc.py import-struct FP at every commit; -F
  commit-message files for heredoc-sensitive text.
- STATE stamps are REAL UTC, read-then-write-then-verify.

## Blocked / deferred (parked — do not burn time)

- RESOLVED (S27 close): the push landed after LO re-authorized gh —
  commits 3ca848d + 8afd49f are on origin/main and CI run 36076363517
  finished GREEN (30 min). No push debt remains.
- Live capture device — parked LAST by LO; P5-4 runs when the phone comes
  up (box side READY; the client just never ran).
- PyPI description + Blender Extensions upload — LO's site-side steps
  (deferred to his final session by LO).
- P6-3 public benchmark suite packaging — roadmap-slack work.
- P6-2a `retarget_clip` session action — the refactor half is DONE; the
  executor wiring is roadmap-slack work.
- P1-8a fallback estimator — parked (D-011/D-012) until P8-9.
- Windowed Blender GL stability — best-effort only, never staged.
