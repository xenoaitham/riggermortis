# SESSION 28 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes landed (P8-1): one
payload poses N paired rigs in one action, pins carried as data, an
APPROXIMATE camera stages from the reference framing. Contact coupling
landed (P8-2): AUTHORED pins close deterministically (fracs 0.00016/0.00035
vs the 0.02 bar), suggested/below-floor pins stay loud data, the solve is
pure position-space surgery the certified apply consumes unchanged. Toon
renders, manga pages. Live pose-stream puppeteering on the replay path.
No cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** V1 = Phase
8 complete + the Scene Test scorecard green (target S35; Annex A.3: the
scorecard overrides the calendar). S27 landed P8-2. **S28's rock is P8-3
fingers** — the additive finger namespace (D-021 WRITTEN at that landing,
never cited before), per-finger confidence gates (occluded = skipped +
flagged, never guessed), preset-mapped apply; NEVER cut (Annex A cut
order), never guessed fingers.

## S27 contract facts (what S28 builds on)

- **P8-2 LANDED** (full entry in TASKS.md; numbers in BENCHMARKS COUPLING):
  core `coupling.py` — `couple_scene(scene, placements)` PURE +
  deterministic (pins in AUTHORED order = precedence; joints root→leaf
  keyed); enforcement = `origin == "authored" AND confidence >= 0.55`
  (the CONVENTIONS bar reused — the PIN's confidence gates, role joint
  confidence feeds the split weights w ∝ 1−c); declared movable-chain
  table (distal limb chains only, girdle/anchor endpoints rigid); damped
  sequential carry (MAX_ITERS 32, EARLY_EXIT_FRAC 2e-4); per-pin
  residuals normalized by mean torso span, unclosable loud.
- **Addon hook**: `apply_scene_payload` = apply → update → placements
  MEASURED from posed rigs (t = world(anchor) − s·R·canonical(anchor);
  R row-normalized; s = posed torso span/0.45) → couple → FULL-precision
  coupled write-back into the in-memory payload → re-apply → `coupling`
  report block. Session `apply_scene` gains optional `couple` (default
  true); KNOWN_ACTION_KINDS + MCP tool tables unchanged.
- **Gate**: `xtask/couple_gate.py` (scene_gate's SIBLING — new files scan
  clean where in-place edits trip Mimosa path FPs) wired into
  verify_pose_apply.sh: RESIDUAL fracs 0.00016/0.00035 (bar 0.02)
  worst_fk 0.0000°; NONCHAIN non-subtree positions byte-equal + live fk
  worst 0.014° (riding subtrees swing rigidly — coupled physics, the
  "unchanged" bar is core-side byte-exact + the 0.5° family); TWIN 42
  bones byte-identical; CONFLICT compromise reported, unclosable loud;
  NOENFORCE suggested pin byte-equal + reason.
- **Fixture-builder law (NEW, earned)**: two-pass build (create every
  bone, THEN wire parents; a missing parent REFUSES) — alphabetical
  creation with a silent `parent in bones` fallback disconnected limbs
  and only the real-Blender gate caught it (the S9 class, again).
- **P8-3 audit DONE** (docs/FINGERS.md): all 133 kps + confidences reach
  the detection payload (hand conf means 0.65/0.86, 0/21 dropouts); the
  drop is at `observations_from_keypoints` (reads only body/foot
  indices). P8-3 = a SOLVE+PAYLOAD+APPLY extension; no new model, no
  wrapper change, P6-6 never-list untouched. **D-021 stays RESERVED —
  WRITTEN only when the finger/face code lands (S28), never cited as
  existing before. D-018 also stays RESERVED.**
- **459 → 482 tests** (S27 added 23 coupling contract tests); CI green
  through the S27 push; all gate numbers through S27 byte-identical
  (RM_BAKE 0.0242° ×2, RM_FOOT_LOCK 0.0371→0.0000, RM_SECONDARY rows,
  RM_TAILS 1.5177→0.2817, RM_MOTION, RM_SCENE, RM_COUPLE).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-3 work order below.
- Silent (16th): proceed with P8-3 directly.
- Then read, in order: STATE/ROADMAP.md (P8-3 + Annex A.1/A.2 — bars are
  law: median ≤ 20° / p90 ≤ 35° VISIBLE fingers, 100% gated-skip on the
  occlusion fixtures, per-class REFUSED branch), docs/FINGERS.md (the
  audit + design skeleton — EXTEND it, never fork it), docs/SCENES.md
  (P8-2 as-built = the probe→core lift pattern), STATE/NEXT.md,
  STATE/TASKS.md (claim P8-3 with [S28]), STATE/PROGRESS.md (S27
  entries), STATE/DECISIONS.md, STATE/CONVENTIONS.md,
  STATE/SESSIONS.md, docs/BENCHMARKS.md (SCENE + COUPLING blocks),
  docs/POLICY.md, and the claim-bearing surfaces docs/LAUNCH.md +
  docs/TUTORIALS.md (one grep sweep together IF a number changes).
- Register as Session 28 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**482 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S27 discipline).

## S28 work order — P8-3 Fingers

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST: extend docs/FINGERS.md** — the as-built design: the
   additive per-figure `hands` payload field (format 3 unchanged,
   optional top-level-per-figure; readers ignoring unknown fields keep
   working byte-identically — contract-test a hands-free payload);
   COCO-WholeBody hand layout via NAMED constants in poses.py (wrist +
   5 fingers × 4 mcp/pip/dip/tip, thumb→pinky) added the same commit;
   per-finger 3-joint chains (mcp→pip, pip→dip, dip→tip) solved ONLY
   from observed kps, wrist-anchored, hand frame from the canonical
   wrist→forearm direction; per-finger confidence gates (occluded =
   skipped + FLAGGED, never guessed — a wrong finger reads as broken, an
   absent one as clean); apply via preset mapping (authored once per
   rig); a rig without finger targets reports a loud capability line.
   **D-021 WRITTEN in the commit where the namespace code lands** — the
   frozen 22-role core untouched.
2. **PROBE-FIRST xtask/finger_probe.py** (RM_FINGER lines, grep-tested
   both shapes before push): (a) hand-frame stability from the canonical
   wrist→forearm direction on real detections; (b) per-finger chain
   accuracy on real models (the audit's 0.65/0.86 hand conf bands);
   (c) the occlusion gate on hand-behind-back / clenched fixtures (100%
   gated-skip, zero guessed fingers).
3. **Core**: finger chains into the solve path (additive namespace +
   loud validation + round-trips; the pose payload carries hands per
   figure; skip ledgers per finger).
4. **Gate**: RM_FINGER section (pose-verify sibling shape, new file per
   the Mimosa workaround): the 20-pose hand benchmark class
   (fist/spread/grip/pinch…) — per-finger direction bars (median ≤ 20° /
   p90 ≤ 35° visible fingers), occlusion fixtures 100% gated-skip,
   metarig + Mixamo-class apply ≤ the FK family, loud no-target rig.
5. **If early**: the P8-2 pin-suggestion inference (keypoint proximity)
   as desk DATA — measured work only, never auto-enforced.

Definition of S28 failure (name it, avoid it): a guessed finger, an
ungated occluded finger, a touched frozen-role set, a D-021 citation
before its commit, a hands-free payload byte change, or ANY claim
without a test/gate citation. Anything 80% done is 0% shipped — park
cleanly at a unit boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored); park criteria (two stalled probe/gate cycles → park with
  evidence, reorder); the cut order (P8-4 gaze → P8-9 time-to-fix →
  P8-5 full solve → P8-6 roll; NEVER cut P8-3 visible fingers or P8-2
  coupling); policy D-019 across new surfaces (MCP stays SFW,
  test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- STATE stamps: real UTC, read-then-write-then-verify.
- Mimosa: bash writes of source files blocked — Write/Edit; new sibling
  FILES scan clean where in-place edits trip path FPs (couple_gate.py
  precedent); expect the pagedoc.py import-struct FP at every commit;
  heredoc/append FPs when text names source files — Edit tool + -F
  commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson (pb.matrix.to_translation()),
  joint-angle keying, factory-EMPTY FBX scenes, rotation modes before
  quaternion writes, the posed-subject extent surprises in camera work,
  place-update-then-measure, the two-pass fixture-builder rule — the
  S15..S27 facts in SESSION27_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S29 =
P8-4 facials per the session map, UNLESS a park/reorder happened (say
which and why); write STATE/SESSION29_PROMPT.md in this pattern (contract
facts, STEP 0, the P8-4 work order with its Annex bars: per-param
monotonicity ≥ 9/10 on the 10-state benchmark, bone apply ≤ 0.5° family,
shape-key delta ≤ 0.1 normalized, gaze ONLY with iris kps); update
STATE/SESSIONS.md row; commit + push (routine commits authorized; keep
CI green, fix inline like S12..S27); expect and disclose the Mimosa
pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up). PyPI
description + Blender Extensions upload — LO's site-side steps (his final
session). P6-3 packaging + P6-2a wiring — roadmap slack. P1-8a — P8-9.
Windowed Blender GL stability — best-effort only, never staged.
