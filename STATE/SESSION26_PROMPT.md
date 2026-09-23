# SESSION 26 PROMPT — riggermortis

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
P6-1 DONE (S22, def156a); P6-6 DONE (S23, docs-only); P6-2 DONE (S23 core +
S24 bridge); **P6-1a DONE (S25, this session)** — chain-binding presets:
a per-rig preset (format 2, back-compat read of 1) carries `secondary`
chain bindings fingerprint-gated from author to bake; **P6-2a's REFACTOR
HALF DONE (S25)** — the clip sampler loop is add-on-owned
(`riggermortis_addon/clip_sample.py`), `xtask/sample_clip.py` is a thin
caller, output proven BYTE-IDENTICAL at promotion. The retarget_clip
session action (P6-2a's remains) is S26's rock. **P6-3 is UNBLOCKED
(D-020, recorded post-S25): the 7 licensing questions are ANSWERED
(CC0 suite, ControlNet + BY-SA slots replaced, in-repo distribution, the
suite becomes the CI gate fixture, P2-8 retired as satisfied-by-Xbot) —
packaging is buildable work order material, do package.** Phase 7:
P7-1/P7-2/P7-3 DONE (S20); P7-4/P7-5 account-bound (LO); P7-6 waits on a
recorded-cut session. The camera blocker is DIAGNOSED but deliberately
PARKED LAST (see Known blockers).
STEP 0 includes verifying the latest main run is green (gh run list / gh
run view; if red: download the log, root-cause, fix the real substance
FIRST, the S12..S25 discipline).

S25's contract facts (what S26 builds on):

- **Preset schema format 2** (`core/presets.py`): WRITES format 2, READS
  formats 1+2 (the P1-11 payload pattern; an old build reading a new file
  refuses loudly). New optional `secondary` list of bindings, each EXACTLY
  `{"chain": <ChainSpec dict>, "bones": [parent-first appendage names]}`.
  `chain` validates through `core.secondary.ChainSpec.from_dict` (ONE
  validator); bones must be non-empty unique strings with
  `len(bones) == chain.links`. `_check_bindings` runs on BOTH the load
  path (`_secondary_from_dict`) and the direct constructor
  (`preset_from_mapping(secondary=…)`): chain names unique, ONE bone per
  chain (cross-chain double-bind refuses). Bindings stored sorted by chain
  name; already-unit rest directions pass through normalization unchanged
  so re-save is byte-stable (test-pinned).
- **`resolve_secondary(preset, rig_fingerprint, force=False)`** is the
  binding gate — the SAME fingerprint contract as the mapping, with the
  apply-time hint. The validation is TWO-LAYER by design: the loader
  checks what a file can know (no rig); `bake_action` re-validates every
  bone against the LIVE rig (exists, parent-first under the anchor role's
  mapped bone, not role-mapped, not double-bound — the bake grew the same
  cross-chain guard). Do not collapse the layers.
- **CLI authoring**: `rigpose preset save RIG OUT --secondary
  BINDINGS.json` and `rigpose preset set-secondary PRESET BINDINGS.json`
  (add/replace chains without re-mapping); `preset load`/`save` print the
  chains (payload visible, never hidden). A bindings file is EXACTLY
  `{"format": 1, "secondary": [binding, …]}` (loud unknown-field refusal;
  a bare list refuses).
- **Session wiring**: the `bake_action` executor (`addon/session.py`)
  gains `preset_path` + `preset_force` + `fps` (default 30.0 — the frame
  rate the secondary simulation assumes; substep alignment is exact for
  any fps). Load → fingerprint-gate → `simulate_secondary` over the
  CERTIFIED (locked) action → feed `bake_action(secondary=…)`. A chain
  whose anchor never orients reports `never_started`; the bake proceeds
  with the chains that did start. Result carries `secondary_preset` + the
  bake's per-chain `secondary` counts.
- **GATE**: `RM_SECONDARY PRESET` (the full author → save → load → gate →
  simulate → bake path in real Blender keys EXACTLY what the direct
  binding keyed: format=2 chains=1 keys=280 direct_keys=280) +
  `RM_SECONDARY PRESET_GATE` (mismatch_refused=True, force_bindings=1),
  both grep-pinned in verify_pose_apply.sh. docs/BENCHMARKS.md SECONDARY
  block carries the equivalence row; docs/SECONDARY_MOTION.md §
  Chain-binding presets is design + as-built; README status line gained
  the gate-cited clause (the ONLY claim-bearing surface touched —
  LAUNCH/TUTORIALS/README-live-bullet git-diff-verified untouched).
- **The sampler promotion (P6-2a half)**: the import/sample loop lives in
  `addon/riggermortis_addon/clip_sample.py` (bpy imported INSIDE
  functions — conftest-shim importable; generic `addon_module()` helper
  in conftest.py, `addon_policy_module()` delegates); the RM_MOTION
  SAMPLE/DETERM/WRITE lines live in `sample_clip()`'s report dict and are
  the gate's grep surface (byte-stable). `xtask/sample_clip.py` = thin
  caller (argv/env glue; usage exit 64, refusals 3, DETERM fail 1 — the
  old 66 for a missing file became 3; nothing depended on it).
  Byte-identity PROVEN at promotion: git-HEAD script vs library → the
  same 57111-byte fixture JSON; gate re-verified with every RM_MOTION
  number unchanged. The `retarget_clip` session action can now call
  `clip_sample.sample_clip(...)` directly — its remaining sketch is
  docs/MOTION_LIBRARY.md § Future.
- 431 tests (S25 added 20: 17 in `test_preset_secondary.py`, 3 CLI
  round-trips in `test_cli.py`, 5 in `test_clip_sample.py`). All prior
  gate numbers byte-identical through S25 (RM_BAKE 0.0242° ×3,
  RM_FOOT_LOCK 0.0371→0.0000 m, RM_SECONDARY 1.81°/280 keys, RM_TAILS
  1.5177→0.2817 m, the whole RM_MOTION block). Full battery PASS: lint +
  431 + media-guard + blender-verify + session-verify + pose-verify ×2.
- S25 instrument catches (fixed in-session, recorded here): the circular
  import (`presets.py` is package-imported since P6-1a — its
  `from . import __version__` is DEFERRED inside `preset_from_mapping`;
  module-level there crashes the package); the Mimosa bash-write
  interception on a `git show … > /tmp/x.py` redirect (routed around with
  a pathspec-scoped `git stash push -- <file>` for the byte-identity
  proof — no scanner bypass); two future-stamped PROGRESS entries caught
  and corrected within minutes (READ the clock, THEN write the stamp,
  THEN verify).

STEP 0 — Session protocol (do this first, always)

CAMERA FORK FIRST — it decides the work order, one command:

timeout 12 ffmpeg -hide_banner -loglevel error -f v4l2 -video_size 640x480 -i /dev/video0 -frames:v 1 out/live_probe/cam_test.png

If frames LAND (first time in thirteen sessions): flip the work order to
P5-4 — record the live demo (xtask/live_capture.sh finally meets a
streaming device; debug the glue honestly, in the shell, per D-009),
measure the TRUE capture→apply budget (age_ms + poll lag + apply,
per-line), claim or retire the <100 ms mid-laptop gate with the measured
number, publish in LIVE.md + the BENCHMARKS blocks, update the three
claim-bearing surfaces in the SAME session. The D-018 failsafe/
duplicate-floor revisit trigger becomes live-relevant (deliberate
amendment or nothing, never silent).
If silent again (14th session): the S26 work order — **A: the
retarget_clip session action** (task P6-2a's REMAINS list: executor
branch in addon/session.py calling `clip_sample.sample_clip(...)`
in-process → `action_from_clip` → the certified composition →
`bake_action` on the scene's mapped rig, metrics returned; local paths
only per D-003; gate + session-verify rows, grep-tested both shapes;
schema v1 stays v1). **B: P6-3 packaging per D-020** (replace the 2
ControlNet slots + the BY-SA slot with owned/CC0 art — n=10 kept,
honest re-run note for swapped slots; SOURCES manifest; media-guard
allowlist in the same commits; the CI detection job over the public
suite; LO reviews the photo set for identifiable people before it
ships). **C** (if A and B land early): a second Xbot clip (run or
sneak_pose — the glb carries SEVEN real clips) through the same REAL
row, measured into BENCHMARKS MOTION. **D cheap wins while gates run**:
windowed UI screenshot attempt (best-effort; miss #12 as of S25 — never
stage a replacement); doc cross-checks (README status vs TASKS/NEXT; the
three claim-bearing surfaces vs BENCHMARKS, one grep sweep;
AGENT_DEMO.md numbers still cite the P3-7 run; docs/PUBLISHING.md
unchanged). Keep docs/LIVE.md and docs/BENCHMARKS.md in sync with
reality as you go.

Then read, in order: STATE/NEXT.md (authoritative for S26 — carries the
work order and the P6-3 question list for LO), STATE/TASKS.md (P6-1a DONE
entry carries the full S25 state; P6-2a carries the refactor boundary),
STATE/PROGRESS.md (S25 entries), STATE/DECISIONS.md (esp. D-003, D-008,
D-009, D-015/016, D-017, D-019 — EXECUTED, don't re-litigate; D-018 is
RESERVED; **D-020 is the P6-3 licensing answers — the packaging brief**), STATE/CONVENTIONS.md, STATE/SESSIONS.md,
docs/MOTION_LIBRARY.md, docs/SECONDARY_MOTION.md, docs/LIVE.md,
docs/BENCHMARKS.md, docs/POLICY.md, docs/STYLE_LORA.md, and the
claim-bearing surfaces docs/LAUNCH.md + docs/TUTORIALS.md.
docs/STYLE.md stays the style source of record — untouched unless style
behavior changes.

Register yourself in STATE/SESSIONS.md as Session 26. Claim tasks in
STATE/TASKS.md by ticking + tagging [S26] before working. Append
timestamped PROGRESS lines per meaningful unit (REAL UTC via `date -u`
IMMEDIATELY before EVERY append — read the clock, write the stamp, then
VERIFY the stamp; S25 future-stamped twice and corrected both in
minutes).

Verify baseline: cd core && /home/potato/miniconda3/bin/python3 -m pytest
tests (expect 431 passed) and make lint PY=/home/potato/miniconda3/bin/
python3 from repo root.

Environment facts (verified through S25) — Blender 5.1.0 at
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

S15..S25 facts (do not reintroduce)

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
clip_sample.iter_fcurves are the pattern). Gate regexes: grep-test BOTH
the PASS and SKIPPED lines locally before pushing. The blender gate's
policy section has NO skip path. Every new RM_ section must match its own
print shape exactly. Mimosa intercepts bash writes of ANY source-looking
file — use Write/Edit; expect the pagedoc.py import-struct FP at every
commit and push, disclose, move on; heredoc/append FPs when text names
source files — Edit tool + -F commit-message files. P5-1 live facts:
envelope timing fields are MEASUREMENTS — never assert their values in
tests; the FIRST stream line carries the ~2 s cold session load; the
detector CADENCE is the lever. P5-2/P5-3 facts: LiveTail (torn-line safe,
restart-safe) + LiveConsumer (latest-wins, miss-keeps-pose, duplicate
guard, stale default 2.0 s); smoothing is CORE-side on the canonical
pose; mirror order PROVEN (smooth-first); defaults min_cutoff 1.0 /
beta 0.05 D-008-untuned; failsafe = sustained silence past failsafe_after
→ one-tick edge → clear to REST; producer-restart suppression is the
documented limit (D-018 reserved). P6-1 facts: chains key strictly AFTER
FK roles; appendage bones only; D-008 spring constants untuned;
direction-only translation-inert contract pinned; pb = C @ rest @ basis
PROVEN — compose locally, never read pb.matrix mid-bake. P6-2 facts:
positions are the only convention-free metric; posed head =
pb.matrix.to_translation(); sample BEFORE any rotation-mode change;
retarget FK-applies onto the TARGET's topology. P6-1a/P6-2a facts: see
S25's contract facts above — presets format 2 write / 1+2 read,
two-layer binding validation, deferred `__version__` import,
byte-identity proofs via `git stash push -- <file>` + pop + diff.

Work order (claim in this sequence; stop cleanly wherever you run out)

A. The fork from STEP 0: A1 (camera alive) — P5-4 as above. A2 (camera
   silent) — the retarget_clip session action (task P6-2a's REMAINS list;
   the sketch in docs/MOTION_LIBRARY.md § Future; the loop is already
   add-on-owned — wire it, gate it, prove it). B. If A lands early: the
   second Xbot REAL row (work order B in NEXT.md). C. Cheap wins while
   gates run: as listed in STEP 0's C.

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
write it for Session 27 (the honest fork again: P5-4 if the camera came
alive mid-stream; otherwise the next rock per what A actually closed —
say which and why). Write STATE/SESSION27_PROMPT.md (the S25→S26
pattern: updated context, the session's contract facts, STEP 0, work
order, non-negotiables) and commit it. Update STATE/SESSIONS.md row.
Commit + push (routine commits authorized; CI runs — keep it green, fix
inline like S12..S25: download the run log, root-cause, fix the real
substance). If a Mimosa finding blocks: verify it's real, fix inline,
re-scan focused, commit again — and expect the pagedoc.py import-struct
FP every time, plus the heredoc/commit-message FPs when text names
source files.

Known blockers (parked — do not burn time on them) Live capture device —
DIAGNOSED post-S25 (not a missing device: /dev/video0 exists via
v4l2loopback_dc; the DroidCam client process was never running and no
phone served port 4747 anywhere on 192.168.100.0/24 — box side READY,
phone step physical). LO deliberately PARKED it as the LAST unblock:
when he brings the phone up (WiFi mode, same network, DroidCam app open),
run the client, re-verify with the one command above, and P5-4 becomes
the session's work. PyPI + Blender Extensions + MCP registry
submissions — account-bound (LO; walkthrough given post-S25);
docs/PUBLISHING.md runbooks. P6-3 public benchmark suite — UNBLOCKED
(D-020); packaging is work order B, not a blocker. Windowed Blender GL
stability — best-effort only; never fake media to compensate. P1-8a
fallback estimator — parked (D-011/D-012). P2-8 real walking clip —
RETIRED (D-020 #7) as satisfied-by-Xbot; a real human clip stays
welcome, never gating.
