# SESSION 26 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Toon renders, manga pages. Live
pose-stream puppeteering shipped on the replay path. No cloud, no accounts,
no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — it is the plan of record,
critic-passed 9.8/10 on independent fresh-subagent verification, and its
Annex A pre-declared bars are LAW for every session from this one on):**
Phase 8 "the Producer" = the V1 scope: coupled multi-character NSFW
scenes (ContactPins + a deterministic coupling pass), FINGERS (the
detected-but-unused hand keypoints), FACIALS (a published
landmark→param table), the reference camera solve, spine arch + roll,
root motion, multi-character video → scene animation, review-UX
speedrun + the anime fallback estimator. **V1 ships when the Scene Test
scorecard is green (target S35 — Annex A.3: the scorecard overrides the
calendar).** Then post-V1: Phase 9 auto-sculpt (proportions + silhouette
volume with the third-model ritual) and Phase 10 text→pose/animation
(the PoseSpec validator, agent path, local-LLM path, measured realism
pass), V2 target ~S45. S26's rock is **P8-1**.

## S25 + triage contract facts (what S26 builds on)

- **P6-1a chain-binding presets (S25)**: preset format 2 (write) /
  formats 1+2 (read); `secondary` bindings via the ONE ChainSpec
  validator; two-layer validation (file-level vs bake-level live-rig
  checks — do not collapse); CLI `preset save --secondary` /
  `preset set-secondary`; `resolve_secondary()` fingerprint gate;
  session `bake_action` params `preset_path`/`preset_force`/`fps`.
  **presets.py is package-imported — its `from . import __version__`
  stays DEFERRED inside `preset_from_mapping`** (module-level there is a
  circular-import crash).
- **P6-2a refactor half (S25)**: the clip-sampler loop lives in
  `riggermortis_addon/clip_sample.py` (bpy imported INSIDE functions,
  conftest-shim testable via the generic `addon_module()` helper in
  conftest.py); `xtask/sample_clip.py` is a thin caller (argv/env glue;
  usage exit 64, refusals 3, DETERM fail 1). Byte-identity PROVEN at
  promotion — the promotion pattern (`git stash push -- <file>` + run +
  pop + diff) is the tool for any future refactor.
- **P6-3 UNBLOCKED (D-020)**: CC0 suite; ControlNet + BY-SA slots
  REPLACED (owned/CC0 art, n=10 kept, honest re-run note for swapped
  slots); LO reviews the photo set at packaging time; in-repo docs/
  distribution; the public suite BECOMES the CI gate fixture; P2-8
  RETIRED as satisfied-by-Xbot. Packaging is roadmap-slack work.
- **P7-5 PyPI DONE (triage)**: riggermortis_core 0.0.1 LIVE —
  https://pypi.org/project/riggermortis-core/0.0.1/ — fresh-venv install
  verified (rigpose CLI runs, PRESET_FORMAT=2 shipped, policy defaults
  OFF). The upload token was env-transient; LO was advised to ROTATE it.
  Nothing in-repo to clean. Remaining: LO's site-side project
  description.
- **P7-4**: LO REGISTERED the blender.org account; publish deliberately
  deferred to LO's FINAL session. Extension zip builds clean on 5.1
  (~80 KB; rebuild right before upload); runbook in docs/PUBLISHING.md.
- **P7-6 PRE-CUT (triage)**: the 60s launch video is BUILT —
  `make launch-cut` (xtask/launch_cut.sh, D-009 shell-glue ffmpeg) from
  committed footage only; parse-back PASS (60.0s/720p30/1800 frames);
  7-shot visual check PASS (3 defects caught+fixed pre-ship). Shot 6
  typesets the REAL tail of a REAL `make gate` run (cached
  out/launch_cut/gate_capture.log; --recapture-gate re-runs). The
  reserved live-shot splice lands after P5-4.
- **Camera DIAGNOSED (triage), PARKED LAST by LO**: /dev/video0 EXISTS
  (v4l2loopback_dc registered) — the 13 silent sessions were the DroidCam
  CLIENT never running + no phone serving 4747 (subnet-scan verified).
  Box side READY (/usr/local/bin/droidcam). When LO brings the phone up
  (WiFi mode, same network, app open): confirm frames with the STEP 0
  command and ASK whether P5-4 jumps the queue — parked, not cancelled.
- **431 tests** (S25 added 20). CI green through 302684c. All gate
  numbers byte-identical through S25 (RM_BAKE 0.0242° ×3, RM_FOOT_LOCK
  0.0371→0.0000 m, RM_SECONDARY 1.81°/280 keys + the PRESET/
  PRESET_GATE rows, RM_TAILS 1.5177→0.2817 m, the RM_MOTION block).
- **D-018 RESERVED** (S18 duplicate-contract amendment — never skip the
  number). **D-021 RESERVED for the finger/face additive namespace** —
  WRITTEN when that code lands (P8-3), never cited as existing before.
- **The Scene Test** (roadmap) is the north star: a two-character
  reference in → coupled, fingered, faced, camera-matched scene out; a
  two-person video in → the same scene animated. Every S26 decision
  should be readable against it.

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P8-1 work order below.
- Silent (14th): proceed with P8-1 directly.
- Then read, in order: STATE/ROADMAP.md (plan of record — the standing
  constraints AND Annex A are law), STATE/NEXT.md, STATE/TASKS.md (claim
  P8-1 with [S26]), STATE/PROGRESS.md (S25 + triage entries),
  STATE/DECISIONS.md (esp. D-003, D-008, D-009, D-015/016, D-017, D-019,
  D-020; D-018 and D-021 RESERVED), STATE/CONVENTIONS.md,
  STATE/SESSIONS.md, docs/SECONDARY_MOTION.md, docs/MOTION_LIBRARY.md,
  docs/LIVE.md, docs/BENCHMARKS.md, docs/POLICY.md, docs/STYLE_LORA.md,
  and the claim-bearing surfaces docs/LAUNCH.md + docs/TUTORIALS.md.
- Register as Session 26 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE —
  do not estimate (S25 misjudged elapsed time five times; every one was
  corrected, none should have existed). Verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**431 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S25 discipline).

## S26 work order — P8-1 CanonicalScene + the Casting Desk + camera v0

The design/probe/build/gate order is NON-NEGOTIABLE (P6-1/P6-2's
discipline; the roadmap's standing constraints apply to every line):

1. **DESIGN-FIRST** in a new docs/SCENES.md (the SECONDARY_MOTION
   pattern — design of record, as-built appended later, never forked):
   - `ScenePose`: N named figures, each a full `CanonicalPose`;
     `ContactPin`: (figure A, role/bone) ↔ (figure B, role/bone),
     authored or suggested — suggestions are data the artist confirms,
     NEVER auto-enforced (the honesty law).
   - Payload v3: ADDITIVE fields only (`figures[]`, `pins[]`); the
     unknown-field policy stays ignore-with-note; v2 readers keep working
     — the back-compat pin is BYTE-IDENTICAL apply of a v2 payload
     through the v3 code (contract test).
   - The Casting Desk UX: one panel listing detected figures × armatures;
     the artist pairs them and applies all in one action. Session/MCP:
     `apply_scene` (v1 additive — KNOWN_ACTION_KINDS grows, the tool
     table does not).
   - Camera v0 semantics: approximate, labeled APPROXIMATE everywhere,
     refuse-to-stage below the confidence floor (Annex A.1: subject bbox
     IoU >= 0.75 vs reference; the floor's DERIVATION publishes in S26's
     benchmark block — strike S12's rule).
2. **PROBE-FIRST** `xtask/scene_probe.py` (RM_SCENE lines, grep-tested
   PASS/FAIL shapes before push): the Blender unknowns — (a) multi-
   armature payload recomputation per rig from ONE payload (the D-009
   recompute path × 2 rigs), (b) the apply order/cleanup semantics for
   two rigs in one scene, (c) camera staging + framing-IoU measurement
   mechanics. Build code only after the probe answers.
3. **Core** `scene.py` + payload v3 + CI tests: loud validation
   (ScenePose/ContactPin from_dict, unknown fields refuse with hints),
   determinism (keyed sorts), v2 back-compat byte-identity, the
   apply-scene contract.
4. **Add-on**: the Casting Desk operator + `apply_scene` session action;
   camera v0 button (stage/refuse per the floor).
5. **Gate**: an RM_SCENE section (verify_pose_apply.sh or a sibling —
   match the house print-shape exactly): 2-rig apply fidelity (the 0.5°
   family), v2 back-compat, camera stage/refuse both shapes demonstrated.
6. **If P8-1 lands early**: the P8-3 fingers DATA AUDIT (measured, not
   assumed): what the detection layer actually exposes of the 133 kps
   today (the payload contract vs the detector output), and the docs/
   FINGERS.md design skeleton. Do NOT start P8-3's build.

Definition of S26 failure (name it, avoid it): scene code that breaks v2
back-compat, a Casting Desk that guesses identity, a camera that stages
without the floor, or ANY claim without a test/gate citation. Anything
80% done is 0% shipped — park cleanly at a unit boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes (D-021 reserved); the coupling/camera honesty law (enforce
  authored, suggest inferred, refuse below floors); park criteria (two
  stalled probe/gate cycles → park with evidence, reorder); the cut
  order (first cut: P8-4 gaze → P8-9 time-to-fix → P8-5 full solve →
  P8-6 roll; NEVER cut P8-2 coupling or P8-3 visible fingers); policy
  D-019 across all new surfaces (MCP stays SFW, test-pinned).
- Fixture law (D-020 + Annex A.3): engine-rendered fixtures for scene
  tests; LO-authored references stay LOCAL, never committed; CC0 only
  for anything shipped.
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose,
  PY=/home/potato/miniconda3/bin/python3 — else they 127 (or grab the
  broken apt 4.0.2).
- STATE stamps: real UTC, read-then-write-then-verify (S25 future-stamped
  five times; the discipline exists because of that).
- Mimosa: bash writes of ANY source-looking file are blocked — use
  Write/Edit; expect the pagedoc.py import-struct FP at every commit and
  push (disclose, move on); heredoc/append FPs when text names source
  files — Edit tool + -F commit-message files.
- Claim-bearing surfaces: README status line / LAUNCH.md / TUTORIALS.md
  change ONLY when a number changes, and get one grep sweep together
  when they do (S25 kept them byte-identical — keep that streak).
- 5.x slotted actions, the posed-head lesson, joint-angle keying,
  factory-EMPTY FBX scenes, rotation modes before quaternion writes —
  the S15..S25 facts in SESSION25_PROMPT.md remain true; skim it if any
  gate touches those paths.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S27 =
P8-2 contact coupling per the session map, UNLESS a park/reorder
happened (say which and why); write STATE/SESSION27_PROMPT.md in this
pattern (contract facts, STEP 0, the P8-2 work order with its Annex
bars: pin residual < 2% torso span, conflict rule, bounded repair);
update STATE/SESSIONS.md row; commit + push (routine commits
authorized; keep CI green, fix inline like S12..S25); expect and
disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device —
DIAGNOSED (see above), parked LAST by LO; P5-4 runs when the phone comes
up. PyPI description + Blender Extensions upload — LO's site-side steps
(deferred to his final session by LO). Windowed Blender GL stability —
best-effort only, never staged. P1-8a — roadmap P8-9.
