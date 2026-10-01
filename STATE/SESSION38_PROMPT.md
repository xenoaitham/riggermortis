# SESSION 38 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Multi-figure scenes (P8-1), contact
coupling (P8-2), fingers (P8-3), facials (P8-4), the MEASURED camera
(P8-5), spine arch + roll (P8-6), root motion as gated additive core with
L7 REFUSED-with-evidence (P8-7), scene animation (P8-8: swap 0.0000),
review fix affordances (P8-9: L10 CLOSED, L9 REFUSED-with-evidence), THE
SCENE TEST (P8-10) GREEN — V1's launch gate MET, the honest-limits ledger
fully CLOSED/REFUSED (the V1 launch announcement itself is a session-sized
event LO owns). Phase 9: P9-1 proportion auto-sculpt MEASURED and LANDED
(S36: `armature_scale_correctives`, pose-translation delivery, worst frac
0.0000). P9-2 volume from silhouette MEASURED and LANDED (S37: D-025
ADOPTED `u2net.onnx` — the P6-6 never-list amends to three — and
`shape_key_inflate` SELECTED, worst region IoU 0.9499 vs bar 0.85, joints
byte-identical through the key warp). Toon renders, manga pages. Live
pose-stream puppeteering on the replay path. No cloud, no accounts, no
uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).

**THE MISSION (read STATE/ROADMAP.md first — plan of record, critic-passed
9.8/10, Annex A pre-declared bars are LAW for every session):** S38's rock
is **P9-3 sculpt + animation wiring** — the declared unit-boundary debt
(S31/S36/S37 precedents) comes due: the user-facing flow wires the P9-1
proportion sculpt + the P9-2 volume sculpt (operator/panel, the
solve-flow integration, the session action), and the animation-order
proof lands (the static sculpt applies at frame one BEFORE animation
drives the rig; the sculpted widths SURVIVE the animation at FK bars).
Per-frame soft tissue stays OUT (declared — simulation is a different
product). **NEVER cut P8-2 coupling or P8-3 visible fingers (Annex A cut
order). NEVER let the wiring relabel a claim** — every new surface cites
its own gate rows.

## S37 contract facts (what S38 builds on)

- **P9-2 LANDED**: D-025 (written BEFORE any adoption code) ADOPTS
  `u2net.onnx` — Apache-2.0 verbatim (upstream xuebinqin/U-2-Net
  API-verified; the ONNX artifact published by rembg, MIT; release
  assets carry no separate license, rembg issue #837), 175,997,641
  bytes, sha256 `8d10d2f3bb75ae3b6d527c77944fc5e7dcd94b29809d47a739a7a7
  28a912b491` pinned in the manifest (the P1-1 flow is the only download
  path: `rigpose models download u2net` — live-verified), contract in
  `input.1` 1x3x320x320 → 1x1x320x320 sigmoid, CPU p50 413.2 ms = 0.73x
  DWPose. The scan refused six families with evidence (the D-024 shape),
  incl. **u2net_human_seg BLIND to the engine mannequin class (0.0000)**
  — the person-specific variant is the one that cannot see the fixture.
- **The volume stack**: core `volume.py` (BAND_PARAMS, clamp law
  [0.5,2.0], the absolute-target value law, the loud capability line,
  VolumeReport), addon `volume.py` (`apply_volume_sculpt` — convention
  keys named == the param, key DATA = the unit band warp (radial in
  mesh space, skin-gated by owned groups, thigh about its own leg
  center), key VALUE = factor-1 ABSOLUTE, `from_mix=False`, slider
  [-1,1], mesh-space units end to end; `measure_zero_restore`), gate
  `xtask/volume_gate.py` (7 RM_VOL GATE rows in pose-verify, model-free,
  CI-runnable). The probe pipeline (volume_common/probe/measure/rows)
  is the two-world template: bash orchestrates single-mode scripts; the
  model rows print SKIPPED honestly when the artifact is absent.
- **The selection**: `shape_key_inflate` — worst region IoU 0.9499 vs
  bar 0.85 over 8 cases (both rig classes x 4 reference classes), EVERY
  case improving over the published no-solve counterfactual 0.8907;
  lattice OUT (0.0000); armature out by joint invariance. GATE-WIDTH:
  all 16 mid-band ratios EXACT to 4 decimals. GATE-EDITABLE 1.19e-07 m.
- **The A1–A5 amendments + product lessons (do not re-learn)**: the
  fixture class (arms +-0.34..0.42 A-pose, legs closed, camera 2.5 m —
  u2net bridges thin arm-torso gaps and fills crotch gaps); the
  mid-band anchor; the model-mediated bar COMPRESSES (the binding A.1
  form is model-free exact-alpha; the unsolved base scores 0.88-0.97
  frame-wide); per-box skin ownership (nearest-bone starves the hip
  band); region-scoped bar + counterfactual. 5.1 lessons: shape-key
  `slider_min` defaults 0.0 (NEGATIVE values — the slender direction —
  silently dead until widened to [-1,1]); ONE unit system (mesh-local
  for Mixamo-class rigs) or the apply is a silent no-op;
  `from_mix=True` contaminates new keys with the mixed state; clean
  scenes per render AND per instrument case; measurement windows over
  OWNED groups covering the CLAMP ceiling.
- **The S36 lessons (standing)**: armature skinning RE-BINDS to rest
  edits (pose-space offsets are the delivery); parent_set LATTICE
  deforms meshes only; float32 noise reads as motion below ~1e-6.
- **654 tests** (S37 added 9); CI GREEN through the S37 push. All gate
  numbers byte-identical (RM_BAKE 0.0242°, RM_FOOT_LOCK 0.0371→0.0000,
  RM_MOTION 44997×, RM_COUPLE 0.00016/0.00035, RM_FINGER 0.0070°/0.00°/
  10.30°, RM_FACE 6 rows, RM_CAM 6 rows, RM_SPINE 5 rows, RM_ROOT 11
  rows, RM_SANIM 10 rows, RM_RUX 10 rows, RST 12 rows, RM_ASCULPT 8
  rows, RM_VOL 7 rows + the pipeline block).
- **D-026 is the next free number** (D-025 consumed by the adoption
  decision — no new pose field: shape keys are mesh data); D-018 stays
  reserved.
- **Gate env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
  miniconda3/bin/python3, and for the gate scripts RM_ADDON_DIR=$REPO/
  addon (the package PARENT) — else they 127 (or grab the broken apt
  4.0.2).
- **Instrument lessons (standing)**: Blender masks crashed scripts with
  exit 0 — grep the FINAL row (`RM_VOL GATE: PASS` / `RM_ASCULPT GATE:
  PASS`); place-update-then-measure; mathutils nested rich-compare FLAKY
  in 5.1 (plain-float tuples only); the session DATE is the UTC date
  (`date -u`); removing a Blender object orphans its data and the purge
  kills the RNA — capture names BEFORE removal; accumulated scenes
  poison renders and instruments (clean scene per case).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the session shape, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

- Frames LAND (the phone came up): confirm to LO, ask whether P5-4 jumps
  the queue; unless he says yes, CONTINUE the P9-3 work order below.
- Silent (26th): proceed with P9-3 directly.
- Then read, in order: STATE/ROADMAP.md (P9-3's scope), docs/VOLUME.md
  (the volume apply the wiring rides; amendments A1–A5), docs/
  AUTO_SCULPT.md (the proportion sculpt), docs/SCENE_TEST.md +
  docs/BENCHMARKS.md (the scorecard + the VOLUME block that must stay
  green), STATE/NEXT.md, STATE/TASKS.md (claim P9-3 with [S38]),
  STATE/PROGRESS.md (S37 entries), STATE/DECISIONS.md (D-018 reserved;
  D-026 next free), STATE/CONVENTIONS.md (**the commit-surface +
  local-devlog rules — LO's standing law**), STATE/SESSIONS.md,
  docs/POLICY.md, and the claim-bearing surfaces README + docs/
  LAUNCH.md + docs/TUTORIALS.md (one grep sweep together IF a number
  changes — untouched in S37).
- Register as Session 38 in STATE/SESSIONS.md. PROGRESS stamps: run
  `date -u` IMMEDIATELY before every append and USE THE ECHOED VALUE;
  verify the stamp after writing.

Baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest tests
(**654 expected**) + make lint PY=/home/potato/miniconda3/bin/python3 +
gh run list --branch main (latest green; if red: download the log,
root-cause, fix the real substance FIRST — the S12..S37 discipline).

## S38 work order — P9-3 sculpt + animation wiring

The ritual order is NON-NEGOTIABLE:

1. **DESIGN-FIRST docs/WIRING.md** (the VOLUME.md sibling): the
   user-facing flow — reference in → detect (DWPose; the volume side
   needs the segmentation pass) → solve proportions (P9-1) + volume
   (P9-2) → apply the static sculpt ONCE at frame one → then the
   pose/animation drives the rig. The honest-physics order: the sculpt
   edits mesh-side data; the certified FK/apply/bake paths consume the
   sculpted character unchanged (zero apply-path changes — the S36
   property).
2. **The operator/panel wiring** (P9-1/P9-2's declared scope): one
   add-on operator + a panel section riding the EXISTING pose-apply
   panel; proportion + volume factors from the last payload solve; loud
   capability lines; editable targets (the artist exit); idempotent
   applies (the absolute-target law holds for BOTH sculpts). The S34
   operator classes: {'REGISTER'} alone is invalid — {'FINISHED'} on
   success, poll + ERROR reports per the S34 findings.
3. **The session/MCP wiring**: a `sculpt` session action (KNOWN_ACTION_
   KINDS additive both sides, the golden-schema test extended in the
   SAME commit); MCP stays SFW (D-019, test-pinned) — the sculpt
   carries no content by itself.
4. **The animation-order proof**: sculpt → animate on BOTH rig classes:
   the sculpted widths SURVIVE the animation (the S36 GATE-COMPOSE
   pattern at animation scale — the drift bar 1e-5 m), FK bars hold
   (0.5 deg family), per-frame soft tissue OUT. New gate rows wired
   into pose-verify like S36/S37's.
5. **If early**: the scene-animation session/MCP wiring (S33's other
   declared follow-up) or the S31 CLI/addon invocation wiring —
   measured work only, each needs its own gate rows.

Definition of S38 failure (name it, avoid it): a wiring without gate
rows, a sculpt that composes instead of overwriting (the absolute-target
law), a silent no-op on the Mixamo class (the units lesson), a joint
moved by the volume path (the invariance contract), a silently-scoped
claim, or ANY claim without a test/gate citation. Anything 80% done is
0% shipped — park cleanly at a unit boundary.

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
  anything shipped. The out/ tree is gitignored — the probe renders and
  the devlog live there, never committed.
- The gate env trap (above).
- STATE stamps: real UTC, read-then-write-then-verify; the session date
  is the UTC date.
- **Mimosa (standing)**: bash writes of .py source blocked — Write/Edit;
  new sibling FILES scan clean where in-place edits trip path FPs;
  parameterized-path helpers and computed-path writes trip the
  path-traversal FP — module-level literal path constants + inline
  literal-join opens are the proven shape (volume_*); zero-IO gates
  where possible; expect the pagedoc.py import-struct FP at every
  commit; heredoc/append FPs when text names source files — Edit tool
  + -F commit-message files.
- **The commit-surface rules (CONVENTIONS, LO's standing law)**: commit
  messages carry no session markers, no AI/tooling mentions, no em
  dashes; each session appends a LOCAL devlog under out/devlog/
  (gitignored, never pushed) with one or two real proof renders
  (pipeline renders/screens of the work itself, never terminal dumps).
- Claim-bearing surfaces: README/LAUNCH/TUTORIALS change ONLY when a
  number changes; one grep sweep together when they do.
- 5.x slotted actions, the posed-head lesson, joint-angle keying,
  factory-EMPTY FBX scenes, rotation modes before quaternion writes,
  the two-pass fixture-builder rule, place-update-then-measure, the
  wrist-is-body-kp-9 lesson, mathutils nested rich-compare FLAKY in 5.1
  (plain-float tuples only), the operator return/poll/ERROR-report
  classes, the RNA-purge lesson, the absolute-target solve law — the
  S15..S37 facts in SESSION37_PROMPT.md remain true.

End of session (non-negotiable): tick claimed tasks (completed vs
partially-done + what remains); append PROGRESS lines (real UTC,
read-then-verify); top of STATE/NEXT.md: "NEXT SESSION SHOULD" — S39 =
sculpt polish + the P10-1 opener per the session map (S39 sculpt polish,
S40 P10-1 PoseSpec + the plausibility validator) — say which shape
landed; write STATE/SESSION39_PROMPT.md in this pattern (contract
facts, STEP 0, the next work order); update STATE/SESSIONS.md row;
write the LOCAL devlog + proof renders under out/devlog/ (never
pushed); commit + push (routine commits authorized; CLEAN messages per
CONVENTIONS — no session markers, no AI mentions, no em dashes; keep CI
green, fix inline like S12..S37); expect and disclose the Mimosa
pagedoc.py FP.

Known blockers (parked — do not burn time): live capture device — parked
LAST by LO (box side READY; P5-4 runs when the phone comes up; silent 25
straight sessions through S37). PyPI description + Blender Extensions
upload — LO's site-side steps (his final session). P6-3 packaging +
P6-2a wiring — roadmap slack. Windowed Blender GL stability —
best-effort only, never staged. Detector-visible mannequin fixtures (the
P8-5 tier-2 path) — NOT MET with evidence; reopened only if a
detector-visible engine-built fixture path exists. Root-motion BAKE —
revisit only when a real root-motion source exists. Scene-animation
session/MCP wiring — S38's step 5 if early. The anime fallback
estimator — REFUSED-with-evidence (D-024); reopened only through the
full P1-1 third-model ritual with a real candidate.