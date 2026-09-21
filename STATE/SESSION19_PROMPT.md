Session 19 prompt (riggermortis)

Project (30-second context)
riggermortis — local, free, rig-agnostic posing & animation engine: (1)
Blender add-on, (2) MCP server so AI agents drive Blender. Drop a rigged
model + reference image → pose applied. Drop a video → animation,
retargeted, foot-slide-cleaned. Toon renders, manga pages. No cloud, no
accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).
Phases 0–4 CLOSED (D-017). Phase 5 OPEN — P5-1 DONE (S17), P5-2 DONE S18
on the buildable (replay) path (commits bd2ed4d + 2352433): the stream
consumer shipped — core LiveTail/LiveConsumer contract CI-tested with
fakes, the add-on live driver on the REAL P1-6 apply path, and the
`make live-verify` gate (REAL producer subprocess + REAL headless
Blender). CI at handoff: run 35655183017 (P5-2) verified GREEN in S18
(tests 3.11/3.13 + media-guard + blender-gate all success); the final
STATE push (2352433, the S18 CI record) was still in flight when S18
ended — STEP 0 includes verifying it (gh run list / gh run view) and, if
red, downloading the log and fixing the real substance FIRST (the
S12/S14/S15/S16/S17/S18 discipline).

P5-2's numbers (the facts S19 builds on) — docs/LIVE.md is the Phase-5
source of record (now covers P5-1 AND P5-2): 9/9 replay lines applied at
0.0000° worst FK self-check (bar 0.5°); Blender-side apply cost p95
≈ 3.8 ms; stream emit→apply p50 ≈ 157 ms with 0.6–0.9 s stalls landing
exactly on the producer's DETECTOR frames and the first line's ~2.1 s in
the cold-session window (consumer tick latency degrades under concurrent
detector load on this CPU — measured as-is, not tuned). The honest replay
end-to-end is EMIT → APPLY: on replayed files the envelope's age_ms is the
frame file's MTIME AGE (an hour), not capture latency — printed
informationally, never summed in. With a real camera, capture → apply =
age_ms + poll lag + apply. Staleness verified (driver flips STALE, keeps
the last pose); a forced all-miss stream (--conf-floor 0.95) yields 9
miss lines, 0 applies, pose bones byte-unchanged. The Phase-5 <100 ms
mid-laptop gate stays UNCLAIMED — camera still silent, nothing replay is
relabeled live.

STEP 0 — Session protocol (do this first, always)
Read, in order: STATE/NEXT.md (authoritative for S19 — its top item IS
this prompt's work order A), STATE/TASKS.md, STATE/PROGRESS.md (S18
entries), STATE/DECISIONS.md (esp. D-003, D-008, D-009, D-011/012,
D-015/016, D-017 — all EXECUTED, don't re-litigate), STATE/CONVENTIONS.md,
STATE/SESSIONS.md, docs/LIVE.md (EXTEND it with the P5-3 design section —
never fork a second live doc), docs/BENCHMARKS.md (LIVE block + the P5-2
consumer paragraph) + docs/POLICY.md. docs/STYLE.md stays the style
source of record — untouched unless style behavior changes. docs/
smoothing facts live in core/smoothing.py's docstring + tests (P2-2).

Register yourself in STATE/SESSIONS.md as Session 19. Claim tasks in
STATE/TASKS.md by ticking + tagging [S19] before working. Append
timestamped PROGRESS lines per meaningful unit (real UTC via `date -u`).

Verify baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest
tests (expect 339 passed — 327 + S18's 12 faked-stream consumer tests)
and make lint
PY=/home/potato/miniconda3/bin/python3 from repo root (lint list includes
xtask/live_probe.py + xtask/live_gate.py).

Environment facts (verified through S18)
Blender 5.1.0 at /home/potato/blender-5.1.0-linux-x64/ is the REAL install.
Gates need explicit env or they 127 on PATH:
BLENDER=/home/potato/blender-5.1.0-linux-x64/blender,
RIGPOSE=/home/potato/miniconda3/bin/rigpose,
PY=/home/potato/miniconda3/bin/python3. conda BASE is the project env.
onnxruntime 1.25.1 CPU provider ONLY (an RTX 3060 exists but no GPU ORT
provider is installed — the honest mid-laptop-relevant baseline); the
pinned DWPose models are downloaded and live (~/.local/share/riggermortis/
models — out/models is a leftover, don't be confused by it); local
ruff 0.16.7 == CI's.

The camera: /dev/video0 exists (DroidCam v4l2loopback) but delivered NO
frames in S17 AND S18 (ffmpeg timeout — the phone side is not streaming).
RE-VERIFY FIRST, one command:
  timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 \
    -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png
If frames land, the live halves (capture → apply measurement, P5-4 demo)
UNLOCK this session; if silent again, everything buildable stays on
replay frames, honestly labeled — exactly like S17/S18.

S15/S16/S17/S18 facts (do not reintroduce)
- Never render a VSE movie from any .py (racy segfault, D-009); movie
  assembly is shell-glue ffmpeg + ffprobe parse-back.
- Panels inherit the SCENE view transform (render_panels doesn't stage
  it): stage Standard + dither 0 explicitly in any page-scene.
- primitive_add deselects (explicit select_set on every part + active);
  canonical T-pose arm pivots sit wide (narrow BEFORE hang poses);
  elbow bends need a pose-relative Rodrigues axis; wide panels need a
  35 mm lens; pose bones default QUATERNION; a SPHERE is rotationally
  symmetric; Bright=0.15 changes ZERO channels (use Contrast); compositor
  graph = scene.compositing_node_group; GPv3 strokes via
  drawing.add_strokes, closed = cyclic; LineArt only via ops
  LINEART_OBJECT + renames; created objects captured by DATABLOCK DIFF.
- Bisect verdicts need run counts (3 runs minimum per config).
- Gate regexes: grep-test BOTH the PASS and SKIPPED lines locally
  before pushing.
- Mimosa intercepts bash writes of ANY source-looking file — use
  Write/Edit; .py-side artifact MOVES live in xtask/*.sh (D-009). Known FP
  on record: "command injection" on `import struct` in pagedoc.py (D-003,
  no process-execution interface in core) — expect it at every commit,
  disclose, move on. S18's one real advisory (shell $REPO interpolation in
  live_verify.sh) was restructured to an env-var pass.
- P5-1 live facts: the stream envelope's timing fields are MEASUREMENTS —
  never assert their values in tests (docs/LIVE.md determinism statement;
  pose data IS byte-identical, envelope excluded). The FIRST stream line
  carries the ~2 s cold session load in detect_ms — consumers warm up or
  drop it. Tracked figures carry identity from the last FULL detection;
  Figure.score is 0.0 on tracked figures (it is a DETECTOR score) — the
  quality signal is mean body confidence (17 COCO body kps, floor 0.3).
  kind=miss lines are NORMAL stream events; per-frame exceptions in the
  producer loop become miss lines — the loop never raises out. The
  detector CADENCE is the lever; input downscale is a dead knob.
- P5-2 consumer facts (new — S19 builds directly on this contract):
  core.live.LiveTail (byte-offset tail; torn-final-line safe — a partial
  line is never consumed until complete; producer restart detected by
  size-shrink OR the newline-boundary check: a line-oriented stream can
  only resume at a newline, so a regrown rewritten file resets to 0) +
  core.live.LiveConsumer (latest-wins per poll; a batch ENDING in a miss
  applies NOTHING; envelope-seq duplicates after a replay are never
  re-applied; stale = no new line past stale_after, default 2.0 s —
  order-of-magnitude, D-008, not tuned). The Blender side is a THIN
  adapter (addon/riggermortis_addon/live_driver.py): the ONLY bpy touch
  is the apply, main-thread; the pump never raises out of the timer
  (apply failures land in the status line with a hint); the stream line
  IS payload-v2 and goes through pose_apply.apply_payload unmodified
  (mirror = the scene toggle; figure label rides through). Gate glue:
  xtask/live_verify.sh + xtask/live_gate.py, RM_LIVE lines, RM_LIVE
  READY / READY-B log handshakes so budget rows measure the consumer
  loop (not Blender boot), producers run --idle-timeout 2 (a replay dir
  exhausts; the live default waits forever — right for a camera), and
  the miss run forces --conf-floor 0.95. The gate answers RM_LIVE GATE:
  SKIPPED honestly without models/frames/rig (grep-tested both paths);
  it is NOT in ci.yml by design (models are local) — the deterministic
  halves are CI-covered by the core fakes in tests/test_live.py.
- Do not "optimize" resolution or add smoothing to make numbers look
  better — measure, publish (D-008).

Work order (claim in this sequence; stop cleanly wherever you run out)

A. P5-3 — smoothing + latency/failsafe layer (the last camera-independent
   Phase-5 piece).
   DESIGN FIRST in docs/LIVE.md (a P5-3 section in the source of record):
   the smoothing wire point, the mirror/timestamp semantics, the failsafe
   policy — BEFORE any engine code. The honest forks to decide there:
   - Smoothing stays CORE-side and CI-tested (the S18 pattern: policy in
     core, addon thin). core/smoothing.py already ships OneEuroFilter /
     smooth_channel / smooth_pose_frames (P2-2, CI-tested). Wire it
     through the consumer contract ON THE CANONICAL POSE (per role,
     partial observation preserved — the P2-2 semantics), NOT as a
     bone-space hack after apply. Consequence to design for: the driver
     currently hands the payload dict to apply_payload; a smoothed pose
     goes through CanonicalPose.from_dict → filter → mirror →
     pose_apply.apply_pose_object (the payload path's own core — still
     the REAL P1-6 path; say so in LIVE.md). Time base: the envelope's
     t_emit_wall (wall seconds) feeds the 1€ filter's timestamps; decide
     and document what happens on gaps (miss lines) and staleness.
   - Mirror ordering: mirror before or after smoothing — decide from the
     math (mirroring commutes with per-axis filtering only if the filter
     state is also mirrored; simplest correct order documented first,
     then implemented once).
   - Defaults: min_cutoff/beta order-of-magnitude starting points, never
     tuned against fixtures (D-008). There is still NO real-motion stream
     — SMOOTHING CLAIMS STAY REPLAY-LABELED.
   - Latency/smoothing UI: promote the existing apply/emit→apply readout
     into a small "latency" block in the Live driver panel; smoothing
     on/off (+ the two constants read-only, or a preset row — no free
     numeric tuning UI). No graphs, no false precision.
   - The failsafe proper (P5-2's stub keeps the last pose + reports
     STALE): on SUSTAINED staleness drop to a defined safe state. The
     TASKS line says "drop to 30fps pose preview"; S18's proposal was
     hold N seconds → clear to rest (pose_apply.clear_pose exists) with
     an honest panel line. Decide the actual policy in docs/LIVE.md
     FIRST (thresholds order-of-magnitude, documented), implement it
     core-side where CI can test it with the faked clock, and keep the
     panel honest about which state it is in.
   Then GATE: extend make live-verify — a smoothing-sweep run (same
   replay frames, smoothing on/off; assert the applied pose curves are
   smoother by the P2-2 variance instrument AND fidelity stays within
   the 0.5° bar class) + failsafe assertions (sustained silence → the
   defined safe state + honest readout). New RM_LIVE lines; grep-test
   PASS and SKIPPED paths before pushing. Deterministic consumer tests
   with faked streams + the injected clock (extend test_live.py, the
   S18 pattern).
B. If A lands early: the launch-kit start (P7-1 README hero refresh +
   P7-3 drafts) — by then every launch claim still cites a gate/number/
   GIF. Never fake the live half (P5-4's 5-minute recorded demo NEEDS the
   camera; it is the last Phase-5 piece and stays blocked).
C. Cheap wins while gates run
- Windowed UI screenshot attempt (best-effort ~1-in-4; S10..S18 all
  missed — replaces docs/media/ui_screenshot.png ONLY if genuine; never
  staged).
- Doc cross-checks: README status line (Phase 5 bullet names P5-3 when
  it ships), AGENT_DEMO.md numbers (still citing the P3-7 run —
  unchanged until the demo re-runs).
- Keep docs/LIVE.md and docs/BENCHMARKS.md in sync with reality as you
  go (the STYLE.md rule applies to every source of record).

Non-negotiables (locked, from mission + CONVENTIONS)
QUALITY ABOVE ALL. Anything 80% done is 0% shipped. LOCAL OR NOTHING
(zero outbound in default use; loopback 127.0.0.1 ONLY, opt-in).
Rig-agnostic or fake — ambiguity reported, never swallowed. Honest
claims: every claim cites a test, number, or GIF; synthetic/replay stays
labeled; media rule — allowlist extension in the SAME commit as the
media, visual check before shipping any image. Deterministic ops: keyed
sorts, same input = same output (tested). No subprocess strings in any
.py; no sockets in core (D-003); core dependency-free except lazy
[inference]. Conventions: Python ≥3.10-compat, Z-up / facing −Y /
character-left = +X, canonical roles frozen API, refusal codes public
API, ruff + pytest green before commits (status check, not a piped
tail). STATE logs append-only, timestamps REAL via `date -u` (S18 caught
itself writing a guessed clock time — do not repeat that). Errors are
actionable — (hint: ...), never trace dumps. Do NOT tune solve priors,
contact thresholds, filter defaults, or latency budgets against fixtures
(D-008 — measure, publish, never fit). Do not loosen gate thresholds to
move numbers. The style gate's expectation (dev box AND CI on 5.1):
LINEART / TONES / PAGES / FRAMES / EXPORT PDF+EPUB / ANIMATIC: PASS +
the ffmpeg assembly PASS — a SKIPPED in CI means the bump broke, not an
honest degradation. 18+ module stays default-OFF, Phase 6 scope.

End of session (non-negotiable)
Tick claimed tasks in STATE/TASKS.md (completed vs partially-done with
what remains). Append PROGRESS lines (real UTC via `date -u`). Top of
STATE/NEXT.md: "NEXT SESSION SHOULD:" — write it for Session 20 (P5-4
demo prep vs the launch kit vs Phase-6 openers; say which and why —
note P5-4 NEEDS the camera, so the honest fork is launch kit vs Phase 6
if the stream is still silent). Update STATE/SESSIONS.md row. Commit +
push (routine commits authorized; CI runs — keep it green, fix inline
like S12/S14/S15/S16/S17/S18 did: download the run log, root-cause, fix
the real substance). If a Mimosa finding blocks: verify it's real, fix
inline, re-scan focused, commit again — and expect the pagedoc.py
import-struct FP every time.

Known blockers (parked — do not burn time on them)
Live capture device — NEEDS-HUMAN (DroidCam silent in S17 AND S18;
re-verify at session start; the phone side must stream). PyPI + Blender
Extensions + MCP registry submissions — account-bound (LO);
docs/PUBLISHING.md runbooks. Windowed Blender GL stability — best-effort
only (~1-in-4); never fake media to compensate. P1-8a fallback
estimator — parked (D-011/D-012). P2-8 real walking clip — NEEDS-HUMAN
(out/video_smoke/SOURCES.md).
