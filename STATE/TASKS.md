# TASKS

Claim by ticking and putting your session number in brackets. Each task has
acceptance criteria and a media note (the repo films itself — every
user-visible milestone produces headless media).

## Phase 0 — Core skeleton + rig profiler
**Gate:** maps 5 varied rigs (Rigify, Mixamo GLTF, VRM, weird names, ambiguous
quadruped) with ≤2 manual corrections each, proven headless.

- [x] P0-01 [S1] Repo scaffold + STATE files + conventions + license.
- [x] P0-02 [S1] Canonical skeleton module: roles, parents, side, direction, length ratios, height bands, `rest_skeleton()`.
  - accept: acyclic, symmetric pairs, continuity test green.
  - media: review-UI ghost skeleton (later).
- [x] P0-03 [S1] Rig data model (`RigData`/`BoneData`) + JSON exchange + fingerprint.
- [x] P0-04 [S1] Name lexicon: tokenization, side detection, Mixamo trap overrides, skip tokens.
- [x] P0-05 [S1] Geometry features: directions, chain topology, proportion priors, branch/leaf analysis.
- [x] P0-06 [S1] Mapper v1: name pass (role-major greedy, side penalties) + confidence blending.
- [x] P0-07 [S1] Chain-order promotion for spine families (spine.001 / Spine1/2) + honest leftovers.
- [x] P0-08 [S1] Geometry-only fallback: root/hips disambiguation, spine-chain ordering, leg/arm/shoulder chains.
- [x] P0-09 [S1] Per-rig presets: fingerprint-keyed save/load/apply, mismatch refusal + force.
- [x] P0-10 [S1] Policy module in core (`PolicyEngine`, `Refusal`, stable codes) + docs/POLICY.md.
- [x] P0-11 [S1] CLI `rigpose`: inspect / map (—json —strict —save-preset) / preset save+load / policy status.
- [x] P0-12 [S1] Headless Blender bridge (`blender_extract.py` + `xtask/extract_blend.sh`); core stays process-free.
- [x] P0-13 [S1] Add-on skeleton registers in Blender 4.x: N-panel, inspect&map operator writing `rm_role_*` props, policy prefs, honest Phase-1 stub.
  - accept: `xtask/blender_verify.sh` end-to-end PASS.
  - media: n/a yet.
- [x] P0-14 [S1] pytest suite (49 tests): 5 synthetic rigs, determinism, presets, policy, CLI, I/O.
- [x] P0-15 [S2] Real-rig gate: Rigify meta-rig (headless generation), a real Mixamo export, a real VRM; map each ≤2 corrections; record in docs/BENCHMARKS.md.
  - done: metarig + generated Rigify (Blender 4.0.2) + Seed-san VRM all ≤2 corrections (0 each); Mixamo real export DONE S5b: Xbot.glb (real mixamorig export via three.js, no Adobe login needed) — 21/22, core complete, 0 corrections, 2 review flags; mapper fixes → DECISIONS D-007.
- [x] P0-16 [S2] CI skeleton: ruff + pytest + blender gate + **network-audit test** (zero outbound in default use).
- [x] P0-17 [S2] Review data model: `propose_reassignment()` + ambiguity ranking for the 30-second review UI.

## Phase 1 — One-image posing (the BOOM)
**Gate:** 20-image benchmark (10 photo / 10 anime), ≥90% usable-straight-away; BOOM GIF via pipeline; polish pass.

- [x] P1-1 [S2] Checksum-pinned model manager: manifest → one-time local download on explicit action, offline verify. media: n/a.
- [x] P1-2 [S3] DWPose/RTMPose ONNX wrapper (133 keypoints, CPU+GPU via onnxruntime, optional extra). accept: <2s CPU per image. — DONE: 0.85 s mean (4-figure 3060x1721), official-demo-faithful numpy re-implementation (no cv2), `rigpose detect [--json --figure N --gpu]`, 17 tests (faked sessions, no downloads).
- [x] P1-3 [S3] Multi-figure detection + figure selection data model. — DONE: `inference/figures.py` FigureBoard (stable labels, select/primary/largest), 3 tests.
- [x] P1-4 [S3] Keypoints → canonical 3D pose solve (2D→3D lift, symmetry, smoothing, elbow/knee flip disambiguation). accept: flip test on 20 poses. — DONE: pure-stdlib solver (`canonical_pose.py`, D-008), 18/20 flips correct; 2 misses are documented single-view limitations (kick, arms-back).
- [x] P1-5 [S3] FK apply engine: canonical pose → any mapped rig, rest-offset aware, undo-friendly. accept: same pose on 3 rigs passes eyeball + angle tolerance. — DONE: pure-stdlib quaternions (`fk_apply.py`), 3 real rigs at worst error 0.0000° (0.5° asserted); payload ordered (depth, name); end-to-end smoke detect→solve→FK on metarig green.
- [x] P1-6 [S4] Add-on pose UX — DONE (payload flow per D-009): Apply Pose / Clear Pose operators, panel v2 (payload picker + actionable hint, figure label + per-role confidence readout with color bands, mirror toggle), payload apply verified headlessly ≤0.5° per bone on real metarig + Seed-san (0.026°/0.020° worst). Caveats, honest: figure thumbnails deferred (a payload carries ONE figure — selection happens at `rigpose pose --figure` time); UI screenshot impossible headless (no display; documented) — media deliverable is the pipeline-rendered BOOM GIF instead.
- [x] P1-7 [S4] Viewport review overlay — DONE within the honest session scope: core data model (`review.review_items` + `skeleton_segments`, unit-tested; D-008 miss classes surface as low flip margins), add-on draw handler (gpu, confidence color bands <0.55 red / <0.75 amber / else green) registered and line data verified headlessly (16 segments, 3 bands); GPUOffScreen draw reports SKIPPED in background Blender (no GPU API — documented, not faked). Joint picking + in-viewport flip toggles + image-plane projection = P1-11.
- [x] P1-9 [S4] 20-image benchmark harness — DONE (harness + metric + docs block): `xtask/benchmark_poses.py` walks out/benchmark/images/{photo,anime}, publishes `usable-straight-away` (reliable AND flip margins ≥0.55 AND no deep-foreshortening flag) with per-image flags + confidence distribution into docs/BENCHMARKS.md between markers. Ran on what exists locally (1 photo, 1 anime — DWPose repo assets): both solve reliable (0.85/0.81 conf) but flag unmeasured flips (wrists below detection) → 0/1 usable, honestly published. 10-image sets = NEEDS-HUMAN (licensing-clean sourcing); P1-8 decision stays pending per plan.
- [x] P1-10 [S4] BOOM GIF — DONE: `xtask/render_boom.sh` = render_demos.py --demo boom (workbench turntable of the rest rig → real payload applied through the add-on's own apply path, self-check gate ≤0.5° → posed turntable; bone-proxy mesh visualizer because armature bones don't render) + assemble_gif.py (side-by-side before|after). media/boom.gif regenerated by pipeline, never committed.
- [x] P1-8 [S5] Anime-art robustness: fallback estimator plan if DWPose <90% on anime set. accept: benchmark decides. — DONE: D-011 (benchmark says <90% on both sets for decomposed reasons; fallback PLAN written, not implemented; detector no-person 2/7 anime is the anime-specific gap; n=7 of 10, re-decide at 10 — sourcing NEEDS-HUMAN). Benchmark instrument fixed first (D-010): arm kp mapping bug (wrists never observed → structural-zero margins on ALL real images), immaterial-flip auto-pass, mean flip aggregation; 18/20 fixture accept unchanged; pose-apply gate re-PASS.
- [ ] P1-8a (from D-011) Fallback estimator evaluation: sketch/anime whole-body estimator candidates, dual-estimator inference interface, per-image confidence-probe selection, `estimator` field in payload v2. Do NOT start before payload v2 (P1-11 B1) lands.
- [x] P1-9 — done 2026-09-15 S4 (see checked entry above; this stub was a stale duplicate).
- [x] P1-10 — done 2026-09-15 S4 (see checked entry above; this stub was a stale duplicate).
- [ ] P1-11 [S5] Polish pass: B1/B2/B3/B4 all done (see entries below) — task CLOSED on S5's session scope; watch P1-8a for the estimator follow-up.
- [x] P1-11 B2 [S5] Overlay interactivity: core `CanonicalPose.toggled()` (D-008 rescue, mirror-commuting, human-verified conf 1.0), `review.joint_points()` + `pick_joint()` (pure ray-cast); addon flip-toggle/pick/reset operators, joint dots, flagged-flip panel buttons; `PRIMARY_CHILD` moved to canonical.py (cycle fix). Verified: RM_REVIEW PICK/TOGGLE/TOGGLE_APPLY PASS (toggle re-apply 0.0000 deg) in pose-verify; 161 tests.
- [x] P1-11 B3 [S5] BOOM GIF framing: camera target now re-centers on the deformed bone-proxy bound-box center after payload apply (depsgraph-evaluated, exact rendered geometry); skiing pose shifted the centroid 0.345 m and the shot stays framed; boom.gif regenerated and visually checked.
- [x] P1-11 B4 [S5] UI screenshot: xvfb/display EXISTS on this box (S4 blocker gone). GENUINE windowed capture captured once and visually verified (posed metarig + review overlay in Blender 4.0.2, media/ui_screenshot.png, git-ignored). Honest caveats: windowed Blender GL on this box is flaky (~1-in-4 runs complete; crashes are GL teardown/startup, not pipeline logic — payload self-check still gates the shot); N-panel TAB not scriptable so the panel tab itself isn't in the shot (draw() is the source of record); automated re-capture is best-effort (xtask/ui_screenshot.sh).
- [x] P1-11 B1 [S5] Multi-figure payloads: core `payload.py` contract module (v2 write, v1 back-compat read, figure resolution — one implementation for addon/CLI/MCP); `rigpose pose --all-figures` embeds every figure's solve+FK; panel figure dropdown switches in-process (EnumProperty from payload, apply by label, per-figure conf readout); 9 contract tests + committed-v1-fixture back-compat test (158 total). Gate: verify_pose_apply.sh extended — 12-figure real payload, in-process switch applied at 0.0247° worst (bar 0.5°), gate PASS.

## Phase 2 — Video → animation
**Gate:** dance + fight clips playable on 3 rigs; honest side-by-side GIFs; foot-slide metric published.

- [x] P2-1 [S5] Video reader + per-frame pose detection — DONE: core `video.py` job container (deterministic stride planning, per-frame detect->solve->FK payloads, crash-safe `job.json` state after EVERY frame, resume skips done frames, plan-mismatch restarts, failures recorded honestly with re-attempt on resume); `rigpose pose-video` CLI (progress prints); decode lives in `xtask/extract_frames.sh` (ffmpeg, confined paths, D-009). LIVE-VERIFIED with real models: person video -> 5/5 reliable payloads (conf 0.70, 16 rotations); person-less frames -> honest failures; resume re-attempts failures. 7 CI tests with faked detection.
- [x] P2-2 [S5] Temporal smoothing — DONE: core `smoothing.py` — `OneEuroFilter` (Casiez 2012, adaptive cutoff via beta, timestamp-aware freq), `smooth_channel`/`smooth_pose_frames` (per-role, partial observation preserved), `reduce_keyframes` (greedy error-driven decimation sketch; endpoints kept, deterministic; P2-3 wires it into actions). 6 CI tests on synthetic jitter: variance cut >4x on stationary, fast-step tracking with beta, spike preservation, tolerance monotonicity.
- [x] P2-3 [S6] Keyframed retarget: canonical action → rig action (FK), root motion option. — DONE: core `action.py` (`load_action` through the payload contract — P2-1's writer was v2-shaped WITHOUT the `figures` list the contract requires; writer fixed, first consumer contract-clean), `condition_action` wires P2-2 smoothing + keyframe reduction (tolerance = canonical-unit joint-position error, documented); addon `bake.py` keys rotations into a NEW action per frame (mapping once, proven B=M⁻¹LM math). Root motion honestly NOT implemented (hip-anchored solve → world translation would be fabricated; documented in bake.py + BENCHMARKS.md). Gate: verify_pose_apply.sh 2-frame bake probe — pose A f1 + mirror f2, BOTH re-evaluated from fcurves: 0.0242°/0.0242° worst (16 roles each, bar 0.5°); 9 CI tests (faked payloads, stdlib).
- [x] P2-4 [S6] Foot contact detection (velocity + height heuristic). — DONE: core `contacts.py` — per-ankle speed + height-over-ground (nearest-rank percentile, self-normalizing) with Schmitt hysteresis (enter 0.02u/f & 0.08u, exit 0.06u/f or 0.20u; documented order-of-magnitude defaults, NOT fixture-fitted); gaps split intervals honestly; `attach_contacts` puts the report on the action for P2-5's IK lock. 12 CI tests: exact-interval GT match on a clean synthetic walk, P/R ≥ 0.9 with wobble, determinism, scale-field invariance, airborne → 0, hysteresis validation. PLUS P2-5's baseline instrument started: `foot_slide` metric (ankle path length in contact; 4 tests) — the ≥5× gate has a number to beat.
- [ ] P2-5 Cleanup v1: IK foot lock during contact, ground-plane fit. accept: foot-slide metric improves ≥5×.
- [ ] P2-6 Motion denoise: hip stabilization, jitter pass.
- [ ] P2-7 Export: Blender actions, FBX, GLTF, VRMA (via Blender where needed).
- [ ] P2-8 Two clips × 3 rigs + side-by-side GIFs + metric in docs. media: side-by-side GIFs.

## Phase 3 — MCP server (the agent angle)
**Gate:** real MCP client, zero human Blender interaction: inspect → pose → animate → render turntable; demo GIF is a launch asset.

- [x] P3-1 [S5] Server skeleton — PARTIAL (honest): stdio JSON-RPC 2.0 (newline-delimited), initialize/server_info (protocol 2024-11-05, local_only, contract version), ping, parse-error handling. Loopback-socket transport deferred to P3-5 (session bridge) — stdio covers agent clients per mcp/DESIGN.md.
- [x] P3-2 [S5] Tool schemas v1 — DONE: 5 tools declared (inspect_rig/policy_status/map_rig LIVE; pose_from_image/animate_from_video declared with structured not_implemented answers); golden-schema test pins names/status/required fields; stdio framing test (requests, notifications, parse errors). 8 tests. Live: inspect_rig (core map), policy_status (defaults + hard lines).
- [ ] P3-3 Structured policy refusals through MCP (tested like any tool).
- [ ] P3-4 Progress streaming for long tools.
- [ ] P3-5 Blender session manager: add-on ↔ server local socket, action queue.
- [ ] P3-6 Example agent configs (Claude Desktop, Cursor) + docs walkthrough (5-minute connect).
- [ ] P3-7 E2E agent demo run. media: **agent-driven turntable GIF** (launch asset).
- [ ] P3-8 MCP registry listing prep.

## Phase 4 — Style system + manga maker
**Gate:** 6-page wordless manga in docs/manga/, readable + charming; same scene in 3 styles side-by-side.

- [ ] P4-1 Toon shader presets (anime / manga / western cartoon) on EEVEE: banded shading, rim.
- [ ] P4-2 Grease Pencil line art pass.
- [ ] P4-3 Screentone/halftone compositor node groups; style packs as data files.
- [ ] P4-4 Multi-camera panel system + layout presets (manga RTL, western LTR).
- [ ] P4-5 Speech-bubble editor (Grease Pencil + text).
- [ ] P4-6 PDF/EPUB/PNG export pipeline.
- [ ] P4-7 Animatic mode from pose sequences.
- [ ] P4-8 The 6-page manga + 3-style hero shot. media: manga PDF + hero stills.

## Phase 5 — Live mode
**Gate:** 5 minutes of recorded live puppeteering; <100 ms mid-laptop.

- [ ] P5-1 Realtime ONNX pose (MediaPipe-class) in a side process.
- [ ] P5-2 Webcam → rig puppeteer with latency budget; Blender driver hookup.
- [ ] P5-3 Smoothing/latency UI + failsafe (drop to 30fps pose preview).
- [ ] P5-4 Recorded demo. media: 5-min live demo video.

## Phase 6 — Pro cleanup + optional modules
**Gate:** benchmark table published; 18+ module proven OFF by default via tests in both frontends; policy refusals fire add-on + MCP.

- [ ] P6-1 Secondary motion: hair/cloth follow-through (spring chains).
- [ ] P6-2 Motion library retarget: Mixamo/BVH/FBX → any mapped rig.
- [ ] P6-3 Public benchmark suite packaging.
- [ ] P6-4 18+ module per docs/POLICY.md (core-enforced, sober docs, no explicit content in repo).
- [ ] P6-5 Enforcement tests: fresh-install default OFF; refusal codes through add-on and MCP.
- [ ] P6-6 Optional style-LoRA trainer docs (honest GPU cost; never a dependency). No training in CI.

## Phase 7 — Launch kit
**Gate:** artist poses a rig <60s from README alone; developer connects MCP <5min from docs; CI regenerates all media.

- [ ] P7-1 README hero (BOOM GIF) + honest limitations; every claim backed.
- [ ] P7-2 Tutorials: gamedev / VTuber / webcomic / indie-animator.
- [ ] P7-3 docs/LAUNCH.md: Show-HN, BlenderNation, r/blender drafts, tweet thread, 60s video script.
- [ ] P7-4 Blender Extensions listing (manifest ready).
- [ ] P7-5 PyPI publish (needs human account) + docs.
- [ ] P7-6 60-second video cut from pipeline footage; CI media-regeneration gate. media: launch video.
