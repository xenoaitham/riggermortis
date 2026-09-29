# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** (Annex A pre-declared bars
   are LAW): S36 landed P9-1 — **the proportion auto-sculpt MECHANISM
   PROBE is MEASURED and LANDED** (`armature_scale_correctives`,
   pose-translation delivery: worst frac **0.0000** on BOTH rig classes ×
   all 3 reference classes; the lattice is structurally mesh-only in 5.1
   and shape keys structurally cannot move joints — both REFUSED as
   mechanisms with measured evidence; the REFUSED-with-evidence branch
   never fired). The gate rides pose-verify (8 RM_ASCULPT GATE rows);
   docs/AUTO_SCULPT.md is the design of record (amendments A1/A2);
   docs/BENCHMARKS.md § AUTO-SCULPT is the numbers block. The honest
   physics stands: keypoints give SKELETON, not VOLUME — **P9-1 claims
   skeleton proportions ONLY; volume is P9-2's separate third-model
   decision**. Per the session map **S37 = P9-2 the volume decision (the
   THIRD-MODEL RITUAL)**: a segmentation model amends the P6-6
   never-list — license, checksum, CPU budget on the mid-laptop baseline
   measured BEFORE adoption, the DECISIONS entry written at the landing
   (D-025 is the next free number; the P9-1 landing consumed none); the
   REFUSED path ships P9-1 + the documented refusal and Phase 10 does
   not wait for it.

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement). Silent 24 straight sessions through S36.
   - **Silent (25th)** → the P9-2 work order below.

2. **Then read, in order**: STATE/ROADMAP.md (Phase 9 — P9-2's third-model
   law, the A.1 volume bar IoU >= 0.85 visible-view scoped, the P6-6
   never-list it amends), docs/AUTO_SCULPT.md (P9-1's design of record —
   the honest-physics decomposition P9-2 extends), docs/SCENE_TEST.md +
   docs/BENCHMARKS.md § SCENE TEST (the scorecard that must stay green),
   STATE/NEXT.md, STATE/TASKS.md (claim P9-2 with [S37]), STATE/PROGRESS.md
   (S36 entries), STATE/DECISIONS.md (D-018 stays reserved; **D-025 is the
   next free number** — the P9-1 landing added no pose field, so the
   number was never consumed), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
   docs/POLICY.md (D-019 — a segmentation model is an input-side tool;
   its surfaces ride the same lines), and the claim-bearing surfaces
   README + docs/LAUNCH.md + docs/TUTORIALS.md (one grep sweep together
   IF a number changes — they were untouched in S36).

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**645 expected** — S36 added 11) + `make lint
   PY=/home/potato/miniconda3/bin/python3`, and `gh run list --branch
   main` (the S36 push is the newest; if red: download the log,
   root-cause, fix the real substance FIRST — the S12..S36 discipline).

## S37 work order — P9-2 volume from silhouette (the deliberate third-model decision)

The ritual order is NON-NEGOTIABLE (the P1-1/P9-2 law; the D-024
precedent of the LAST third-model scan):

1. **SCAN-FIRST (the ritual's gate)**: survey real segmentation/silhouette
   candidates (ONNX-runnable, local-only, CPU-viable) — e.g.
   human-matting / portrait-segmentation families, COCO-class person
   segmentation. EVERY candidate carries: license verbatim, weights size,
   sha256 + bytes (the P1-1 manifest ritual), input/output contract, and
   a CPU budget measured on THIS box (the mid-laptop baseline — the
   P5-1 latency precedent: measure, never assume). A candidate WITHOUT
   an adoptable artifact ends the scan REFUSED-with-evidence (the D-024
   shape: document what exists, why it is not adoptable, scan verbatim).
2. **THE DECISION (written, either way)**: adopt → the P6-6 never-list
   amendment is a DECISIONS entry (D-025) with license/checksum/CPU
   budget, BEFORE any adoption code; refuse → the DECISIONS entry
   documents the refusal with the scan evidence, P9-1 + the refusal
   ship, and Phase 10 does not wait.
3. **If adopted — design-first docs/VOLUME.md** (the AUTO_SCULPT.md
   sibling): silhouette → the P9-1 body-region shape language (the
   visible-view scope; depth from declared width priors, D-008); the
   A.1 bar **silhouette IoU >= 0.85 on the benchmark, visible-view
   scoped**; the volume benchmark (silhouette IoU of sculpted render vs
   reference mask); every result lands on editable targets (the P9-1
   artist-exit rule); probe-first xtask/volume_probe.py (RM_VOL rows),
   gate wired like S36's. Per-frame soft tissue stays OUT (P9-3's
   declared limit).
4. **If refused — the session still lands**: the proportion REPORT +
   auto-sculpt stand as shipped; the refusal entry + the roadmap's
   honest-limits update; S38 opens P9-3 (sculpt + animation wiring on
   the P9-1 mechanism) per the session map, with the volume refusal
   documented — never a half-claimed volume feature.
5. **If early**: the declared wiring items (scene-animation session/MCP
   wiring; the S31 CLI/addon invocation wiring) — measured work only,
   each needs its own gate rows.

**S36's contract facts S37 builds on** (do not re-learn):

- The auto-sculpt stack: core `auto_sculpt.py` (the pure target math +
  the 5% bar instrument + the proportion REPORT), addon
  `auto_sculpt.py` (pose-translation correctives — ABSOLUTE-TARGET
  solves, parent-first keyed order, measured linear response), gate
  `xtask/auto_sculpt_gate.py` (8 rows in pose-verify). A volume feature
  rides THIS stack (editable targets, the capability-line pattern,
  `validate_sculpt` as the template for a silhouette-IoU instrument).
- The A1/A2 probe lessons: armature skinning RE-BINDS to rest edits
  (the mesh does NOT follow — pose-space offsets are the delivery);
  parent_set LATTICE deforms meshes only (no armature lattice in 5.1);
  float32 noise reads as motion below ~1e-6 (the follow/width
  instruments use 1e-6–1e-5 bands).
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose,
  PY=/home/potato/miniconda3/bin/python3, RM_ADDON_DIR=$REPO/addon (the
  package PARENT, not the package dir) — else they 127 or ImportError.
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  zero-IO gates are the proven shape; expect the pagedoc.py
  import-struct FP at every commit; heredoc/append FPs when text names
  source files — Edit tool + -F commit-message files.
- STATE stamps are REAL UTC, read-then-write-then-verify (the session
  date is the UTC date; use the echoed `date -u` value).
- 645 tests expected at S37 open; CI green through the S36 pushes (the
  pose-verify block rides CI's blender-gate on apt 4.0.2 — the auto-
  sculpt gate is 4.x-safe by construction, verify the run).

## Blocked / deferred (parked — do not burn time)

- Live capture device — parked LAST by LO; P5-4 runs when the phone comes
  up (box side READY; the client just never ran; silent 24 sessions).
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
- Scene-animation session/MCP wiring — declared S33 follow-up (needs its
  own gate rows).
- The anime fallback estimator — REFUSED-with-evidence (D-024); reopened
  only through the full P1-1 third-model ritual with a real candidate.
- P9-1 operator/panel wiring + user-facing solve-flow integration —
  P9-3's declared scope (the S31 unit-boundary precedent; S36 landed
  the mechanism core + the REAL-apply gate).
