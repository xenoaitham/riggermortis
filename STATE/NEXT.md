# NEXT SESSION SHOULD …

1. **Camera re-verify FIRST, one command** (it decides everything):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly; update the three live-number surfaces in the same session;
     the D-018 failsafe/duplicate-floor revisit trigger becomes live-relevant).
   - **Silent again (11th session)** → **finish P6-2** (the work S23 set up):
     the Blender-side bridge sampler, the fixtures, and the RM_MOTION gate
     section. Details in the work order below. P6-3 packaging stays blocked
     until LO answers the licensing questions (a POLICY call only LO makes).

2. **Then read, in order**: STATE/TASKS.md (the P6-2 PARTIAL entry carries
   the full S23 state), STATE/PROGRESS.md (S23 entries), STATE/DECISIONS.md
   (D-019 executed; D-018 stays RESERVED), STATE/CONVENTIONS.md,
   STATE/SESSIONS.md, docs/MOTION_LIBRARY.md (P6-2's design of record —
   the as-built probe section IS the S24 recipe), docs/SECONDARY_MOTION.md,
   docs/LIVE.md, docs/BENCHMARKS.md, docs/POLICY.md, docs/STYLE_LORA.md
   (NEW — P6-6, docs-only). Register as **Session 24**, claim tasks with
   [S24], PROGRESS stamps via `date -u` ONLY (S23 had to correct one
   in-line estimated stamp — read the clock before every append).

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m pytest
   tests` (**406 expected** — S23 added 27) + `make lint
   PY=/home/potato/miniconda3/bin/python3`, and verify the latest main CI
   run green (`gh run list --branch main`; S23's push is the newest run).
   If red: download the log, root-cause, fix the real substance FIRST.

## P6-2 completion (S24's rock, unless the camera flips the fork)

What exists after S23 (all probe-proven, see docs/MOTION_LIBRARY.md
§ Probe answers): the core converter (`motion.py`: clip JSON →
`CanonicalAction`), 27 CI tests, and the probe `xtask/motion_probe.py`
whose code IS the recipe. What S24 builds:

1. **The bridge sampler** (shell glue per D-009 — spawn never lives in a
   .py): import a clip file with the BUILTIN importers (the probe's
   `import_path`: BVH needs `axis_forward='Y', axis_up='Z'` — MEASURED),
   map the source skeleton via the existing mapper/`import_and_extract.py`
   machinery, then per frame: `frame_set` → `view_layer.update()` → sample
   mapped-role `pb.matrix.to_translation()` heads → write the format-1 clip
   JSON (`fps`, `scale_ref` = the source REST torso span, role-keyed
   positions in source meters). Extend `import_and_extract.py` or add
   `xtask/sample_clip.py` — your call, follow the existing script shapes.
2. **Fixture generation** (CI-safe, zero downloads): headless export of
   synthetic BVH/FBX clips (the probe's `build_humanoid` + `key_step_action`
   + the exporters; BVH export has NO axis params — files are Blender-world
   already). Commit nothing binary; generate at gate time into out/.
3. **The RM_MOTION gate section** (in `verify_pose_apply.sh`, grep-tested
   BOTH the PASS and SKIPPED lines like every RM_ section): fixture →
   import → sample → `action_from_clip` → certified composition →
   `bake_action` on the metarig → re-eval from fcurves vs the source clip
   (the 0.5° FK-family bar) + foot_slide before/after on a deliberately
   sliding walk (the lock's ≥5x family). Sections must print exactly their
   own shape — S22's rule: no combined PASS line unless that IS the shape.
4. **The REAL-Motion row**: the local `out/real_rigs/Xbot.glb` carries
   SEVEN real Mixamo clips (walk/run/idle/agree/headShake/sad_pose/
   sneak_pose — 670 fcurves each, probe-measured). Gate on `walk`:
   import → sample → convert → lock → report the slide numbers in
   docs/BENCHMARKS.md (new MOTION block, test/gate-cited). SKIPPED
   honestly when the glb is absent (CI has no models/assets).

Then: TASKS tick with the full done entry, BENCHMARKS block, README status
line gains the P6-2 clause (no live-number surfaces touched), SESSIONS row,
SESSION25_PROMPT.md.

Watch out for:

- **S23 probe facts (do not re-learn them the hard way)**: posed head =
  `pb.matrix.to_translation()` (pb.matrix @ head_local double-applies
  rest); positions are the ONLY convention-free metric (BVH re-rolls and
  reverses bone AXES while positions stay right); sample positions BEFORE
  any rotation-mode change (forcing QUATERNION orphans euler fcurves —
  the motion silently freezes); retarget FK-applies onto the TARGET's own
  topology, never re-applies rotations onto the imported rig; a
  mode-forced re-import evaluates STATIC (all frames one pose).
- **BVH axis flags are a measured contract**: exporter has NO axis params
  (files are Blender-world); importer defaults land a 90° rotation,
  `-Y` lands a VERTICAL MIRROR, `Y`/`Z` is exact. Pin them in the sampler.
- **S22 secondary facts (standing)**: pb = C @ rest @ basis is PROVEN;
  chains key strictly AFTER FK roles; D-008 constants stay untuned; the
  direction-only translation-inert contract is pinned.
- **S21 policy facts (standing)**: add-on modules bpy-free AT IMPORT if
  unit-tested via the conftest shim; no MCP enable tool (D-019).
- **Claim-bearing surfaces**: when a number changes, grep README +
  docs/LAUNCH.md + docs/TUTORIALS.md together. S23 changed NO live
  numbers (the README status line gained clauses only) — verify the same
  holds for whatever S24 lands, and put any new motion numbers ONLY in
  docs/BENCHMARKS.md + docs/MOTION_LIBRARY.md.
- **ui_screenshot.sh is FIXED (S23)**: it now resolves $BLENDER → the
  5.1.0 install → PATH (it spent S16..S22 launching the BROKEN apt 4.0.2
  — LO caught it), and `timeout --kill-after=10` prevents a hung GL
  teardown from stalling the attempt loop. The windowed miss persists
  (miss #10 was ON 5.1) — attempts stay best-effort, never staged.
- **STATE timestamps are REAL**: `date -u` before every PROGRESS append.
- **Gates' env trap**: BLENDER=/home/potato/blender-5.1.0-linux-x64/
  blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose,
  PY=/home/potato/miniconda3/bin/python3 — else they 127 (or worse, grab
  the broken 4.0.2).
- **Media rules**: any new media ships with the allowlist extension in the
  SAME commit + a visual check. The WALKRIGS block is generator-owned.
- **Mimosa**: intercepts bash writes of ANY source-looking file — use
  Write/Edit; expect the pagedoc.py `import struct` FP at every commit;
  heredoc/append FPs when text names source files — Edit tool + `-F`
  commit-message files.
- **P5-2/P5-3 facts (load-bearing)**: LiveTail/LiveConsumer semantics,
  smoothing core-side on the canonical pose, mirror order PROVEN,
  defaults D-008-untuned, failsafe one-tick edge, replay never relabeled
  live, <100 ms gate UNCLAIMED until a real stream.

## P6-3 scope probe — the licensing/redistribution questions ONLY LO can answer

(unchanged from S21/S22; packaging waits)

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

- Live capture device — NEEDS-HUMAN (DroidCam silent in S17–S23; the
  phone side must stream; P5-4 and the live capture→apply measurement wait
  on it — everything buildable shipped without it).
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P6-3 public benchmark suite — NEEDS-HUMAN (LO's answers gate packaging).
- P1-8a fallback estimator — parked (D-011/D-012).
- P2-8 real walking clip — NEEDS-HUMAN (out/video_smoke/SOURCES.md).
  NOTE: the Xbot.glb `walk` clip (S23 finding) may satisfy much of what
  P2-8 wanted from a real clip — LO's call whether that reopens it.
- Phase 4 — CLOSED (D-017); manga media regenerates via
  `bash xtask/manga_build.sh` (media-guard pins the 8 files).
- P5-1..P5-3 DONE (S17/S18/S19); P5-4 needs the camera.
- Phase 6: P6-1 DONE (S22); P6-4/P6-5 DONE (S21); P6-6 DONE (S23);
  P6-2 core DONE (S23), bridge+gate S24; P6-3 blocked on LO's answers.
- Phase 7: P7-1/P7-2/P7-3 DONE; P7-4/P7-5 account-bound; P7-6 waits on a
  recorded-cut session.
