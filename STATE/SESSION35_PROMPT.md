# SESSION 35 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes (P8-1), contact
coupling (P8-2), fingers (P8-3), facials (P8-4), the MEASURED camera
(P8-5), spine arch + roll (P8-6), root motion as gated additive core with
L7 REFUSED-with-evidence (P8-8 scene animation: identity-stable
multi-character video → scene actions, swap rate 0.0000). Review fix
affordances landed (P8-9): the four authored corrections (finger drag /
face trim / figure flip / pin retarget+confirm) ride the existing
namespaces and apply paths, the DECLARED scripted click-through instrument
measures median time-to-fix 2.00 s over 54 flagged defects (bar 15 s) →
**L10 CLOSED**; the anime fallback estimator ends **L9 REFUSED-with-
evidence after one candidate** (no adoptable anime/sketch whole-body
estimator exists — D-024's scan evidence), the dual-estimator INTERFACE
ships (protocol + keyed fallback + the additive `estimator` payload
provenance field). **THE LEDGER IS FULLY CLOSED/REFUSED — every L-row.**
Toon renders, manga pages. Live pose-stream puppeteering on the replay
path. No cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** V1 = the
Scene Test scorecard green (Annex A.3: the scorecard overrides the
calendar). **S35's rock is P8-10 the Scene Test + V1 launch**: one E2E
scenario on engine-rendered couple fixtures (the A.3 fixture law — the
pipeline's own deterministic renderer, clothed + the SFW fallback; NO
external sourcing; LO-authored references stay LOCAL, never committed),
INDEPENDENT measures per stage against the pre-declared Annex A.1 bars,
assembled into ONE table in docs/BENCHMARKS.md; pass = every measure green
AND every residual limitation is a labeled choice; then the launch
surfaces (README/LAUNCH/TUTORIALS) refreshed to claim exactly the scored
reality. The scorecard measures: pin residuals (< 2% torso span),
per-finger accuracy (median <= 20 deg / p90 <= 35 deg visible), per-param
expression monotonicity (>= 9/10), camera framing IoU (>= 0.75), identity
swap rate (<= 2%, alarm >= 90%), FK fidelity (<= 0.5 deg family).
NEVER cut P8-2 coupling or P8-3 visible fingers (Annex A cut order).

## S34 contract facts (what S35 builds on)

- **P8-9 LANDED, L10 = CLOSED, L9 = REFUSED-with-evidence** (full entry in
  TASKS.md; numbers in BENCHMARKS.md REVIEW-UX; verdicts in DECISIONS.md
  D-024): the instrument's interaction-cost model (CLICK 1.0 / DRAG 3.0 /
  SLIDER 2.0) was declared BEFORE any measurement with the op wall-clock
  published alongside; the probe ran draft-first and re-ran against the
  core with numbers reproduced exactly; the gate drives the REAL operators
  (10 RM_RUX rows). The estimator refusal is a FIRST-CLASS terminal: the
  manifest stays exactly the two pinned DWPose models (RUX-EST-RITUAL
  pins it); any future candidate enters ONLY through the P1-1 ritual.
- **Gate-earned operator facts (S34, do not re-learn)**: execute() returns
  `{'FINISHED'}` — never `{'REGISTER'}` (five legacy operators were broken
  on 5.1 until S34; no earlier gate ever invoked ops through bpy.ops);
  operators subclass an Operator MIXIN (`_SceneFixOp(Operator)`), never
  `(Operator, mixin)` — the MRO refuses; background Blender RAISES an
  operator's `report({'ERROR'})` at the invoking script (and a failed poll
  raises its own RuntimeError) — both are the loud CANCELLED path.
- **NOT landed (declared)**: viewport drag-gizmo polish (the operators ARE
  the interactive surface); scene-animation session/MCP wiring (S33
  follow-up); the S31 CLI/addon invocation wiring; the root-motion BAKE;
  real-detector-stream validation (the A.1 re-validation trigger).
- **Gate env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- **Instrument lessons (S34, do not re-learn)**: Blender masks crashed
  scripts with exit 0 — grep the FINAL row (`RM_RUX GATE: PASS`); the
  Mimosa scanner blocks env-sourced file-WRITE shapes in gate scripts —
  the ZERO-IO gate pattern is the proven shape (ops read the payloads
  verify_pose_apply.sh already generates; fixtures live in memory);
  place-update-then-measure; mathutils nested rich-compare FLAKY in 5.1
  (plain-float tuples only); the session DATE is the UTC date (use the
  echoed `date -u`).
- **634 → expect 650+ tests** (S35 adds its own); CI GREEN through the
  S34 pushes (checked at close; appended in PROGRESS). All gate numbers
  through S34 byte-identical (RM_BAKE 0.0242° ×2, RM_FOOT_LOCK
  0.0371→0.0000, RM_MOTION 44997x, RM_SCENE 0.3388/0.8279, RM_COUPLE
  0.00016/0.00035, RM_FINGER 0.0070°/0.00°/10.30°, RM_FACE 6 rows,
  RM_CAM 6 rows, RM_SPINE 5 rows, RM_ROOT 11 grep rows, RM_SANIM 10
  grep rows, RM_RUX 10 rows).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-10 work order below.
- Silent (23rd): proceed with P8-10 directly.
- Then read, in order: STATE/ROADMAP.md (The Scene Test + Annex A — the
  scorecard bars are LAW; A.3 precedence: the scorecard overrides the
  calendar; the fixture law), docs/REVIEW_UX.md (the S34 as-built + the
  gate-earned corrections), docs/SCENES.md + docs/SCENE_ANIMATION.md +
  docs/CAMERA.md + docs/FINGERS.md + docs/FACE.md (the surfaces the Scene
  Test composes), STATE/NEXT.md, STATE/TASKS.md (claim P8-10 with [S35]),
  STATE/PROGRESS.md (S34 entries), STATE/DECISIONS.md (D-024 — the ledger
  is closed/refused; D-018 stays reserved), STATE/CONVENTIONS.md,
  STATE/SESSIONS.md, docs/BENCHMARKS.md (every block the scorecard
  composes), docs/POLICY.md (D-019 — engine-rendered fixtures; MCP stays
  SFW, test-pinned), and the claim-bearing surfaces README + docs/LAUNCH.md
  + docs/TUTORIALS.md (the V1 refresh: they MUST claim exactly the scored
  reality — one grep sweep together).
- Register as Session 35 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**634 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S34 discipline).

## S35 work order — P8-10 the Scene Test + V1 launch

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST**: open docs/SCENE_TEST.md (the REVIEW_UX.md sibling —
   never a fork): the fixture plan (engine-rendered couple scenes through
   the pipeline's own deterministic renderer; clothed mannequins + the SFW
   fallback; deterministic; nothing external committed), the scorecard's
   measures + bars VERBATIM from Annex A.1, the labeled-choices section
   (every residual limitation must be a labeled choice: gated skips,
   unclosable pins, camera error bars, the AMBIGUITY class, walk-in-place,
   the L9 estimator refusal, the D-008 miss classes), and the optimism
   caveat verbatim on every synthetic-derived claim.
2. **PROBE/BUILD xtask/scene_test_probe.py** (RST lines, grep-tested both
   shapes before push): run the E2E chain on the fixture set — reference
   render -> detect -> solve -> scene + pins + fingers + face + camera +
   (video path) identity assignment -> apply/couple/bake — MEASURING each
   scorecard row independently, each against its Annex A.1 bar.
3. **The scorecard table** lands in docs/BENCHMARKS.md SCENE TEST block:
   every measure with its number, bar, and verdict; the labeled choices;
   nothing averaged, nothing hidden.
4. **Pass = every measure green AND every residual limitation labeled** →
   V1 launch prep: README/LAUNCH/TUTORIALS refreshed to claim exactly the
   scored reality (one grep sweep together), the ledger cited as fully
   CLOSED/REFUSED. A missed measure = the A.3 precedence (the scorecard
   overrides the calendar; the honest miss is published, the launch waits).
5. **If early**: the declared wiring items (scene-animation session/MCP
   wiring; the S31 CLI/addon invocation wiring) — measured work only,
   each needs its own gate rows.

Definition of S35 failure (name it, avoid it): a scorecard row without a
measured number, a bar quietly reinterpreted to pass, a residual
limitation averaged into a rate instead of labeled, a launch claim without
a test/gate citation, an external fixture committed against the A.3 law,
or ANY claim without a test/gate citation. Anything 80% done is 0%
shipped — park cleanly at a unit boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored; every inferred thing carries confidence + residual); park
  criteria (two stalled probe/gate cycles → park with evidence, reorder);
  the cut order (NEVER P8-2/P8-3); policy D-019 across new surfaces (MCP
  stays SFW, test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap (above).
- STATE stamps: real UTC, read-then-write-then-verify; the session date
  is the UTC date.
- Mimosa: bash writes of source files blocked — Write/Edit; the scanner
  blocks env-sourced path-write shapes in gate scripts (zero-IO gates are
  the proven shape); new sibling FILES scan clean where in-place edits
  trip path FPs (couple_gate.py / finger_gate.py / face_gate.py /
  camera_gate.py / spine_gate.py / root_motion_gate.py / scene_anim_gate.py
  / review_ux_gate.py precedent); expect the pagedoc.py import-struct FP
  at every commit; heredoc/append FPs when text names source files —
  Edit tool + -F commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson (pb.matrix.to_translation()),
  joint-angle keying, factory-EMPTY FBX scenes, rotation modes before
  quaternion writes, the two-pass fixture-builder rule,
  place-update-then-measure, the wrist-is-body-kp-9 lesson, the
  girdle-kps-are-rulers fixture law, mathutils nested rich-compare FLAKY
  in 5.1 (plain-float tuples only), the operator return/poll/ERROR-report
  classes — the S15..S34 facts in SESSION34_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S36 =
Phase 9 opens (P9-1 proportion auto-sculpt: the mechanism probe — lattice
vs shape-key binding vs scale-correctives; selection bar 5% on metarig +
Mixamo-class, fewest rig artifacts, name-ascending tie-break) per the
session map, UNLESS the Scene Test missed a measure (then the honest
repair/reorder per A.3, say which and why); V1's launch itself is a
session-sized event LO owns the announcements of; write
STATE/SESSION36_PROMPT.md in this pattern (contract facts, STEP 0, the
next work order); update STATE/SESSIONS.md row; commit + push (routine
commits authorized; keep CI green, fix inline like S12..S34); expect and
disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up). PyPI
description + Blender Extensions upload — LO's site-side steps (his final
session). P6-3 packaging + P6-2a wiring — roadmap slack. Windowed
Blender GL stability — best-effort only, never staged. Detector-visible
mannequin fixtures (the P8-5 tier-2 path) — NOT MET with evidence;
reopened only if a detector-visible engine-built fixture path exists.
Root-motion BAKE — revisit only when a real root-motion source exists.
Scene-animation session/MCP wiring — declared S33 follow-up (needs its
own gate rows). The anime fallback estimator — REFUSED-with-evidence
(D-024); reopened only through the full P1-1 third-model ritual with a
real candidate.
