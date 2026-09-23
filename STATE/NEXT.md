# NEXT SESSION SHOULD …

1. **Camera re-verify FIRST, one command** (it decides everything):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly; update the three live-number surfaces in the same session;
     the D-018 failsafe/duplicate-floor revisit trigger becomes
     live-relevant). Silent 12 straight sessions so far.
   - **Silent again (13th)** → the work order below. P6-3 packaging stays
     blocked until LO answers the licensing questions (a POLICY call only
     LO makes; the 7 questions are at the bottom of this file).

2. **Then read, in order**: STATE/TASKS.md (P6-2 is DONE with the full
   S23+S24 entry), STATE/PROGRESS.md (S24 entries), STATE/DECISIONS.md
   (D-019 executed; D-018 stays RESERVED), STATE/CONVENTIONS.md,
   STATE/SESSIONS.md, docs/MOTION_LIBRARY.md (now carries the S24
   as-built section + the DESIGN-only retarget_clip sketch),
   docs/SECONDARY_MOTION.md, docs/LIVE.md, docs/BENCHMARKS.md (new MOTION
   block), docs/POLICY.md, docs/STYLE_LORA.md. Register as **Session 25**,
   claim tasks with [S25], PROGRESS stamps via `date -u` ONLY (S24 caught
   its own future-stamp slip within minutes — read the clock immediately
   before every append).

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m pytest
   tests` (**406 expected** — S24 added no tests; the motion contract is
   S23's 27) + `make lint PY=/home/potato/miniconda3/bin/python3`, and
   verify the latest main CI run green (`gh run list --branch main`; S24's
   push is the newest run). If red: download the log, root-cause, fix the
   real substance FIRST.

## S25 work order (unless the camera flips the fork)

P6-2 is CLOSED (converter core S23 + bridge/gate S24). What remains in
Phase 6 is P6-3 (blocked on LO's answers) — so S25's rock is a declared
follow-up, in this order:

1. **A — chain-binding presets** (the P6-1 follow-up, declared twice as
   the most user-visible): extend the P0-09 per-rig preset schema so a
   saved preset can carry `secondary` chain bindings (ChainSpec list per
   rig, appendage bones resolved against the preset's mapping). Schema is
   format-versioned DATA with loud validation like every preset family;
   wire the panel/session path so a loaded preset feeds
   `bake_action(secondary=…)` without re-authoring chains per session.
   Design-first in docs/SECONDARY_MOTION.md (extend it, never fork it),
   CI tests for the schema, gate extension only if the probe discipline
   calls for one.
2. **B — if A lands early**: the retarget_clip session action, per the
   DESIGN sketch in docs/MOTION_LIBRARY.md — which starts with the
   honest refactor: promote the import/sample loop from
   `xtask/sample_clip.py` into a bpy-owning `riggermortis_addon` module
   (conftest-shim testable) with the xtask script becoming a thin caller,
   gate re-verified byte-identical BEFORE any new wiring. Schema stays
   v1 additive.
3. **C — if B also lands**: deepen the RM_MOTION REAL row with a second
   Xbot clip (run or sneak_pose) through the same path — measured rows
   into the BENCHMARKS MOTION block, gate line per clip.

Watch out for (S24's earned facts — do not re-learn them):

- **Fixture/sampler keying is JOINT-angle**: a pose-bone basis rotates the
  bone about its OWN head in the parent-posed frame — keying a parent's
  angle onto the child bends the joint (the first fixture draft doubled
  its stance drift to 0.029 u/f and the detector honestly refused it).
- **Blender 5.1.0's bundled FBX importer CRASHES on any light**
  (`lamp.cycles.cast_shadow` gone upstream) — generated/exported scenes
  must be factory-EMPTY before FBX export.
- **The Xbot `walk` REAL row has 0 detected plants — published, not
  tuned** (root motion → hips-anchored treadmill glide 0.022–0.19 u/f vs
  the D-008-untuned enter_speed 0.02). Do NOT retune contact thresholds to
  make real clips plant; the remedy is the declared coordinated
  positional/root-motion upgrade.
- The sampler's BVH axis flags (`axis_forward='Y', axis_up='Z'`) are a
  MEASURED contract; the mapper maps the BVH-conventional names 19/19 with
  0 corrections (measured S24), Xbot 21 roles + 46 unmapped.
- **The gate's env trap** (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  worse, grab the broken apt 4.0.2).
- **STATE timestamps are REAL**: `date -u` immediately before every
  PROGRESS append (S24 future-stamped one entry and corrected it in-line
  within minutes — don't be S24).
- **Mimosa** (standing): intercepts bash writes of ANY source-looking
  file — use Write/Edit; expect the pagedoc.py import-struct FP at every
  commit and push; heredoc/append FPs when text names source files.
- **Claim-bearing surfaces**: S24 touched ONLY the README status line
  (gate-cited numbers) + BENCHMARKS + MOTION_LIBRARY; LAUNCH.md and
  TUTORIALS.md and the README live bullet are untouched. Keep it that way
  unless a number actually changes, and grep all three together when it
  does.

## P6-3 scope probe — the licensing/redistribution questions ONLY LO can answer

(unchanged from S21/S22/S23; packaging waits)

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
   join the public suite under the same bar? NOTE (S24): the Xbot.glb
   `walk` clip now flows the whole pipeline — whether IT reopens P2-8 is
   LO's call (it is Mixamo-rooted synthetic-real hybrid data, not a human
   video).

Blocked / deferred (unchanged unless noted):

- Live capture device — NEEDS-HUMAN (DroidCam silent in S17–S24; the
  phone side must stream; P5-4 and the live capture→apply measurement wait
  on it — everything buildable shipped without it).
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks.
- P6-3 public benchmark suite — NEEDS-HUMAN (LO's answers gate packaging).
- P1-8a fallback estimator — parked (D-011/D-012).
- P2-8 real walking clip — NEEDS-HUMAN; the Xbot.glb `walk` clip (S23/S24)
  may satisfy much of what it wanted — LO's call whether that reopens it.
- Phase 4 — CLOSED (D-017); manga media regenerates via
  `bash xtask/manga_build.sh` (media-guard pins the 8 files).
- Phase 5 — P5-1..P5-3 DONE; P5-4 needs the camera.
- Phase 6 — P6-1 DONE (S22); P6-2 DONE (S23+S24); P6-4/P6-5 DONE (S21);
  P6-6 DONE (S23); P6-3 blocked on LO's answers.
- Phase 7: P7-1/P7-2/P7-3 DONE; P7-4/P7-5 account-bound; P7-6 waits on a
  recorded-cut session.
