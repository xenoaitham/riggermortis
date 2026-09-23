# SESSION 25 PROMPT — riggermortis

Project (30-second context) riggermortis — local, free, rig-agnostic posing
& animation engine: (1) Blender add-on, (2) MCP server so AI agents drive
Blender. Drop a rigged model + reference image → pose applied. Drop a video
→ animation, retargeted, foot-slide-cleaned. Drop a Mixamo/BVH/FBX clip →
the same, via the motion library. Toon renders, manga pages. Live
pose-stream puppeteering (smoothing + failsafe) shipped on the replay path.
No cloud, no accounts, no uploads, ever.

Repo: /home/potato/osint/riggermortis — LIVE ON GITHUB:
https://github.com/xenoaitham/riggermortis (public, MIT, branch main).
Phases 0–4 CLOSED (D-017). Phase 5: P5-1/P5-2/P5-3 DONE (S17/S18/S19);
P5-4 (recorded live demo + the TRUE capture→apply measurement) is the last
Phase-5 piece — needs the camera. Phase 6: P6-4/P6-5 DONE (S21, aec492f);
P6-1 DONE (S22, def156a); P6-6 DONE (S23, docs-only); **P6-2 DONE
(S23 core + S24 bridge, this session)** — the motion library is complete:
imported Mixamo/BVH/FBX clips convert to the same canonical actions the
video pipeline produces, and the certified foot-slide cleanup runs
unchanged. P6-3 stays BLOCKED on LO's answers to the licensing question
list (7 questions, in STATE/NEXT.md — a POLICY call only LO makes; do not
package). Phase 7: P7-1/P7-2/P7-3 DONE (S20); P7-4/P7-5 account-bound
(LO); P7-6 waits on a recorded-cut session. STEP 0 includes verifying the
latest main run is green (gh run list / gh run view; if red: download the
log, root-cause, fix the real substance FIRST, the S12..S24 discipline).

S24's contract facts (what S25 builds on):

- docs/MOTION_LIBRARY.md is the motion-library design of record — EXTEND
  it, never fork a second motion doc. Its § What landed in S24 carries the
  bridge as-built; its § Instruments marks the sampler + fixture builder;
  its § Future holds the DESIGN-ONLY retarget_clip MCP session action
  sketch (schema stays v1 additive; the honest build path starts with
  promoting the import/sample loop into riggermortis_addon — no second
  copy of the loop, the D-016 lockstep lesson).
- **The bridge sampler** `xtask/sample_clip.py` (Blender-side, shell glue
  spawns it, D-009): builtin importers ONLY — BVH pins the MEASURED
  `axis_forward='Y', axis_up='Z'` (defaults land a 90° rotation, '-Y' a
  vertical mirror); the REAL core mapper (no name hardcoding; refuses
  with a hint if hips unmapped; measured: fixture names 19/19 with 0
  corrections, Xbot 21 roles + 46 honestly unmapped); per frame
  `frame_set` → `view_layer.update()` → mapped-role
  `pb.matrix.to_translation()` heads in ARMATURE space; format-1 clip
  JSON (scale_ref = measured rest torso span — Xbot measures 40.4154,
  cm-scale source, the scale-free contract's whole point; fingerprint
  carried; positions rounded 6 dp for stable bytes; near-static samples
  warn + note, never silent); multi-action files without `--action`
  refuse listing the actions; 5.x slot mismatch fixed explicitly; TWO
  sample passes must agree byte-for-byte (DETERM, exit 1 otherwise).
- **The fixture builder** `xtask/motion_fixture.py`: 49-frame SYNTHETIC
  sliding walk (rigid ±5° stance = 0.0143 canonical u/frame ankle drift,
  below the D-008-untuned 0.02 enter bar; 50° swing knee flexion; C1
  transitions), BVH+FBX generated at gate time into the gate's temp dir —
  nothing binary committed. KEYS ARE JOINT ANGLES: a basis rotates the
  bone about its own head in the parent-posed frame — keying a parent's
  angle onto the child bends the joint (first draft: stance drift doubled
  to 0.029 u/f, the detector honestly refused it; rigid stance = knee 0).
  Scenes must be factory-EMPTY before FBX export — 5.1.0's bundled FBX
  importer CRASHES on any light (`lamp.cycles.cast_shadow` gone upstream).
- **The RM_MOTION gate** (verify_pose_apply.sh): fixtures + sampler run
  as real per-file spawns, then the motion-gate probe converts
  (`action_from_clip`), runs the certified composition (detect → lock),
  bakes on the real metarig (`bake_action`, frame_offset=0, contacts
  passed) and independently re-evaluates fcurves at 6 spread frames.
  GATE NUMBERS (docs/BENCHMARKS.md MOTION, all gate-cited): fixture slide
  0.6140 u → 0.000014 u (**44997×**, bar ≥5×); contacts = the authored
  phases exactly (L (2,12)(25,36)(49), R (13,24)(37,48)); metarig re-eval
  0.0000° both rows (bars 0.5°; 84 + 96 checks); FBX vs BVH canonical
  0.000005 u (bar 0.005).
- **THE REAL-DATA FINDING (published, never tuned)**: the Xbot `walk`
  carries Mixamo ROOT MOTION → hips-anchored (walk-in-place, D-008) it
  becomes a treadmill whose stance feet glide 0.022–0.19 u/f — above the
  untuned enter_speed 0.02, so the detector honestly reports 0 plants and
  the lock is a verified bit-for-bit no-op. Do NOT retune contact
  thresholds to make real clips plant; the remedy is the declared
  coordinated positional/root-motion upgrade. In-place/slow clips plant
  normally (the fixture IS that shape).
- XBOT row: PASS on the local box (glb present), SKIPPED honestly without
  the clip sample — BOTH grep shapes verified; the full gate's top asset
  check exits early when the glb is absent (by design; the SKIPPED branch
  guards the direct-probe path).
- 406 tests (S24 added none — the motion contract is S23's 27). All prior
  gate numbers byte-identical through S24 (RM_BAKE 0.0242° ×3,
  RM_FOOT_LOCK 0.0371→0.0000 m, RM_SECONDARY 1.81°, RM_TAILS
  1.5177→0.2817 m). Claim-bearing surfaces: ONLY the README status line
  changed (gate-cited numbers); LAUNCH.md / TUTORIALS.md / the README
  live bullet untouched.
- S24 instrument catches (both fixed in-session, recorded in
  MOTION_LIBRARY.md): the joint-angle keying lesson above; the FBX
  light crash above; `RigData.fingerprint()` is a METHOD (call it, don't
  pass the bound method into JSON); the pose-apply gate's motion-gate
  heredoc reuses `bpy_bridge` (import it alongside bake/pose_apply).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the work order, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

If frames LAND (first time in twelve sessions): flip the work order to
P5-4 — record the live demo (xtask/live_capture.sh finally meets a
streaming device; debug the glue honestly, in the shell, per D-009),
measure the TRUE capture→apply budget (age_ms + poll lag + apply,
per-line), claim or retire the <100 ms mid-laptop gate with the measured
number, publish in LIVE.md + the BENCHMARKS blocks, update the three
claim-bearing surfaces in the SAME session. The D-018 failsafe/
duplicate-floor revisit trigger becomes live-relevant (deliberate
amendment or nothing, never silent).
If silent again (13th session): the S25 work order — **A: chain-binding
presets** (the P6-1 follow-up: extend the P0-09 per-rig preset schema so a
preset can carry secondary chain bindings; design-first in
docs/SECONDARY_MOTION.md, loud-validating format-versioned DATA, panel/
session wiring so a loaded preset feeds bake_action(secondary=…)). **B**
(if A lands early): the retarget_clip session action per the DESIGN
sketch — the honest refactor first (promote import/sample into a
bpy-owning addon module, conftest-shim testable; xtask script becomes a
thin caller; gate re-verified byte-identical BEFORE new wiring). **C** (if
B also lands): a second Xbot clip (run or sneak_pose) through the same
REAL row. **D cheap wins while gates run**: windowed UI screenshot attempt
(best-effort; miss #11 as of S24 — never stage a replacement); doc
cross-checks (README status vs TASKS/NEXT; the three claim-bearing
surfaces vs BENCHMARKS, one grep sweep; AGENT_DEMO.md numbers still cite
the P3-7 run; docs/PUBLISHING.md unchanged). Keep docs/LIVE.md and
docs/BENCHMARKS.md in sync with reality as you go.

Then read, in order: STATE/NEXT.md (authoritative for S25 — carries the
work order and the P6-3 question list for LO), STATE/TASKS.md (P6-2 DONE
entry carries the full S23+S24 state), STATE/PROGRESS.md (S24 entries),
STATE/DECISIONS.md (esp. D-003, D-008, D-009, D-015/016, D-017, D-019 —
EXECUTED, don't re-litigate; D-018 is RESERVED), STATE/CONVENTIONS.md,
STATE/SESSIONS.md, docs/MOTION_LIBRARY.md, docs/SECONDARY_MOTION.md,
docs/LIVE.md, docs/BENCHMARKS.md, docs/POLICY.md, docs/STYLE_LORA.md, and
the claim-bearing surfaces docs/LAUNCH.md + docs/TUTORIALS.md.
docs/STYLE.md stays the style source of record — untouched unless style
behavior changes.

Register yourself in STATE/SESSIONS.md as Session 25. Claim tasks in
STATE/TASKS.md by ticking + tagging [S25] before working. Append
timestamped PROGRESS lines per meaningful unit (REAL UTC via `date -u`
IMMEDIATELY before EVERY append — S24 future-stamped one entry and
corrected it within minutes; read the clock, then write the stamp).

Verify baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest
tests (expect 406 passed) and make lint PY=/home/potato/miniconda3/bin/
python3 from repo root.

Environment facts (verified through S24) — Blender 5.1.0 at
/home/potato/blender-5.1.0-linux-x64/ is the REAL install (the PATH
`blender` is the BROKEN apt 4.0.2 — never let a script grab it by
accident; ui_screenshot.sh guards this). Gates need explicit env:
BLENDER=/home/potato/blender-5.1.0-linux-x64/blender,
RIGPOSE=/home/potato/miniconda3/bin/rigpose,
PY=/home/potato/miniconda3/bin/python3. conda BASE is the project env.
onnxruntime 1.25.1 CPU provider ONLY (an RTX 3060 exists but no GPU ORT
provider — the honest mid-laptop-relevant baseline; see
docs/STYLE_LORA.md for the training-hardware truth); the pinned DWPose
models live in ~/.local/share/riggermortis/models; local ruff 0.16.7 ==
CI's. The live gate needs out/live_probe/smoke_frames +
out/real_rigs/metarig.rig.json (git-ignored) — without them it answers
RM_LIVE GATE: SKIPPED (...) honestly, exit 0. The walk manifests live at
out/p28/ (walk_docs.py --dir out/p28). The motion gate's XBOT row needs
out/real_rigs/Xbot.glb (present locally, absent in CI — and pose-verify
is a local gate anyway).

S15..S24 facts (do not reintroduce)

Never render a VSE movie from any .py (racy segfault, D-009); movie
assembly is shell-glue ffmpeg + ffprobe parse-back. Panels inherit the
SCENE view transform (stage Standard + dither 0 explicitly).
primitive_add deselects (explicit select_set); canonical T-pose arm pivots
sit wide (narrow BEFORE hang poses); elbow bends need a pose-relative
Rodrigues axis; wide panels need a 35 mm lens; pose bones default
QUATERNION — and IMPORTED rigs land euler modes (check before quaternion
writes); a SPHERE is rotationally symmetric; Bright=0.15 changes ZERO
channels (use Contrast); compositor graph = scene.compositing_node_group;
GPv3 strokes via drawing.add_strokes, closed = cyclic; LineArt only via
ops LINEART_OBJECT + renames; created objects captured by DATABLOCK DIFF.
EditBone uses .head/.tail; Bone uses .head_local/.tail_local. Bisect
verdicts need run counts (3 runs minimum per config). 5.x slotted
actions: legacy act.fcurves is GONE on fresh actions — iterate
layers→strips→channelbags→fcurves (export_clip.sh's fcurve_count and
sample_clip.py's iter_fcurves are the pattern). Gate regexes: grep-test
BOTH the PASS and SKIPPED lines locally before pushing. The blender
gate's policy section has NO skip path. Every new RM_ section must match
its own print shape exactly. Mimosa intercepts bash writes of ANY
source-looking file — use Write/Edit; expect the pagedoc.py
import-struct FP at every commit and push, disclose, move on; heredoc/
append FPs when text names source files — Edit tool + -F commit-message
files. P5-1 live facts: envelope timing fields are MEASUREMENTS — never
assert their values in tests; the FIRST stream line carries the ~2 s cold
session load; the detector CADENCE is the lever. P5-2/P5-3 facts:
LiveTail (torn-line safe, restart-safe) + LiveConsumer (latest-wins,
miss-keeps-pose, duplicate guard, stale default 2.0 s); smoothing is
CORE-side on the canonical pose; mirror order PROVEN (smooth-first);
defaults min_cutoff 1.0 / beta 0.05 D-008-untuned; failsafe = sustained
silence past failsafe_after → one-tick edge → clear to REST;
producer-restart suppression is the documented limit (D-018 reserved).
P6-1 facts: chains key strictly AFTER FK roles; appendage bones only;
D-008 spring constants untuned; direction-only translation-inert contract
pinned; pb = C @ rest @ basis PROVEN — compose locally, never read
pb.matrix mid-bake. P6-2 facts: see S24's contract facts above —
positions are the only convention-free metric; posed head =
pb.matrix.to_translation(); sample BEFORE any rotation-mode change;
retarget FK-applies onto the TARGET's topology.

Work order (claim in this sequence; stop cleanly wherever you run out)

A. The fork from STEP 0: A1 (camera alive) — P5-4 as above. A2 (camera
   silent) — chain-binding presets (work order A in NEXT.md). B. If A
   lands early: the retarget_clip session action (refactor-first per the
   sketch) or, if that feels too big late in the session, the second
   Xbot REAL row (work order C). C. Cheap wins while gates run: as listed
   in STEP 0's D.

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
defaults, spring constants, or latency budgets against fixtures (D-008 —
measure, publish, never fit). Do not loosen gate thresholds to move
numbers. The style gate's expectation (dev box AND CI on 5.1): LINEART /
TONES / PAGES / FRAMES / ANIMATIC / EXPORT PDF+EPUB: PASS + the ffmpeg
assembly PASS. 18+ module stays default-OFF; the enable path is the
add-on preferences ONLY (D-019); the policy spec in docs/POLICY.md is the
whole contract. Launch surfaces NEVER overstate. P6-6's rule (repo law
by docs): nothing in the repo trains anything — no training deps, no CI
training job, no new extras.

End of session (non-negotiable) Tick claimed tasks in STATE/TASKS.md
(completed vs partially-done with what remains). Append PROGRESS lines
(real UTC via date -u). Top of STATE/NEXT.md: "NEXT SESSION SHOULD:" —
write it for Session 26 (the honest fork again: P5-4 if the camera came
alive mid-stream; otherwise the next rock per what A actually closed —
say which and why). Write STATE/SESSION26_PROMPT.md (the S24→S25
pattern: updated context, the session's contract facts, STEP 0, work
order, non-negotiables) and commit it. Update STATE/SESSIONS.md row.
Commit + push (routine commits authorized; CI runs — keep it green, fix
inline like S12..S24: download the run log, root-cause, fix the real
substance). If a Mimosa finding blocks: verify it's real, fix inline,
re-scan focused, commit again — and expect the pagedoc.py import-struct
FP every time, plus the heredoc/commit-message FPs when text names
source files.

Known blockers (parked — do not burn time on them) Live capture device —
NEEDS-HUMAN (DroidCam silent in S17..S24; re-verify at session start with
the one command above; the phone side must stream). PyPI + Blender
Extensions + MCP registry submissions — account-bound (LO);
docs/PUBLISHING.md runbooks. P6-3 public benchmark suite —
NEEDS-LO-ANSWERS (the 7-question licensing list is in STATE/NEXT.md;
packaging waits). Windowed Blender GL stability — best-effort only; never
fake media to compensate. P1-8a fallback estimator — parked
(D-011/D-012). P2-8 real walking clip — NEEDS-HUMAN, but see the NEXT
note: the Xbot.glb walk clip may satisfy much of what it wanted — LO's
call.
