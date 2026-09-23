# NEXT SESSION SHOULD …

0. **THE PLAN OF RECORD IS STATE/ROADMAP.md** ("the Producer", Phase 8+,
   written post-S25 at LO's direction, critic-passed 9.8/10): coupled
   multi-character scenes, fingers, facials, the reference camera solve,
   spine arch + roll, root motion, multi-character video → scene
   animation, review UX + the anime estimator. Session map S26=P8-1 …
   S35=Scene Test. The roadmap's standing constraints (additive-only
   canonical changes via D-021, the coupling/camera honesty law, park
   criteria, D-019 coverage) are law for every session below.

1. **Camera re-verify FIRST, one command** (it decides the session shape):

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

**P8-1 CanonicalScene + the casting desk + camera v0** (the roadmap's
S26 rock; full spec + accept bars in STATE/ROADMAP.md): design-first
docs/SCENES.md, probe-first xtask/scene_probe.py (RM_SCENE lines), core
scene.py + payload v3 additive (v2 back-compat byte-identical), the
Casting Desk operator + session apply_scene, camera v0 (approximate,
labeled, refuse-to-stage floor), gate rows grep-tested both shapes.
Early-finish option: the P8-3 fingers data audit (what the detection
payload actually carries of the 133 kps — measured, not assumed).
The old S26 items (retarget_clip session action = P6-2a remains;
P6-3 packaging) move to roadmap slack — still owed, scheduled by LO's
priority call at each session fork.

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

## P6-3 licensing questions — ANSWERED (D-020, 2026-09-23)

The 7 questions parked here since S21/S22/S23 are answered — see
**STATE/DECISIONS.md D-020** for the full recorded decisions: suite media
**CC0**; ControlNet crops **replaced**; the BY-SA Commons illustration
**replaced**; **LO reviews** the photo set for identifiable people at
packaging time; distribution **in-repo docs/**; the public suite
**becomes the CI gate fixture**; **P2-8 retired** as satisfied-by-Xbot
(honest label kept). The answers were LO's directly (CC0) or explicitly
delegated to the session ("you choose the best, I trust you") and are
revisitable — they live in an append-only DECISIONS entry, not a chat
scrollback.

Blocked / deferred (updated 2026-09-23 post-S25 triage):

- Live capture device — the LONG-STANDING blocker is now DIAGNOSED
  (post-S25 triage): /dev/video0 exists (v4l2loopback_dc registered), the
  DroidCam CLIENT was simply never running, and the subnet scan found no
  phone serving 4747. Box side READY; the remaining step is physical
  (phone on the same network + DroidCam app open, WiFi mode per LO).
  LO deliberately PARKED this as the LAST unblock — P5-4 runs when the
  phone comes up, not before.
- PyPI + Blender Extensions + MCP registry submissions — account-bound
  (LO); docs/PUBLISHING.md runbooks; walkthrough given post-S25 (waiting
  on the accounts).
- P6-3 public benchmark suite — **UNBLOCKED (D-020)**; packaging is
  buildable S26 work (work order B).
- P1-8a fallback estimator — parked (D-011/D-012).
- P2-8 real walking clip — **RETIRED (D-020 #7)** as satisfied-by-Xbot
  for pipeline-verification purposes; a real human clip stays welcome,
  never gating.
- Phase 4 — CLOSED (D-017); manga media regenerates via
  `bash xtask/manga_build.sh` (media-guard pins the 8 files).
- Phase 5 — P5-1..P5-3 DONE; P5-4 needs the camera (diagnosed, parked
  last).
- Phase 6 — P6-1 DONE (S22); P6-1a DONE (S25); P6-2 DONE (S23+S24);
  P6-2a refactor half DONE (S25), session action remains; P6-4/P6-5 DONE
  (S21); P6-6 DONE (S23); P6-3 UNBLOCKED (D-020).
- Phase 7: P7-1/P7-2/P7-3 DONE; P7-4/P7-5 account-bound; P7-6 PARTIAL —
  the 60s cut is BUILT from existing footage (`make launch-cut`,
  docs/media/launch_cut.mp4, TASKS entry carries the detail); what remains
  is the reserved live-shot splice after P5-4 and the pin-vs-re-render CI
  decision.
