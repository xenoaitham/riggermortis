Session 20 prompt (riggermortis)

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Toon renders, manga pages. No
cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).
Phases 0–4 CLOSED (D-017). Phase 5 OPEN — P5-1 DONE (S17), P5-2 DONE on the
buildable (replay) path (S18), P5-3 DONE (S19, commit 220ddbf): the last
camera-independent Phase-5 piece shipped — core `LivePoseSmoother` (per-role
1€ on the canonical pose, mirror-order proven, defaults declared untuned) +
the failsafe (sustained stream silence → clear to rest, honest recovery) +
the latency/smoothing panel block + the extended live-verify gate (jitter
sweep 8.5x vs the P2-2 ≥4x bar; failsafe/rest/recovery runs). CI at handoff:
run 35669228199 (P5-3) verified GREEN in S19 (tests 3.11/3.13 + media-guard
+ blender-gate all success; the style gate's LINEART/TONES/PAGES/FRAMES/
ANIMATIC/EXPORT halves show PASS on 5.1 — the D-14 expectation); the last
pushes (c3d5265, 27711ad) are STATE-only records. STEP 0 includes verifying
the latest main run is green (gh run list / gh run view) and, if red,
downloading the log and fixing the real substance FIRST (the S12..S19
discipline).

P5-3's facts (the contract S20 builds on) — docs/LIVE.md is the Phase-5
source of record (covers P5-1 AND P5-2 AND P5-3):

- Smoothing is CORE-side ON THE CANONICAL POSE: payload →
  `CanonicalPose.from_dict` → `LivePoseSmoother.smooth(pose, t_emit_wall)` →
  mirror → `pose_apply.apply_pose_object` (the P1-6 apply's own core). The
  smoothing-OFF path is `pose_apply.apply_payload` unchanged — byte-identical
  P5-2 behavior, and run A of the gate stays that UNsmoothed control.
- Mirror order is PROVEN, not preference: the 1€ filter is odd-symmetric, so
  `smooth(mirror(p)) == mirror(smooth(p))` exactly on a consistently mirrored
  stream (CI-tested); smooth-first was chosen so a mid-session mirror toggle
  needs no filter-state surgery. Do not "simplify" to mirror-first.
- Time base: the envelope's `t_emit_wall` feeds the filter; gaps mean no
  update; long gaps open the filter (the next pose snaps through).
- Defaults `min_cutoff 1.0 Hz` / `beta 0.05` are DECLARED order-of-magnitude
  starting points (D-008) — there is still NO real-motion stream, so
  smoothing claims stay replay/synthetic-labeled. NEVER tune them against
  the gate fixture.
- Failsafe: `stale_after` keeps the last pose (P5-2 semantics unchanged);
  sustained silence past `failsafe_after` (default 10 s, core-validated to
  be > stale_after) fires a ONE-TICK edge in `LiveConsumer` (re-armed by any
  new event) → the driver clears to REST via `pose_apply.clear_pose`, resets
  the smoother (the first recovery pose passes through EXACTLY), and the
  panel says FAILSAFE; a continuing stream re-applies automatically.
- KNOWN LIMIT (documented in LIVE.md, not hidden): a producer RESTART with a
  fresh seq space is suppressed by the P5-2 duplicate floor (replayed-data
  semantics) — the operator remedy is Stop/Start on the panel. Revisit
  trigger: if the P5-4 demo shows this hurts real recovery, amend the S18
  duplicate contract deliberately (D-018 class: new tests + LIVE.md
  amendment), never silently.
- The gate's sweep instrument: J1/J2 are GATE-FED (no producer) from a
  fixture derived from run A's first REAL payload line — deterministic
  two-tone jitter, amplitude 0.01 canonical units, envelopes at 30 Hz
  spacing (the P2-2 sampling class); the bars are the P2-2 ≥4x variance
  instrument REUSED verbatim, not a new threshold; constant-channel
  stillness is asserted with an epsilon (1e-20), NOT ==0.0 (summing 40
  identical floats rounds — the gate caught this pre-ship; positions in
  budget rows are rounded to 1e-6).
- P5-3 measured (REPLAY/SYNTHETIC-labeled, docs/BENCHMARKS.md): run A 9/9 at
  0.0000° worst, apply p95 ≈ 2.7 ms, emit→apply p50 ≈ 124 ms (S19 run;
  S18 read 157 ms — run-to-run jitter is normal, stalls land on the
  producer's DETECTOR frames, the first line sits in the ~2 s cold window;
  never tune it away); sweep variance cut 8.5x on both jittered axes, mean
  tracking 9e-4 ≤ amplitude; failsafe edge at the configured 2.0 s (gate
  knob; default 10), rig byte-at-rest, recovery pass-through exact.

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the work order, one command:
  timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480
    -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png
- If frames LAND: flip the work order to P5-4 (the recorded live demo +
  the TRUE capture→apply measurement — the last Phase-5 piece; claim or
  retire the <100 ms mid-laptop gate honestly) and read the P5-4 scope in
  STATE/NEXT.md. The failsafe/duplicate-floor revisit trigger above becomes
  live-relevant too.
- If silent again (fourth session running): work order A is the LAUNCH KIT,
  exactly as NEXT.md plans. The camera is NEEDS-HUMAN (DroidCam phone side
  not streaming); do not burn time on it beyond the one probe.

Then read, in order: STATE/NEXT.md (authoritative for S20 — its top item IS
this prompt's work order A), STATE/TASKS.md, STATE/PROGRESS.md (S19
entries), STATE/DECISIONS.md (esp. D-003, D-008, D-009, D-011/012, D-015/
016, D-017 — all EXECUTED, don't re-litigate), STATE/CONVENTIONS.md,
STATE/SESSIONS.md, docs/LIVE.md (EXTEND it if a live design changes — never
fork a second live doc), docs/BENCHMARKS.md (LIVE block + the P5-2 consumer
paragraph + the P5-3 sweep/failsafe block) + docs/POLICY.md. docs/STYLE.md
stays the style source of record — untouched unless style behavior changes.
docs/ smoothing facts live in core/smoothing.py's docstring + tests.

Register yourself in STATE/SESSIONS.md as Session 20. Claim tasks in
STATE/TASKS.md by ticking + tagging [S20] before working. Append
timestamped PROGRESS lines per meaningful unit (REAL UTC via `date -u` —
S19 stamped guessed clock times twice and had to correct both in-repo; do
not write a clock value you did not read).

Verify baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest
tests (expect 349 passed — 327 + S18's 12 faked-stream tests + S19's 10
smoother/failsafe tests) and make lint PY=/home/potato/miniconda3/bin/
python3 from repo root.

Environment facts (verified through S19) — Blender 5.1.0 at
/home/potato/blender-5.1.0-linux-x64/ is the REAL install. Gates need
explicit env or they 127 on PATH: BLENDER=/home/potato/blender-5.1.0-linux-
x64/blender, RIGPOSE=/home/potato/miniconda3/bin/rigpose, PY=/home/potato/
miniconda3/bin/python3. conda BASE is the project env. onnxruntime 1.25.1
CPU provider ONLY (an RTX 3060 exists but no GPU ORT provider is installed
— the honest mid-laptop-relevant baseline); the pinned DWPose models live
in ~/.local/share/riggermortis/models (out/models is a leftover); local
ruff 0.16.7 == CI's. The live gate needs out/live_probe/smoke_frames +
out/real_rigs/metarig.rig.json (git-ignored) — without them it answers
`RM_LIVE GATE: SKIPPED (...)` honestly, exit 0.

S15/S16/S17/S18/S19 facts (do not reintroduce)

- Never render a VSE movie from any .py (racy segfault, D-009); movie
  assembly is shell-glue ffmpeg + ffprobe parse-back.
- Panels inherit the SCENE view transform (render_panels doesn't stage it):
  stage Standard + dither 0 explicitly in any page-scene.
- primitive_add deselects (explicit select_set on every part + active);
  canonical T-pose arm pivots sit wide (narrow BEFORE hang poses); elbow
  bends need a pose-relative Rodrigues axis; wide panels need a 35 mm lens;
  pose bones default QUATERNION; a SPHERE is rotationally symmetric;
  Bright=0.15 changes ZERO channels (use Contrast); compositor graph =
  scene.compositing_node_group; GPv3 strokes via drawing.add_strokes,
  closed = cyclic; LineArt only via ops LINEART_OBJECT + renames; created
  objects captured by DATABLOCK DIFF.
- Bisect verdicts need run counts (3 runs minimum per config).
- Gate regexes: grep-test BOTH the PASS and SKIPPED lines locally before
  pushing (live-verify's SKIPPED paths: missing frames dir, missing
  Blender, missing rigpose, missing models — all exit 0 with
  `RM_LIVE GATE: SKIPPED (...)`).
- Mimosa intercepts bash writes of ANY source-looking file — use Write/
  Edit; .py-side artifact MOVES live in xtask/*.sh (D-009). Known FP on
  record: "command injection" on import struct in pagedoc.py (D-003) —
  expect it at every commit, disclose, move on.
- P5-1 live facts: envelope timing fields are MEASUREMENTS — never assert
  their values in tests (pose data IS byte-identical, envelope excluded).
  The FIRST stream line carries the ~2 s cold session load in detect_ms.
  Tracked figures carry identity from the last FULL detection;
  Figure.score is 0.0 on tracked figures — the quality signal is mean body
  confidence (17 COCO body kps, floor 0.3). kind=miss lines are NORMAL
  stream events; the detector CADENCE is the lever; input downscale is a
  dead knob.
- P5-2 consumer facts: core.live.LiveTail (byte-offset tail; torn-final-
  line safe; producer restart detected by size-shrink OR the newline-
  boundary check) + core.live.LiveConsumer (latest-wins per poll; a batch
  ENDING in a miss applies NOTHING; envelope-seq duplicates after a replay
  are never re-applied; stale = no new line past stale_after, default
  2.0 s). The Blender side is a THIN adapter — the ONLY bpy touches are
  the apply, the failsafe clear, and the readout, main-thread; the pump
  never raises out of the timer (apply/failsafe failures land in the
  status line with a hint). The stream line IS payload-v2 through the REAL
  P1-6 path. The gate's RM_LIVE READY / READY-B log handshakes make budget
  rows measure the consumer loop, not Blender boot; producers run
  --idle-timeout 2 (a replay dir exhausts; the live default waits forever
  — right for a camera); the miss run forces --conf-floor 0.95. The gate
  is NOT in ci.yml by design (models are local) — the deterministic halves
  are CI-covered by the core fakes in tests/test_live.py.
- The replay budget definition: on replayed files the envelope's age_ms is
  the frame file's MTIME AGE (an hour), not capture latency — printed
  informationally, never summed in. The published replay end-to-end is
  EMIT → APPLY. With a real camera, capture → apply = age_ms + poll lag +
  apply. The Phase-5 <100 ms mid-laptop gate stays UNCLAIMED — never
  relabel replay numbers live.
- Do not "optimize" resolution or add smoothing strength to make numbers
  look better — measure, publish (D-008).

Work order (claim in this sequence; stop cleanly wherever you run out)

A. P7-1 — README hero refresh + honest limitations. The README is good but
   Phase-4-shaped: fold the live-mode story in properly (P5-1 budget table
   numbers, P5-2 consumer gate, P5-3 conditioning + failsafe) and refresh
   the limitations block so a stranger knows exactly what is measured vs
   labeled. Rules:
   - Every claim cites a gate, number, or GIF (docs/BENCHMARKS.md is the
     numbers source; link, never re-transcribe by hand where a generator
     owns the block).
   - The <100 ms live gate stays UNCLAIMED in launch copy too; replay/
     synthetic labels carry through verbatim ("measured on replayed
     frames; real-camera number pending" — the repo's own phrasing).
   - Honest limitations to state plainly: single-view solve limits (the
     two documented D-008 miss classes), the anime detector gap (D-011/
     D-012, 3/10 no-person at n=10), synthetic-labeled motion media, the
     live demo pending a camera, windowed-GL flakiness on the dev box.
   - Existing launch media (boom.gif, walk_3rigs.gif, agent_turntable.gif)
     are pipeline-generated — reference, never hand-edit. If ANY new media
     ships: allowlist extension in the SAME commit + visual check before
     shipping (the media rule), and it must be pipeline-generated.
B. P7-3 — docs/LAUNCH.md drafts: Show-HN post, BlenderNation blurb,
   r/blender post, tweet thread, 60-second video script. Same claim
   discipline: each claim in each draft cites its test/gate/GIF; the live
   half is labeled; the 60s script cuts ONLY from footage that exists
   (pipeline GIFs + gate renders + the P3-7 agent demo transcript) — no
   promised-but-unfilmed live demo. Include the install/quickstart paths
   that actually work today (pip install -e core[inference], the add-on
   zip, the MCP stdio config) and the honest "what's next" line (real-
   camera capture number pending).
C. If A+B land early: P7-2 tutorial skeletons (gamedev / VTuber /
   webcomic / indie-animator) — outlines with real command sequences only;
   a tutorial that needs the camera or unshipped features stays an outline
   with the gap named.
D. Cheap wins while gates run
- Windowed UI screenshot attempt (best-effort ~1-in-4; S10..S19 all
  missed — replaces docs/media/ui_screenshot.png ONLY if genuine; never
  staged).
- Doc cross-checks: README status line vs TASKS/NEXT reality after your
  edits; AGENT_DEMO.md numbers (still citing the P3-7 run — unchanged
  until the demo re-runs); docs/PUBLISHING.md runbooks unchanged.
- Keep docs/LIVE.md and docs/BENCHMARKS.md in sync with reality as you go.

Non-negotiables (locked, from mission + CONVENTIONS) QUALITY ABOVE ALL.
Anything 80% done is 0% shipped. LOCAL OR NOTHING (zero outbound in
default use; loopback 127.0.0.1 ONLY, opt-in). Rig-agnostic or fake —
ambiguity reported, never swallowed. Honest claims: every claim cites a
test, number, or GIF; synthetic/replay stays labeled; media rule —
allowlist extension in the SAME commit as the media, visual check before
shipping any image. Deterministic ops: keyed sorts, same input = same
output (tested). No subprocess strings in any .py; no sockets in core
(D-003); core dependency-free except lazy [inference]. Conventions:
Python ≥3.10-compat, Z-up / facing −Y / character-left = +X, canonical
roles frozen API, refusal codes public API, ruff + pytest green before
commits (status check, not a piped tail). STATE logs append-only,
timestamps REAL via date -u. Errors are actionable — (hint: ...), never
trace dumps. Do NOT tune solve priors, contact thresholds, filter
defaults, or latency budgets against fixtures (D-008 — measure, publish,
never fit). Do not loosen gate thresholds to move numbers. The style
gate's expectation (dev box AND CI on 5.1): LINEART / TONES / PAGES /
FRAMES / EXPORT PDF+EPUB / ANIMATIC: PASS + the ffmpeg assembly PASS — a
SKIPPED in CI means the bump broke, not an honest degradation. 18+ module
stays default-OFF, Phase 6 scope. Launch drafts NEVER overstate: a draft
that needs a number the repo hasn't published gets the number's absence
stated, not rounded up.

End of session (non-negotiable) Tick claimed tasks in STATE/TASKS.md
(completed vs partially-done with what remains). Append PROGRESS lines
(real UTC via date -u). Top of STATE/NEXT.md: "NEXT SESSION SHOULD:" —
write it for Session 21 (the honest fork: P5-4 demo prep if the camera
came alive; otherwise P7-2 tutorials vs Phase-6 openers (P6-3 benchmark
packaging or P6-4/P6-5 the 18+ enforcement pair) — say which and why).
Update STATE/SESSIONS.md row. Commit + push (routine commits authorized;
CI runs — keep it green, fix inline like S12..S19: download the run log,
root-cause, fix the real substance). If a Mimosa finding blocks: verify
it's real, fix inline, re-scan focused, commit again — and expect the
pagedoc.py import-struct FP every time.

Known blockers (parked — do not burn time on them) Live capture device —
NEEDS-HUMAN (DroidCam silent in S17, S18, AND S19; re-verify at session
start with the one command above; the phone side must stream). PyPI +
Blender Extensions + MCP registry submissions — account-bound (LO);
docs/PUBLISHING.md runbooks. Windowed Blender GL stability — best-effort
only (~1-in-4); never fake media to compensate. P1-8a fallback estimator
— parked (D-011/D-012). P2-8 real walking clip — NEEDS-HUMAN
(out/video_smoke/SOURCES.md).
