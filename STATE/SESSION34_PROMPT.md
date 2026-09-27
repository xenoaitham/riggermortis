# SESSION 34 PROMPT — riggermortis

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
arch + roll landed (P8-6): the A1 Hermite arch + the D-023 roll namespace,
monotone benchmark, FK bars through the REAL apply, straight arms
BIT-IDENTICAL. Root motion landed (P8-7) as gated additive core — and L7
ended REFUSED-with-evidence (the first exercised Annex A.2 branch): the
drift track + root-motion-aware contact model work and are gated, but the
REAL fixture measurably carries NO root motion (A3 corrected finding), so
walk-in-place ships. Scene animation landed (P8-8): identity-stable
multi-character video → scene actions — swap rate 0.0000 through both
authored label-swap events, the swap alarm catching 2/2, per-frame
coupling through the UNTOUCHED P8-2 pass with placements MEASURED per
frame, the bake cost MEASURED + PUBLISHED, the ambiguity class published
separately with the manual override as the designed answer. Toon renders,
manga pages. Live pose-stream puppeteering on the replay path. No cloud,
no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** V1 = Phase
8 complete + the Scene Test scorecard green (target S35; Annex A.3: the
scorecard overrides the calendar). S33 landed P8-8 (L8 CLOSED). **S34's
rock is P8-9 review UX speedrun + the P1-8a fallback estimator — the last
two ledger openers before the Scene Test**: the per-defect fix
affordances (click a finger, drag the direction; pin nudge; per-figure
flip; per-param face trim) with the time-to-fix bar; the sketch/anime
fallback estimator behind the D-011 dual-estimator interface; **bars: the
median scripted time-to-fix <= 15 s per flagged defect on the benchmark
fixture set (click-through measured, published), else L10 ends REFUSED-
with-evidence; estimator adoption: no-person <= 1/10 on the anime
benchmark, latency <= 2x DWPose CPU, flip-margin parity within the D-010
tolerance on the detected set, else L9 ends REFUSED-with-evidence after
one candidate (the dual-estimator INTERFACE remains); P1-8a IS a third
pinned model — the FULL amendment ritual applies: license, checksum, CPU
budget measured BEFORE adoption, the DECISIONS entry WRITTEN at the
landing; NO fine-tune in the repo, adopted weights only**; NEVER cut P8-3
visible fingers or P8-2 coupling (Annex A cut order).

## S33 contract facts (what S34 builds on)

- **P8-8 LANDED, L8 = CLOSED** (full entry in TASKS.md; numbers in
  BENCHMARKS.md SCENE ANIMATION block): core `scene_anim.py` — the
  identity assignment (pose+scale cost, deterministic Kuhn-Munkres over
  SORTED keys, keyed seed), the evidence swap alarm (continuation-vs-
  chosen cost jump, no GT needed; ALARM_ABS 0.02 / ALARM_REL 0.25
  published with both distributions: event min_abs 0.4463 vs non-event
  max_abs 0.0000), manual overrides winning over everything (marked,
  disagreement reported, excluded from the automatic rate), per-frame
  placements MEASURED from the stream bboxes (SHARED scene origin —
  A1; in-plane, dy == 0 exactly, apparent-size staging), per-frame
  coupling = P8-2's `couple_scene` UNTOUCHED, per-character drift
  tracks = S32 verbatim, `actions_view()` = the certified bake's exact
  per-character input; **30 tests in test_scene_anim.py = 615 total**;
  swap_rate **0.0000** (0/49, bar <= 0.02); ambiguity class **0.1224**
  published separately (the declared single-view limit); coupling
  **13/13** window frames at worst_frac **0.000190**; bake cost
  **0.8–1.0 ms/frame-bake = 1.7–1.9 ms/scene-frame across 2 rigs**
  (MEASURED + PUBLISHED, the Annex publication bar).
- **Gate-earned corrections (S33, in SCENE_ANIMATION.md A1–A3, do not
  re-learn)**: the placements' reference is the SHARED scene origin (a
  per-character reference staged both figures ON the origin and passed
  vacuously); the fixture's contact distance must clear ANATOMY (1.71u
  shoulders vs ~1.35u chain reach — fix the FIXTURE, never the solver);
  a label swap moves the WHOLE data stream (shape AND scale — the
  chimera test fixture was wrong).
- **NOT landed (declared)**: the session/MCP scene-animation wiring
  (the S31/S32 user-facing precedent); the S31 CLI/addon invocation
  wiring for the arch/roll passes; the root-motion BAKE (no real source
  exists locally per A3); real-detector-stream validation (the A.1
  re-validation trigger).
- **Gate env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- **Instrument lessons (S33, do not re-learn)**: Blender can mask a
  crashed script with exit 0 — grep the FINAL row (`RM_SANIM GATE:
  PASS`), never trust the exit code alone; mathutils nested
  rich-compare FLAKY in 5.1 (plain-float tuples only);
  place-update-then-measure (`view_layer.update()` BEFORE any
  world-space read); the session DATE is the UTC date (use the echoed
  `date -u`, not local — S33's local EEST evening was still the same
  UTC day).
- **615 → expect 645+ tests** (S34 adds its own); CI GREEN through the
  S33 pushes (checked at close; appended in PROGRESS). All gate numbers
  through S33 byte-identical (RM_BAKE 0.0242° ×2, RM_FOOT_LOCK
  0.0371→0.0000, RM_MOTION 44997x, RM_SCENE 0.3388/0.8279, RM_COUPLE
  0.00016/0.00035, RM_FINGER 0.0070°/0.00°/10.30°, RM_FACE 6 rows,
  RM_CAM 6 rows, RM_SPINE 5 rows, RM_ROOT 11 grep rows, RM_SANIM 10
  grep rows).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-9 work order below.
- Silent (22nd): proceed with P8-9 directly.
- Then read, in order: STATE/ROADMAP.md (P8-9 + Annex A.1/A.2 — the bars
  are law: median scripted time-to-fix <= 15 s per flagged defect,
  else L10 REFUSED-with-evidence; estimator no-person <= 1/10, latency
  <= 2x DWPose CPU, flip-margin parity within D-010, else L9
  REFUSED-with-evidence after one candidate — the dual-estimator
  INTERFACE remains; the third-model amendment ritual binds P1-8a),
  docs/SCENE_ANIMATION.md + docs/ROOT_MOTION.md (the two newest
  siblings — the design→probe→core→gate pattern), docs/STYLE.md (the
  review overlay's current shape — P8-9 extends it), STATE/NEXT.md,
  STATE/TASKS.md (claim P8-9 with [S34]), STATE/PROGRESS.md (S33
  entries), STATE/DECISIONS.md (D-011/D-012 for P1-8a's history;
  D-023 WRITTEN; D-018 stays reserved), STATE/CONVENTIONS.md,
  STATE/SESSIONS.md, docs/BENCHMARKS.md (the pose-benchmark block the
  time-to-fix bar measures on + the newest blocks), docs/POLICY.md
  (D-019 — review affordances carry artist-authored content; the
  estimator consumes images locally only; MCP stays SFW, test-pinned),
  and the claim-bearing surfaces docs/LAUNCH.md + docs/TUTORIALS.md
  (one grep sweep together IF a number changes).
- Register as Session 34 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**615 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S33 discipline).

## S34 work order — P8-9 Review UX speedrun + P1-8a fallback estimator

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST**: open docs/REVIEW_UX.md (the SCENE_ANIMATION.md
   sibling pattern — never a fork): the per-defect fix affordances ride
   the EXISTING review overlay + the additive namespaces
   (D-021/D-022/D-023 — nothing new to solve, no new canonical roles);
   the time-to-fix INSTRUMENT is declared BEFORE any measurement (the
   scripted click-through: defect injected → the scripted affordance
   sequence → the corrected apply; median over the benchmark fixture
   set, PUBLISHED); the estimator's third-model ritual is declared
   FIRST (license, checksum, CPU budget on the mid-laptop baseline
   BEFORE adoption, the DECISIONS entry WRITTEN at the landing; NO
   fine-tune in the repo). Declare every additive field; NO payload
   format change.
2. **PROBE-FIRST xtask/review_ux_probe.py** (RM_RUX lines, grep-tested
   both shapes before push): (a) the time-to-fix instrument on the
   benchmark fixture set — the median <= 15 s bar (Annex A.1),
   click-through measured, PUBLISHED; (b) the estimator adoption bars
   on the anime benchmark: no-person <= 1/10, latency <= 2x DWPose CPU,
   flip-margin parity within the D-010 tolerance on the detected set;
   (c) the affordances are byte-identity-safe (an untouched pose
   applies identically with the affordances registered); (d) REFUSE
   classes loud; (e) DETERM twins.
3. **Core + add-on**: the affordances as additive overlay data + small
   operators on the EXISTING review/apply paths; the estimator behind
   the D-011 dual-estimator interface ONLY where the ritual passed —
   otherwise the interface ships and the estimator is
   REFUSED-with-evidence (L9's honest terminal).
4. **Gate**: `xtask/review_ux_gate.py` (the sibling file per the Mimosa
   workaround, RM_RUX rows wired into verify_pose_apply.sh + the
   Makefile lint list): the bars above + twin byte-identity + all prior
   numbers byte-identical (incl. the S33 RM_SANIM rows).
5. **If early**: the S33 declared-open scene-animation session wiring,
   or the S31 CLI/addon invocation wiring for the arch/roll passes —
   measured work only, each needs its own gate rows.

Definition of S34 failure (name it, avoid it): a time-to-fix claim
without a measured click-through median, an estimator adoption claim
before the CPU budget measurement, a third pinned model WITHOUT the
amendment ritual (license/checksum/DECISIONS first), an affordance that
moves a byte of the certified apply, a touched frozen-role set /
D-021 / D-022 / D-023 namespace, or ANY claim without a test/gate
citation. Anything 80% done is 0% shipped — park cleanly at a unit
boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored; every inferred thing carries confidence + residual); park
  criteria (two stalled probe/gate cycles → park with evidence,
  reorder); the cut order (P8-9 time-to-fix -> P8-5 full solve
  (CLOSED) -> P8-6 roll (LANDED) — the remaining cuts; NEVER P8-2/P8-3);
  policy D-019 across new surfaces (MCP stays SFW, test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap (above).
- STATE stamps: real UTC, read-then-write-then-verify; the session
  date is the UTC date.
- Mimosa: bash writes of source files blocked — Write/Edit; new sibling
  FILES scan clean where in-place edits trip path FPs (couple_gate.py /
  finger_gate.py / face_gate.py / camera_gate.py / spine_gate.py /
  root_motion_gate.py / scene_anim_gate.py precedent); expect the
  pagedoc.py import-struct FP at every commit; heredoc/append FPs when
  text names source files — Edit tool + -F commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson (pb.matrix.to_translation()),
  joint-angle keying, factory-EMPTY FBX scenes, rotation modes before
  quaternion writes (rotation_mode BEFORE rotation_quaternion!), the
  two-pass fixture-builder rule, place-update-then-measure, the
  wrist-is-body-kp-9 lesson, the girdle-kps-are-rulers fixture law,
  mathutils nested rich-compare FLAKY in 5.1 (plain-float tuples only)
  — the S15..S33 facts in SESSION33_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S35 =
P8-10 the Scene Test + V1 launch per the session map (the composite
scorecard: pin residuals, per-finger accuracy, per-param expression
monotonicity, camera framing IoU, identity swap rate, FK fidelity —
each against its pre-declared bar; pass = every measure green AND every
residual limitation is a labeled choice), UNLESS a park/reorder happened
(say which and why); write STATE/SESSION35_PROMPT.md in this pattern
(contract facts, STEP 0, the P8-10 work order with the scorecard's
measures); update STATE/SESSIONS.md row; commit + push (routine commits
authorized; keep CI green, fix inline like S12..S33); expect and
disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up). PyPI
description + Blender Extensions upload — LO's site-side steps (his final
session). P6-3 packaging + P6-2a wiring — roadmap slack. Windowed
Blender GL stability — best-effort only, never staged. Detector-visible
mannequin fixtures (the P8-5 tier-2 path) — NOT MET with evidence;
reopened only if a detector-visible engine-built fixture path exists.
Root-motion BAKE — declared S32 follow-up; revisit only when a real
root-motion source exists. Scene-animation session/MCP wiring — declared
S33 follow-up (needs its own gate rows).
