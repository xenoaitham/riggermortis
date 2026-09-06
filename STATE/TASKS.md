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
  - done: metarig + generated Rigify (Blender 4.0.2) + Seed-san VRM all ≤2 corrections (0 each); Mixamo export NEEDS-HUMAN (Adobe login) — gap recorded honestly in docs/BENCHMARKS.md; mapper fixes → DECISIONS D-007.
- [x] P0-16 [S2] CI skeleton: ruff + pytest + blender gate + **network-audit test** (zero outbound in default use).
- [x] P0-17 [S2] Review data model: `propose_reassignment()` + ambiguity ranking for the 30-second review UI.

## Phase 1 — One-image posing (the BOOM)
**Gate:** 20-image benchmark (10 photo / 10 anime), ≥90% usable-straight-away; BOOM GIF via pipeline; polish pass.

- [x] P1-1 [S2] Checksum-pinned model manager: manifest → one-time local download on explicit action, offline verify. media: n/a.
- [ ] P1-2 DWPose/RTMPose ONNX wrapper (133 keypoints, CPU+GPU via onnxruntime, optional extra). accept: <2s CPU per image.
- [ ] P1-3 Multi-figure detection + figure selection data model.
- [ ] P1-4 Keypoints → canonical 3D pose solve (2D→3D lift, symmetry, smoothing, elbow/knee flip disambiguation). accept: flip test on 20 poses.
- [ ] P1-5 FK apply engine: canonical pose → any mapped rig, rest-offset aware, undo-friendly. accept: same pose on 3 rigs passes eyeball + angle tolerance.
- [ ] P1-6 Add-on pose UX: image picker, figure thumbnails, mirror toggle, confidence readout. media: UI screenshot.
- [ ] P1-7 Viewport review overlay: ghost skeleton over image, per-joint confidence heat.
- [ ] P1-8 Anime-art robustness: fallback estimator plan if DWPose <90% on anime set. accept: benchmark decides.
- [ ] P1-9 20-image benchmark harness + usable-rate metric → docs/BENCHMARKS.md.
- [ ] P1-10 BOOM GIF pipeline (`xtask/render_demos.py --demo boom`): before/after, headless. media: **the BOOM GIF**.
- [ ] P1-11 Polish pass: wrong-elbow/flipped-knee bugs, snap UX, error messages. media: updated GIF.

## Phase 2 — Video → animation
**Gate:** dance + fight clips playable on 3 rigs; honest side-by-side GIFs; foot-slide metric published.

- [ ] P2-1 Video reader + per-frame pose detection (progress, resume).
- [ ] P2-2 Temporal smoothing: 1€ filter-class + keyframe reduction.
- [ ] P2-3 Keyframed retarget: canonical action → rig action (FK), root motion option.
- [ ] P2-4 Foot contact detection (velocity + height heuristic).
- [ ] P2-5 Cleanup v1: IK foot lock during contact, ground-plane fit. accept: foot-slide metric improves ≥5×.
- [ ] P2-6 Motion denoise: hip stabilization, jitter pass.
- [ ] P2-7 Export: Blender actions, FBX, GLTF, VRMA (via Blender where needed).
- [ ] P2-8 Two clips × 3 rigs + side-by-side GIFs + metric in docs. media: side-by-side GIFs.

## Phase 3 — MCP server (the agent angle)
**Gate:** real MCP client, zero human Blender interaction: inspect → pose → animate → render turntable; demo GIF is a launch asset.

- [ ] P3-1 Server skeleton: stdio + 127.0.0.1-socket transports, server_info, protocol version.
- [ ] P3-2 Tool schemas v1 per mcp/DESIGN.md; golden-schema tests.
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
