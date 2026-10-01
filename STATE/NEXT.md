# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** (Annex A pre-declared bars
   are LAW): S37 landed P9-2 — **the volume third-model decision is MADE
   and the mechanism MEASURED and LANDED**. D-025 ADOPTED `u2net.onnx`
   (Apache-2.0 verbatim, sha256-pinned in the manifest — the third
   pinned model; CPU 0.73x DWPose; the scan refused six families with
   evidence, incl. the u2net_human_seg BLIND catch). `shape_key_inflate`
   SELECTED (worst region IoU **0.9499** vs bar 0.85 over 8 cases,
   EVERY case improving over the published no-solve counterfactual
   0.8907; joints byte-identical through the key warp; the lattice class
   measured OUT; the armature class out by invariance). docs/VOLUME.md
   is the design of record (amendments A1–A5); docs/BENCHMARKS.md §
   VOLUME is the numbers block; the gate rides pose-verify (7 RM_VOL
   GATE rows + the pipeline block with SKIPPED-honest model rows). The
   volume CLAIM's scope exactly: region widths on the four bands
   (hips/waist/chest/thigh), visible-view, static (applied once, before
   animation); depth follows the declared circular prior; per-frame
   soft tissue is OUT. **S38 = P9-3 sculpt + animation wiring** per the
   session map: the static sculpt applies at frame one BEFORE animation
   drives the rig; the P9-1 proportion sculpt + the P9-2 volume sculpt
   wire into the user-facing flow (operator/panel, the solve-flow
   integration, session/MCP wiring); per-frame soft tissue stays OUT.

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement). Silent 25 straight sessions through S37.
   - **Silent (26th)** → the P9-3 work order below.

2. **Then read, in order**: STATE/ROADMAP.md (P9-3's scope), docs/
   VOLUME.md (P9-2's design of record + amendments A1–A5 — the volume
   apply the wiring rides), docs/AUTO_SCULPT.md (P9-1's design of
   record — the proportion sculpt the wiring rides), docs/SCENE_TEST.md
   + docs/BENCHMARKS.md (the scorecard + the VOLUME block that must
   stay green), STATE/NEXT.md, STATE/TASKS.md (claim P9-3 with [S38]),
   STATE/PROGRESS.md (S37 entries), STATE/DECISIONS.md (D-018 stays
   reserved; **D-026 is the next free number**), STATE/CONVENTIONS.md
   (the NEW commit-surface + local-devlog rules — LO's standing law),
   STATE/SESSIONS.md, docs/POLICY.md, and the claim-bearing surfaces
   README + docs/LAUNCH.md + docs/TUTORIALS.md (one grep sweep together
   IF a number changes — untouched in S37 unless the wiring ships a
   user-facing capability worth claiming, then claim it honestly).

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**654 expected** — S37 added 9) + `make lint
   PY=/home/potato/miniconda3/bin/python3`, and `gh run list --branch
   main` (the S37 push is the newest; if red: download the log,
   root-cause, fix the real substance FIRST — the S12..S37 discipline).

## S38 work order — P9-3 sculpt + animation wiring

The declared unit-boundary debt (S31/S36/S37 precedents) comes due:

1. **DESIGN-FIRST docs/WIRING.md** (the VOLUME.md sibling): the
   user-facing flow — reference in → detect (the pinned DWPose; the
   volume side needs the SEGMENTATION pass too) → solve proportions
   (P9-1) + solve volume (P9-2) → apply the static sculpt ONCE at frame
   one → then animation/pose drives the rig. The order is the honest
   physics: the sculpt edits the REST-side mesh data; the certified
   apply/bake paths consume the sculpted character unchanged.
2. **The operator/panel wiring** (the P9-1/P9-2 declared scope): one
   add-on operator (`rm.apply_sculpt` class) + a panel section riding
   the EXISTING pose-apply panel — proportion + volume factors from the
   last payload solve, loud capability lines, every result on editable
   targets (the artist-exit rule), the apply idempotent (the S36
   absolute-target law holds for BOTH sculpts).
3. **The session/MCP wiring** (the S33 declared follow-up): a
   `sculpt` session action (kinds table additive both sides, the
   golden-schema test extended same-commit); MCP stays SFW
   (test-pinned) — the sculpt carries no content by itself.
4. **The animation-order proof** (the phase's honest-physics gate):
   sculpt → animate on BOTH rig classes: the sculpted girdle widths
   SURVIVE the animation (the S36 GATE-COMPOSE pattern at animation
   scale), FK bars hold (0.5 deg family), the per-frame soft-tissue OUT
   declaration stands. New gate rows (RM_WIRE or RM_SCULPTWIRE), wired
   into pose-verify like S36/S37's.
5. **If early**: the scene-animation session/MCP wiring (S33's other
   declared follow-up) or the S31 CLI/addon invocation wiring —
   measured work only, each needs its own gate rows.

**S37's contract facts S38 builds on** (do not re-learn):

- The volume stack: core `volume.py` (clamp law [0.5,2.0], the
  absolute-target value law, capability line, VolumeReport), addon
  `volume.py` (apply_volume_sculpt — convention keys, mesh-space units,
  from_mix=False, slider [-1,1]; measure_zero_restore), gate
  `xtask/volume_gate.py` (7 rows in pose-verify). The proportion stack:
  core `auto_sculpt.py` + addon `auto_sculpt.py` (absolute-target
  pose-translation correctives). BOTH sculpt idempotent; BOTH land on
  editable targets; BOTH loud-refuse starved rigs.
- The P9-2 probe pipeline (volume_common/probe/measure/rows) is the
  two-world template: bash orchestrates single-mode scripts; the model
  artifact rides the P1-1 manifest flow (`rigpose models download
  u2net`); model rows print SKIPPED honestly when absent.
- The A1–A5 + 5.1 product lessons (docs/VOLUME.md as-built): shape-key
  slider_min defaults 0.0 (negatives dead until widened); ONE unit
  system (mesh-local for Mixamo-class rigs) or the apply is a silent
  no-op; from_mix=True contaminates; accumulated scenes poison renders
  and instruments; measurement windows over OWNED groups covering the
  clamp ceiling.
- The A1/A2 probe lessons (S36, standing): armature skinning RE-BINDS
  to rest edits (pose-space offsets are the delivery); parent_set
  LATTICE deforms meshes only; float32 noise reads as motion below
  ~1e-6 (instruments use 1e-6–1e-5 bands).
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose,
  PY=/home/potato/miniconda3/bin/python3, RM_ADDON_DIR=$REPO/addon (the
  package PARENT) — else 127 or ImportError.
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  new sibling FILES scan clean where in-place edits trip path FPs;
  parameterized-path helpers and computed-path writes trip the
  path-traversal FP — module-level literal path constants + inline
  literal-join opens are the proven shape (volume_*); expect the
  pagedoc.py import-struct FP at every commit.
- STATE stamps are REAL UTC, read-then-write-then-verify.
- **The commit-surface rules (CONVENTIONS, LO's standing law)**: commit
  messages carry no session markers, no AI/tooling mentions, no em
  dashes; each session appends a LOCAL devlog under out/devlog/
  (gitignored, never pushed) with one or two real proof renders.
- 654 tests expected at S38 open; CI green through the S37 push (the
  volume gate is model-free and 4.x-safe by construction — the
  pipeline's model rows print SKIPPED on CI where the artifact is
  absent; verify the run).

## Blocked / deferred (parked — do not burn time)

- Live capture device — parked LAST by LO; P5-4 runs when the phone comes
  up (box side READY; the client just never ran; silent 25 sessions).
- PyPI description + Blender Extensions upload — LO's site-side steps
  (deferred to his final session by LO).
- P6-3 public benchmark suite packaging — roadmap-slack work.
- P6-2a `retarget_clip` session action — the refactor half is DONE; the
  executor wiring is roadmap-slack work.
- Windowed Blender GL stability — best-effort only, never staged.
- Detector-visible mannequin fixtures (the P8-5 tier-2 path) — NOT MET
  with evidence; reopened only if a detector-visible engine-built
  fixture path exists (the A.3 re-validation trigger).
- Root-motion BAKE — revisit only when a real root-motion source exists.
- Scene-animation session/MCP wiring — declared S33 follow-up (S38's
  step 5 if early).
- The anime fallback estimator — REFUSED-with-evidence (D-024); reopened
  only through the full P1-1 third-model ritual with a real candidate.
- P9-1/P9-2 operator/panel + solve-flow wiring — S38's declared scope
  (steps 2–4).
