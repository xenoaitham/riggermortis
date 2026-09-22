# NEXT SESSION SHOULD …

1. **Camera re-verify FIRST, one command** (it decides everything):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly). The failsafe/duplicate-floor revisit trigger in LIVE.md
     becomes live-relevant (a D-018-class amendment, deliberately — the
     number is reserved for exactly that). The launch copy's live halves
     (README live bullet, docs/LAUNCH.md, docs/TUTORIALS.md VTuber track)
     then get their first REAL number — update all of them in the same
     session, they are written to make that swap easy.
   - **Silent again (9th session)** → **P6-6 opener: style-LoRA trainer
     docs** (honest GPU cost numbers, never a dependency of anything, NO
     training in CI, sober POLICY.md voice — docs-only, nothing in the repo
     trains anything), then the **P6-2 opener (motion-library retarget:
     Mixamo/BVH/FBX → any mapped rig)** with the S22 pattern: DESIGN page
     first, probe the import paths headlessly, honest scope note on what
     lands in-repo vs stays a documented recipe. P6-3 packaging stays
     blocked until LO answers the licensing questions below (a POLICY call
     only LO can make — do not package).

2. **Then read, in order**: STATE/TASKS.md, STATE/PROGRESS.md (S22
   entries), STATE/DECISIONS.md (D-019 executed; D-018 stays RESERVED for
   the live duplicate-contract amendment), STATE/CONVENTIONS.md,
   STATE/SESSIONS.md, docs/LIVE.md, docs/BENCHMARKS.md, docs/POLICY.md,
   docs/SECONDARY_MOTION.md (NEW — P6-1's design of record). Register as
   **Session 23**, claim tasks with [S23], PROGRESS stamps via `date -u`
   ONLY.

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m pytest
   tests` (**379 expected** — S22 added 21) + `make lint
   PY=/home/potato/miniconda3/bin/python3`, and verify the latest main CI
   run green (`gh run list --branch main`; S22's push is the newest run).
   If red: download the log, root-cause, fix the real substance FIRST.

Watch out for:

- **S21 policy facts (new)**: the add-on policy binding
  (`addon/riggermortis_addon/policy.py`) is bpy-free AT IMPORT by design —
  the core tests mount the package with a `__path__` shim
  (`conftest.addon_policy_module`) WITHOUT executing the bpy-importing
  `__init__`; keep new add-on modules bpy-free at import if they are to be
  unit-tested the same way. The enable path is the two Blender preference
  toggles ONLY, routed through `enable_adult_module(confirm=True)` /
  `disable_adult_module()`; the MCP server has NO enable tool (D-019,
  test-pinned — do not add one without a new deliberate decision).
  `bpy.context.preferences.addons.new()` takes NO arguments on 5.1; the
  real user path is `addon_utils.enable(...)` (what blender_verify 5/5
  exercises). Refusal codes are verbatim in the add-on report line
  (`refused [<code>] …`); `policy.py`-named modules exist in BOTH core and
  addon — imports are package-qualified, never bare.
- **S20 launch-surface facts (standing)**: docs/LAUNCH.md and
  docs/TUTORIALS.md are claim-bearing surfaces — when a number changes,
  grep BOTH plus the README (three places carry the live numbers). The 60s
  script in LAUNCH.md is P7-6's shot list — cut-only-from-existing-footage.
  TUTORIALS commands were verified against cli.py + the registered add-on
  operators; re-verify if the CLI or panel changes (S21 ADDED an operator +
  panel section — `rm.policy_check` / "Content policy" — none of the
  tutorial command sequences touch it, but keep the rule in mind).
- **P5-3 facts (do not reintroduce)**: smoothing is CORE-side
  (`live.LivePoseSmoother`) on the CANONICAL POSE per role per axis — the
  driver path is payload → `CanonicalPose.from_dict` → filter (STREAM
  space) → mirror → `pose_apply.apply_pose_object`; smoothing OFF is
  `pose_apply.apply_payload` byte-identical P5-2. Mirror order is PROVEN
  (odd-symmetric filter commutes; smooth-first for state stability).
  Timestamps are the envelope's `t_emit_wall`; gaps mean no update, long
  gaps open the filter. Defaults min_cutoff 1.0 Hz / beta 0.05 are
  DECLARED untuned (D-008) — never tune them against the gate fixture.
- **P5-3 failsafe contract**: stale_after keeps the last pose; SUSTAINED
  silence past failsafe_after (default 10 s, > stale_after validated)
  fires a ONE-TICK edge in `LiveConsumer` (re-armed by any new event) →
  driver clears to REST via `pose_apply.clear_pose`, resets the smoother
  (first recovery pose passes through EXACTLY), panel says FAILSAFE.
  Known limit (documented LIVE.md): producer RESTART with fresh seq space
  is suppressed by the P5-2 duplicate floor — remedy Stop/Start. Revisit
  only via a deliberate D-018-class amendment, never silently.
- **The gate's sweep instrument**: run A is the UNsmoothed control;
  J1/J2 gate-fed from run A's first REAL payload line; the variance bar is
  the P2-2 ≥4x instrument REUSED verbatim; constant-channel stillness is
  an epsilon (1e-20) assertion, NOT ==0.0. After ANY gate print change,
  grep-test BOTH the PASS and SKIPPED lines before pushing.
- **P5-2 facts (load-bearing)**: `LiveTail` (offset tail, torn-line safe,
  restart-safe via size-shrink AND newline-boundary) + `LiveConsumer`
  (latest-wins; batch ENDING in a miss applies nothing; envelope-seq
  duplicates never re-applied; stale = no new line past stale_after,
  default 2.0 s). Blender side is a THIN adapter; the pump never raises.
- **The replay budget definition**: published replay end-to-end is
  EMIT → APPLY — apply p95 ≈ 2.7–3.8 ms, emit→apply p50 ≈ 124–157 ms
  across gate runs (S18/S19/S21; jitter normal — stalls land on the
  producer's DETECTOR frames, first line in the ~2 s cold window, never
  tuned away). On replayed files `age_ms` is the frame file's MTIME AGE —
  printed, never summed in. The <100 ms mid-laptop gate stays UNCLAIMED
  until a real stream; never relabel replay numbers live.
- **P5-1 facts (load-bearing)**: the detector CADENCE is the realtime
  lever — input downscale is a dead knob; the FIRST stream line carries
  the ~2 s cold load; `Figure.score` is 0.0 on tracked figures; the
  quality signal is mean body confidence (17 COCO kps, floor 0.3);
  kind=miss lines are NORMAL; envelope timing fields are MEASUREMENTS —
  never assert their values in tests.
- **5.1 API facts the probes keep earning**: compositor graph =
  `scene.compositing_node_group`; GPv3 strokes = `drawing.add_strokes`,
  closed = `cyclic`; LineArt only via ops LINEART_OBJECT + renames;
  created objects captured by DATABLOCK DIFF; EXACTLY ONE Group Output
  AFTER the interface socket; page backgrounds are FULL-PAGE solid images;
  byte-identity = default-sRGB loads + Standard view transform + dither 0.
- **PANELS INHERIT THE SCENE VIEW TRANSFORM**: stage Standard + dither 0
  explicitly in any page-scene.
- **Never render a VSE movie from any .py** (racy segfault, D-009); movie
  assembly is shell-glue ffmpeg + ffprobe parse-back. Primitive_add
  deselects (explicit select_set); T-pose arm pivots sit wide (narrow
  BEFORE hang poses); elbow bends need a pose-relative Rodrigues axis;
  wide panels need a 35 mm lens; pose bones default QUATERNION; a SPHERE
  is rotationally symmetric; Bright=0.15 changes ZERO channels (use
  Contrast). Bisect verdicts need run counts (3 runs minimum per config).
- **Gates' env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose,
  PY=/home/potato/miniconda3/bin/python3 — else they 127. The live gate
  needs out/live_probe/smoke_frames + out/real_rigs/metarig.rig.json
  (git-ignored) or it answers `RM_LIVE GATE: SKIPPED (...)` honestly,
  exit 0. The style gate on 5.1 must show LINEART/TONES/PAGES/FRAMES/
  ANIMATIC/EXPORT PASS in CI (SKIPPED there = the bump broke). The
  blender gate now has a 5/5 policy section (RM_POLICY lines) — grep-test
  those if you touch the policy flow.
- **Media rules**: existing launch media (boom.gif, walk GIFs,
  agent_turntable.gif, ui_screenshot.png, manga set) are
  pipeline-generated — reference, never hand-edit; ANY new media ships
  with the allowlist extension in the SAME commit + a visual check. The
  WALKRIGS block is generator-owned (xtask/walk_docs.py + out/p28
  manifests): edit the GENERATOR, then regenerate — never hand-edit.
- **Mimosa**: intercepts bash writes of ANY source-looking file — use
  Write/Edit; expect the pagedoc.py `import struct` FP at every commit;
  S20/S21 caught heredoc/append FPs when the TEXT merely NAMES source
  files (PROGRESS/BENCHMARKS appends) — restructure as an Edit-tool
  append and move on.
- **STATE timestamps are REAL**: `date -u` before every PROGRESS append.

## P6-3 scope probe — the licensing/redistribution questions ONLY LO can answer

(S21's sanctioned work-order-C output: questions, NOT packaging. Until
these have answers, P6-3 stays blocked and the benchmark images stay
git-ignored locals with provenance in out/benchmark/SOURCES.md.)

1. **Suite license**: the repo is MIT (code). Images are NOT code — pick
   the suite's media license (CC0 / CC-BY / CC-BY-SA?) and confirm it is
   compatible with every sourced item's terms.
2. **The Apache-2.0 ControlNet screenshot crops** (anime_4/anime_6):
   redistributing screenshots of a third-party web UI is a different
   question from the license on the underlying repo — is LO comfortable
   shipping them publicly, or do those two slots get replaced?
3. **CC BY-SA items** (the Commons illustration): attribution +
   share-alike-on-derivatives — are benchmark crops "derivatives" LO wants
   under share-alike, and is per-image attribution in a shipped SOURCES
   file the format he wants?
4. **Identifiable people**: confirm no photo-set image shows an
   identifiable real person (else model-release territory — the policy
   page's real-person line applies to inputs too, not just outputs).
5. **Distribution mechanics**: in-repo `docs/`-tracked, a separate release
   artifact, or an external dataset host? (In-repo grows the clone and
   touches the media-guard allowlist; a release artifact keeps the repo
   light but splits the CI story.)
6. **Does the PUBLIC suite become the canonical gate fixture** (CI runs
   detection on 20 images per push — cost + determinism implications), or
   do published numbers stay tied to the git-ignored local sets with the
   public suite as a re-runnable extra?
7. **If the P2-8 real walking clip ever lands** (NEEDS-HUMAN): does it
   join the public suite under the same bar?

Blocked / deferred (unchanged unless noted):

- Live capture device — NEEDS-HUMAN (DroidCam silent in S17–S21; the phone
  side must stream; P5-4 and the live capture→apply measurement wait on
  it — everything buildable shipped without it).
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P6-3 public benchmark suite — NEEDS-HUMAN (NEW: LO's answers to the
  question list above are the gate; packaging waits).
- P1-8a fallback estimator — parked (D-011/D-012).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md).
- Phase 4 — CLOSED (D-017); manga media regenerates via
  `bash xtask/manga_build.sh` (media-guard pins the 8 files).
- P5-1..P5-3 DONE (S17/S18/S19); P5-4 (recorded demo) needs the camera.
- Phase 6 after S21: P6-4/P6-5 DONE; P6-1 (secondary motion) and P6-2
  (motion-library retarget) are the remaining engine rocks; P6-6 (style-
  LoRA trainer docs) is the small honest-docs item.
- Phase 7 after S20: P7-1/P7-2/P7-3 DONE; P7-4/P7-5 account-bound; P7-6
  waits on a recorded-cut session (shot list exists in docs/LAUNCH.md).
