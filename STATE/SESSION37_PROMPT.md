# SESSION 37 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes (P8-1), contact
coupling (P8-2), fingers (P8-3), facials (P8-4), the MEASURED camera
(P8-5), spine arch + roll (P8-6), root motion as gated additive core with
L7 REFUSED-with-evidence (P8-7), scene animation (P8-8: swap 0.0000),
review fix affordances (P8-9: L10 CLOSED, L9 REFUSED-with-evidence), and
THE SCENE TEST (P8-10) GREEN — V1's launch gate is MET, the honest-limits
ledger fully CLOSED/REFUSED (the V1 launch announcement itself is a
session-sized event LO owns). **Phase 9 is OPEN: P9-1 proportion
auto-sculpt is MEASURED and LANDED** (S36: the mechanism probe picked
`armature_scale_correctives` — pose-translation correctives, worst frac
0.0000 on both rig classes; the lattice is structurally mesh-only in 5.1,
shape keys structurally cannot move joints; gate = 8 RM_ASCULPT GATE rows
in pose-verify; design of record docs/AUTO_SCULPT.md A1/A2). Toon renders,
manga pages. Live pose-stream puppeteering on the replay path. No cloud,
no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** S37's rock
is **P9-2 volume from silhouette — the deliberate THIRD-MODEL DECISION**.
Volume (hips/waist/bust/thighs — the NSFW-relevant shapes) is a
SILHOUETTE property; getting it needs a segmentation pass = a THIRD
pinned model, which AMENDS the P6-6 never-list ("no weights beyond the
two pinned DWPose models"). That amendment is a written DECISIONS entry
(D-025 is the next free number) with the model's license, size, checksum
pinning, and CPU budget MEASURED on the mid-laptop baseline BEFORE
adoption. If the decision is NO (or no adoptable candidate exists — the
D-024 precedent), the phase ships P9-1 + a documented REFUSED row and
Phase 10 does not wait. **NEVER cut P8-2 coupling or P8-3 visible
fingers (Annex A cut order). NEVER make a volume claim through P9-1's
scope** — P9-1 claims skeleton proportions ONLY.

## S36 contract facts (what S37 builds on)

- **P9-1 LANDED, the mechanism MEASURED**: core `auto_sculpt.py` (the
  ruler set, `build_proportion_target`, `validate_sculpt` = the Annex
  A.1 5% bar instrument, capability lines, `ProportionReport` ships as
  data), addon `auto_sculpt.py` (`apply_proportion_sculpt` —
  pose-translation correctives: parent-first keyed order, measured
  linear response solve, ABSOLUTE-TARGET solves, loud capability
  refusals), gate `xtask/auto_sculpt_gate.py` (8 RM_ASCULPT GATE rows,
  wired into pose-verify). GATE-SCALE worst 0.0000 everywhere;
  GATE-COMPOSE FK 0.0000° + the sculpted girdle width SURVIVES the
  payload pose (drift 1.5e-06 m); twins byte-identical; FULL battery
  PASS with every prior gate number byte-identical.
- **The A1/A2 probe lessons (do not re-learn)**: armature skinning
  RE-BINDS to rest edits — the mesh does NOT follow (pose-space offsets
  are the delivery); `parent_set LATTICE` deforms meshes only (no
  armature lattice in 5.1 — a 20% stretch moves armature heads EXACTLY
  0.0); shape keys deform surface, never joints; float32 noise reads as
  motion below ~1e-6 (follow/width instruments use 1e-6–1e-5 bands);
  relative solves leak R·L_old on re-runs — solve ABSOLUTE targets.
- **634 → 645 tests** (S36 added 11); CI GREEN through the S36 pushes
  (checked at close; appended in PROGRESS). All gate numbers through
  S36 byte-identical (RM_BAKE 0.0242°, RM_FOOT_LOCK 0.0371→0.0000,
  RM_MOTION 44997×, RM_SCENE 0.3388/0.8279, RM_COUPLE 0.00016/0.00035,
  RM_FINGER 0.0070°/0.00°/10.30°, RM_FACE 6 rows, RM_CAM 6 rows,
  RM_SPINE 5 rows, RM_ROOT 11 grep rows, RM_SANIM 10 grep rows, RM_RUX
  10 rows, RST 12 rows incl. GATE, RM_ASCULPT 8 gate rows).
- **D-025 is the next free number** (the P9-1 landing added no pose
  field, so the number was never consumed); D-018 stays reserved.
- **Gate env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3, and for the gate scripts RM_ADDON_DIR=$REPO/
  addon (the package PARENT — the package dir itself ImportErrors) —
  else they 127 (or grab the broken apt 4.0.2).
- **Instrument lessons (standing)**: Blender masks crashed scripts with
  exit 0 — grep the FINAL row (`RM_ASCULPT GATE: PASS` for auto-sculpt);
  place-update-then-measure; mathutils nested rich-compare FLAKY in 5.1
  (plain-float tuples only); the session DATE is the UTC date (`date
  -u`); removing a Blender object orphans its data and the purge kills
  the RNA — capture names BEFORE removal.

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P9-2 work order below.
- Silent (25th): proceed with P9-2 directly.
- Then read, in order: STATE/ROADMAP.md (Phase 9 — P9-2's third-model
  law, the A.1 volume bar, the P6-6 never-list it amends), docs/
  AUTO_SCULPT.md (the P9-1 design of record — the honest-physics
  decomposition P9-2 extends), docs/SCENE_TEST.md + docs/BENCHMARKS.md
  § SCENE TEST (the scorecard that must stay green), STATE/NEXT.md,
  STATE/TASKS.md (claim P9-2 with [S37]), STATE/PROGRESS.md (S36
  entries), STATE/DECISIONS.md (the ledger state; D-018 stays reserved;
  D-025 is the next free number), STATE/CONVENTIONS.md,
  STATE/SESSIONS.md, docs/POLICY.md (D-019 — an input-side model rides
  the same lines), and the claim-bearing surfaces README + docs/
  LAUNCH.md + docs/TUTORIALS.md (one grep sweep together IF a number
  changes — untouched in S36).
- Register as Session 37 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**645 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S36 discipline).

## S37 work order — P9-2 volume from silhouette (the third-model decision)

The ritual order is NON-NEGOTIABLE:

1. **SCAN-FIRST (the ritual's gate)**: survey real segmentation/
   silhouette candidates (ONNX-runnable, local-only, CPU-viable —
   human-matting / portrait-segmentation / person-segmentation
   families). EVERY candidate carries: license verbatim, weights size,
   sha256 + bytes (the P1-1 manifest ritual), input/output contract,
   and a CPU budget measured on THIS box (measure, never assume — the
   P5-1 latency precedent). A candidate WITHOUT an adoptable artifact
   ends the scan REFUSED-with-evidence (the D-024 shape: document what
   exists, why it is not adoptable, scan verbatim — a scan that finds
   nothing is a RESULT, not a failure of effort).
2. **THE DECISION (written, either way)**: adopt → the P6-6 never-list
   amendment is the DECISIONS entry (D-025) with license/checksum/CPU
   budget, written BEFORE any adoption code; refuse → the DECISIONS
   entry documents the refusal with the scan evidence.
3. **If adopted — DESIGN-FIRST docs/VOLUME.md** (the AUTO_SCULPT.md
   sibling): silhouette → body-region volume targets riding the P9-1
   stack (the visible-view scope; depth from declared width priors,
   D-008-declared); the A.1 bar **silhouette IoU >= 0.85 on the
   benchmark, visible-view scoped**; the volume benchmark (silhouette
   IoU of sculpted render vs reference mask); every result lands on
   editable targets (the artist-exit rule); probe-first
   xtask/volume_probe.py (RM_VOL rows), gate wired like S36's; per-
   frame soft tissue stays OUT (P9-3's declared limit).
4. **If refused — the session still lands**: the proportion REPORT +
   auto-sculpt stand as shipped; the refusal entry + the honest-limits
   update; declare the S38 fork (P9-3 sculpt + animation wiring on the
   P9-1 mechanism) — never a half-claimed volume feature.
5. **If early**: the declared wiring items (scene-animation session/MCP
   wiring; the S31 CLI/addon invocation wiring; the P9-1 operator/panel
   wiring if LO asks) — measured work only, each needs its own gate
   rows.

Definition of S37 failure (name it, avoid it): an adoption without the
measured CPU budget + license + checksum (the ritual skipped), a volume
claim from skeleton keypoints (the honest physics — SKELETON is not
VOLUME), a silently-scoped IoU claim (the visible-view scope is part of
the bar), a touched frozen-role set / D-021 / D-022 / D-023 namespace,
or ANY claim without a test/gate citation. Anything 80% done is 0%
shipped — park cleanly at a unit boundary.

Watch out for (standing, earned — do not re-learn):

- The roadmap's standing constraints are law: additive-only canonical
  changes; the honesty law (suggest what's inferred, enforce what's
  authored; every inferred thing carries confidence + residual); park
  criteria (two stalled probe/gate cycles → park with evidence,
  reorder); the cut order (NEVER P8-2/P8-3); policy D-019 across new
  surfaces (MCP stays SFW, test-pinned; the model's download path is
  the P1-1 manifest flow — checksum-pinned, user-initiated, zero
  default-use outbound).
- Fixture law (Annex A.3): engine-rendered/engine-built fixtures;
  LO-authored references stay LOCAL, never committed; CC0 only for
  anything shipped.
- The gate env trap (above).
- STATE stamps: real UTC, read-then-write-then-verify; the session date
  is the UTC date.
- Mimosa: bash writes of source files blocked — Write/Edit; the scanner
  blocks env-sourced path-write shapes in gate scripts (zero-IO gates
  are the proven shape); new sibling FILES scan clean where in-place
  edits trip path FPs; expect the pagedoc.py import-struct FP at every
  commit; heredoc/append FPs when text names source files — Edit tool
  + -F commit-message files.
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson, joint-angle keying,
  factory-EMPTY FBX scenes, rotation modes before quaternion writes,
  the two-pass fixture-builder rule, place-update-then-measure, the
  wrist-is-body-kp-9 lesson, mathutils nested rich-compare FLAKY in
  5.1 (plain-float tuples only), the operator return/poll/ERROR-report
  classes, the S36 RNA-purge lesson (capture datablock names before
  removal), the absolute-target solve law — the S15..S36 facts in
  SESSION36_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S38 =
P9-3 sculpt + animation wiring (static sculpt at frame one before
animation drives the rig; the operator/panel wiring; per-frame soft
tissue OUT) per the session map — UNLESS P9-2 ended REFUSED-with-
evidence (then S38 STILL opens P9-3: the refusal ships P9-1 + the
documented refusal, Phase 10 does not wait — say which shape) or a
park/reorder happened (say which and why); write
STATE/SESSION38_PROMPT.md in this pattern (contract facts, STEP 0, the
next work order); update STATE/SESSIONS.md row; commit + push (routine
commits authorized; keep CI green, fix inline like S12..S36); expect
and disclose the Mimosa pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up; silent 24
straight sessions through S36). PyPI description + Blender Extensions
upload — LO's site-side steps (his final session). P6-3 packaging +
P6-2a wiring — roadmap slack. Windowed Blender GL stability —
best-effort only, never staged. Detector-visible mannequin fixtures (the
P8-5 tier-2 path) — NOT MET with evidence; reopened only if a
detector-visible engine-built fixture path exists. Root-motion BAKE —
revisit only when a real root-motion source exists. Scene-animation
session/MCP wiring — declared S33 follow-up (needs its own gate rows).
The anime fallback estimator — REFUSED-with-evidence (D-024); reopened
only through the full P1-1 third-model ritual with a real candidate.
The P9-1 operator/panel wiring — P9-3's declared scope.
