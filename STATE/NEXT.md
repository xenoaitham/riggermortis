# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** (Annex A pre-declared bars
   are LAW): S38 landed P9-3 — **the sculpt is WIRED into the product
   flow and the animation-order proof is GREEN**. `rigpose solve-sculpt`
   (LIVE-VERIFIED on a real reference) writes the format-1 solve artifact
   (core `riggermortis.sculpt`; the S37 measurement lifted verbatim — the
   volume pipeline aliases the core copies and its certified rows re-ran
   byte-identical); the `rm.apply_sculpt` operator + the `sculpt` session
   action (kinds additive both sides, MCP untouched, D-019 SFW pinned)
   apply proportion + volume ONCE at the rest state through ONE shared
   addon path; the RM_WIRE rows prove the honest-physics order: the baked
   action stays rotation-only, the sculpt survives byte-identically,
   frame-one width drift 0.00e+00 m, FK 0.0000 deg x70 checks, re-sculpt
   at the sculpt frame re-lands byte-identically. docs/WIRING.md is the
   design of record (as-built amendments A2-A4); docs/BENCHMARKS.md §
   WIRING is the numbers block. Per-frame soft tissue stays OUT.
   **S39 = sculpt polish + the P10-1 opener** per the session map:
   polish = the measured gaps S38's landing exposed (mixamo-class
   re-sculpt worst frac 0.047085 vs bar 0.05 — thin; the volume solve on
   oblique references is outside the declared frontal class; driven shape
   keys are a documented staging limit) — each polish item must carry its
   own gate rows; P10-1 = the PoseSpec contract + the plausibility
   validator (pure core, model-free) if the polish lands early. The
   session map: S39 sculpt polish + P10-1 opener, S40 P10-1 PoseSpec +
   the plausibility validator.

1. **Camera re-verify FIRST, one command** (it decides the session shape):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement). Silent 26 straight sessions through S38.
   - **Silent (27th)** → the S39 work order below.

2. **Then read, in order**: STATE/ROADMAP.md (P9-3 landed; P10-1's
   scope), docs/WIRING.md (the wiring design of record + as-built
   A2-A4), docs/AUTO_SCULPT.md + docs/VOLUME.md (the sculpt mechanisms
   the polish rides; the landed-since pointers), docs/SCENE_TEST.md +
   docs/BENCHMARKS.md (the scorecard + the WIRING block that must stay
   green), STATE/NEXT.md, STATE/TASKS.md (claim the session's rock with
   [S39]), STATE/PROGRESS.md (S38 entries), STATE/DECISIONS.md (**D-026
   is the next free number**; D-018 stays reserved), STATE/CONVENTIONS.md
   (**LO's standing rules live here — reread them**), STATE/SESSIONS.md,
   docs/POLICY.md, and the claim-bearing surfaces README + docs/LAUNCH.md
   + docs/TUTORIALS.md (one grep sweep together IF a number changes —
   S38 swept them: the README P9 bullet, the three-model quickstart
   lines, the TUTORIALS 3b sculpt step, the LAUNCH V2 note; a polish
   number change re-sweeps them together).

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m
   pytest tests` (**669 expected** — S38 added 15) + `make lint
   PY=/home/potato/miniconda3/bin/python3`, and `gh run list --branch
   main` (the S38 push is the newest; if red: download the log,
   root-cause, fix the real substance FIRST — the S12..S38 discipline).

## S39 work order — sculpt polish (+ the P10-1 opener if early)

1. **DESIGN-FIRST any polish page** (extend docs/WIRING.md — never fork
   it): the measured gaps, each with its declared bar + gate rows BEFORE
   code:
   - the Mixamo-class re-sculpt frac (0.047085 vs the 0.05 bar — the
     frame-one rotations are not exactly identity after the bake; the
     polish declares the tolerance basis or improves the solve);
   - the oblique-reference limit (the volume solve assumes the declared
     frontal class; either a measured oblique class or a loud refusal
     with the measured error bars — never a silent wrong solve);
   - the driven-shape-key staging limit (a driven key ignores the staged
     zero — either stage the driver or refuse loud with the measured
     class).
2. **Measured work only**: each polish item lands with its own RM_WIRE
   (or sibling) grep rows; every prior gate number stays byte-identical.
3. **If early**: the P10-1 opener — the PoseSpec contract skeleton (pure
   core, model-free: the versioned per-role spec + the loud validator's
   shape), declared in docs/POSE_SPEC.md design-first, its red-set
   refusal bar pre-declared per the roadmap (validator refuses 100% of
   the impossible-spec red set; injection constants frozen in the
   contract BEFORE any measurement).

**S38's contract facts S39 builds on** (do not re-learn):

- The wiring stack: core `sculpt.py` (SCULPT_FORMAT 1, SculptSolve loud
  validation, anchor_points_px A1, region_widths/solve_factors — the
  ONE copies; volume_common aliases them), `inference/segment.py` (the
  one u2net wrapper; `rigpose models download u2net` is the only path),
  the CLI `solve-sculpt` (payload label must match the image's
  detection — loud on stale); addon `sculpt_wire.py` (apply_sculpt ONE
  shared path: proportion = payload positions -> S36 target -> S36
  apply; volume = staged rest-snapshot render measurement [pose cleared,
  keys zeroed, action MUTED, render settings + camera staged/restored]
  -> factors -> S37 apply; CAPABILITY_NO_PAYLOAD/NO_SCULPT lines);
  operator `rm.apply_sculpt` + the panel section; session `sculpt`
  (params payload_path/sculpt_path/armature_name/proportions/volume;
  validates BEFORE bpy).
- The gate: xtask/wiring_gate.py (WIRE-FIXTURE/MEASURE/SOLVE/FLOW/
  RESCULPT/OPS/SESSION/NOTARGET/DETERM + WIRE + GATE), fresh scene per
  render-adjacent case (THE scene law, earned twice), reeval reads
  frame_set(f + 1) (the bake's frame_offset 1), the re-sculpt checks are
  values-bytes + target-frac + action-intact (NOT location bytes).
- The gate env trap: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose,
  PY=/home/potato/miniconda3/bin/python3, RM_ADDON_DIR=$REPO/addon —
  pose-verify needs ALL of them (the first S38 run died on an unbound
  $PY at the volume stage).
- Mimosa (standing): bash writes of .py source blocked — Write/Edit;
  parameterized-path write opens trip the path-traversal FP — the
  proven shape: module-level literal Path constants + `.write_text()`
  (walk_job's shape) and inline literal-join opens for reads; expect
  the pagedoc.py import-struct FP at every commit (disclose it,
  non-blocking, every session).
- STATE stamps: real UTC, read-then-write-then-verify; the session date
  is the UTC date.
- **The commit-surface rules (CONVENTIONS, LO's standing law)**: commit
  messages carry no session markers, no AI/tooling mentions, no em
  dashes; scratch-file + `git commit -F`; each session appends a LOCAL
  devlog under out/devlog/ (gitignored, never pushed) with one or two
  real proof renders (S38's: out/devlog/s38_sculpt_before.png /
  s38_sculpt_after.png — the fixture sculpted by the LIVE solve
  artifact).
- 669 tests expected at S39 open; CI green through the S38 push
  (verify the run).

## Blocked / deferred (parked — do not burn time)

- Live capture device — parked LAST by LO; P5-4 runs when the phone comes
  up (box side READY; silent 26 sessions).
- PyPI description + Blender Extensions upload — LO's site-side steps
  (his final session).
- P6-3 public benchmark suite packaging — roadmap-slack work.
- P6-2a `retarget_clip` session action — the refactor half is DONE; the
  executor wiring is roadmap-slack work.
- Windowed Blender GL stability — best-effort only, never staged.
- Detector-visible mannequin fixtures (the P8-5 tier-2 path) — NOT MET
  with evidence; reopened only if a detector-visible engine-built
  fixture path exists (the A.3 re-validation trigger).
- Root-motion BAKE — revisit only when a real root-motion source exists.
- Scene-animation session/MCP wiring — S33's declared follow-up, still
  open (measured work only, its own gate rows).
- The anime fallback estimator — REFUSED-with-evidence (D-024); reopened
  only through the full P1-1 third-model ritual with a real candidate.
- P10-1 PoseSpec + the plausibility validator — S39's step 3 if early,
  S40's rock per the session map.
