# SESSION 27 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes landed (P8-1): one
payload poses N paired rigs in one action, pins carried as data, an
APPROXIMATE camera stages from the reference framing above the measured
floor. Toon renders, manga pages. Live pose-stream puppeteering on the
replay path. No cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** V1 = Phase
8 complete + the Scene Test scorecard green (target S35; Annex A.3: the
scorecard overrides the calendar). S26 landed P8-1. **S27's rock is P8-2
contact coupling** — the "not touching = bad" fix; NEVER cut (Annex A cut
order), never enforced without the artist's authored pin.

## S26 contract facts (what S27 builds on)

- **P8-1 LANDED** (full entry in TASKS.md; numbers in BENCHMARKS SCENE):
  core `scene.py` — SceneFigure/ContactPin/ScenePose (scene format 1;
  loud validation; figures label-SORTED, pins in AUTHORED ORDER — that
  order is P8-2's precedence; self-figure pins refuse; byte-stable
  round-trip); `scene_from_payload` is the ONE builder;
  `validate_casting` allows SUBSETS (uncast labels reported by the apply,
  never silent; unknown-label/double-cast/unknown-armature refuse).
- **Payload v3 ADDITIVE**: FORMAT=3 write, formats 1+2+3 read; optional
  top-level `pins` (each validated by `ContactPin.from_dict` — the ONE
  validator: origin ∈ {authored, suggested}, confidence [0,1]); a pins-free
  v3 file differs from v2 output only in the format int; **a v2 payload
  through v3 code applies BYTE-IDENTICALLY** (pinned contract test);
  old builds refuse v3 files loudly (accepted house pattern).
- **apply_scene session action** (KNOWN_ACTION_KINDS 5→6 BOTH bridge
  sides; MCP tool table UNCHANGED — it rides enqueue_action, schema stays
  v1): casting validated BEFORE any pose is written, then the REAL
  per-figure apply_payload (tails repair per figure, one undo push);
  report carries per_figure rows + figures_uncast + pins CARRIED AND
  REPORTED, never enforced.
- **The Casting Desk** (addon/casting_desk.py — operators live there after
  Mimosa FP'd on execute-bodies in __init__; rows via RM_CastSlot
  CollectionProperty on the scene, saved with the .blend; refresh is
  APPEND-ONLY): rm.cast_refresh / rm.apply_scene / rm.stage_scene_camera
  + RM_PT_casting_desk. The desk NEVER guesses identity.
- **Camera v0** (addon/scene_camera.py): front-prior closed-form solve
  (50 mm, width fraction + center; pinned projection: u = 0.5 − Δx/d·
  f/sensor_w, v = 0.5 + Δz/d·f/sensor_h, sensor_h = sensor_w·res_y/res_x;
  world_to_camera_view is v-UP, UNCLAMPED — flip + clamp the reference),
  measures its own framing, **stages iff IoU >= 0.75 else REFUSES**
  (restores the previous scene camera, deletes the created one).
  Floor derivation published (SYNTHETIC-labeled): solved 0.9657 vs
  degraded 0.4684 / 0.1324. **THE LESSON: place, view_layer.update(),
  THEN measure** — world_to_camera_view reads a stale matrix_world
  otherwise (the gate honestly failed at 0.07-0.65 until fixed).
- **RM_SCENE gate section** (xtask/scene_gate.py inside verify_pose_apply.sh;
  gate fmt checks accept formats 2|3): CASTING 3/3 refusals + subset valid;
  APPLY2 (real session executor, real 12-figure detector payload, 2 rigs)
  worst 0.0198°/0.0063° bar 0.5; V2-BACKCOMPAT byte-identical 38 bones;
  CAMERA-REFUSE 0.3388 nothing staged; CAMERA-STAGE 0.8279 labeled
  APPROXIMATE. The gate's camera benchmark derives the scene layout FROM
  the reference (posed-aspect fixture loop) — a mismatched layout measures
  nothing about the solver.
- **P8-3 audit DONE, build NOT started**: docs/FINGERS.md (all 133 kps +
  confidences reach the detection payload; the drop is at the canonical
  solve; hand conf means 0.65/0.86 measured, 0/21 dropouts). **D-021 stays
  RESERVED — written only when finger/face code lands (S28), never cited
  as existing before.** D-018 also stays RESERVED (live amendment).
- **431 → 459 tests** (S26 added 28); CI green through the S26 push; all
  gate numbers through S26 byte-identical (RM_BAKE 0.0242° ×2,
  RM_FOOT_LOCK 0.0371→0.0000, RM_SECONDARY 1.81°/280, RM_TAILS
  1.5177→0.2817, RM_MOTION LOCK 44997×, RM_SCENE rows above).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-2 work order below.
- Silent (15th): proceed with P8-2 directly.
- Then read, in order: STATE/ROADMAP.md (P8-2 + Annex A.1/A.2 — bars are
  law), docs/SCENES.md (P8-2 EXTENDS this page, never forks it),
  STATE/NEXT.md, STATE/TASKS.md (claim P8-2 with [S27]), STATE/PROGRESS.md
  (S26 entries), STATE/DECISIONS.md, STATE/CONVENTIONS.md,
  STATE/SESSIONS.md, docs/BENCHMARKS.md (SCENE block), docs/FINGERS.md
  (audit only — do NOT start P8-3), docs/POLICY.md, and the claim-bearing
  surfaces docs/LAUNCH.md + docs/TUTORIALS.md.
- Register as Session 27 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**459 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S26 discipline).

## S27 work order — P8-2 Contact coupling

The design/probe/build/gate order is NON-NEGOTIABLE:

1. **DESIGN-FIRST: extend docs/SCENES.md** — the coupling pass (deterministic
   iterative redistribution over the canonical figures) hooked AFTER the
   per-figure solves and BEFORE the bake. **Conflict rule (pre-declared)**:
   pins resolve in AUTHORED order, weighted by per-role confidence;
   over-determined sets solve least-squares with a keyed iteration order
   (deterministic); every pin REPORTS its residual; unclosable pins stay
   loud; the solve never moves a role below its confidence floor.
   Enforcement = AUTHORED pins only; suggested pins are confirmed in the
   Casting Desk first (the honesty law). The pin-SUGGESTION inference
   (keypoint proximity) is P8-2 work too — it feeds the desk as data,
   never auto-enforced.
2. **PROBE-FIRST xtask/coupling_probe.py** (RM_COUPLE lines, grep-tested
   both shapes before push): (a) convergence on the hold-from-behind-class
   fixture within the bar; (b) non-chain roles byte-identical through the
   solve; (c) the competing-pins conflict case behaves per the rule.
3. **Core**: the coupling pass (pure, deterministic, keyed sorts) over
   ScenePose figures; per-pin residuals; bounded repair (Annex A.2: one
   default cycle, then rigid pin-SNAP reported as such → L1 CLOSED-LIMITED
   in DECISIONS).
4. **Gate**: RM_COUPLE section (scene_gate.py sibling shape): engine-built
   hold-from-behind fixture (Annex A.3 — no external sourcing), pin
   residual < **2% torso span**, non-chain roles ≤ **0.5°** (chain roles on
   resolved pins report deviation as pin cost), twin-run byte-identical,
   conflict case gated.
5. **If early**: the suggestion inference as desk data, or P8-3 prep —
   measured work only.

Definition of S27 failure (name it, avoid it): a coupling pass that moves
unauthored contact, breaks v2 back-compat, guesses identity, enforces a
suggested pin, or ANY claim without a test/gate citation. Anything 80%
done is 0% shipped — park cleanly at a unit boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes (D-021 reserved for fingers/faces); the honesty law; park
  criteria (two stalled probe/gate cycles → park with evidence, reorder);
  the cut order (P8-4 gaze → P8-9 time-to-fix → P8-5 full solve → P8-6
  roll; NEVER cut P8-2 coupling or P8-3 visible fingers); policy D-019
  across new surfaces (MCP stays SFW, test-pinned).
- Fixture law (Annex A.3): engine-rendered/engine-built scene fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/blender,
  RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3 — else they 127 (or grab the broken apt 4.0.2).
- STATE stamps: real UTC, read-then-write-then-verify.
- Mimosa: bash writes of source files blocked — Write/Edit; expect the
  pagedoc.py import-struct FP at every commit; the S26 SQL-injection FP on
  operator-execute bodies in __init__ (no SQL exists; new operator classes
  go in module files); heredoc/append FPs when text names source files —
  Edit tool + -F commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson (pb.matrix.to_translation()),
  joint-angle keying, factory-EMPTY FBX scenes, rotation modes before
  quaternion writes, the posed-subject extent surprises in camera work —
  the S15..S26 facts in SESSION26_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S28 =
P8-3 fingers per the session map (D-021 WRITTEN at that landing), UNLESS a
park/reorder happened (say which and why); write STATE/SESSION28_PROMPT.md
in this pattern (contract facts, STEP 0, the P8-3 work order with its Annex
bars: median ≤ 20° / p90 ≤ 35° visible fingers, 100% gated-skip on
occlusion fixtures); update STATE/SESSIONS.md row; commit + push (routine
commits authorized; keep CI green, fix inline like S12..S26); expect and
disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up). PyPI
description + Blender Extensions upload — LO's site-side steps (his final
session). P6-3 packaging + P6-2a wiring — roadmap slack. P1-8a — P8-9.
Windowed Blender GL stability — best-effort only, never staged.
