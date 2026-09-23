# NEXT SESSION SHOULD …

1. **Camera re-verify FIRST, one command** (it decides everything):

   `timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png`

   - **Frames land** → flip to **P5-4** (the recorded live demo + the TRUE
     capture→apply measurement; claim or retire the <100 ms mid-laptop gate
     honestly; update the three live-number surfaces in the same session;
     the D-018 failsafe/duplicate-floor revisit trigger becomes
     live-relevant). Silent 13 straight sessions so far.
   - **Silent again (14th)** → the work order below. P6-3 packaging stays
     blocked until LO answers the licensing questions (a POLICY call only
     LO makes; the 7 questions are at the bottom of this file).

2. **Then read, in order**: STATE/TASKS.md (P6-1a DONE with the full S25
   entry; P6-2a CLAIMED with the refactor half done), STATE/PROGRESS.md
   (S25 entries), STATE/DECISIONS.md (D-019 executed; D-018 stays
   RESERVED), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
   docs/MOTION_LIBRARY.md (its § Future sketch is now HALF-built: the
   sampler loop lives in `riggermortis_addon/clip_sample.py`, the
   session-action wiring is what remains), docs/SECONDARY_MOTION.md (§
   Chain-binding presets = the P6-1a as-built), docs/LIVE.md,
   docs/BENCHMARKS.md (SECONDARY block gained the P6-1a equivalence row),
   docs/POLICY.md, docs/STYLE_LORA.md. Register as **Session 26**, claim
   tasks with [S26], PROGRESS stamps via `date -u` read IMMEDIATELY before
   every append (S25 future-stamped twice and corrected both within
   minutes — read the clock, then write the stamp, then verify the stamp).

3. **Baseline**: `cd core && /home/potato/miniconda3/bin/python3 -m pytest
   tests` (**431 expected** — S25 added 20: 17 preset-schema + 3 CLI + 5
   clip-sample… minus none removed) + `make lint
   PY=/home/potato/miniconda3/bin/python3`, and verify the latest main CI
   run green (`gh run list --branch main`; S25's push is the newest run).
   If red: download the log, root-cause, fix the real substance FIRST.

## S26 work order (unless the camera flips the fork)

P6-1a is CLOSED (schema + CLI + session wiring + gate equivalence row).
The sampler refactor (the retarget_clip precondition) is DONE. So:

1. **A — the retarget_clip session action** (task P6-2a, its REMAINS
   list): the executor branch in `addon/session.py` calling
   `clip_sample.sample_clip(...)` in-process (the loop is already
   add-on-owned — no second copy, the D-016 lesson applied early), then
   `core.action_from_clip` → the certified composition → `bake_action` on
   the scene's mapped rig, returning the metrics the gate prints
   (frames/roles/scale_ref/contacts/slide/reeval). Local paths only
   (D-003); the action vocabulary is additive (P3-5 bridge); gate +
   session-verify rows proving it, grep-tested both shapes. Schema v1
   stays v1.
2. **B — if A lands early**: deepen the RM_MOTION REAL row with a second
   Xbot clip (run or sneak_pose — the glb carries SEVEN clips) through the
   same path, measured rows into the BENCHMARKS MOTION block.
3. **C — cheap wins while gates run**: windowed UI screenshot attempt
   (best-effort; miss #12 as of S25 — never stage a replacement); doc
   cross-checks (README status vs TASKS/NEXT; the three claim-bearing
   surfaces vs BENCHMARKS, one grep sweep; AGENT_DEMO.md numbers still
   cite the P3-7 run; docs/PUBLISHING.md unchanged). Keep docs/LIVE.md and
   docs/BENCHMARKS.md in sync with reality as you go.

Watch out for (S25's earned facts — do not re-learn them):

- **presets.py is package-imported since P6-1a** — its `from . import
  __version__` is DEFERRED inside `preset_from_mapping` (a module-level
  import there is a circular-import crash). Same trap for any module
  `__init__` gains.
- **Preset schema is format 2 (write) / formats 1+2 (read)** — never bump
  without widening `_READ_FORMATS`, and never add a binding field without
  going through `SecondaryBinding.from_dict` (the ONE validator: unknown
  fields refuse, bones == links, one-bone-per-chain via `_check_bindings`
  on BOTH the load path and the constructor).
- **The binding validation is two-layer by design**: the preset loader
  checks what a file can know (no rig); `bake_action` re-validates every
  bone against the LIVE rig (exists, parent-first under the anchor's
  mapped bone, not role-mapped, not double-bound across chains). Do not
  collapse the layers.
- **Sampler promotion contract**: `xtask/sample_clip.py` is a THIN CALLER;
  the loop is `riggermortis_addon/clip_sample.py` with bpy imported
  INSIDE functions (conftest-shim importable). The RM_MOTION SAMPLE/
  DETERM/WRITE lines are the gate's grep surface — they live in
  `sample_clip()`'s report and must stay byte-stable. Error-path exit
  codes: usage 64, refusals 3, DETERM fail 1 (the old 66 for a missing
  file became 3; nothing depended on 66).
- **Byte-identity proofs are cheap**: `git stash push -- <file>`, run the
  old path, `git stash pop`, diff. S25 proved the sampler promotion this
  way (57111 bytes == 57111 bytes). Use it for the session action too.
- **Fixture/sampler keying is JOINT-angle** (S24, standing); **5.1's FBX
  importer crashes on any light** (factory-EMPTY scenes, standing); **the
  Xbot walk REAL row has 0 detected plants — published, not tuned**
  (root motion → hips-anchored glide above the D-008-untuned enter bar;
  remedy = the declared positional/root-motion upgrade, never
  threshold-fitting).
- **The gate's env trap** (standing): BLENDER=/home/potato/
  blender-5.1.0-linux-x64/blender, RIGPOSE=/home/potato/miniconda3/bin/
  rigpose, PY=/home/potato/miniconda3/bin/python3 — else they 127 (or
  worse, grab the broken apt 4.0.2).
- **STATE timestamps are REAL**: `date -u` immediately before every
  PROGRESS append — and CHECK the stamp against the clock after writing
  (S25 wrote 21:40Z when the clock said 21:27Z and fixed it in minutes;
  the S24 slip, twice).
- **Mimosa** (standing): intercepts bash writes of ANY source-looking
  file — use Write/Edit (S25: a `git show HEAD:file > /tmp/x.py` redirect
  was blocked; a pathspec-scoped `git stash push -- <file>` routed the
  byte-identity proof around it without bypassing the scanner); expect
  the pagedoc.py import-struct FP at every commit and push; heredoc/append
  FPs when text names source files.
- **Claim-bearing surfaces**: S25 touched ONLY the README status line
  (gate-cited numbers) + BENCHMARKS + SECONDARY_MOTION + MOTION_LIBRARY;
  LAUNCH.md and TUTORIALS.md and the README live bullet are untouched
  (git-diff-verified at close). Keep it that way unless a number actually
  changes, and grep all three together when it does.

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

- Live capture device — NEEDS-HUMAN (DroidCam silent in S17–S25; the
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
- Phase 6 — P6-1 DONE (S22); P6-1a DONE (S25); P6-2 DONE (S23+S24);
  P6-2a refactor half DONE (S25), session action remains; P6-4/P6-5 DONE
  (S21); P6-6 DONE (S23); P6-3 blocked on LO's answers.
- Phase 7: P7-1/P7-2/P7-3 DONE; P7-4/P7-5 account-bound; P7-6 waits on a
  recorded-cut session.
